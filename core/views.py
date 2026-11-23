"""Publish derived, human-facing views within a declared extension namespace."""
import re
import json
from catalog import publish_note, require

OWNER = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _-]{0,79}\.(?:md|canvas)")
FOLDER = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*/")
MEMBER = re.compile(r"[a-z0-9][a-z0-9_-]{0,119}\.md")
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
            require(line.startswith("- ") and (NAME.fullmatch(line[2:]) or FOLDER.fullmatch(line[2:])),
                    "invalid view declaration: " + line)
            names.append(line[2:])
    require(len({name.casefold() for name in names}) == len(names), "duplicate view declaration")
    return names


def safe_child(parent, part):
    path = no_symlink(parent / part)
    if parent.exists():
        require(parent.is_dir(), "unsafe view directory")
        require(not any(q.name.casefold() == part.casefold() and q.name != part
                        for q in parent.iterdir()), "case-colliding view path")
    return path


def output(base, owner, name):
    require(name in declared(base, owner) and NAME.fullmatch(name),
            "undeclared or cross-owner view path")
    return safe_child(safe_child(no_symlink(base / "views"), owner), name)


def marked(content, header=HEADER):
    """Recognize exact boundary markers, including pre-footer generated output."""
    newline = b"\n" if isinstance(content, bytes) else "\n"
    if isinstance(content, bytes):
        header = header.encode("utf-8")
    return content.startswith(header + newline) or content.rstrip().endswith(newline + header)


def write_generated(p, body, *, header=HEADER):
    # Standalone generated comments follow human-facing content by default.
    lines = body.rstrip().splitlines()
    comments = [line for line in lines if re.fullmatch(r"<!--.*-->", line)]
    content = "\n".join(line for line in lines if not re.fullmatch(r"<!--.*-->", line)).strip("\n")
    content += ("\n\n" + "\n".join(comments) if comments else "") + "\n\n" + header + "\n"
    if p.exists():
        require(p.is_file(), "unsafe view file: " + str(p))
        existing = p.read_text(encoding="utf-8")
        require(marked(existing, header),
                "refusing to overwrite a non-generated document: " + str(p))
        if existing == content:
            return
    p.parent.mkdir(parents=True, exist_ok=True)
    publish_note(p, content, replace=p.exists())


def publish_collection(base, owner, folder, bodies):
    """Publish a complete one-level collection; caller holds the catalog lock."""
    require(FOLDER.fullmatch(folder + "/") and folder + "/" in declared(base, owner),
            "undeclared or cross-owner view collection")
    require(all(MEMBER.fullmatch(name) and isinstance(body, str)
                for name, body in bodies.items()), "invalid view collection member")
    root = no_symlink(base / "views")
    parent = safe_child(safe_child(root, owner), folder)
    header = f"<!-- Generated human view: {owner}/{folder}. Not canonical knowledge. -->"
    owned = set()
    if parent.exists():
        require(parent.is_dir(), "unsafe view collection directory")
        desired = {name.casefold(): name for name in bodies}
        for p in parent.iterdir():
            if p.name.casefold() in desired:
                require(p.name == desired[p.name.casefold()], "case-colliding view path")
                require(not p.is_symlink() and p.is_file(), "unsafe view collection member")
                require(marked(p.read_text(encoding="utf-8"), header),
                        "refusing to overwrite a non-generated document: " + str(p))
            if not p.is_symlink() and p.is_file() and MEMBER.fullmatch(p.name):
                if marked(p.read_bytes(), header):
                    owned.add(p.name)
    # Validate the entire batch before changing any member. Each replacement is atomic.
    for name, body in sorted(bodies.items()):
        write_generated(no_symlink(parent / name), body, header=header)
    for name in sorted(owned - bodies.keys()):
        no_symlink(parent / name).unlink()
    return {name: parent / name for name in bodies}


def index(base):
    root = no_symlink(base / "views")
    index_path = no_symlink(root / "README.md")
    if index_path.exists():
        require(index_path.is_file() and marked(index_path.read_text(encoding="utf-8")),
                "refusing to overwrite a non-generated view index")
    lines = ["# Generated views", "", "Browse these derived views. Canonical knowledge lives in the catalog and knowledge records.", ""]
    for ext in sorted(no_symlink(base / "extensions").iterdir()):
        if ext.is_symlink() or not ext.is_dir() or not (ext / "VIEWS.md").is_file():
            continue
        for name in declared(base, ext.name):
            if name.endswith("/"):
                continue  # The extension guides humans through its flat entry view.
            p = output(base, ext.name, name)
            if name.endswith(".canvas"):
                if p.is_file():
                    try:
                        generated = json.loads(p.read_text(encoding="utf-8"))
                    except (ValueError, UnicodeError):
                        continue
                    if isinstance(generated, dict) and generated.get("generatedBy") == ext.name + "/" + name:
                        lines.append(f"- [{name[:-7]}]({ext.name}/{name.replace(' ', '%20')})")
                continue
            if p.is_file() and marked(p.read_text(encoding="utf-8")):
                lines.append(f"- [{name[:-3]}]({ext.name}/{name.replace(' ', '%20')})")
    return index_path, "\n".join(lines)


def publish(base, owner, name, body):
    """Caller holds catalog lock; no imports or execution of other extensions."""
    require(name.endswith(".md"), "use publish_canvas for Canvas outputs")
    p = output(base, owner, name)
    index(base)  # Validate known destinations before the first write.
    write_generated(p, body)
    index_path, index_body = index(base)
    write_generated(index_path, index_body)
    return p


def publish_canvas(base, owner, name, document):
    """Publish an explicitly declared experimental JSON Canvas under the same lock."""
    require(name.endswith(".canvas"), "invalid Canvas name")
    p = output(base, owner, name)
    marker = owner + "/" + name
    if p.exists():
        require(p.is_file(), "unsafe Canvas file")
        try:
            previous = json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError):
            raise ValueError("refusing to overwrite a non-generated Canvas")
        require(isinstance(previous, dict) and previous.get("generatedBy") == marker,
                "refusing to overwrite a non-generated Canvas")
    require(isinstance(document, dict) and set(document) == {"nodes", "edges"}, "invalid Canvas document")
    index(base)
    content = json.dumps(dict(document, generatedBy=marker), ensure_ascii=False, indent=2) + "\n"
    if not p.exists() or p.read_text(encoding="utf-8") != content:
        p.parent.mkdir(parents=True, exist_ok=True)
        publish_note(p, content, replace=p.exists())
    index_path, index_body = index(base)
    write_generated(index_path, index_body)
    return p
