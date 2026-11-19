# Knowledge Vault

Open [START-HERE.md](START-HERE.md) in Obsidian or point an agent at [AGENTS.md](AGENTS.md).
This is a working vault, not the [core engineering checkout](https://github.com/bitpantry/knowledge-management).

## What belongs here

`catalog/` records sources and where to find them. `knowledge/` contains concepts, evidence,
decisions and interpretations. `extensions/` starts empty apart from its README;
add a domain extension only when you need one. Keep originals in their source systems.
If using Git, track approved records and extensions. Do not commit credentials,
raw source material, staging files, or anything the repository audience is not authorized to see.
A private repository does not authorize sharing client material.

## Update the core

Build a fresh staging vault from the chosen committed revision in the separate
engineering checkout using its `packaging/new-vault.sh`. Use a temporary directory,
not a sibling in a working projects folder. Compare that clean export with this
vault and apply only reviewed changes to the shared runtime files (`core/`,
`AGENTS.md`, `CLAUDE.md`, and linked reference examples). Review entry-point
changes separately to preserve the vault scope and extension links. Don't merge
the entire engineering repository or replace a live vault. Preserve live records,
installed extensions, local settings, and the vault's Git configuration. If a
record format changes, test migration on an authorized copy first. Commit updates
only after validation, and publish only to the intended vault remote.

```sh
python3 -B core/catalog.py check
python3 -B core/concepts.py check
python3 -B core/reconcile_extension.py check
```
