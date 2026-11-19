#!/usr/bin/env python3
"""A small portable lending workflow using only local Markdown."""
from argparse import ArgumentParser
from contextlib import nullcontext, contextmanager
import fcntl
from datetime import date
import json
import os
from pathlib import Path
import re
import sys
from tempfile import NamedTemporaryFile

RECORDS = Path(__file__).resolve().parent / "records"
ID = re.compile(r"loan-[a-z0-9]+(?:-[a-z0-9]+)*\Z")

def need(condition, problem):
    if not condition:
        raise ValueError(problem)

def clean(value):
    need(value and value == value.strip() and len(value) <= 120
         and not any(ord(ch) < 32 or ord(ch) == 127 for ch in value), "Use short single-line text.")
    return value

def iso(value):
    need(date.fromisoformat(value).isoformat() == value, "Use YYYY-MM-DD.")
    return value

def render(d):
    fields = ("id","tool","borrower","checked_out","returned")
    status = "Returned" if d["returned"] else "Open"
    meta = [k+": "+json.dumps(d[k],ensure_ascii=False) for k in fields]
    return "\n".join(["---",*meta,"---","", "# "+d["tool"], "",
                      "Borrower: "+d["borrower"], "Status: "+status,
                      "Checked out: "+d["checked_out"],
                      "Returned: "+(d["returned"] or "Not yet"),""])

def record_path(rid):
    need(ID.fullmatch(rid) and len(rid)<=80, "Use loan-id in lowercase kebab case.")
    need(not RECORDS.is_symlink(), "Records directory cannot be a symlink.")
    p = RECORDS/(rid+".md")
    need(not p.is_symlink(), "Record cannot be a symlink.")
    return p

def read(p):
    need(record_path(p.stem)==p,"Unexpected loan path.")
    s=p.read_text(encoding="utf-8")
    parts=s.split("---\n",2)
    need(len(parts)==3 and not parts[0],"Missing loan metadata.")
    d=dict((line.split(": ",1)[0],json.loads(line.split(": ",1)[1]))
           for line in parts[1].splitlines())
    need(set(d)=={"id","tool","borrower","checked_out","returned"} and d["id"]==p.stem,
         "Invalid loan metadata or filename.")
    clean(d["tool"]); clean(d["borrower"]); iso(d["checked_out"])
    if d["returned"] is not None:
        need(iso(d["returned"]) >= d["checked_out"],"Return cannot predate checkout.")
    need(s==render(d),"Noncanonical loan record.")
    return d

def save(p, d, update=False):
    p.parent.mkdir(parents=True,exist_ok=True)
    with NamedTemporaryFile("w",encoding="utf-8",dir=p.parent,prefix=".loan-",delete=False) as f:
        tmp=Path(f.name)
        try:
            f.write(render(d)); f.flush()
            if update:
                os.replace(tmp,p)
            else:
                os.link(tmp,p)
        finally:
            if tmp.exists():
                tmp.unlink()

@contextmanager
def writer_lock():
    need(not RECORDS.is_symlink(), "Records directory cannot be a symlink.")
    RECORDS.mkdir(parents=True,exist_ok=True)
    fd=os.open(RECORDS/".loan-writer.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd,"r+") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        yield

def main():
    ap=ArgumentParser(description=__doc__)
    sub=ap.add_subparsers(dest="cmd",required=True)
    new=sub.add_parser("checkout")
    for f in ("id","tool","borrower","date"):
        new.add_argument(f)
    ret=sub.add_parser("return"); ret.add_argument("id"); ret.add_argument("date")
    listing=sub.add_parser("list"); listing.add_argument("--open",action="store_true")
    sub.add_parser("check")
    a=ap.parse_args()
    with writer_lock() if a.cmd in {"checkout","return"} else nullcontext():
        if a.cmd=="checkout":
            p=record_path(a.id)
            need(not p.exists(),"Loan ID already exists.")
            d={"id":a.id,"tool":clean(a.tool),"borrower":clean(a.borrower),
               "checked_out":iso(a.date),"returned":None}
            save(p,d)
            out={"status":"checked out","loan":d}
        elif a.cmd=="return":
            p=record_path(a.id); d=read(p)
            need(not d["returned"],"Loan is already closed.")
            need(iso(a.date)>=d["checked_out"],"Return cannot predate checkout.")
            d["returned"]=a.date
            save(p,d,update=True); out={"status":"returned","loan":d}
        else:
            need(not RECORDS.is_symlink(), "Records directory cannot be a symlink.")
            ds=[read(p) for p in sorted(RECORDS.glob("*.md")) if p.name!="README.md"]
            out={"validated":len(ds)} if a.cmd=="check" else [d for d in ds if not a.open or not d["returned"]]
    print(json.dumps(out,indent=2,ensure_ascii=False))

if __name__=="__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, IndexError, TypeError) as e:
        print(str(e),file=sys.stderr)
        sys.exit(2)
