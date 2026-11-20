#!/usr/bin/env python3
"""Preview and apply managed core and extension packages."""
import argparse
import io
import json
from pathlib import Path
import re
import stat
import subprocess
import sys
import zipfile

from catalog import write_lock
from update import (ASSET, LIMIT, MANIFEST, changes, decode, digest, encode, lock,
                    release_asset, release_index, unbundle, write)
from wire_extension import SLUG, extension_title, revise

RECEIPT = ".extension-release.json"


def package_name(slug):
    if not SLUG.fullmatch(slug):
        raise ValueError("use the extension folder's lowercase slug")
    return f"extension-{slug}.zip"


def managed_extension(name):
    parts = name.split("/")
    return (len(parts) <= 6 and
            all(re.fullmatch(r"[A-Za-z0-9_-]+", x) and x.lower() not in {"records","data","tests","fixtures","local","intake","archive"} for x in parts[:-1]) and
            bool(re.fullmatch(r"[A-Za-z0-9_-]+\.(md|py)", parts[-1])))


def extension_receipt(slug, commit, files):
    return {"schema": 1, "extension": slug, "commit": commit,
            "files": {p: digest(data) for p, data in sorted(files.items())}}


def read_receipt(raw, slug):
    obj = json.loads(raw)
    if (not isinstance(obj, dict) or set(obj) != {"schema","extension","commit","files"}
            or obj["schema"] != 1 or obj["extension"] != slug
            or not isinstance(obj["commit"],str) or not re.fullmatch(r"[a-f0-9]{40}", obj["commit"])
            or not isinstance(obj["files"],dict) or "EXTENSION.md" not in obj["files"]
            or len({n.casefold() for n in obj["files"]}) != len(obj["files"])
            or any(not managed_extension(p) or not isinstance(h,str) or not re.fullmatch(r"[a-f0-9]{64}",h)
                   for p,h in obj["files"].items())):
        raise ValueError(f"invalid extension package receipt: {slug}")
    return obj


def load_extension(raw, slug):
    if len(raw) > LIMIT:
        raise ValueError("extension package too large")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        entries = z.infolist()
        names = {m.filename for m in entries}
        if (len({p.casefold() for p in names}) != len(entries) or len(entries) > 256
                or sum(m.file_size for m in entries) > LIMIT or RECEIPT not in names
                or any(not (m.filename == RECEIPT or managed_extension(m.filename))
                       or stat.S_IFMT(m.external_attr >> 16) not in (0,stat.S_IFREG) for m in entries)):
            raise ValueError("invalid extension package members")
        receipt = read_receipt(z.read(RECEIPT), slug)
        if names != set(receipt["files"]) | {RECEIPT}:
            raise ValueError("extension package members do not match receipt")
        files = {p:z.read(p) for p in receipt["files"]}
        if extension_receipt(slug,receipt["commit"],files) != receipt:
            raise ValueError("extension package checksum mismatch")
        extension_title(files["EXTENSION.md"].decode())
        return receipt, files


def path_at(root, name):
    p = root
    for part in name.split("/")[:-1]:
        p /= part
        if p.is_symlink() or (p.exists() and not p.is_dir()):
            raise ValueError(f"unsafe vault directory: {name}")
    p = root/name
    if p.is_symlink() or (p.exists() and not p.is_file()):
        raise ValueError(f"unsafe vault file: {name}")
    return p


def read(root,name):
    p = path_at(root,name)
    return p.read_bytes() if p.exists() else None


def installed(root):
    parent = root/"extensions"
    if parent.is_symlink() or not parent.is_dir():
        raise ValueError("extensions directory missing or unsafe")
    return sorted(p.name for p in parent.iterdir()
                  if SLUG.fullmatch(p.name) and not p.is_symlink() and p.is_dir()
                  and ((p/RECEIPT).exists() or (p/RECEIPT).is_symlink()))


def preview(root, action, slug, release, fetch=release_asset):
    plan, targets = [], {}
    start = None

    def add(name, before, after):
        if before != after:
            plan.append((name,before,after))

    if action == "update" and slug is None:
        raw = read(root,MANIFEST)
        if raw is None:
            raise ValueError("vault core receipt is missing")
        previous = decode(raw)
        target, files = unbundle(fetch(release,ASSET))
        core_plan, bad = changes(root,previous,target,files)
        if bad:
            raise ValueError("locally changed core files: " + ", ".join(bad))
        plan.extend(core_plan)
        add(MANIFEST,raw,encode(target))
        targets["core"] = target["commit"]

    slugs = [slug] if slug is not None else installed(root)
    for name in slugs:
        asset = package_name(name)
        prefix = f"extensions/{name}/"
        receipt_path = prefix + RECEIPT
        raw = read(root,receipt_path)
        if action == "install":
            folder = root/"extensions"/name
            if folder.exists() or folder.is_symlink():
                raise ValueError(f"{name} already has a folder; use update for managed extensions")
        elif raw is None:
            raise ValueError(f"{name} is not a managed installed extension")
        previous = read_receipt(raw,name)["files"] if raw else {}
        target, files = load_extension(fetch(release,asset),name)
        bad = []
        names = previous.keys() | target["files"].keys()
        if len({rel.casefold() for rel in names}) != len(names):
            raise ValueError("case-only managed extension renames require review")
        for rel in sorted(names):
            p = prefix + rel
            old = read(root,p)
            actual = None if old is None else digest(old)
            if actual != target["files"].get(rel):
                if actual != previous.get(rel):
                    bad.append(rel)
                else:
                    add(p,old,files.get(rel))
        if bad:
            raise ValueError(f"locally changed {name} files: " + ", ".join(bad))
        add(receipt_path,raw,encode(target))
        targets[name] = target["commit"]
        if action == "install":
            start = read(root,"START-HERE.md")
            if start is None:
                raise ValueError("normal start page is missing")
            dest = prefix + "EXTENSION.md"
            title = extension_title(files["EXTENSION.md"].decode())
            add("START-HERE.md",start,revise(root,start.decode(),title,dest).encode())

    token = digest(encode([action,slug,release["tag_name"],targets,
                          [(p,None if a is None else digest(a),None if b is None else digest(b)) for p,a,b in plan]]))
    return plan, targets, token


def apply(root, plan):
    created, written = [], []
    # Caller holds both the release and catalog locks; recheck paths at point of write.
    try:
        if any(read(root,p) != old for p,old,_ in plan):
            raise ValueError("vault changed since preview")
        for name, old, new in plan:
            p = path_at(root,name)
            missing = []
            parent = p.parent
            while not parent.exists():
                missing.append(parent)
                parent = parent.parent
            for folder in reversed(missing):
                folder.mkdir()
                created.append(folder)
            if read(root,name) != old:
                raise ValueError(f"vault changed during update: {name}")
            write(p,new)
            written.append((p,old))
    except Exception:
        for p,old in reversed(written):
            write(p,old)
        for folder in reversed(created):
            folder.rmdir()
        raise


def run(root, action, slug, release, if_preview=None, fetch=release_asset):
    if slug is not None:
        package_name(slug)
    plan, targets, token = preview(root,action,slug,release,fetch)
    if if_preview is not None and token != if_preview:
        raise ValueError("stale vault preview; review the current plan")
    for name, commit in targets.items():
        print(f"{name}: {commit[:12]}")
    for name, old, new in plan:
        print(f"{'REMOVE' if new is None else 'ADD' if old is None else 'UPDATE'} {name}")
    if not plan:
        print("Already up to date.")
    elif if_preview is None:
        print(f"Preview only. To apply, append --if-preview {token}")
    else:
        with lock(root), write_lock(root):
            if action == "install" and (root/"extensions"/slug).exists():
                raise ValueError("extension folder appeared since preview")
            apply(root,plan)
        print("Applied. Run vault checks before committing.")
        if action == "install":
            print("For prior records, an agent can propose matches using core/RECONCILE.md. No records were classified.")
    return token


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="action", required=True)
    for verb in ("install","update"):
        cmd = sub.add_parser(verb)
        cmd.add_argument("extension",nargs=None if verb=="install" else "?")
        cmd.add_argument("--if-preview",help="apply only the exact preview")
    a = p.parse_args()
    try:
        run(Path(__file__).resolve().parents[1],a.action,a.extension,release_index(),a.if_preview)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, zipfile.BadZipFile, subprocess.SubprocessError) as exc:
        print(f"Vault manager: {exc}",file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
