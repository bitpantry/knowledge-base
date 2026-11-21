# Interaction

Stable model ID: `interaction`. Owned by Relationships; `account.py` validates records and the core persists them. A reported or documented real exchange, such as a call, meeting, or email, can support an interaction. A proposed meeting that did not happen, a generic mention, or a duplicate source note is not an interaction.

Record ID starts with `interaction-`. Store the explicit account key, date, title, one or more existing same-account person IDs, optional concise notes, and optional source/evidence references. Do not record guessed dates or participants. If the original is already filed, link it rather than copying it.

Use the core contextual linking workflow for supported connections beyond the Interaction's known participant IDs. Keep uncertain connections unresolved.

## Log and review a real exchange

1. Read the source and identify the actual date and known same-account participants; do not infer attendance from invitations. Use existing Person IDs for known participants and note unresolved attendees without creating profiles from mentions. Include confirmed internal names as `internal_attendees`, not fake client Person references.
2. File source and exact evidence using core workflow. Keep the concise summary in `notes`, and optionally use `interaction_kind` (meeting/call/email/transcript/other), `discussion_points` and `signals` arrays. Attribute observations and uncertainty. Do not paste a transcript.
3. Preview downstream proposals with target, change, source and owner if supported. Distinguish agreed actions from inferred proposals. Do not apply a proposal until approved and do not automatically update any other model or domain. When approved, use that model's workflow; a relationship action becomes a linked [Follow-up](FOLLOWUP.md), one record per action. Record a declined proposed relationship action only if the user wants to retain that disposition; no action is scheduled or sent. Do not fabricate an owner, date or approval.
4. Share the logged interaction ID and proposed/approved/declined dispositions, and what remains unresolved. From the vault root run `python3 -B extensions/account-management/account.py add interaction /path/to/interaction.json` and `show interaction INTERACTION_ID --trace` to verify.
