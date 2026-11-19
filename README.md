# Knowledge Management Core v1.1

Open this folder in Obsidian and begin at [START-HERE.md](START-HERE.md), or send an agent to [AGENTS.md](AGENTS.md).

- [core](core/SCHEMA.md): contracts, workflows, and local catalog CLI.
- [catalog](catalog/README.md): live Markdown source metadata.
- [knowledge](knowledge/README.md): Markdown concepts, evidence and dated decisions.
- `examples/`: source-recovery example; development walkthroughs are excluded from vault exports.
- [extensions](extensions/README.md): portable domain workflows; wired entries are on START-HERE.md.
- `tests/`: synthetic fixtures and automated checks; never live data.
- [docs](docs/README.md): engineering design notes; not part of a working vault.

The code repository deliberately excludes live catalog and knowledge records, local settings, and staging files. The live data directories contain only scaffold READMEs. Keep access-approved backups of live records separately; Git history in this code repo is not a vault backup. Do not force-add or blindly copy live records into the code repository.

Run `python3 core/catalog.py check` `python3 -B core/concepts.py check` and `python3 -B -m unittest discover -s tests -v` from this folder. No credentials or services are required.

## Start a new vault

From this engineering checkout, run:

```sh
bash packaging/new-vault.sh "/path/to/new-vault"
```

Use a destination that does not exist. The command packages the committed core,
adds live-vault documentation and record-tracking rules, and leaves out tests,
engineering docs, the Tool Loans demo, the packaging scripts, and Git history.
Initialize a separate Git repository in the new vault if desired. Its README
describes how to review future core updates without overwriting live data.

## Publish a compatible core update

After committing and testing in the engineering base, export that exact commit
to a fresh directory in OS temporary storage using `packaging/new-vault.sh`.
Then package its managed runtime files:

```sh
python3 -B packaging/vault-release.py "$TEMP_VAULT" "$TEMP_DIR/knowledge-vault-core.zip"
```

Attach the resulting asset to a published, non-prerelease GitHub Release for
that commit. The installed updater reads published releases, not untagged
changes on `main`. Keep releases on this channel compatible with existing
vault records; review data migrations separately. A release is not permission
to sync or publish any vault's records.
