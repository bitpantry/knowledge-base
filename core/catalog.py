#!/usr/bin/env python3
"""Local Markdown catalog. No network requests, connectors, or document copies."""
import argparse
from contextlib import contextmanager
import fcntl
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit, unquote

ROOT = Path(__file__).resolve().parent.parent
CORE_VERSION = "1.1.0-beta"
FIELDS = {"source_id", "title", "kind", "native_id", "namespace", "date", "tags", "pointer", "capture", "fallback"}
ID = re.compile(r"src-[0-9a-f]{24}\Z")
KEY = re.compile(r"[a-z][a-z0-9_]*\Z")
KINDS = {"chat", "email", "slack", "transcript", "artifact", "web"}

def require(condition, reason):
    if not condition:
        raise ValueError(reason)

def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def digest(kind, namespace, native_id):
    key = json.dumps([kind, namespace, native_id], separators=(",", ":"), ensure_ascii=False)
    return "src-" + hashlib.sha256(key.encode()).hexdigest()[:24]

def clean_text(value, label, limit):
    require(isinstance(value, str) and value == value.strip() and 0 < len(value) <= limit
            and all(ord(c) >= 32 and ord(c) != 127 for c in value), "invalid " + label)
    return value

def pointer(value):
    clean_text(value, "pointer", 2000)
    u = urlsplit(value)
    if u.scheme == "https":
        require(u.hostname and not u.username and not u.password and not u.query,
                "use a stable HTTPS pointer without credentials/query parameters")
        require(not any(c.isspace() for c in value), "percent-encode whitespace")
    elif u.scheme == "vault":
        parts = [u.netloc] + unquote(u.path).split("/")[1:]
        require(re.fullmatch(r"[a-z][a-z0-9-]*", u.netloc) and not u.query and not u.fragment and u.path.startswith("/")
                and all(p not in ("", ".", "..") and "\\" not in p for p in parts),
                "use vault://alias/relative/path for approved external custody")
    else:
        raise ValueError("pointer must use https:// or vault://")
    return value

def normalize(data):
    require(isinstance(data, dict), "object expected")
    require(set(data) <= FIELDS and FIELDS - {"source_id", "tags", "fallback"} <= set(data),
            "metadata-only input; required: title, kind, native_id, namespace, date, pointer, capture")
    for key, length in (("title",180),("kind",20),("native_id",220),("namespace",160),("date",10),("capture",20)):
        clean_text(data[key], key, length)
    require(data["kind"] in KINDS, "unsupported source kind")
    require(datetime.strptime(data["date"], "%Y-%m-%d").date().isoformat() == data["date"], "use YYYY-MM-DD")
    require(data["capture"] in {"approved", "pending"}, "capture must be approved or pending")
    tags = data.get("tags", [])
    require(isinstance(tags, list) and len(tags) <= 20, "tags must be a short list")
    for tag in tags:
        clean_text(tag, "tag", 64)
    fallback = data.get("fallback")
    if fallback is not None:
        require(isinstance(fallback, dict), "fallback must be an object")
        if fallback.get("status") == "pending":
            require(set(fallback) == {"status"}, "a pending fallback must not contain a location")
        else:
            require(data["kind"] == "chat" and fallback.get("status") == "approved"
                    and set(fallback) == {"status", "pointer"}, "approved fallback is for chat uploads only")
            require(isinstance(fallback["pointer"], str) and fallback["pointer"].startswith("vault://"),
                    "approved fallback must be outside the repository")
            pointer(fallback["pointer"])
        require(data["kind"] == "chat", "fallback is reserved for chat uploads")
    out = {**data, "tags": tags, "fallback": fallback}
    out["source_id"] = digest(data["kind"], data["namespace"], data["native_id"])
    require(data.get("source_id", out["source_id"]) == out["source_id"], "source ID does not match native identity")
    if out["capture"] == "approved":
        pointer(data["pointer"])
    else:
        require(data["pointer"] is None and fallback in (None, {"status":"pending"}),
                "hold pending pointers outside the repository")
    return out

def render(data):
    lines = ["---"] + [f"{key}: {json.dumps(val, ensure_ascii=False)}" for key,val in sorted(data.items()) if key != "title"]
    return "\n".join(lines + ["---", "", "# " + data["title"], ""])

def decode(path):
    raw = path.read_bytes().decode("utf-8")
    parts = raw.split("---\n", 2)
    require(len(parts) == 3 and not parts[0], f"{path.name}: missing front matter")
    data = {}
    for line in parts[1].splitlines():
        key, sep, value = line.partition(":")
        require(sep and KEY.fullmatch(key) and key not in data, f"{path.name}: invalid/duplicate key {key}")
        data[key] = json.loads(value.strip())
    body = parts[2].split("\n")
    require("title" not in data and len(body) == 3 and body[1].startswith("# "),
            f"{path.name}: title belongs only in the body heading")
    data["title"] = body[1][2:]
    data = normalize(data)
    require(raw == render(data), f"{path.name}: noncanonical entry or unexpected content")
    return data


def list_records(base):
    catalog = base / "catalog"
    require(not catalog.is_symlink(), "catalog cannot be a symlink")
    for p in sorted(catalog.glob("*.md")):
        if p.name == "README.md":
            continue
        require(not p.is_symlink(), f"symlink source note is not allowed: {p.name}")
        yield p, decode(p)

@contextmanager
def write_lock(base):
    # Keep one stable inode so simultaneous writers coordinate even after a crash.
    # No long-lived process or stale-owner cleanup is required: flock releases on exit.
    lock_path = base / ".catalog.lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield

def publish_note(path, content, *, replace=False):
    # Publish a complete note atomically; a killed process cannot leave half a note.
    # A leftover temporary file is hidden, ignored by Git, and never read as a record.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                     prefix=".catalog-tmp-", dir=path.parent,
                                     delete=False) as scratch:
        tmp = Path(scratch.name)
        try:
            scratch.write(content)
            scratch.flush()
            os.fsync(scratch.fileno())
            if replace:
                require(not path.is_symlink(), "refusing to replace a symlink")
                os.replace(tmp, path)
            else:
                os.link(tmp, path)
        finally:
            if tmp.exists():
                tmp.unlink()

def file_record(base, supplied):
    with write_lock(base):
        return file_record_locked(base, supplied)

def file_record_locked(base, supplied):
    data = normalize(supplied)
    require(data["capture"] == "approved", "pending approval: no catalog entry was written")
    records = list(list_records(base))
    identical = [(p,r) for p,r in records if r["source_id"] == data["source_id"]]
    require(len(identical) <= 1, "duplicate ID exists; reconcile manually")
    if identical:
        p, previous = identical[0]
        if previous == data:
            return "already filed", p, data
        raise ValueError("same native source already filed with different metadata; review or use recovery")
    p = base / "catalog" / (data["source_id"] + ".md")
    p.parent.mkdir(parents=True, exist_ok=True)
    publish_note(p, render(data))
    return "filed",p,data

def lookup(base, source_id):
    require(ID.fullmatch(source_id), "invalid source ID")
    matches = [(p,r) for p,r in list_records(base) if r["source_id"] == source_id]
    require(len(matches) == 1, "source ID not found or duplicated")
    return matches[0]

def revision(record):
    return hashlib.sha256(render(record).encode("utf-8")).hexdigest()

def revise(base, source_id, updates, expected_revision):
    allowed = {"title", "date", "tags"}
    require(isinstance(updates, dict) and updates and set(updates) <= allowed,
            "metadata revision allows only title, date, and tags")
    return update_note(base, source_id, updates, expected_revision)

def set_fallback(base, source_id, fallback, expected_revision):
    return update_note(base, source_id, {"fallback": fallback}, expected_revision, chat_only=True)

def update_note(base, source_id, updates, expected_revision, *, chat_only=False):
    with write_lock(base):
        path, record = lookup(base, source_id)
        require(revision(record) == expected_revision, "stale revision; review the current record")
        require(not chat_only or record["kind"] == "chat", "fallback is reserved for chat uploads")
        new = normalize({**record, **updates})
        status = "unchanged"
        if new != record:
            require(decode(path) == record, "source changed during revision; review again")
            publish_note(path, render(new), replace=True)
            status = "revised"
        return {"status": status, **cite(base, path, new)}

def cite(base, path, record):
    return {"source_id": record["source_id"], "note": path.relative_to(base).as_posix(),
            "title": record["title"], "date": record["date"], "kind": record["kind"],
            "pointer": record["pointer"], "revision": revision(record)}

def recover(base, source_id, observation):
    path, record = lookup(base, source_id)
    require(isinstance(observation, dict), "observation must be an object")
    require(observation.get("attempted_pointer") == record["pointer"], "try the current saved pointer first")
    status = observation.get("status")
    require(status in {"available","missing","offline","denied"}, "invalid observation status")
    result = {"source_id":source_id, "observed":status, "note":path.relative_to(base).as_posix()}
    if status != "missing":
        return {**result, "decision":"keep", "reason":{"available":"saved pointer available",
                "offline":"source not checked while offline", "denied":"respect source access boundary"}[status]}
    if observation.get("authorized_search") is not True:
        decision = {**result, "decision":"keep", "reason":"authorized source search not performed"}
    else:
        candidates = observation.get("candidates", [])
        require(isinstance(candidates, list) and all(isinstance(c, dict) for c in candidates), "invalid candidates")
        candidates = [c for c in candidates if c.get("verified") is True
                      and all(c.get(k) == record[k] for k in ("kind","namespace","native_id"))]
        distinct = {pointer(c.get("pointer")) for c in candidates}
        distinct.discard(record["pointer"])
        if len(distinct) == 1:
            return {**result, "decision":"propose-repair", "from":record["pointer"], "to":distinct.pop()}
        decision = {**result, "decision":"keep", "reason":"ambiguous" if distinct else "no verified exact match"}
    if record["kind"] == "chat" and record["fallback"] and decision["reason"] != "ambiguous":
        decision["fallback"] = record["fallback"]
    return decision

def apply_repair(base, source_id, observation, expected_from, expected_to):
    with write_lock(base):
        return apply_repair_locked(base, source_id, observation, expected_from, expected_to)

def apply_repair_locked(base, source_id, observation, expected_from, expected_to):
    proposal = recover(base, source_id, observation)
    require(proposal["decision"] == "propose-repair" and proposal["from"] == expected_from
            and proposal["to"] == expected_to, "approval does not match the current repair proposal")
    path, record = lookup(base, source_id)
    require(decode(path) == record, "source changed during repair; review again")
    publish_note(path, render({**record, "pointer": expected_to}), replace=True)
    return cite(base, path, {**record, "pointer":expected_to})

def check(base):
    seen, problems = {}, []
    for path, record in list_records(base):
        key = record["source_id"]
        if key in seen:
            problems.append(f"duplicate ID {key}: {seen[key]} and {path.name}")
        seen[key] = path.name
        if path.stem != key:
            problems.append(f"{path.name}: filename must equal {key}")
    for path in base.rglob("*.md"):
        if any(x.startswith(".") or x in {"local","intake","archive","__pycache__"}
               for x in path.relative_to(base).parts) or path.is_symlink():
            continue
        for target in re.findall(r"(?<!!)\[[^\]\n]+\]\(([^)\n]+)\)", path.read_text(encoding="utf-8")):
            if urlsplit(target).scheme or target.startswith("#"):
                continue
            dest = (path.parent / unquote(target.split("#",1)[0])).resolve()
            if not dest.is_relative_to(base) or not dest.exists():
                problems.append(f"broken internal link: {path.relative_to(base)} → {target}")
    return {"sources":len(seen),"problems":problems}

def scope_guard(base, extension, changes):
    require(re.fullmatch(r"[a-z][a-z0-9-]*",extension), "invalid extension name")
    require(isinstance(changes, list) and all(isinstance(p,str) for p in changes), "expected a list of paths")
    prefix = f"extensions/{extension}/"
    denied = [p for p in changes if not p.startswith(prefix) or any(i in ("",".","..") for i in p.split("/"))]
    require(not denied, "extension diff touches outside its boundary: " + ", ".join(denied))
    return {"extension":extension,"allowed":len(changes)}

def git_changes(base, reference):
    def run(*args):
        return subprocess.check_output(["git","-C",str(base),*args])
    git_root = Path(os.fsdecode(run("rev-parse","--show-toplevel")).rstrip("\n")).resolve()
    require(git_root == base, "scope check requires Git rooted at this project")
    commit = os.fsdecode(run("rev-parse","--verify","--end-of-options",reference+"^{commit}")).strip()
    modified = run("diff","--no-renames","--name-only","-z",commit,"--")
    untracked = run("ls-files","--others","--exclude-standard","-z")
    return sorted(set(os.fsdecode(p) for p in (modified+untracked).split(b"\0") if p))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=CORE_VERSION)
    parser.add_argument("--root", type=Path, default=ROOT, help="local workspace root override for tests or a detached catalog")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    p = sub.add_parser("file"); p.add_argument("input")
    p = sub.add_parser("search"); p.add_argument("terms", nargs="+")
    p = sub.add_parser("cite"); p.add_argument("source_id")
    p = sub.add_parser("revise"); p.add_argument("source_id"); p.add_argument("changes")
    p.add_argument("--if-revision", required=True)
    p = sub.add_parser("set-fallback"); p.add_argument("source_id")
    p.add_argument("--if-revision", required=True)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--approve-pointer", metavar="EXTERNAL_VAULT_POINTER")
    mode.add_argument("--pending", action="store_true")
    mode.add_argument("--clear", action="store_true")
    p = sub.add_parser("recover"); p.add_argument("source_id"); p.add_argument("observation")
    p = sub.add_parser("repair"); p.add_argument("source_id"); p.add_argument("observation")
    p.add_argument("--approve-from",required=True); p.add_argument("--approve-to",required=True)
    p = sub.add_parser("check-scope"); p.add_argument("extension")
    p.add_argument("--base",default="HEAD"); p.add_argument("--fixture-paths",type=Path,help="synthetic test mode only")
    a = parser.parse_args()
    base = a.root.resolve()
    require(base.is_dir(), "catalog root must already exist")
    if a.command == "file":
        status,p,r = file_record(base,load_json(a.input))
        result = {"status":status,**cite(base,p,r)}
    elif a.command == "cite":
        result = cite(base,*lookup(base,a.source_id))
    elif a.command == "search":
        terms = [t.casefold() for t in a.terms]
        result = [cite(base,p,r) for p,r in list_records(base)
                  if all(t in " ".join([r["title"],r["date"],r["kind"],r["source_id"],*r["tags"]]).casefold()
                         for t in terms)]
    elif a.command == "revise":
        result = revise(base,a.source_id,load_json(a.changes),a.if_revision)
    elif a.command == "set-fallback":
        fallback = None
        if a.pending:
            fallback = {"status":"pending"}
        elif a.approve_pointer is not None:
            fallback = {"status":"approved", "pointer":a.approve_pointer}
        result = set_fallback(base,a.source_id,fallback,a.if_revision)
    elif a.command == "recover":
        result = recover(base,a.source_id,load_json(a.observation))
    elif a.command == "repair":
        result = apply_repair(base,a.source_id,load_json(a.observation),a.approve_from,a.approve_to)
    elif a.command == "check-scope":
        paths = load_json(a.fixture_paths) if a.fixture_paths else git_changes(base,a.base)
        result = scope_guard(base,a.extension,paths)
    else:
        result = check(base)
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return 1 if a.command == "check" and result["problems"] else 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.CalledProcessError) as e:
        print(str(e),file=sys.stderr)
        sys.exit(2)
