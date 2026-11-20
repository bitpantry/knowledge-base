# Optional extension reconciliation

**“Install <extension>” is one common workflow in the core.** Wire the copied folder into the normal start page, inspect existing knowledge using the extension's model definitions, show the reconciliation preview, then ask whether to apply it. No extension-specific installer is required. Apply only if the user approves clear matches. Copy/drop-in and an explicit bare “wire it up” still work alone and do not preview or classify prior knowledge. If there are no existing records to assess or no applicable definitions, report no candidates; nothing needs applying.

## Preview before writing

1. Honor the user's stated scope: account, project, topic, folder, source set, or any other explicit boundary. Separate vaults are optional; a vault can hold multiple scopes. Do not infer membership from record type, count, or proximity. Leave out-of-scope records out of the proposal and keep mixed or uncertain cases out of any approved application. If needed, ask one short scope question or preview only the safely identifiable subset. Read the extension's own entry, module instructions and applicable model definitions. Read the relevant existing core records and available evidence in their own context. Do not treat a label shared by both as a semantic match. Ordinary lookup still excludes architecture/maintenance documentation.
2. Propose a clear match only if the existing evidence supports it. Mark ambiguous cases or no match as such; explain why briefly. Note any overlap: the same core record can be viewed through multiple independent models, even from different extensions. Do not decide that one model displaces another. A map to a model is not a new extension-owned record or an assertion that its workflow has happened.
3. Put a reviewed JSON array outside the vault. Each item contains: extension folder slug `extension`, extension-relative Markdown definition `model`, stable extension-local `model_id`, display `model_name`, `record_type` (source, concept, evidence, or decision), `record_id`, `state` (match, ambiguous, or no-match), and a short evidence-grounded `reason`. Use the stable model ID from its definition or coordinate a consistent slug with the owner. If there is nothing applicable, use an empty array. Do not quote or copy originals.

Example for a synthetic garden-equipment concept:

    [
      {
        "extension": "repair-planning",
        "model": "modules/maintenance/MODEL.md",
        "model_id": "maintenance-item",
        "model_name": "Maintenance Item",
        "record_type": "concept",
        "record_id": "con-garden-pump",
        "state": "match",
        "reason": "The approved service note describes a recurring maintenance requirement."
      }
    ]

    python3 -B core/reconcile_extension.py preview /path/to/plan.json

Preview validates IDs and relative links, reports the status of every item, and shows proposed and existing overlaps. It writes nothing. The agent evaluates model fit; the CLI does not infer or independently verify semantic claims. Present counts and details for clear matches, ambiguities, no-matches and overlap to the operator. Ask what to record. To narrow the batch, remove unwanted clear matches and generate a new preview.

## Apply only the approved preview

    python3 -B core/reconcile_extension.py apply /path/to/plan.json --if-preview APPROVED_PREVIEW
    python3 -B core/reconcile_extension.py list concept con-garden-pump
    python3 -B core/reconcile_extension.py check
    python3 -B core/catalog.py check

The token binds the plan, affected prior interpretations, and current local record/model input. It protects against stale input, not improper authorization. Only clear new approved matches are written. Ambiguities and no-matches are never persisted by this tool; an existing interpretation with different metadata is flagged, never silently overwritten. Re-preview after a write or interruption; a replay of the same approved matches will not duplicate them. The batch writes complete notes one at a time, not in an all-or-nothing transaction.

A mapping is a small Markdown note in `knowledge/interpretations/`, keyed by extension, stable model ID, core record type, and core record ID. Its reason appears once, in the body, next to the navigation links to the core note and model definition. IDs and other structured fields stay in the header. The original IDs, content, citations and prior extension records are not changed. Retrieve any number of interpretations side by side with `list`. Retain and separately back up live mappings with the vault; they are ignored by the code repository. If a model definition is moved or removed, the check reports the stale reference; review its disposition instead of replacing or recategorizing existing records automatically.
