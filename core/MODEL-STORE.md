# Core model records and relationships

The core is the only storage layer. Catalog notes identify sources; evidence
attributes passages to sources; typed records and sourced relationships grow
the vault's connected knowledge. An extension defines its models, field rules,
relationship vocabulary and capture workflow. It does not create a second
record store. Its command validates domain meaning, then calls the core writer.

- `knowledge/records/<model-id>.md`: one typed record per stable ID. Scope,
  owner, type and references are metadata; its title and notes are in the
  body. The namespace/owner determines which extension understands the type,
  not which folder stores it. Read a known ID directly. Use that same record
  when linking a new interaction or source; do not copy it.
- `knowledge/relationships/<scope>/<relationship-id>.md`: a directed,
  evidence-backed link. It has scope, from/to IDs, predicate, and supporting
  evidence or source IDs. Every endpoint must exist and model endpoints must
  be in the same scope. A relationship references the source rather than
  copying its text. The same exact link deduplicates. Query the relevant scope
  rather than searching the entire vault.

This is a storage rule, not a claim that an agent has independently verified
the source. Tools validate IDs and references. The agent reads the source,
finds related existing records, determines whether the relationship is
supported, and invokes the documented writer. If identity or scope is
ambiguous, preserve the evidence or label without creating a confirmed link.
Do not infer a person from any mention of their name. Write clearly supported
links during authorized ingestion; do not defer all linking to a later,
unrequested cleanup. A separate retrospective reconciliation still requires
review; it is not a substitute for ordinary context-aware intake.

The core Python interface is `model_store.py`; extension writers use
`read_model`, `write_model`, and `write_relationship` under the shared write
lock. A model-specific command remains responsible for semantic validation.
After a change, run `python3 -B core/model_store.py check` with the other core
checks. Do not publish live records as part of an extension package.

## Link knowledge during intake

Use the same linking workflow for any applicable source. Read the source in
context, look for existing records that it actually refers to, and identify
what connection is supported. The relationship does not have to be listed
in an extension, and the source does not need a dedicated intake command.

1. Check the vault's reusable relationship labels before choosing a label:

       python3 -B core/model_store.py labels

   The list is stored in `knowledge/relationship-labels.md`. It starts empty.
   Reuse an existing label if its definition and direction fit. Otherwise,
   create a short, reusable label with a definition and direction in this
   vault. Defining a label does not require a core or extension change.

       python3 -B core/model_store.py define-label LABEL --definition "What the relationship means" --direction "From role → to role"

2. Record each clear, useful link with the original source or the precise
   evidence passage that supports it. Do not use a name match alone as proof
   of identity or invent an attribution. Leave uncertain links unresolved.
   Examples in model instructions are illustrative, not allowed-label lists.

       python3 -B core/model_store.py link SCOPE FROM_ID LABEL TO_ID --evidence-id EVIDENCE_ID
       python3 -B core/model_store.py links SCOPE RECORD_ID

   Use `--source-id SOURCE_ID` for a source-level assertion such as a verified
   byline; both provenance flags can be repeated. The core checks that the
   label is defined, the references exist and model endpoints share the scope.
   It does not decide whether the source semantically proves the link.
   The label document and live edges are vault data, never replaced by updates.
