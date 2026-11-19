# Source catalog contract · v1

The source of truth is one UTF-8 Markdown note in the live [catalog](../catalog/README.md) for each approved source. The filename is the stable source ID. Notes use LF, a YAML front matter block with JSON-valued fields and a fixed Markdown body. This is a deliberately narrow, deterministic subset, not arbitrary YAML. The CLI is the writer; a secondary index may be derived, never authoritative.

| Field | Meaning |
| --- | --- |
| source_id | Derived from kind, namespace and native_id; stable across pointer moves |
| kind, namespace, native_id | Origin type and immutable ID scoped to the verified provider or external custodian; together they are source provenance |
| title, date, tags | Minimal, audience-approved discovery metadata; date is the origin date |
| pointer | Current stable location in the authorized source or approved external custody |
| capture | Approved in the live catalog; pending intake stays outside the catalog |
| fallback | Null, pending without a pointer, or separately approved external custody for a chat upload |

The allowed `kind` values are `artifact` (ordinary file or document, including a PDF), `transcript`, `chat` (chat upload), `email`, `slack`, and `web`. Use the stable origin category, not its file extension; `file` is not a valid kind. The `file` command requires `kind`, `namespace`, `native_id`, `title`, `date` (YYYY-MM-DD), `pointer`, and `capture`; the tool computes `source_id`. `tags` and `fallback` are optional.

A recovered pointer may change without changing provenance. It must resolve to the original identity; without authorized exact-match evidence the existing record stays put. The core does not store contents, excerpts, credentials, unsafe links, or project fields. Source-app permissions still apply. There are no installed extension models.

Core CLI version: run the absolute or relative path to the tool with `--version`. The default catalog is relative to the tool location, not the shell’s working directory. Intake/observation paths work as normal shell-relative or absolute paths. A change to the canonical format requires separate review, a backed-up isolated migration test, and an explicit migration plan. Layout changes alone do not change this v1 record format.

The citation receipt includes a revision hash of the exact canonical record. It is not stored in the note. Metadata corrections use that hash as a precondition; repair remains the separate path for changing the primary pointer.

The additive [V1.1 concepts contract](CONCEPTS.md) references this catalog without changing its record format.
