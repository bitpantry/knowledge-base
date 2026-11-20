# Account Management workflow

For capture, use the three model guides from [the extension entry](EXTENSION.md). Start by establishing the user's intended account; do not treat every record in a vault as applicable. Use the current core source/evidence workflow for citations, and use known IDs instead of assuming identity. Sources not yet filed need not block clearly user-supplied information, but an unattached note is not independently verified.

The CLI validates Account Management models and delegates persistence to the core. The core stores model records and typed relationships in its live knowledge areas, not inside the extension folder. It accepts one JSON object per add. Required fields are `id`, `account` (lowercase dashed key), and `title`. Interactions also require `date` (YYYY-MM-DD) and `person_ids`. Optional fields: `notes`, `source_ids`, and `evidence_ids`; leads may also specify `person_ids`, `interaction_ids`, and `status` (defaults to open). An already-filed identical ID is a no-op; conflicting data for that ID is rejected, not merged. The input file can be kept outside the vault.

## Transcript intake and speaker links

1. Establish the account in scope and find its existing people with the person list command. Read the approved transcript and, if applicable, file it and its relevant evidence using the core intake workflow. Keep exact locator labels, including speaker labels and timestamps, on the evidence.
2. Record the interaction with known participant IDs and its explicit transcript source ID or selected evidence IDs. Include a speaker binding only where that exact label clearly identifies an in-scope participant. For example, add `"speaker_bindings":{"River (coordinator)":"person-fictional-river"}` to the interaction input. Do not bind by spelling similarity, account proximity, or a generic label. Ambiguous identities remain unbound.
3. An explicit binding writes a core `said` connection to matching in-scope evidence with the exact source citation. The speaker label remains on the evidence, not in a separate extension record. No additional confirmation is required for clearly supported links within the requested intake; if uncertain, do not bind. The CLI verifies bindings and does not make identity guesses. Repeating the same intake does not duplicate connections.
4. Trace either the interaction or the person to see backed speaker attributions. A person trace also lists their in-account interactions by date and title. An unbound speaker can still appear in a transcript citation but is not attributed to a person in the vault. A later verified intake may supply a missing binding. A contradictory proposed person for an already attributed passage stops for review rather than overwriting it.

## Fictional first use in a spare vault

Save each object below in its own temporary input file. Do not add the demo records to a live account vault.

    {"id":"person-fictional-river","account":"fictional-birch","title":"River Finch"}
    {"id":"interaction-fictional-call","account":"fictional-birch","title":"Workshop renewal call","date":"2026-11-19","person_ids":["person-fictional-river"],"notes":"The fictional coordinator asked for a follow-up."}
    {"id":"lead-fictional-renewal","account":"fictional-birch","title":"Shared tool renewal","person_ids":["person-fictional-river"],"interaction_ids":["interaction-fictional-call"],"notes":"Follow up to clarify the scope of a possible renewal."}

From the vault root:

    python3 -B extensions/account-management/account.py add person /path/to/person.json
    python3 -B extensions/account-management/account.py add interaction /path/to/interaction.json
    python3 -B extensions/account-management/account.py add lead /path/to/lead.json
    python3 -B extensions/account-management/account.py list lead --account fictional-birch
    python3 -B extensions/account-management/account.py show lead lead-fictional-renewal --trace
    python3 -B extensions/account-management/account.py set-lead-status lead-fictional-renewal qualifying --if-revision REVISION_FROM_SHOW
    python3 -B extensions/account-management/account.py check

A traced record returns its own exact core source and evidence references, including precise locator/speaker when captured. To inspect a related interaction's evidence, trace the interaction separately. Core records remain authoritative for source claims and confirmations. Model prose appears once in the core-owned Markdown body; IDs, scope, dates, status, and references stay in front matter. Lead status changes require the current revision so a stale read cannot replace a newer status. Back up the vault’s live knowledge separately from the extension package.

Installation and the optional retrospective preview use the core's shared workflow. An approved interpretation is a reference from prior core knowledge to a model, not a new person, interaction, or lead. Capture actual model records only when the user requests that work.
