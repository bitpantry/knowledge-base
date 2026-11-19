#!/usr/bin/env python3
"""Preview or apply shared core files from the engineering base's latest published release."""
import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile

REPO = "bitpantry/knowledge-management"
ASSET = "knowledge-vault-core.zip"
MANIFEST = ".core-release.json"
LIMIT = 8 * 1024 * 1024
FIXED = {"AGENTS.md", "CLAUDE.md", "examples/recovery-observation.json"}
REQUIRED = {"AGENTS.md", "core/update.py", "core/catalog.py", "core/concepts.py"}


def managed(name):
    return name in FIXED or bool(re.fullmatch(r"core/[A-Za-z0-9_-]+\.(?:py|md)", name))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def manifest(commit, files):
    return {"schema": 1, "repository": REPO, "commit": commit,
            "files": {name: digest(data) for name, data in sorted(files.items())}}


def encode(obj):
    return (json.dumps(obj, sort_keys=True, indent=2) + "\n").encode()


def decode(raw, required=REQUIRED):
    obj = json.loads(raw)
    if (not isinstance(obj, dict) or set(obj) != {"schema", "repository", "commit", "files"}
            or obj["schema"] != 1 or obj["repository"] != REPO
            or not isinstance(obj["commit"], str) or not re.fullmatch(r"[a-f0-9]{40}", obj["commit"])
            or not isinstance(obj["files"], dict) or not required <= obj["files"].keys()):
        raise ValueError("invalid core release manifest")
    for name, checksum in obj["files"].items():
        if not managed(name) or not isinstance(checksum, str) or not re.fullmatch(r"[a-f0-9]{64}", checksum):
            raise ValueError(f"invalid managed entry: {name}")
    return obj


def local_path(root, name):
    p = root
    for parent in name.split("/")[:-1]:
        p = p / parent
        if p.is_symlink() or not p.is_dir():
            raise ValueError(f"invalid vault directory for {name}")
    p = root / name
    if p.is_symlink() or (p.exists() and not p.is_file()):
        raise ValueError(f"not a regular vault file: {name}")
    return p


def local_files(root):
    names = sorted(FIXED | {"core/" + p.name for p in (root / "core").iterdir() if managed("core/" + p.name)})
    return {name: local_path(root, name).read_bytes() for name in names if (root / name).exists()}


def release_bytes():
    url = "https://api.github.com/repos/" + REPO + "/releases/latest"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "knowledge-vault-updater"})
        with urllib.request.urlopen(req, timeout=20) as response:
            release = json.loads(response.read(LIMIT + 1))
        assets = [a for a in release["assets"] if a["name"] == ASSET]
        if release["draft"] or release["prerelease"] or len(assets) != 1:
            raise ValueError("the latest published release has no unique core asset")
        asset = assets[0]
        expected = f"https://github.com/{REPO}/releases/download/{release['tag_name']}/{ASSET}"
        if asset["browser_download_url"] != expected:
            raise ValueError("unexpected core asset URL")
        with urllib.request.urlopen(expected, timeout=20) as response:
            raw = response.read(LIMIT + 1)
        if asset.get("digest") and asset["digest"] != "sha256:" + digest(raw):
            raise ValueError("GitHub asset digest does not match")
        return raw
    except urllib.error.HTTPError as exc:
        if exc.code not in (401, 403, 404):
            raise
        if not shutil.which("gh"):
            raise ValueError("release not publicly accessible; install and sign in to GitHub CLI for private access") from exc
        with tempfile.TemporaryDirectory(prefix="km-release-") as tmp:
            out = Path(tmp) / ASSET
            subprocess.run(["gh", "release", "download", "--repo", REPO,
                            "--pattern", ASSET, "--output", str(out)], check=True, timeout=60)
            if out.stat().st_size > LIMIT:
                raise ValueError("core release asset is too large")
            return out.read_bytes()


def unbundle(raw):
    if len(raw) > LIMIT:
        raise ValueError("core release asset is too large")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        members = z.infolist()
        names = {m.filename for m in members}
        if (len(names) != len(members) or len(members) > 256
                or sum(m.file_size for m in members) > LIMIT or MANIFEST not in names
                or any(not (m.filename == MANIFEST or managed(m.filename))
                       or stat.S_IFMT(m.external_attr >> 16) not in (0, stat.S_IFREG) for m in members)):
            raise ValueError("unexpected file, duplicate, or invalid size in the core release")
        target = decode(z.read(MANIFEST))
        if names != set(target["files"]) | {MANIFEST}:
            raise ValueError("asset contents do not match manifest")
        files = {name: z.read(name) for name in target["files"]}
        if manifest(target["commit"], files) != target:
            raise ValueError("asset checksum mismatch")
        return target, files


def changes(root, previous, target, files):
    names = previous["files"].keys() | target["files"].keys()
    plan, conflicts = [], []
    for name in sorted(names):
        p = local_path(root, name)
        content = p.read_bytes() if p.exists() else None
        actual = None if content is None else digest(content)
        old, new = previous["files"].get(name), target["files"].get(name)
        if actual == new:
            continue  # already on the release bytes
        if actual != old:
            conflicts.append(name)
        elif actual != new:
            plan.append((name, content, files.get(name)))
    return plan, conflicts


def write(path, data):
    if data is None:
        path.unlink()
        return
    existing_mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    with tempfile.NamedTemporaryFile(prefix=".km-update-", dir=path.parent, delete=False) as f:
        t = Path(f.name)
        try:
            f.write(data)
            f.flush()
            os.fchmod(f.fileno(), existing_mode)
            f.close()
            os.replace(t, path)
        finally:
            if t.exists():
                t.unlink()


@contextlib.contextmanager
def lock(root):
    p = Path(tempfile.gettempdir()) / (".km-update-" + digest(os.fsencode(root.resolve())) + ".lock")
    fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        yield
    finally:
        p.unlink()


def update(root, raw, apply=False):
    target, files = unbundle(raw)
    receipt = local_path(root, MANIFEST)
    if not receipt.exists():
        raise ValueError("this vault has no installed-core manifest; initialize it from a verified baseline")
    with lock(root) if apply else contextlib.nullcontext():
        before = receipt.read_bytes()
        previous = decode(before, required=REQUIRED - {"core/update.py"})
        plan, conflicts = changes(root, previous, target, files)
        print(f"Core: {previous['commit'][:12]} -> {target['commit'][:12]}")
        for name, old, new in plan:
            print(f"{'REMOVE' if new is None else 'ADD' if old is None else 'UPDATE'} {name}")
        if conflicts:
            raise ValueError("locally changed shared files (nothing applied): " + ", ".join(conflicts))
        if not plan and previous == target:
            print("Already up to date.")
            return
        if not apply:
            print("Preview only. Re-run with --apply and the exact --commit shown above to install.")
            print(f"Target commit: {target['commit']}")
            return
        written = []
        try:
            for name, old, new in plan:
                p = local_path(root, name)
                if (p.read_bytes() if p.exists() else None) != old:
                    raise ValueError(f"file changed during update: {name}")
                write(p, new)
                written.append((p, old))
            if receipt.read_bytes() != before:
                raise ValueError("core receipt changed during update")
            write(receipt, encode(target))
        except Exception:
            for p, old in reversed(written):
                write(p, old)
            raise
        print("Core updated. Run the vault checks before committing.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="install the previewed commit")
    parser.add_argument("--commit", help="full commit from preview; required for --apply")
    args = parser.parse_args()
    if args.apply != (args.commit is not None):
        parser.error("--apply and --commit must be used together")
    try:
        raw = release_bytes()
        if args.apply and unbundle(raw)[0]["commit"] != args.commit:
            raise ValueError("the available release differs from the preview; preview it again")
        update(Path(__file__).resolve().parents[1], raw, args.apply)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, zipfile.BadZipFile, subprocess.SubprocessError) as exc:
        print(f"Core updater: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
