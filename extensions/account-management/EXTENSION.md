# Account Management

Track people, interactions, and leads without copying source content or rewriting the core. This extension is usable as a drop-in; the core owns install and optional reconciliation.

- [Relationships](modules/relationships/README.md) owns [Person](modules/relationships/PERSON.md) and [Interaction](modules/relationships/INTERACTION.md).
- [Pipeline](modules/pipeline/README.md) owns [Lead](modules/pipeline/LEAD.md).
- [First use and fictional walkthrough](WORKFLOW.md).

The vault operator owns the extension. Use only with material approved for this vault's audience and purpose. An account key keeps extension relationships in the intended context; it is not a permissions boundary. The extension uses the vault's source/evidence CLI APIs and Python 3.9+ standard library. All three models have one writer, `account.py`, and store their local Markdown notes under the extension's `records/` directory, which is created when needed and is not shipped.
