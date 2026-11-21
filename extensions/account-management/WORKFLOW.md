# Account Management workflow

For capture, use the three model guides from [the extension entry](EXTENSION.md). Start by establishing the user's intended account; do not treat every record in a vault as applicable. Use the current core source/evidence workflow for citations, and use known IDs instead of assuming identity. Sources not yet filed need not block clearly user-supplied information, but an unattached note is not independently verified.

The CLI validates Account Management models and delegates persistence to the core. The core stores model records and typed relationships in its live knowledge areas, not inside the extension folder. It accepts one JSON object per add. Required fields are `id`, `account` (lowercase dashed key), and `title`. Interactions also require `date` (YYYY-MM-DD) and `person_ids`. Optional fields: `notes`, `source_ids`, and `evidence_ids`; leads may also specify `person_ids`, `interaction_ids`, and `status` (defaults to open). An already-filed identical ID is a no-op; conflicting data for that ID is rejected, not merged. The input file can be kept outside the vault.

## Contextual relationships

The extension only defines its model fields and the meaning of its own Person and Interaction references. For contextual links from any source, including direct user statements, use [the core workflow](../../core/MODEL-STORE.md). Read the source and the vault's current registered labels, use only a matching directed label, and supply the exact evidence or source IDs. An unfamiliar term, ambiguous identity, or nearby record alone is not a supported link. Do not generate links from a model write.

**Reporting lines.** For an explicit, unambiguous statement such as “River reports to Jordan,” resolve both names to their existing in-scope Person IDs, file the statement as an attributable source and precise evidence, then write `reports-to` from the direct report to the manager. This includes a direct user statement: cite the message by stable ID and link where available, noting that it is user-supplied, not independently verified. Check existing links first. Do not infer reporting from title, a common team, or project coordination. Use one direction, not a second inverse label. If new evidence conflicts with an existing direct manager, preserve both source claims and surface the disagreement; do not silently overwrite or pick a current manager. Do not make unverified links look confirmed.

    python3 -B extensions/account-management/account.py link-reporting ACCOUNT REPORT_PERSON_ID MANAGER_PERSON_ID --evidence-id EVIDENCE_ID

For other relationships, reuse the vault's matching label or define a reusable one under the core workflow. These examples are not an exhaustive vocabulary.

A model trace shows both incoming and outgoing core relationships for that endpoint, together with source/evidence citations. A person trace also lists their same-account interactions by date and title. This is a read of the core's relationships, not a second copy or a private vocabulary.

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

A traced record returns its own exact core source and evidence references, including the precise locator when captured. To inspect a related interaction's evidence, trace the interaction separately. Core records remain authoritative for source claims and confirmations. Model prose appears once in the core-owned Markdown body; IDs, scope, dates, status, and references stay in front matter. Lead status changes require the current revision so a stale read cannot replace a newer status. Back up the vault’s live knowledge separately from the extension package.

Installation and the optional retrospective preview use the core's shared workflow. An approved interpretation is a reference from prior core knowledge to a model, not a new person, interaction, or lead. Capture actual model records only when the user requests that work.

## Generated org chart

Open `views/README.md` in Obsidian and choose Org Chart or People. In Reading view the chart shows manager-to-report arrows, omitting disputed and circular arrows and listing their exceptions. Its People link opens the searchable alphabetical roster; each name opens the exact canonical Person note. Known aliases appear only in the roster. Empty details are not filled in, and evidence is not copied into either view. The filenames provide titles when Obsidian's inline title is enabled. To create or rebuild both views, run:

    python3 -B extensions/account-management/account.py rebuild-org-chart

Once either view exists, supported Person additions, alias changes and revisions, Interaction additions, and the extension's `link-reporting` command refresh both. Raw core writes do not execute extension code. If a command reports a view warning, its canonical write succeeded; correct the issue and rebuild. Rebuilding writes only derived Markdown. There is no scheduler or sync task. Do not maintain the chart by hand, or treat an unknown manager, conflicting claims or cycles as a confirmed hierarchy.
