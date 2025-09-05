# How to link `pom.xml` → source files (practical plan)

## 1) Discover modules
- Walk the repo, find all `pom.xml`.
- Parse them (Tree-sitter XML) to capture:
   - `groupId`, `artifactId`, `version`, `packaging`
   - `<modules>`
   - Any `<build><sourceDirectory>` / `<testSourceDirectory>` overrides

## 2) Build a module graph
- For aggregator POMs (with `<modules>`), resolve each `<module>` to a directory:
   - `path.join(aggregatorDir, moduleEntry)` → that directory should contain its own `pom.xml`.
- Resolve `<parent>` relationships (optional) to understand inheritance.
   - You can ignore this for basic linking.

## 3) Map source roots
- If overrides exist, use them; otherwise default to Maven layout:
   - `src/main/java`, `src/test/java`, `src/main/resources`, etc.
- Create an index:
   - `moduleDir → { pomMetadata, sourceRoots[] }`.

## 4) Attach files to modules
- For each `*.java` (or any language), walk **up** directories from the file’s folder until you find the nearest `pom.xml`.
   - That directory is the module root → you now have the owning POM.
- Store:
   - `filePath → moduleFQN (groupId:artifactId:version), pomPath`.

## 5) (Optional) Strengthen accuracy
- Honor `<build><sourceDirectory>` if non-standard.
- Respect multi-module trees: `<modules>` + `<parent>`.
- For non-Maven projects, apply the same pattern with their manifests:
   - Gradle: `settings.gradle[.kts]`, `build.gradle[.kts]`
   - Node: `package.json`
