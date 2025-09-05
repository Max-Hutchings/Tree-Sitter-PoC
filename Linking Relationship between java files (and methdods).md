# Linking Relationships Between Java Files and Methods

Tree-sitter gives you per-file syntax trees. To turn "a call name" into a pointer to "the method node that will actually run" (possibly in another file/module), you need a thin semantic layer on top of Tree-sitter.

## The Plan (Overview)

### 1. Parse Everything (Syntax)

Use Tree-sitter to extract declarations and call sites from all source files:

- **packages, imports**
- **classes/interfaces/enums** + extends/implements
- **fields** (types), **methods** (name, params, return, modifiers), **constructors**
- **method calls**, **constructor calls**, **method references** (`A::m`), `new A(...)`

### 2. Index the World (Symbols)

Build a fast, queryable symbol index:

- `ClassSymbol { fqn, kind, supertypes[], isFinal, methods[] }`
- `MethodSymbol { id, classFqn, name, paramTypes[], returnType, isStatic, isFinal, visibility }`
- Map `FQCN → ClassSymbol`, `(FQCN, name, arity) → candidates`
- Use stable IDs like `com.acme.UserService#addUser(java.lang.String):com.acme.User`

### 3. Resolve Types Inside Methods (Light Type Inference)

For each method body, derive a type environment:

- **Parameters**: known types
- **Locals**: from declarations (var desugared via initializer type)
- **Fields**: from class symbol
- **Simple expression typing** to propagate types through `a.b()`, `new`, casts, conditionals
- Use unions if ambiguous (e.g., `Optional<T>` unwrap heuristics)

### 4. Build Class Hierarchy (CHA) & Reachable Types (RTA)

- **CHA**: graph of extends/implements
- **RTA**: gather allocated types (`new T(...)`, deserialization hints, Spring bean types, etc.) reachable from your entry points to prune dynamic dispatch candidates

### 5. Resolve Each Call Site → Target Method(s)

For every `method_invocation` node:

#### Receiver Kind

- `TypeName.m(...)` → static or interface static call (receiver is a type)
- `expr.m(...)` or unqualified `m(...)` → instance/virtual call (receiver is a value)

#### Static Target Set (Overloads)

Pick candidates with name & arity, filter by applicability (argument types after erasure/boxing/varargs).

#### Virtual Dispatch Tightening

If receiver type is T, the call may target any override of selected method on subtypes of T → intersect with RTA reachable subtypes and drop impossible ones.

#### Special Cases

- **constructors** `<init>`
- `super.m()`
- **private/final** (de-virtualize)
- **method references** `A::m`
- **lambdas** to SAM methods

#### Emit Call Edges

Create edges from caller method ID → callee method ID(s). Annotate edges with site file/line/column and whether they're precise or an over-approximation.

### 6. Fill Gaps with Runtime Signals (Optional but Powerful)

Static analysis won't see reflection/proxies. Ship a tiny Java agent (ByteBuddy/ASM) in staging/test to log edges for:

- `java.lang.reflect.Method.invoke`
- Proxy / CGLIB / framework proxies
- Dependency injection calls (Spring beans), scheduled tasks, message listeners

Merge these observed edges back into your graph with a "runtime" tag.

## Concretely, What You Build

### 1) Per-file Tree-sitter Extraction (Fast)

From each AST:

#### File Facts
- package, imports, top-level types

#### Type Facts
- class/interface name, extends/implements, nested types

#### Member Facts
- fields (type name)
- methods (modifiers, name, param types, return type, throws)

#### Call Sites
- `method_invocation` → capture receiver text + arg expressions + byte range
- `object_creation_expression` (`new T(...)`) → constructor call to `<init:T>`
- `method_reference` (`A::m` / `obj::m`) → call candidate to m

Store byte ranges (file + start/end bytes) for every declaration and call site.

### 2) Global Symbol & Classpath Index

#### Project Sources
Populate your symbol tables from the facts above.

#### Dependencies
You still need method/return types for third-party classes:

**Fast path**: index JARs using ASM to read `.class` → signatures (no sources needed).

Or use `jdeps`/`javap` to dump, then parse.

Persist minimal stubs: classes, method names, param types, return types, modifiers.

This is the single biggest enabler for linking calls to methods across files & libs.

### 3) Intra-method Type Environment (Pragmatic)

You don't need full Java typing to get good results:

Maintain a map: identifier → set of possible FQCNs.

Seed it with params/locals/fields; import resolution turns simple names into FQCNs.

Track simple expressions:

- `x = new T(...)` → `x : {T}`
- `x = y.m(...)` → if you resolve `m` on `types(y)`, set `x` to union of the resolved return types.
- Casts `(U) x` → add `U` to `types(x)` in that path.
- Ternaries/ifs → union.
- Method chains `a.b().c()` → propagate stepwise.

Use erasure for generics when comparing param types; keep generic info only for return-type propagation if available.

### 4) Overload & Dispatch Resolution (Deterministic Steps)

Given a call site:

Determine receiver types:

- Unqualified call → treat as `this` in current (enclosing) class(es); include statically imported methods.
- `TypeName.m` → static call on `TypeName`.
- `expr.m` → use type env for `expr`.

Find applicable overloads: same name & arity; filter by assignability after erasure/boxing/varargs.

For instance calls, compute virtual targets: for each applicable method declared in type `T`, add overrides on reachable subtypes of `T` (`CHA ∩ RTA`).
De-virtualize if final/private/static.

This yields a set of `MethodSymbol` IDs. In most business code with RTA, that set collapses to 1–2 targets.

## Schema to Persist (Minimal & Scalable)

- `class(id, fqn, kind, is_final, super_fqn, interface_fqns[])`
- `method(id, class_id, name, param_erasure[], return_erasure, is_static, is_final, visibility)`
- `call_site(id, file, start_byte, end_byte, caller_method_id)`
- `call_edge(caller_method_id, callee_method_id, call_site_id, resolution_kind ENUM('static','virtual_cha','virtual_rta','runtime'), confidence FLOAT)`

Re-index only the files that changed (content hash). Re-resolve their call sites and then update edges.