# Onboard or enrich a Person

Use this for a named stakeholder intentionally tracked by the user, not a passing mention, unconfirmed identity, or scraped roster. These steps do not send messages, request access, or start ongoing monitoring.

1. **Establish scope and check for duplicates.** Identify the requested account. Run `list person --account ACCOUNT` and trace plausible candidates using `show person PERSON_ID --trace`. Compare known names/aliases, role, organization and existing sources; do not merge by name alone. If evidence is ambiguous, ask which identity to use and leave records unchanged.
2. **Read what is already known.** Open the authorized source or user-supplied message and file it via [core capture and evidence](../../../../core/WORKFLOWS.md) with stable identity, pointer and precise citation. Prefer approved internal context; if useful, check an employer’s public bio, an official industry role announcement or another reputable professional source. Use LinkedIn only when the visible page is accessible and identity is supported; ask for a direct profile link if it materially resolves ambiguity. Don’t invent missing fields or add personal phone/email. A dated older source is history, not necessarily current.
3. **Preview before applying.** Show the existing Person or proposed new one, populated field changes with sources/dates, any contradictions and fields left unresolved. Separate public work facts from an explicitly attributed account owner, relationship status, priority and strategic value. Record current facts only where supported; hold conflicts until resolved and keep old evidence. Get the user’s approval of the proposed changes unless their instruction already explicitly confirms the exact identity and changes. In a shared vault, include only fields and source references approved for that audience.
4. **Use the revision-gated writer.** Create a temporary JSON input outside the vault, with concrete IDs from the capture step. For a new person:

       {"id":"person-river-finch","account":"fictional-birch","title":"River Finch","organization":"Birch Workshop","job_title":"Operations Lead","evidence_ids":["REPLACE_WITH_EVIDENCE_ID"]}

       python3 -B extensions/account-management/account.py add person /path/to/person.json

   For an existing record, use `show person PERSON_ID --trace` for the revision and send only the approved changed fields and citations. JSON example:

       {"business_unit":"Field Operations","evidence_ids":["REPLACE_WITH_EVIDENCE_ID"]}

       python3 -B extensions/account-management/account.py revise-person PERSON_ID /path/to/patch.json --if-revision CURRENT_REVISION

   Null removes an optional profile property explicitly; absent fields are untouched. Revisions must cite the reviewed change and retain previous source/evidence references. If stale, reread and re-evaluate rather than forcing the update. Add a verified alternate name through `add-person-alias`; recording a manager uses the sourced `link-reporting` workflow, never a profile patch.
5. **Verify.** Rerun `show person PERSON_ID --trace`, verify cited changes, and use the People roster with the exact Person note link. Use `rebuild-org-chart` if the local generated views were not initialized. Report what changed and what remains uncertain. No bulk import, background enrichment, or outreach.

Commands above run from the vault root using `python3 -B extensions/account-management/account.py` followed by the documented action.
