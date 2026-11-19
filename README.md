# Knowledge Management Core v1.1

Open this folder in Obsidian and begin at [START-HERE.md](START-HERE.md), or send an agent to [AGENTS.md](AGENTS.md).

- [core](core/SCHEMA.md): contracts, workflows, and local catalog CLI.
- [catalog](catalog/README.md): live Markdown source metadata.
- [knowledge](knowledge/README.md): Markdown concepts, evidence and dated decisions.
- `examples/`: source-recovery example; development walkthroughs are excluded from vault exports.
- [extensions](extensions/README.md): portable domain workflows; wired entries are on START-HERE.md.
- `tests/`: synthetic fixtures and automated checks; never live data.

The code repository deliberately excludes live catalog and knowledge records, local settings, and staging files. The live data directories contain only scaffold READMEs. Keep access-approved backups of live records separately; Git history in this code repo is not a vault backup. Do not force-add or blindly copy live records into the code repository.

Run `python3 core/catalog.py check` `python3 -B core/concepts.py check` and `python3 -B -m unittest discover -s tests -v` from this folder. No credentials or services are required.

## Start a new vault

Export a committed core revision with `git archive`, not a clone or a copy of
the development checkout. The export excludes the test suite and the Tool Loans
demo. Use a new, explicitly chosen destination; never extract over a live vault.

```sh
mkdir "/path/to/new-vault" &&
  git archive HEAD | tar -x -C "/path/to/new-vault"
```

Initialize Git separately in the new vault if desired. For a vault that tracks
live records, replace the development-only catalog and knowledge ignore rules
with the vault's tracking policy before adding records. Review and validate
updates separately; never reintroduce developer tests or demo extensions.
