# Knowledge Management Core

Version 1.1.0. A local, Markdown-first catalog of **sources and evidence**, not a dump of documents. Open this folder as a vault in Obsidian, browse it in a private Git checkout, or point an agent at this page. All three read the same files; no plugin or index service is required.

- [File and find a source](core/WORKFLOWS.md#file-and-find-a-source)
- [Index concepts, connect evidence, and answer from sources](core/CONCEPTS.md)
- [Correct catalog metadata](core/WORKFLOWS.md#correct-catalog-metadata)
- [Recover a moved or unavailable source](core/WORKFLOWS.md#recover-a-source)
- [Design a separate extension](core/EXTENDING.md)
- [Source catalog contract](core/SCHEMA.md)
- [Catalog](catalog/README.md)
- [Try the synthetic examples](examples/README.md)

The core owns source identity, metadata, references, and recovery rules. Account strategy, relationships, CRM deal notes, engagements, and reporting are examples of future extensions, not source catalog fields or installed modules. The original system or app remains authoritative for its records.

## For a fresh agent

Use this vault the same way for research notes, a home project, community or volunteer work, or a business RFP. Consult the current catalog and [concept intake workflow](core/CONCEPTS.md#intake-is-context-aware-by-default) before filing or answering. Ordinary use writes approved source/evidence notes and explicit user decisions through the CLI; it does not edit schemas, docs, tests or code. Only do those when the user explicitly requests a core change. Nothing here requires an account or extension.

Run the local checks (Python 3.9+):
```sh
python3 -B core/catalog.py check
python3 -B core/concepts.py check
python3 -B -m unittest discover -s tests -v
```
