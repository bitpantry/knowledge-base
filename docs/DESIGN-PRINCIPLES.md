# Knowledge Management Design Principles

Use these principles to evaluate changes to the core, its boundaries, and the
working-vault package. See [Architecture](README.md) for how the system works
today and what remains a design direction.

1. **Make the core useful on its own.** An empty vault can ingest, connect, and answer questions about knowledge without an extension. Keep the core domain-neutral.
2. **Design for a large vault.** Shared search and indexing belong in the core. Give a fresh agent one clear entry point and predictable paths to records and extensions. Routine work should not require scanning the vault or loading engineering notes. Any derived index should be rebuildable from canonical records.
3. **Keep the layers distinct.** The core owns knowledge, evidence, and shared retrieval. An extension packages a domain, modules group capabilities, and models define record types, relationships, and rules. Reuse core mechanisms rather than introducing parallel storage or search.
4. **Make extensions portable and installs consistent.** An extension is a self-documenting folder. A common install workflow wires it into the entry point, proposes matches to prior records in scope, and asks before applying them. One core record can carry distinct model interpretations without being copied or retyped.
5. **Ingest with context, not blinders.** Read for what matters in the source. Index useful new concepts generously even if they are unfamiliar. Link them to existing knowledge where supported, and leave ambiguous relationships unresolved.
6. **Keep answers traceable.** Store record content once and use metadata for identifiers, references, and locators. Leave originals in authorized source systems. Store resolvable pointers and precise citations; distinguish mentions, claims, and confirmed answers. Preserve conflicting evidence and the history of confirmations.
7. **Do not change the architecture during ordinary use.** Explain gaps and get explicit approval before introducing a new convention, storage location, locator rule, or dependency. A local lookup convention that another agent must discover is an architectural dependency, even if Git ignores it.
8. **Separate engineering from use.** Keep tests, demos, and design notes in the engineering repo. Ship a clean working vault. Review core updates separately and preserve live records, settings, and installed extensions.
