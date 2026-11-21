# Person

Stable model ID: `person`. Owned by Relationships; `account.py` validates records and the core persists them. An approved in-scope identity or an existing sourced relationship is needed to create one. A mention of a name alone is not evidence of identity or membership.

Record ID starts with `person-` and must be unique within this vault. Store an explicit account key, a display name (title), optional concise notes, and optional source/evidence IDs. Do not collect contact details by default or copy source text. Reuse the existing person ID across interactions and leads in the same scope. People can share a display name; keep distinct IDs only when their identities can be distinguished.

Store an explicitly supported alternate name as an optional `aliases` list, not a different Person ID. Use names and aliases to find candidates, never as proof of identity. For an existing person, trace to get the current revision and cite the source passage that confirms the alias:

    python3 -B extensions/account-management/account.py show person PERSON_ID --trace
    python3 -B extensions/account-management/account.py add-person-alias PERSON_ID "Alternate name" --if-revision REVISION --evidence-id EVIDENCE_ID

## Optional verified profile properties

- Work: `organization`, `business_unit`, `job_title`, `work_email`, `work_phone`, `linkedin_url` (clean HTTPS public profile link). Do not collect private contact details or publish work contact details in the shared roster.
- This account’s relationship: `relationship_owner`, `relationship_status`, `priority`, `strategic_value`. These are attributable user/team judgments, not facts inferred from job title. Keep them within the record’s account scope. Use the account’s own wording and omit unassigned values.

Properties are optional and empty/unknown values should be omitted. Profile values render as Obsidian Properties; the note body remains display name and optional readable notes. Reporting, direct reports and last recorded contact are derived from sourced reporting edges and documented interactions, not editable fields. A real exchange can support last recorded contact; an invite or mention cannot. The Person trace exposes these summaries and citations. No archival workflow is provided; preserve historical records rather than deleting them to change the roster.

See [the onboarding and enrichment workflow](ONBOARD-PERSON.md).
