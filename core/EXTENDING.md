# Extending the core

**Core → Extension → Module → Model** describes responsibilities, not an installed plugin framework.

| Layer | Owns | Example, not installed |
| --- | --- | --- |
| Core | Stable source IDs, metadata and pointers, recovery, base checks | Catalog |
| Extension | A bounded business capability and its access rules | Account Knowledge |
| Module | A coherent part of one extension | Relationships, Pursuits, Delivery |
| Model | The declared record shape and authoritative writer | Person, Lead, Deal Context, Engagement |

1. Place each proposed extension under `extensions/<extension>/` with an `EXTENSION.md` listing its owner, permitted data audience, modules, declared dependencies, and each model's sole owner, stable ID format and source-of-truth policy. Proposed dependencies point toward the core or specifically declared public interfaces, never into another owner’s private files.
2. Use source IDs and relative links to approved catalog entries rather than embedding originals or private evidence. Keep business records in the owning model; consumers reference them. For example, a deal-context model can reference an external CRM deal without rewriting CRM-owned facts. Snapshot strategy and generated reports can reference live records without owning them.
3. Own and test only files under your extension boundary. A shared/core change has wider consequences: propose it separately and obtain review; never bundle it into an extension diff. In a Git checkout rooted here, run `python3 core/catalog.py check-scope my-extension --base HEAD` before review. For a committed branch, provide its intended comparison base. The guard tests tracked and nonignored untracked path scope; it cannot prove ownership, permissions, or semantic compatibility.
4. Validate with `python3 core/catalog.py check` and the extension's own tests. One owner per model across enabled extensions; resolve ownership/dependency collisions in design review before enabling anything.

The guard is a **review check**, not an OS sandbox. It rejects any path outside the selected extension, including core contracts/tooling, root entry docs, tests, examples, live catalog records, or another extension. Do not change the core, its tests, or this guard in extension mode. If a genuine shared change is necessary, pause and request a separately reviewed core change; test compatibility on an isolated copy, then resume the extension. No extension receives write access by declaring a dependency.

The [concept and evidence contract](CONCEPTS.md) and live knowledge data are core, not extension-owned. Use stable references to approved core data rather than copying it.

## Copy or wire an extension

An extension is a folder. Copy it to the vault's extensions directory and read its own EXTENSION.md. Drop-in use needs nothing else. If a task fits an unwired extension, use it when authorized; optionally offer to wire it, but never change the entry page silently or make wiring a prerequisite for use.

When the user explicitly says “wire it up,” verify the copied folder and read its EXTENSION.md first. Then run from the vault root:

    python3 -B core/wire_extension.py <folder-name>
    python3 -B core/catalog.py check

This puts exactly one short, named relative link to the extension's own entry document in the Extensions section of START-HERE.md. It repairs stale or duplicate links for that folder, leaves unrelated entries intact, and does nothing when already correct. If a broken link is no longer recognizable as belonging to that extension, or its name belongs to another existing entry, stop and review rather than guessing. This is a narrowly scoped, explicitly authorized start-page edit, not permission to rewrite core or bypass the extension diff guard. Do not add a second registry, extension-specific installer, compatibility matrix, or duplicated workflow; fix any obsolete “no extensions” wording if it actually conflicts with the new state.

Design for quick orientation: wire only the extension name and link at the normal entry point. Keep purpose, prerequisites, safe defaults, write boundaries, and a first-use workflow on the extension's own page or linked module. Make behavior discoverable and bounded; a fresh agent should be able to use it from the vault page without a separate explanation.

## Install and optionally reconcile

For a published package, preview `python3 -B core/vault.py install <extension>`,
then apply only the approved preview with `--if-preview`. This copies the package,
records which files it manages, and uses the same start-page wiring rules above.
A manually copied extension remains usable without a package receipt; the
package manager does not silently adopt it.

The package command does **not** classify records. As a separate step, an agent
reads the extension's model definitions and evaluates prior knowledge in the
user's scope. Follow [reconciliation](RECONCILE.md) to preview possible matches,
ambiguity, and overlap, and record only separately approved matches.
An interpretation is a core-owned reference, not a new extension record; an
extension cannot overwrite or claim exclusive ownership of the source note.
