# Knowledge Management architecture

Start here if you're evaluating the design, maintaining the core, or deciding where a new capability belongs. This is a companion to the operational guides, not required reading each time someone opens the vault.

## Purpose

Keep knowledge usable after the conversation ends. In a home project, a service manual and a technician's note might disagree about a part. In a volunteer project, plans and interviews may describe different ways of working. The vault helps you find what was said, where it came from, which interpretation a person confirmed, and what later evidence could change it. It is not the home for original documents, a universal source of truth, or an automation platform.

**Design for a quick start.** The normal entry point is [START-HERE](../START-HERE.md). Use readable Markdown, ordinary links, and small local tools when they can enforce a real rule. Keep the authoritative records portable and inspectable, and make specialized workflows explain themselves at their own entry point.

## Ownership and layout

| Layer | Owns | Where to look |
| --- | --- | --- |
| **Core** | Domain-neutral source identity and pointers; concepts, mentions, claims, and decisions; shared validation and retrieval | [Core contracts](../core/SCHEMA.md), [concepts contract](../core/CONCEPTS.md) |
| **Extension** | A bounded domain capability and its audience and dependency rules | [Extension contract](../core/EXTENDING.md), [drop-in folders](../extensions/README.md) |
| **Module** | A coherent workflow inside one extension | The module links on that extension's own entry page |
| **Model** | A record shape, stable identity, source of truth, and one authoritative writer | The owning module's model documentation |

The live source catalog is in [catalog](../catalog/README.md). [Knowledge](../knowledge/README.md) holds source-linked concept, evidence, and decision notes. The repo tracks their scaffolds, not the live notes, and is not a backup of the vault. Originals remain at their authorized sources or approved custody; even titles, locators, and pointers must suit the vault's audience. Examples and tests use synthetic data.

An extension is a portable folder, not an installation framework. Copy it into the extension directory and use its own entry page. Explicit wire-up adds a single named link to the normal start page, where it is easy to discover; it does not copy instructions, make wiring required for use, or grant authority. When working on an extension, keep changes inside it. Propose shared/core changes separately. The [extension guide](../core/EXTENDING.md#copy-or-wire-an-extension) documents the workflow and scope guard.

## How knowledge becomes reliable

1. **Locate and read.** Start from the artifact type, authorized access, and relevant known context, then read the source on its own terms. Existing concepts guide attention, not the outcome. Index generously without a quota; preserve clearly evidenced new topics or leave ambiguous references searchable rather than forcing a match. The agent makes the contextual judgment; the local tools validate records, not source contents.
2. **Separate the source from the assertion.** A source entry tracks a stable identity and replaceable pointer. Evidence cites the precise page, section, time, or other locator and distinguishes a bare mention from an attributed claim. An acronym can refer to different concepts in different contexts; uncertainty is recorded, not guessed away.
3. **Separate evidence from the current answer.** Evidence and prior decisions stay in history. An explicit, dated user confirmation selects a cited claim for one concept, scope, and question. A skip leaves a question open without prompting again automatically. A later disagreement is surfaced without erasing the prior confirmation; the user can explicitly supersede it. Domain-specific current records remain with their owning model, with references back to evidence when appropriate.

## What exists, and what is a design direction

- **Implemented:** Local Markdown source catalog, explicit source-link recovery, concept and evidence recording and retrieval, scoped resolution, history, and extension folder copy plus optional wire-up. The current tools search structured metadata and recorded evidence. They do not automatically read, sync, or analyze outside sources.
- **Direction:** Keep common retrieval and cross-source relationships in the core so extensions can reuse them without inventing duplicate systems. Build richer relationship discovery or indexing only as real use demands. A derived index could use SQLite for structured queries or vector search for semantic matching, but either would be rebuildable from canonical records. Neither is required, selected, or implemented. Likewise, this document does not install another domain extension.

For changes, start with the [source workflow](../core/WORKFLOWS.md), [concept workflow](../core/CONCEPTS.md), or [extension contract](../core/EXTENDING.md). Read the surrounding code and targeted tests before changing behavior. Keep the normal vault entry lightweight.

## Applying new models to prior knowledge

An explicit install request uses one shared core workflow: wire the folder, assess prior records in the user's stated scope against the new extension's model definitions, and ask whether to apply the preview. No per-extension installer or one-scope-per-vault rule is required. The preview distinguishes proposed matches, ambiguity, and overlaps with other interpretations; only approved clear matches become local core-owned Markdown links. A single underlying record may support several independent namespaces without source duplication or reclassification. See the [reconciliation workflow](../core/RECONCILE.md). Bare wire-up does not perform reconciliation.
