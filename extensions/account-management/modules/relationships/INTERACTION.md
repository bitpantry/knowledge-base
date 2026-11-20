# Interaction

Stable model ID: `interaction`. Owned by Relationships; `account.py` validates records and the core persists them. A reported or documented real exchange, such as a call, meeting, or email, can support an interaction. A proposed meeting that did not happen, a generic mention, or a duplicate source note is not an interaction.

Record ID starts with `interaction-`. Store the explicit account key, date, title, one or more existing same-account person IDs, optional concise notes, and optional source/evidence references. Do not record guessed dates or participants. If the original is already filed, link it rather than copying it.

An exact source speaker label may be mapped to an existing same-account participant during intake. The core stores a separate, evidence-backed speaker relationship; an unbound or ambiguous speaker stays only on the source evidence and is not guessed.
