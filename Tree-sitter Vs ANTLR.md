# Tree-sitter vs ANTLR: High-level Recommendation (for 70k repos)

Use **Tree-sitter** as the fast, resilient, multi-language CST layer (Java, XML pom.xml, JS/TS, etc.) to index files, declarations, and call sites. For languages where you need precise target resolution (e.g., Java’s virtual dispatch/overloads), pipe those files through a semantic front-end (e.g., JDT/JavaParser, or a custom ANTLR pass + your own type resolver) to tighten edges. Tree-sitter’s incremental parser + query language makes your first pass cheap and scalable; ANTLR (or JDT) shines when you need richer semantics.

---

## What They Produce (and How)

**Tree-sitter** builds a Concrete Syntax Tree (CST) and updates it incrementally on edits. It exposes a query DSL (S-expressions) to find nodes like `method_declaration` or `method_invocation`, with byte/line spans for each node. It’s robust to errors and designed for editors and large-scale indexing.

**ANTLR** generates a lexer + parser from a grammar and produces a parse tree (a CST). You usually build your own AST by walking the parse tree with listeners/visitors and mapping to your semantic nodes. This is great when you need full control over the AST shape and downstream analysis.

> **TL;DR:** Both give you a CST/parse tree. Tree-sitter adds incremental parsing + queries; ANTLR gives you generator-driven listeners/visitors to craft a custom AST layer.

---

## Pros & Cons (at a Glance)

| Dimension                | Tree-sitter                                                                 | ANTLR                                                                                   |
|-------------------------|-----------------------------------------------------------------------------|----------------------------------------------------------------------------------------|
| Primary output          | CST (incremental) with query language                                       | Parse tree (CST). You typically build your own AST via visitors/listeners              |
| Incremental parsing     | Built-in & fast; ideal for massive codebases and IDE use                    | Not incremental by default; you re-parse (can build a smaller AST manually for perf)   |
| Error recovery          | Strong; produces trees even for incomplete/invalid code                     | Good but generally not as editor-centric                                               |
| Finding nodes           | Powerful queries (S-expressions) over the tree                              | You implement listeners/visitors and your own match logic                              |
| Language coverage       | Many community grammars; official ones for Java, plus XML for pom.xml       | Huge grammar zoo (grammars-v4) for many languages                                      |
| Ecosystem goal          | Editor/indexing/search; multi-language CST with positions                   | Language tooling, DSLs, compilers; fine-grained AST control                            |
| Type/semantic analysis  | Not built-in; you integrate separate analyzers (e.g., JDT for Java)         | You build it (or integrate with language front-ends) via visitors                      |
| Performance @ scale     | Very good for first-pass indexing and repeated updates                      | Great for batch analysis; more code to get incremental-like wins                       |
| XML/pom support         | `@tree-sitter-grammars/tree-sitter-xml`                                     | ANTLR XML grammars available, too                                                      |
| Tooling ergonomics      | Simple runtime API; unified query syntax across languages                   | Mature tooling; listeners/visitors well-documented and flexible                        |

---

## How This Maps to Your Goals

### Tree of the Whole Repo (incl. pom.xml)
- Use Tree-sitter to parse all files (Java, XML, JS, etc.).
- Persist nodes (file → declarations → call sites) with byte/line positions.
- For pom.xml, parse via Tree-sitter XML and capture project/groupId/artifactId/version/dependency nodes.

### Search for Any Class/Method Within the Repo
- Tree-sitter queries give you fast structural search.
- Index captures (`class_declaration`, `method_declaration`) into Postgres/SQLite/Elastic or a graph store.

### See Exactly What Methods Are Called Within a Function
- **First pass:** Tree-sitter query for `method_invocation` inside each `method_declaration` (fast, language-agnostic).
- **Precision pass (Java):** Feed those files to a semantic analyzer (e.g., Eclipse JDT ASTParser) to resolve targets (CHA/RTA, overloads, imports, generics). If you prefer full control, do an ANTLR-based pass plus your resolver.

---

## When to Choose Which

- **Tree-sitter first pass (recommended):** Massive, multi-language indexing; resilient CST for search/navigation; quick call-site harvesting. Great for pom.xml too via its XML grammar.
- **ANTLR (or JDT) precision pass:** When you need call targets (not just call sites). For Java, JDT’s ASTParser gives bindings and a full semantic model; otherwise roll your own with ANTLR visitors + CHA/RTA and a points-to heuristic.

---

## Scaling Tips for 70k Repos (Quick Hits)

- Sharded workers per language; reuse parsers/queries; batch results.
- Content-addressed cache keyed by (path, size, hash) so unchanged files are skipped.
- Store minimal facts: documents, symbols (classes, methods), calls (caller span → callee name, + optional inferred FQN).
- Tighten edges lazily: resolve callee FQNs only for hot paths (e.g., methods frequently referenced) to control cost.
- Incremental CI: Tree-sitter re-parse only changed files; keep previous CSTs to diff query captures quickly.

---

## Sources (Key)

- Tree-sitter overview & incremental parsing; using parsers & queries.
- Tree-sitter Java & XML grammars (JS/npm).
- ANTLR overview; grammars-v4; listeners vs visitors.
- JDT ASTParser for semantic Java analysis.
