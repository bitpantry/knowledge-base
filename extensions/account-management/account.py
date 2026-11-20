#!/usr/bin/env python3
"""Account Management's sole writer for Person, Interaction and Lead notes."""
import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sys

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
sys.path.insert(0,str(ROOT/"core"))

from catalog import clean_text, load_json, lookup, publish_note, require, write_lock
from concepts import cite_evidence, encode, records as core_records

KINDS={"person":"people", "interaction":"interactions", "lead":"leads"}
SLUG=r"[a-z0-9]+(?:-[a-z0-9]+)*"
STATUS={"open","qualifying","closed"}
KEYS={
    "person":{"id","account","title","notes","source_ids","evidence_ids"},
    "interaction":{"id","account","title","notes","source_ids","evidence_ids","date","person_ids"},
    "lead":{"id","account","title","notes","source_ids","evidence_ids","person_ids","interaction_ids","status"},
}

def text(v,label,limit=200):
    return clean_text(v,label,limit)

def token(v,label,prefix=""):
    text(v,label,100)
    require(re.fullmatch(prefix+SLUG,v),"invalid "+label)
    return v

def exact_date(v):
    text(v,"date",10)
    require(date.fromisoformat(v).isoformat()==v,"date must be YYYY-MM-DD")
    return v

def ids(v,name,pattern):
    require(isinstance(v,list),name+" must be a list")
    for item in v:
        text(item,name,100)
        require(re.fullmatch(pattern,item),"invalid "+name+" entry")
    require(len(set(v))==len(v),"duplicate "+name+" entry")
    return sorted(v)

def normalize(kind,d):
    required={"id","account","title"}|({"date","person_ids"} if kind=="interaction" else set())
    require(isinstance(d,dict) and required<=set(d)<=KEYS[kind],"missing or unexpected "+kind+" fields")
    normalized={**d}
    token(d["id"],"record ID",kind+"-")
    token(d["account"],"account scope")
    text(d["title"],"title")
    notes=d.get("notes")
    if notes is not None:
        text(notes,"notes",800)
    normalized["notes"]=notes
    for field,patt in [("source_ids",r"src-[0-9a-f]{24}"),("evidence_ids",r"ev-[0-9a-f]{24}")]:
        normalized[field]=ids(d.get(field,[]),field,patt)
    if kind in {"interaction","lead"}:
        normalized["person_ids"]=ids(d.get("person_ids",[]),"person IDs","person-"+SLUG)
    if kind=="interaction":
        require(normalized["person_ids"],"link at least one known, in-scope person before recording an interaction")
        exact_date(d["date"])
    elif kind=="lead":
        normalized["interaction_ids"]=ids(d.get("interaction_ids",[]),"interaction IDs","interaction-"+SLUG)
        status=d.get("status","open")
        require(isinstance(status,str) and status in STATUS,"invalid lead status")
        normalized["status"]=status
    return normalized

def folder(kind):
    p=BASE/"records"/KINDS[kind]
    require(not p.is_symlink() and not p.parent.is_symlink(),"unsafe record directory")
    return p

def render(kind,d):
    header={k:v for k,v in d.items() if k not in {"title","notes"}}
    rows=["---","type: "+encode(kind),*[k+": "+encode(v) for k,v in sorted(header.items())],
          "---","","# "+d["title"]]
    if d["notes"] is not None:
        rows += ["",d["notes"]]
    return "\n".join(rows+[""])

def parse(kind,p):
    require(p.is_file() and not p.is_symlink(),"record is not a regular file")
    raw=p.read_text(encoding="utf-8")
    head=raw.split("---\n",2)
    require(len(head)==3 and not head[0],"invalid record metadata")
    pairs=[line.split(": ",1) for line in head[1].splitlines()]
    require(all(len(row)==2 for row in pairs),"invalid record metadata")
    fields={k:json.loads(v) for k,v in pairs}
    require(len(fields)==len(pairs) and fields.pop("type",None)==kind,"invalid or repeated metadata")
    match=re.fullmatch(r"\n# ([^\n]+)(?:\n\n([^\n]+))?\n",head[2])
    require(match,"invalid record body")
    result=normalize(kind,{**fields,"title":match.group(1),"notes":match.group(2)})
    require(p.stem==result["id"] and raw==render(kind,result),"noncanonical or mismatched record")
    return result

def one(kind,rid):
    token(rid,"record ID",kind+"-")
    p=folder(kind)/(rid+".md")
    require(p.exists(),"unknown "+kind+": "+rid)
    return p,parse(kind,p)

def list_kind(kind):
    return [(p,parse(kind,p)) for p in sorted(folder(kind).glob("*.md"))]

def verify(d, kind, evidence=None):
    for pid in d.get("person_ids",[]):
        require(one("person",pid)[1]["account"]==d["account"],"person belongs to another account scope: "+pid)
    for iid in d.get("interaction_ids",[]):
        require(one("interaction",iid)[1]["account"]==d["account"],"interaction belongs to another account scope: "+iid)
    for sid in d["source_ids"]:
        lookup(ROOT,sid)
    if d["evidence_ids"]:
        es=evidence if evidence is not None else core_records(ROOT,"evidence")
        for eid in d["evidence_ids"]:
            require(eid in es,"unknown core evidence: "+eid)
            cite_evidence(ROOT,eid,es[eid])

def digest(kind,d):
    return hashlib.sha256(render(kind,d).encode("utf-8")).hexdigest()

def receipt(kind,p,d,trace=False):
    response={"kind":kind,"note":p.relative_to(ROOT).as_posix(),"revision":digest(kind,d),**d}
    if trace:
        es=core_records(ROOT,"evidence") if d["evidence_ids"] else {}
        verify(d,kind,es)
        response["citations"]={
            "source":[{"source_id":sid,"note":p.relative_to(ROOT).as_posix(),"title":s["title"],"pointer":s["pointer"]}
                      for sid in d["source_ids"] for p,s in [lookup(ROOT,sid)]],
            "evidence":[cite_evidence(ROOT,eid,es[eid]) for eid in d["evidence_ids"]]
        }
    return response

def submit(kind,data):
    with write_lock(ROOT):
        d=normalize(kind,data)
        verify(d,kind)
        p=folder(kind)/(d["id"]+".md")
        status="already filed"
        if p.exists() or p.is_symlink():
            require(parse(kind,p)==d,"ID already exists with different contents")
        else:
            p.parent.mkdir(parents=True,exist_ok=True)
            publish_note(p,render(kind,d))
            status="filed"
        return {"result":status,**receipt(kind,p,d)}

def change_status(rid,status,revision):
    with write_lock(ROOT):
        p,d=one("lead",rid)
        verify(d,"lead")
        require(revision==digest("lead",d),"stale lead revision; read current record")
        if d["status"]==status:
            return {"result":"unchanged",**receipt("lead",p,d)}
        new={**d,"status":status}
        require(parse("lead",p)==d,"lead changed while editing; review and retry")
        publish_note(p,render("lead",new),replace=True)
        return {"result":"status changed",**receipt("lead",p,new)}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="action",required=True)
    a=sub.add_parser("add"); a.add_argument("kind",choices=KINDS); a.add_argument("input")
    a=sub.add_parser("show"); a.add_argument("kind",choices=KINDS); a.add_argument("id")
    a.add_argument("--trace",action="store_true")
    a=sub.add_parser("list"); a.add_argument("kind",choices=KINDS); a.add_argument("--account",required=True)
    a=sub.add_parser("set-lead-status"); a.add_argument("id"); a.add_argument("status",choices=sorted(STATUS))
    a.add_argument("--if-revision",required=True)
    sub.add_parser("check")
    args=p.parse_args()
    if args.action=="add":
        result=submit(args.kind,load_json(args.input))
    elif args.action=="show":
        result=receipt(args.kind,*one(args.kind,args.id),trace=args.trace)
    elif args.action=="list":
        token(args.account,"account scope")
        result=[receipt(args.kind,p,d) for p,d in list_kind(args.kind) if d["account"]==args.account]
    elif args.action=="set-lead-status":
        result=change_status(args.id,args.status,args.if_revision)
    else:
        result={}
        for kind in KINDS:
            found=list_kind(kind)
            for _,d in found:
                verify(d,kind)
            result[KINDS[kind]]=len(found)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__":
    try:
        main()
    except (OSError,ValueError,KeyError,TypeError) as e:
        print(str(e),file=sys.stderr)
        sys.exit(2)
