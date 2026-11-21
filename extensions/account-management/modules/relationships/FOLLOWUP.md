# Follow-up

Owned by Relationships. One canonical `followup-*` record per reviewed relationship action, even when shared across several people. Search existing in-scope follow-ups and the source interaction before adding; do not assume duplicate text is the same occurrence. Include account, specific action title, and same-account `person_ids`. Link the originating `interaction_id` if applicable; otherwise cite approved `source_ids` or `evidence_ids`. An interaction with no source does not by itself establish provenance. `owner_name`, `due` (YYYY-MM-DD) and concise `notes` are optional. Status is `open` by default, or `done` / `declined`. A due date is information only; nothing schedules a reminder or contacts anyone.

After reviewing with the user or receiving their explicit direction to capture an agreed action, use the Account Management CLI from the vault root:

    {"id":"followup-fictional-readout","account":"fictional-birch","title":"Send readout for review","person_ids":["person-fictional-river"],"interaction_id":"interaction-fictional-call","due":"2026-12-03"}

    python3 -B extensions/account-management/account.py add followup /path/to/followup.json
    python3 -B extensions/account-management/account.py list followup --account ACCOUNT
    python3 -B extensions/account-management/account.py show followup FOLLOWUP_ID --trace
    python3 -B extensions/account-management/account.py set-followup-status FOLLOWUP_ID done --if-revision CURRENT_REVISION

When closing or declining, keep the record and source instead of deleting it. Reopening requires an active associated person. The People roster shows the open count and earliest actual due date; Needs Attention shows active people with recorded priority or open items, ordered by earliest due, then open work, then H/M/L and name. Shared actions retain one ID and full details are rendered once. Historical People and interaction navigation stays in Person Details. The source interaction remains the source for evidence about what was agreed.
