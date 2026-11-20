# Account Management workflow

For capture, use the three model guides from [the extension entry](EXTENSION.md). Start by establishing the user's intended account; do not treat every record in a vault as applicable. Use the current core source/evidence workflow for citations, and use known IDs instead of assuming identity. Sources not yet filed need not block clearly user-supplied information, but an unattached note is not independently verified.

The CLI writes only its live extension records (apart from coordinating via the common vault write lock). It accepts one JSON object per add. Required fields are `id`, `account` (lowercase dashed key), and `title`. Interactions also require `date` (YYYY-MM-DD) and `person_ids`. Optional fields: `notes`, `source_ids`, and `evidence_ids`; leads may also specify `person_ids`, `interaction_ids`, and `status` (defaults to open). An already-filed identical ID is a no-op; conflicting data for that ID is rejected, not merged. The input file can be kept outside the vault.

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

A traced record returns its own exact core source and evidence references, including precise locator/speaker when captured. To inspect a related interaction's evidence, trace the interaction separately. Core records remain authoritative for source claims and confirmations. Own record prose appears once in the Markdown body; IDs, scope, dates, status, and references stay in front matter. Lead status changes require the current revision so a stale read cannot replace a newer status. Keep an access-approved backup of local records separately from the extension package.

Installation and the optional retrospective preview use the core's shared workflow. An approved interpretation is a reference from prior core knowledge to a model, not a new person, interaction, or lead. Capture actual model records only when the user requests that work.
