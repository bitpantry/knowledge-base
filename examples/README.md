# Try the core with fictional sources

Inputs live in the [synthetic test-fixture directory](../tests/fixtures/). The pointers are documentation placeholders, not live links. The observation fixtures model what an operator verified; they do not claim real provider access. Run from the project folder:
```sh
DEMO="$(mktemp -d)"
python3 core/catalog.py --root "$DEMO" file tests/fixtures/file-source.json
python3 core/catalog.py --root "$DEMO" file tests/fixtures/file-source.json
python3 core/catalog.py --root "$DEMO" search intake operations
SOURCE="$(basename "$(find "$DEMO/catalog" -name 'src-*.md' -print)" .md)"
python3 core/catalog.py --root "$DEMO" cite "$SOURCE"
python3 core/catalog.py --root "$DEMO" recover "$SOURCE" tests/fixtures/recovery/moved.json
python3 core/catalog.py --root "$DEMO" recover "$SOURCE" tests/fixtures/recovery/ambiguous.json
python3 core/catalog.py --root "$DEMO" recover "$SOURCE" tests/fixtures/recovery/offline.json
python3 core/catalog.py --root "$DEMO" check
```
Expect one source with metadata only, the second file call to report “already filed,” one moved-pointer proposal, and no repairs for ambiguity or offline. No core starter file is changed.

See the [synthetic concept walkthrough](CONCEPTS.md) for precise evidence, a conflicting claim and user confirmation.
