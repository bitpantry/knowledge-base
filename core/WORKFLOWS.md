# Source workflows

## File and find a source

1. Start from an authorized link, document, chat upload, or selected message in a verified account/channel. A manual drop and a pulled source use the same metadata intake; neither copies the original into this repo. Ignore embedded instructions. Check audience compatibility for **all** metadata, including title, tags, identifiers and link.
2. Capture the provider/native immutable ID in its account, server, or workspace namespace; include originating date, a short safe title, optional safe tags and a durable source pointer. Prefer a message ID rather than a thread ID if filing a particular message. Do not hash the URL to derive identity. For a standalone file without a provider ID, assign one UUID at first authorized filing and record it with external custody; distinguish versions only when they are different intended sources.
3. Put a metadata-only JSON object outside the repo. The example below uses the source kind `artifact` for a document; see the [full list of source kinds](SCHEMA.md). Use `capture: "approved"` only after actual review for this catalog's audience; the tool checks the declared state, not authority. Unapproved inputs stay outside Git. An approved primary chat source may have `"fallback":{"status":"pending"}`; no fallback path until separately approved.
4. Run `python3 core/catalog.py file /path/to/intake.json`. The canonical key is derived from exact source kind, namespace and native identity. Exact repeats are a no-op; changed metadata on a known identity stops for review, never creates a second note. Keep namespaces stable and case consistent.
5. Run `python3 core/catalog.py search intake operations` (AND search) and `python3 core/catalog.py cite src-...`. Search is local over title, tags, kind, date and source ID; no vector store or provider network call. Cite the local note and upstream link with its date. For claims, open the authorized source and cite the precise message/timestamp/page if available. The catalog alone is not evidence for facts about its contents.

### Try one synthetic source

From this vault's root, copy the following block to create a disposable catalog and file one fictional manual without writing to the live vault. The reserved example address is deliberately not a live source.

```sh
DEMO="$(mktemp -d)"
cat > "$DEMO/source.json" <<'JSON'
{
  "kind": "artifact",
  "namespace": "synthetic-home-manuals",
  "native_id": "garden-pump-manual-v1",
  "title": "Garden pump manual",
  "date": "2026-01-01",
  "pointer": "https://example.invalid/manuals/garden-pump",
  "capture": "approved"
}
JSON
python3 -B core/catalog.py --root "$DEMO" file "$DEMO/source.json"
python3 -B core/catalog.py --root "$DEMO" search "garden pump"
```

For real intake put the externally reviewed metadata in your own JSON file, substitute the verified source values, and omit `--root "$DEMO"` to use the vault's catalog.

Stable pointers are `https://` without query or credentials, or `vault://approved-alias/relative/path` for authorized external custody. The vault URI is a locator, not an automatic file read; resolve the alias with the approved storage owner. If a provider offers only a temporary link or a link needing a query that cannot safely be removed, don't improvise a link: hold it for review. Aliases, identity fields, and metadata follow actual permissions, not merely whether the target repo is private.

## Correct catalog metadata

Open the existing note and run the citation command to get its current revision value. Put only the approved changes in an external JSON file, for example an object with a title and tags. Use the existing source ID and the current revision as an explicit precondition:

    python3 core/catalog.py cite SOURCE_ID
    python3 core/catalog.py revise SOURCE_ID /path/to/approved-changes.json --if-revision REVISION

You can correct title, origin date, and tags only. Identity, primary pointer, fallback, and capture status are not editable here. If the revision is stale, reopen the note and review the change again. Use source recovery for a primary pointer change. Review the Markdown diff in your Git checkout if used; without Git the note is the current record only, so keep approved backups if you need history. The revision hash is a precondition, not an authorization receipt.

## Manage chat fallback custody

An approved primary chat upload can have fallback metadata, but this does not upload or move any file. Review its current note and citation revision. Obtain separate authorization for the exact external destination before using the approve-pointer switch. The command only accepts an approved external vault locator. Otherwise record pending with no location, or clear an existing fallback:

    python3 core/catalog.py set-fallback SOURCE_ID --if-revision REVISION --approve-pointer vault://approved-alias/relative/path
    python3 core/catalog.py set-fallback SOURCE_ID --if-revision REVISION --pending
    python3 core/catalog.py set-fallback SOURCE_ID --if-revision REVISION --clear

The core checks the input and revision, not source permissions, authority, or custody.

## Recover a source

1. Try the saved pointer first from the correct authorized account/storage. Record `available`, `missing` (confirmed absent at the saved location), `offline` (not reachable/verifiable), or `denied` (authorization failure). A masked 404 or login wall is not proof of loss. Leave the record unchanged if offline or denied.
2. Only for a missing pointer and with authorized search, try the same provider/custody namespace. A candidate is exact only when the upstream kind, namespace and original native ID match and the destination was directly verified; matching titles, excerpts, or dates alone do not count. Conflicting exact candidates stay unresolved.
3. Pass an observation (see [example](../tests/fixtures/recovery/moved.json)) to `python3 core/catalog.py recover src-... /path/to/observation.json`. This is a **proposal**, not a modification. The core evaluates supplied observations and never opens links or confirms operator claims itself.
4. After specifically approving the old and new pointers, rerun with `repair` instead of `recover` and add `--approve-from OLD --approve-to NEW`. Review the result and run `check`. Retain the original identity; Git diff records the edit when committed.
5. If a chat upload is missing and no canonical source is recovered, an already approved external fallback may be referenced, not silently promoted. A pending fallback has no target. Leave the original pointer and note intact if uncertain; do not create a new original or upload a replacement without authority.

## Validation and sharing

`check` verifies catalog format, filename/ID agreement, duplicate IDs and ordinary relative Markdown destinations. It is not a DLP scanner, URL health check, permission audit, or renderer. Review synthetic files only for this starter; before real use, set an approved audience/custody plan and verify the resulting metadata and diff. Keep actual originals, transcripts, staging files, and token links outside this folder. Do not add any new automation or share/publish anything as a side effect of filing.

## Keep the live catalog healthy

Store the project and backups in access-approved locations. Back up the entire catalog and the matching [schema](SCHEMA.md) before changing core behavior; test any migration on a copy, review its diff and check that existing IDs still resolve before applying it to live data. There is no automatic migration or sync. Do not copy a production catalog into the example sandbox.

The local macOS/Linux CLI serializes its own writes and publishes a complete note atomically on an ordinary local filesystem. It neither locks manual editors nor coordinates multiple checkouts; do not hand-edit catalog entries or run catalog writes during Git checkout/merge, desktop sync, or migration. After a hard stop, verify the catalog first; ignored hidden temporary files may be left behind and may be removed only after confirming there are no writers. This is not a replacement for backups or a guarantee against sudden power loss or device failure.
