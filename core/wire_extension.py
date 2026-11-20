#!/usr/bin/env python3
"""Wire one approved drop-in extension to the vault's START-HERE.md."""
import argparse
from pathlib import Path
import re
import sys

from catalog import ROOT, require, publish_note, write_lock

SLUG = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")
HEADING = "## Extensions"
NEXT = "## For a fresh agent"
LINK = re.compile(r"- \[([^\]\n]+)\]\(([^)\n]+)\)")

def extension_title(text):
    title = next((s for s in text.splitlines() if s.strip()), "")
    require(re.fullmatch(r"# [^\[\]\\<>]{1,80}",title) and title == title.rstrip(),
            "EXTENSION.md must start with a short plain Markdown H1 title.")
    return title[2:]


def attached_path(base, slug):
    require(SLUG.fullmatch(slug), "Use the existing lowercase extension folder name.")
    path = base / "extensions" / slug / "EXTENSION.md"
    require(path.is_file() and not any(p.is_symlink() for p in (path, path.parent, path.parent.parent)),
            "No copied extension with a regular EXTENSION.md in this vault.")
    return extension_title(path.read_text(encoding="utf-8")),path.relative_to(base).as_posix()

def revise(base, text, name, destination):
    rows = text.splitlines(keepends=True)
    positions = [i for i,s in enumerate(rows) if s.rstrip("\r\n") == HEADING]
    require(len(positions)<=1,"More than one Extensions section; review the start page before wiring.")
    canonical = f"- [{name}]({destination})\n"
    if not positions:
        split = next((i for i,s in enumerate(rows) if s.rstrip("\r\n")==NEXT),None)
        require(split is not None,"Could not locate the normal start-page insertion point.")
        rows[split:split]=[HEADING+"\n","\n",canonical,"\n"]
        return "".join(rows)
    lower=positions[0]+1
    upper=next((i for i in range(lower,len(rows)) if rows[i].startswith(("## ","# "))),len(rows))
    placeholder = re.compile(r"No extensions are wired by default\.|No extensions are installed\.(?: Add an? [A-Za-z0-9 -]+ extension only when explicitly approved\.)?")
    for i in reversed(range(lower,upper)):
        if placeholder.fullmatch(rows[i].rstrip("\r\n")):
            del rows[i]
            upper-=1
    folder=destination.rsplit("/",1)[0]+"/"
    matches=[]
    for i in range(lower,upper):
        m=LINK.fullmatch(rows[i].rstrip("\r\n"))
        if not m:
            continue
        label,target=m.groups()
        if target.removeprefix("./").startswith(folder):
            matches.append(i)
        elif label.casefold()==name.casefold():
            p=(base/target.split("#",1)[0]).resolve()
            require(not p.is_file(),"The same display name points to a different existing file; review before wiring.")
            matches.append(i)
    if matches:
        rows[matches[0]]=canonical
        for i in reversed(matches[1:]):
            del rows[i]
    else:
        insert=upper
        while insert>lower and not rows[insert-1].strip():
            insert-=1
        if insert==lower:
            rows[insert:insert]=["\n",canonical,"\n"]
        else:
            require(rows[insert-1].endswith("\n"),"Resume after giving the start page a final newline.")
            rows.insert(insert,canonical)
    return "".join(rows)

def wire(base, slug):
    with write_lock(base):
        name,dest=attached_path(base,slug)
        start=base/"START-HERE.md"
        require(start.is_file() and not start.is_symlink(),"Normal start page missing or unsafe.")
        before=start.read_bytes()
        after=revise(base,before.decode("utf-8"),name,dest).encode("utf-8")
        if before!=after:
            require(start.read_bytes()==before,"Start page changed while wiring; review and retry.")
            publish_note(start,after.decode("utf-8"),replace=True)
        return "wired" if before!=after else "already wired"

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("folder",help="copied extension folder name")
    p.add_argument("--root",type=Path,default=ROOT,help="another local vault, for example an isolated test copy")
    a=p.parse_args()
    print(wire(a.root.resolve(),a.folder))

if __name__=="__main__":
    try:
        main()
    except (ValueError,OSError) as e:
        print(str(e),file=sys.stderr)
        sys.exit(2)
