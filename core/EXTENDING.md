# Extending the core

**Core → Extension → Module → Model** describes responsibilities, not an installed plugin framework.

| Layer | Owns | Example, not installed |
| --- | --- | --- |
| Core | Stable source IDs, metadata and pointers, recovery, base checks | Catalog |
| Extension | A bounded business capability and its access rules | Account Knowledge |
| Module | A coherent part of one extension | Relationships, Pursuits, Delivery |
| Model | The declared record shape and authoritative writer | Person, Lead, Deal Context, Engagement |

1. Place each proposed extension under `extensions/<extension>/` with an `EXTENSION.md` listing its owner, permitted data audience, modules, declared dependencies and versions, and each model's sole owner, stable ID format and source-of-truth policy. Proposed dependencies point toward the core or specifically declared public interfaces, never into another owner’s private files. A clean starter installs no extensions.
2. Use source IDs and relative links to approved catalog entries rather than embedding originals or private evidence. Keep business records in the owning model; consumers reference them. For example, a deal-context model can reference an external CRM deal without rewriting CRM-owned facts. Snapshot strategy and generated reports can reference live records without owning them.
3. Own and test only files under your extension boundary. A shared/core change has wider consequences: propose it separately and obtain review; never bundle it into an extension diff. In a Git checkout rooted here, run `python3 core/catalog.py check-scope my-extension --base HEAD` before review. For a committed branch, provide its intended comparison base. The guard tests tracked and nonignored untracked path scope; it cannot prove ownership, permissions, or semantic compatibility.
4. Validate with `python3 core/catalog.py check` and the extension's own tests. One owner per model across enabled extensions; resolve ownership/dependency collisions in design review before enabling anything.

The guard is a **review check**, not an OS sandbox. It rejects any path outside the selected extension, including core contracts/tooling, root entry docs, tests, examples, live catalog records, or another extension. Do not change the core, its tests, or this guard in extension mode. If a genuine shared change is necessary, pause and request a separately reviewed core change; test compatibility on an isolated copy, then resume the extension. No extension receives write access by declaring a dependency.

The [concept and evidence contract](CONCEPTS.md) and live knowledge data are core, not extension-owned. Use stable references to approved core data rather than copying it.
