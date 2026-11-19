# Knowledge Management Core

Version 1.1.0. A local, Markdown-first catalog of **sources and evidence**, not a dump of documents. Open this folder as a vault in Obsidian, browse it in a private Git checkout, or point an agent at this page. All three read the same files; no plugin or index service is required.

- [File and find a source](core/WORKFLOWS.md#file-and-find-a-source)
- [Index concepts, connect evidence, and answer from sources](core/CONCEPTS.md)
- [Correct catalog metadata](core/WORKFLOWS.md#correct-catalog-metadata)
- [Recover a moved or unavailable source](core/WORKFLOWS.md#recover-a-source)
- [Design a separate extension](core/EXTENDING.md)
- [Source catalog contract](core/SCHEMA.md)
- [Catalog](catalog/README.md)

The core owns source identity, metadata, references, and recovery rules. Account strategy, relationships, CRM deal notes, engagements, and reporting are examples of extensions, not source catalog fields. The original system or app remains authoritative for its records.

## Extensions

No extensions are wired by default.

## For a fresh agent

Use this vault the same way for research notes, a home project, community or volunteer work, or a business RFP. Consult the current catalog and [concept intake workflow](core/CONCEPTS.md#intake-is-context-aware-by-default) before filing or answering. Ordinary use writes approved source/evidence notes and explicit user decisions through the CLI; it does not edit schemas, docs, tests or code. Only do those when the user explicitly requests a core change. Nothing here requires an account or extension. For a task that fits an extension, follow the named link above; if none fits, a copied folder in the extensions directory can still be used by opening its EXTENSION.md.

**Keep ordinary lookup scoped.** The repository’s `docs/` folder is for architecture and maintenance. Do not read it during startup, or include it in ordinary knowledge search, ingestion, indexing, or answers, even when using a broad file search. Use the catalog, knowledge records, and any relevant extension-owned records for ordinary work. Open `docs/` only when the user asks for architecture or maintenance documentation, or explicitly asks to include it.

Run the local checks (Python 3.9+):
```sh
python3 -B core/catalog.py check
python3 -B core/concepts.py check
python3 -B core/reconcile_extension.py check
```
