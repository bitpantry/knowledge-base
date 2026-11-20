#!/usr/bin/env python3
"""Account Management model validation and workflows over the core record store."""
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

from catalog import clean_text, lookup, require, write_lock
from concepts import cite_evidence, encode, records as core_records
import model_store

OWNER="account-management"
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
    require(isinstance(d,dict) and required<=set(d)<=KEYS[kind]|{"type"},"missing or unexpected "+kind+" fields")
    require(d.get("type",kind)==kind,"record type does not match model")
    normalized={**d,"type":kind}
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

def models():
    found=model_store.records(ROOT,OWNER)
    for rid,d in found.items():
        kind=d.get("type")
        require(kind in KINDS and rid==d.get("id") and normalize(kind,d)==d,
                "noncanonical Account Management payload: "+rid)
    return found

def one(kind,rid,stored=None):
    token(rid,"record ID",kind+"-")
    d=model_store.read_model(ROOT,rid,OWNER) if stored is None else stored.get(rid)
    require(d is not None and d.get("type")==kind,"unknown "+kind+": "+rid)
    require(normalize(kind,d)==d,"noncanonical Account Management payload: "+rid)
    return model_store.path(ROOT,rid),d

def list_kind(kind,stored=None):
    found=models() if stored is None else stored
    return [(model_store.path(ROOT,rid),d) for rid,d in sorted(found.items()) if d["type"]==kind]

def verify(d, kind, evidence=None, stored=None):
    for pid in d.get("person_ids",[]):
        require(one("person",pid,stored)[1]["account"]==d["account"],"person belongs to another account scope: "+pid)
    for iid in d.get("interaction_ids",[]):
        require(one("interaction",iid,stored)[1]["account"]==d["account"],"interaction belongs to another account scope: "+iid)
    for sid in d["source_ids"]:
        lookup(ROOT,sid)
    if d["evidence_ids"]:
        es=evidence if evidence is not None else core_records(ROOT,"evidence")
        for eid in d["evidence_ids"]:
            require(eid in es,"unknown core evidence: "+eid)
            cite_evidence(ROOT,eid,es[eid])

def digest(kind,d):
    return hashlib.sha256(encode(d).encode("utf-8")).hexdigest()

def cite_source(sid):
    path,source=lookup(ROOT,sid)
    return {"source_id":sid,"note":path.relative_to(ROOT).as_posix(),"title":source["title"],
            "date":source["date"],"pointer":source["pointer"]}

def receipt(kind,p,d,trace=False):
    response={"kind":kind,"note":p.relative_to(ROOT).as_posix(),"revision":digest(kind,d),**d}
    if trace:
        rid=d["id"]
        links=[edge for _,edge in sorted(model_store.relationships(ROOT,d["account"]).items())
               if rid in (edge["from_id"],edge["to_id"])]
        es=core_records(ROOT,"evidence") if d["evidence_ids"] or any(edge["evidence_ids"] for edge in links) else {}
        verify(d,kind,es)
        def citations(record):
            return {"source":[cite_source(sid) for sid in record["source_ids"]],
                    "evidence":[cite_evidence(ROOT,eid,es[eid]) for eid in record["evidence_ids"]]}
        response["citations"]=citations(d)
        response["relationships"]=[
            {**edge,"direction":"both" if edge["from_id"]==edge["to_id"] else
             ("outgoing" if edge["from_id"]==rid else "incoming"),"citations":citations(edge)}
            for edge in links]
        if kind=="person":
            response["interactions"]=[{key:item[key] for key in ("id","date","title")}
                for _,item in list_kind("interaction") if item["account"]==d["account"] and rid in item["person_ids"]]
            response["interactions"].sort(key=lambda item:(item["date"],item["id"]),reverse=True)
    return response

def submit(kind,data):
    with write_lock(ROOT):
        d=normalize(kind,data)
        stored=models()
        verify(d,kind,stored=stored)
        p=model_store.path(ROOT,d["id"])
        status="already filed"
        if d["id"] in stored:
            require(stored[d["id"]]==d,"ID already exists with different contents")
        else:
            model_store.write_model(ROOT,OWNER,d)
            status="filed"
        return {"result":status,**receipt(kind,p,d)}

def change_status(rid,status,revision):
    with write_lock(ROOT):
        stored=models()
        p,d=one("lead",rid,stored)
        verify(d,"lead",stored=stored)
        require(revision==digest("lead",d),"stale lead revision; read current record")
        if d["status"]==status:
            return {"result":"unchanged",**receipt("lead",p,d)}
        new={**d,"status":status}
        require(one("lead",rid)[1]==d,"lead changed while editing; review and retry")
        model_store.write_model(ROOT,OWNER,new,replace=True)
        return {"result":"status changed",**receipt("lead",p,new)}

def load_input(filename):
    def unique(pairs):
        d=dict(pairs)
        require(len(d)==len(pairs),"duplicate input field")
        return d
    return json.loads(Path(filename).read_text(encoding="utf-8"),object_pairs_hook=unique)

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
        result=submit(args.kind,load_input(args.input))
    elif args.action=="show":
        result=receipt(args.kind,*one(args.kind,args.id),trace=args.trace)
    elif args.action=="list":
        token(args.account,"account scope")
        result=[receipt(args.kind,p,d) for p,d in list_kind(args.kind) if d["account"]==args.account]
    elif args.action=="set-lead-status":
        result=change_status(args.id,args.status,args.if_revision)
    else:
        result={}
        stored=models()
        for kind in KINDS:
            found=list_kind(kind,stored)
            for _,d in found:
                verify(d,kind,stored=stored)
            result[KINDS[kind]]=len(found)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__":
    try:
        main()
    except (OSError,ValueError,KeyError,TypeError) as e:
        print(str(e),file=sys.stderr)
        sys.exit(2)
