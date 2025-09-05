import os
from typing import Optional

from tree_sitter import Parser, Tree, Node

from call_graph.src.call_graph.models.ast_models import ClassInfo, MethodCall, MethodInfo
from call_graph.src.call_graph.tree_sitter_helpers import node_text, node_point


# --- Tree-sitter language loading -------------------------------------------

def load_java_language():
    """
    Loads the Tree-sitter Java language for the Python bindings.
    We try the easy path (tree_sitter_languages) first. If that isn't available,
    we try loading a user-built shared library via TS_LANGUAGE_SO.
    """
    # Easy mode: prepackaged grammars (no build step)
    try:
        # tree_sitter_languages bundles many grammars, including Java
        from tree_sitter_languages import get_language
        return get_language("java")
    except Exception:
        pass

    # Manual mode: user must have built a .so that includes tree-sitter-java
    # Example build (run once from your project root):
    #   git clone https://github.com/tree-sitter/tree-sitter-java
    #   python - <<'PY'
    #   from tree_sitter import Language
    #   Language.build_library(
    #       'build/my-languages.so',
    #       ['tree-sitter-java']
    #   )
    #   PY
    #   export TS_LANGUAGE_SO=build/my-languages.so
    from tree_sitter import Language
    so_path = os.environ.get("TS_LANGUAGE_SO")
    if not so_path or not os.path.exists(so_path):
        raise RuntimeError(
            "Could not load Java grammar.\n"
            "- Install `tree_sitter_languages` (pip install tree_sitter_languages), OR\n"
            "- Build a shared library and set TS_LANGUAGE_SO to its path.\n"
            "See code comments for build instructions."
        )
    return Language(so_path, "java")


# --- The Indexer -------------------------------------------------------------

class JavaIndexer:
    """
    Walks a Tree-sitter Java AST to build a minimal semantic index:
    packages -> classes -> methods -> calls.
    """

    def __init__(self):
        self.language = load_java_language()
        self.parser = Parser()
        self.parser.set_language(self.language)

        # In-memory index
        self.packages: set[str] = set()
        self.classes: dict[str, ClassInfo] = {}  # fqcn -> ClassInfo

    def parse(self, source: str):
        """
        Parses a single source string into a Tree-sitter tree.
        """
        tree = self.parser.parse(source.encode("utf-8"))
        return tree

    def index_source(self, source: str, file_path: Optional[str] = None):
        """
        Parses & indexes a Java source file.
        """
        source_bytes = source.encode("utf-8")
        tree: Tree = self.parse(source)
        root: Node = tree.root_node

        current_package = self._find_package(source_bytes, root)
        if current_package:
            self.packages.add(current_package)

        # DFS over the AST. We maintain a stack of nested class names to support inner classes.
        class_stack: list[tuple[str, int, int]] = []  # (simple_name, line, col)
        self._walk_and_index(source_bytes, root, current_package, class_stack)

    # -- AST helpers ----------------------------------------------------------

    def _find_package(self, source_bytes: bytes, root: Node) -> Optional[str]:
        """
        Grabs the package name from a 'package_declaration' node if present.
        """
        for child in root.children:
            if child.type == "package_declaration":
                name_node = child.child_by_field_name("name")
                if name_node:
                    return node_text(source_bytes, name_node)
        return None

    def _walk_and_index(self, source_bytes: bytes, node, pkg: Optional[str],
                        class_stack: list[tuple[str, int, int]]):
        """
        Generic DFS that watches for class_declaration and method_declaration,
        and when inside a method, collects method_invocation nodes.
        """
        # Detect class declarations as we descend
        if node.type == "class_declaration":
            class_name_node = node.child_by_field_name("name")
            if class_name_node is not None:
                simple = node_text(source_bytes, class_name_node)
                line, col = node_point(node)
                class_stack.append((simple, line, col))

                # Compute FQCN: package + outer.inner.Simple
                fqcn = self._fqcn(pkg, [c[0] for c in class_stack])

                # Register class if not present
                if fqcn not in self.classes:
                    self.classes[fqcn] = ClassInfo(
                        simple_name=simple,
                        fqcn=fqcn,
                        line=line,
                        col=col,
                        methods={}
                    )

                # Recurse into the class body
                for child in node.children:
                    self._walk_and_index(source_bytes, child, pkg, class_stack)

                # Pop when done
                class_stack.pop()
                return  # Important: we handled recursion ourselves for the class subtree

        # Detect method declarations and index them
        if node.type in ("method_declaration", "constructor_declaration"):
            self._index_method(source_bytes, node, pkg, class_stack)
            # Still walk inside so we catch nested declarations (rare) and be thorough.
            # (Calls for this method are collected by _index_method.)

        # Recurse into children for everything else
        for child in node.children:
            self._walk_and_index(source_bytes, child, pkg, class_stack)

    def _fqcn(self, pkg: Optional[str], class_names: list[str]) -> str:
        """Builds a fully-qualified class name from package + nested classes."""
        left = pkg + "." if pkg else ""
        return left + ".".join(class_names)

    def _index_method(self, source_bytes: bytes, node, pkg: Optional[str],
                      class_stack: list[tuple[str, int, int]]):
        """
        Pulls out a method's name, parameters, (light) return type, and then
        finds all method_invocation nodes within its body.
        """
        # Resolve owning class FQCN (we assume we're inside at least one class)
        if not class_stack:
            # Edge case: method outside class (shouldn't happen in Java) — ignore.
            return
        fqcn = self._fqcn(pkg, [c[0] for c in class_stack])

        # Method name
        name_node = node.child_by_field_name("name")
        method_name = node_text(source_bytes, name_node) if name_node else "<anonymous>"

        # Return type (simple text capture; could be None for constructors)
        return_type = None
        if node.type == "method_declaration":
            ret_node = node.child_by_field_name("type")
            return_type = node_text(source_bytes, ret_node) if ret_node else None

        # Parameters (simple textual grab; not fully normalized)
        params_node = node.child_by_field_name("parameters")
        params = []
        if params_node:
            # parameters -> "(" [parameter ("," parameter)*] ")"
            for p in params_node.children:
                if p.type == "parameter":
                    # param has 'type' and 'name' fields
                    p_type = p.child_by_field_name("type")
                    p_name = p.child_by_field_name("name")
                    p_type_s = node_text(source_bytes, p_type) if p_type else "?"
                    p_name_s = node_text(source_bytes, p_name) if p_name else "param"
                    params.append(f"{p_type_s} {p_name_s}")

        line, col = node_point(node)
        method_info = MethodInfo(
            name=method_name,
            params=params,
            return_type=return_type,
            line=line,
            col=col,
        )

        # Walk the method's subtree to find calls
        self._collect_calls_in_method(source_bytes, node, method_info)

        # Store under class -> method name (supporting overloads)
        cls = self.classes[fqcn]
        cls.methods.setdefault(method_name, []).append(method_info)

    def _collect_calls_in_method(self, source_bytes: bytes, method_node, method_info: MethodInfo):
        """
        Finds `method_invocation` and captures:
          - the simple method name being called,
          - the receiver/object text (if present), and
          - source location of the call.

        Note: This is SSG (syntax-only). We do not resolve which class actually defines
        the target method (that requires type resolution + classpath).
        """
        stack = [method_node]
        while stack:
            node = stack.pop()
            # Record method calls
            if node.type == "method_invocation":
                name_node = node.child_by_field_name("name")
                obj_node = node.child_by_field_name("object")  # present for calls like obj.save()
                call_name = node_text(source_bytes, name_node) if name_node else "<unknown>"
                receiver = node_text(source_bytes, obj_node) if obj_node else None
                line, col = node_point(node)
                method_info.calls.append(MethodCall(call_name, receiver, line, col))

            # (Optional) record `object_creation_expression` as constructor calls
            if node.type == "object_creation_expression":
                # E.g., `new Foo(bar)` → treat as call to constructor "Foo"
                type_node = node.child_by_field_name("type")
                ctor_name = node_text(source_bytes, type_node) if type_node else "<anon>"
                line, col = node_point(node)
                method_info.calls.append(MethodCall(f"<init:{ctor_name}>", None, line, col))

            # Continue DFS
            stack.extend(node.children)