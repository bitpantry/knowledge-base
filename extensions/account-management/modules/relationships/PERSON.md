# Person

Stable model ID: `person`. Owned by Relationships; `account.py` validates records and the core persists them. An approved in-scope identity or an existing sourced relationship is needed to create one. A mention of a name alone is not evidence of identity or membership.

Record ID starts with `person-` and must be unique within this vault. Store an explicit account key, a display name (title), optional concise notes, and optional source/evidence IDs. Do not collect contact details by default or copy source text. Reuse the existing person ID across interactions and leads in the same scope. People can share a display name; keep distinct IDs only when their identities can be distinguished.
