"""Publish derived, human-facing Markdown within a declared extension namespace."""
from pathlib import Path
import re
from catalog import publish_note, require

OWNER = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _-]{0,79}\.md")
HEADER = "<!-- Generated human view. Not canonical knowledge. -->"


def no_symlink(path):
    require(not path.is_symlink(), "unsafe symlink: " + str(path))
    return path


def declared(base, owner):
    require(OWNER.fullmatch(owner) is not None, "invalid extension owner")
    parent = no_symlink(no_symlink(base / "extensions") / owner)
    p = no_symlink(parent / "VIEWS.md")
    require(p.is_file(), "extension has no VIEWS.md declaration: " + owner)
    names = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            require(line.startswith("- ") and NAME.fullmatch(line[2:]) is not None,
                    "invalid view declaration: " + line)
            names.append(line[2:])
    require(len({name.casefold() for name in names}) == len(names), "duplicate view declaration")
    return names


def output(base, owner, name):
    require(name in declared(base, owner), "undeclared or cross-owner view path")
    root = no_symlink(base / "views")
    parent = no_symlink(root / owner)
    p = no_symlink(parent / name)
    for home, part in ((root, owner), (parent, name)):
        if home.exists():
            require(home.is_dir(), "unsafe view directory")
            require(not any(q.name.casefold() == part.casefold() and q.name != part for q in home.iterdir()),
                    "case-colliding view path")
    return p


def write_generated(p, body):
    content = HEADER + "\n\n" + body.rstrip() + "\n"
    if p.exists():
        require(p.is_file() and p.read_text(encoding="utf-8").startswith(HEADER + "\n"),
                "refusing to overwrite a non-generated document: " + str(p))
        if p.read_text(encoding="utf-8") == content:
            return
    p.parent.mkdir(parents=True, exist_ok=True)
    publish_note(p, content, replace=p.exists())


def index(base):
    root = no_symlink(base / "views")
    index_path = no_symlink(root / "README.md")
    if index_path.exists():
        require(index_path.is_file() and index_path.read_text(encoding="utf-8").startswith(HEADER + "\n"),
                "refusing to overwrite a non-generated view index")
    lines = ["# Generated views", "", "Browse these derived views. Canonical knowledge lives in the catalog and knowledge records.", ""]
    for ext in sorted(no_symlink(base / "extensions").iterdir()):
        if ext.is_symlink() or not ext.is_dir() or not (ext / "VIEWS.md").is_file():
            continue
        for name in declared(base, ext.name):
            p = output(base, ext.name, name)
            if p.is_file() and p.read_text(encoding="utf-8").startswith(HEADER + "\n"):
                lines.append(f"- [{name[:-3]}]({ext.name}/{name.replace(' ', '%20')})")
    return index_path, "\n".join(lines)


def publish(base, owner, name, body):
    """Caller holds catalog lock; no imports or execution of other extensions."""
    p = output(base, owner, name)
    index(base)  # Validate known destinations before the first write.
    write_generated(p, body)
    index_path, index_body = index(base)
    write_generated(index_path, index_body)
    return p
