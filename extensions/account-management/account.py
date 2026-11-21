#!/usr/bin/env python3
"""Account Management model validation and workflows over the core record store."""
import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
sys.path.insert(0,str(ROOT/"core"))

from catalog import clean_text, lookup, require, write_lock
from concepts import cite_evidence, encode, records as core_records
import model_store
import org_chart

OWNER="account-management"
KINDS={"person":"people", "interaction":"interactions", "lead":"leads", "followup":"followups"}
SLUG=r"[a-z0-9]+(?:-[a-z0-9]+)*"
STATUS={"open","qualifying","closed"}
PERSON_WORK = {"organization", "business_unit", "job_title", "work_email", "work_phone", "linkedin_url"}
PERSON_RELATIONSHIP = {"relationship_owner", "relationship_status", "relationship_temperature", "relationship_temperature_rationale", "priority", "strategic_value"}
PERSON_FIELDS = PERSON_WORK | PERSON_RELATIONSHIP | {"archived_on", "opportunity_relevance"}
INTERACTION_KINDS = {"meeting", "call", "email", "transcript", "other"}
FOLLOWUP_STATUS = {"open", "done", "declined"}
KEYS={
    "person":{"id","account","title","notes","source_ids","evidence_ids","aliases"} | PERSON_FIELDS,
    "interaction":{"id","account","title","notes","source_ids","evidence_ids","date","person_ids","interaction_kind","internal_attendees","discussion_points","signals"},
    "lead":{"id","account","title","notes","source_ids","evidence_ids","person_ids","interaction_ids","status"},
    "followup":{"id","account","title","notes","source_ids","evidence_ids","person_ids","interaction_id","owner_name","due","status"},
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
    required={"id","account","title"}|({"date","person_ids"} if kind=="interaction" else {"person_ids"} if kind=="followup" else set())
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
    if kind=="person":
        if PERSON_FIELDS & d.keys():
            require(normalized["source_ids"] or normalized["evidence_ids"],
                    "populated Person profile needs an approved source or evidence reference")
        if "relationship_temperature" in d:
            score=d["relationship_temperature"]
            require(type(score) is int and -3<=score<=3,"relationship temperature must be an integer from -3 to +3")
        require("relationship_temperature_rationale" not in d or "relationship_temperature" in d,
                "relationship temperature rationale requires a score")
        for field in (PERSON_FIELDS - {"relationship_temperature"}) & d.keys():
            text(d[field],field,500 if field=="strategic_value" else 250)
        if "work_email" in d:
            require(re.fullmatch(r"[^\s@<>]+@[^\s@<>.]+(?:\.[^\s@<>.]+)+",d["work_email"]) is not None,
                    "invalid work email")
        if "work_phone" in d:
            require(len(re.findall(r"[0-9]",d["work_phone"]))>=7 and len(d["work_phone"])<=60,
                    "invalid work phone")
        if "linkedin_url" in d:
            target=urlsplit(d["linkedin_url"])
            require(target.scheme=="https" and target.netloc.lower() in {"linkedin.com","www.linkedin.com"}
                    and re.fullmatch(r"/in/[A-Za-z0-9_%.-]+/?",target.path) and not target.query and not target.fragment,
                    "use a clean HTTPS LinkedIn profile URL")
    if kind=="person" and "aliases" in d:
        aliases=d["aliases"]
        require(isinstance(aliases,list) and bool(aliases),"aliases must be a nonempty list")
        for alias in aliases:
            text(alias,"alias",200)
        folded=[alias.casefold() for alias in aliases]
        require(len(set(folded))==len(folded) and d["title"].casefold() not in folded,
                "duplicate alias or display name")
        normalized["aliases"]=sorted(aliases,key=str.casefold)
    if kind=="person" and "archived_on" in d:
        exact_date(d["archived_on"])
    if kind in {"interaction","lead","followup"}:
        normalized["person_ids"]=ids(d.get("person_ids",[]),"person IDs","person-"+SLUG)
    if kind=="interaction":
        require(normalized["person_ids"],"link at least one known, in-scope person before recording an interaction")
        exact_date(d["date"])
        if "interaction_kind" in d:
            require(d["interaction_kind"] in INTERACTION_KINDS,"invalid interaction kind")
        for field in ("internal_attendees","discussion_points","signals"):
            if field in d:
                values=d[field]
                require(isinstance(values,list) and bool(values),"expected a nonempty list: "+field)
                for value in values:
                    text(value,field,500)
    elif kind=="followup":
        require(normalized["person_ids"],"follow-up needs an in-scope person")
        require(d.get("interaction_id") or normalized["source_ids"] or normalized["evidence_ids"],
                "follow-up needs an interaction, source or evidence")
        if "interaction_id" in d:
            token(d["interaction_id"],"interaction ID","interaction-")
        if "due" in d:
            exact_date(d["due"])
        if "owner_name" in d:
            text(d["owner_name"],"owner")
        status=d.get("status","open")
        require(status in FOLLOWUP_STATUS,"invalid follow-up status")
        normalized["status"]=status
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
        person=one("person",pid,stored)[1]
        require(person["account"]==d["account"],"person belongs to another account scope: "+pid)
    for iid in d.get("interaction_ids",[]):
        require(one("interaction",iid,stored)[1]["account"]==d["account"],"interaction belongs to another account scope: "+iid)
    if kind=="followup" and "interaction_id" in d:
        meeting=one("interaction",d["interaction_id"],stored)[1]
        require(meeting["account"]==d["account"],"interaction belongs to another account scope")
        require(meeting["source_ids"] or meeting["evidence_ids"] or d["source_ids"] or d["evidence_ids"],
                "follow-up needs a sourced interaction or an independent source")
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
        if kind=="followup" and "interaction_id" in d:
            interaction_path,interaction=one("interaction",d["interaction_id"])
            response["source_interaction"]=receipt("interaction",interaction_path,interaction,trace=True)
        if kind=="person":
            response["followups"]=[{key:item[key] for key in ("id","title","status","due","owner_name") if key in item}
                for _,item in list_kind("followup") if item["account"]==d["account"] and rid in item["person_ids"]]
            response["interactions"]=[{key:item[key] for key in ("id","date","title")}
                for _,item in list_kind("interaction") if item["account"]==d["account"] and rid in item["person_ids"]]
            response["interactions"].sort(key=lambda item:(item["date"],item["id"]),reverse=True)
            if response["interactions"]:
                response["last_recorded_contact"]=response["interactions"][0]["date"]
            scoped={pid:p for _,p in list_kind("person") if p["account"]==d["account"] for pid in [p["id"]]}
            grouped,conflicts,parents,cycles=org_chart.reporting(ROOT,d["account"],scoped)
            if rid in conflicts or rid in cycles:
                response["reporting_exception"]={"reason":"conflicting manager claims" if rid in conflicts else "circular manager claims",
                    "recorded_managers":[{"id":mid,"title":scoped[mid]["title"]} for mid in sorted(grouped[rid])]}
            elif rid in parents:
                response["manager"]={"id":parents[rid],"title":scoped[parents[rid]]["title"]}
            reports=[{"id":pid,"title":scoped[pid]["title"]} for pid in sorted(parents) if parents[pid]==rid and pid not in cycles]
            if reports: response["direct_reports"]=reports
    return response

def refresh_chart(initialize=False):
    stored=models()
    people={rid:d for rid,d in stored.items() if d["type"]=="person"}
    interactions=[d for d in stored.values() if d["type"]=="interaction"]
    followups=[d for d in stored.values() if d["type"]=="followup"]
    stamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    return org_chart.refresh(ROOT,people,interactions,followups,stamp,initialize=initialize)

def refresh_after_write(result):
    # The canonical write has already succeeded. Do not hide that result when
    # the optional, derived view needs manual recovery.
    try:
        p=refresh_chart()
        if p is not None:
            result["view"]=p.relative_to(ROOT).as_posix()
    except (OSError,ValueError,KeyError) as exc:
        result["view_warning"]="Canonical write complete; People views refresh failed: "+str(exc)
    return result

def link_reporting(account,report,manager,evidence_ids,source_ids):
    with write_lock(ROOT):
        require(report!=manager,"a person cannot report to themself")
        for rid in (report,manager):
            require(one("person",rid)[1]["account"]==account,"person belongs to another account scope")
        require(evidence_ids or source_ids,"a reporting claim needs evidence or a source")
        known=model_store.labels(ROOT)
        if "reports-to" not in known:
            model_store.relation_data(ROOT,account,report,"reports-to",manager,evidence_ids,source_ids,{**known,"reports-to":None})
            model_store.define_label(ROOT,"reports-to","A person's direct organizational reporting line to their manager.","Direct report to manager")
        p=model_store.write_relationship(ROOT,account,report,"reports-to",manager,evidence_ids=evidence_ids,source_ids=source_ids)
        _,result,_=model_store.parse(p)
        return refresh_after_write(result)

def submit(kind,data):
    with write_lock(ROOT):
        if kind=="person" and isinstance(data,dict):
            verify_new_person_fields(data)
        d=normalize(kind,data)
        stored=models()
        verify(d,kind,stored=stored)
        p=model_store.path(ROOT,d["id"])
        status="already filed"
        if kind=="followup" and d["status"]=="open":
            require(any("archived_on" not in stored[pid] for pid in d["person_ids"]), "open follow-up needs an active person")
        if d["id"] in stored:
            require(stored[d["id"]]==d,"ID already exists with different contents")
        else:
            model_store.write_model(ROOT,OWNER,d)
            status="filed"
        result={"result":status,**receipt(kind,p,d)}
        return refresh_after_write(result) if kind in {"person","interaction","followup"} else result

def change_status(rid,status,revision,kind="lead"):
    with write_lock(ROOT):
        stored=models()
        p,d=one(kind,rid,stored)
        verify(d,kind,stored=stored)
        require(revision==digest(kind,d),"stale "+kind+" revision; read current record")
        if d["status"]==status:
            return {"result":"unchanged",**receipt(kind,p,d)}
        if kind=="followup" and status=="open":
            require(any("archived_on" not in stored[pid] for pid in d["person_ids"]), "open follow-up needs an active person")
        new={**d,"status":status}
        require(one(kind,rid)[1]==d,kind+" changed while editing; review and retry")
        model_store.write_model(ROOT,OWNER,new,replace=True)
        result={"result":"status changed",**receipt(kind,p,new)}
        return refresh_after_write(result) if kind=="followup" else result

def add_alias(rid,alias,revision,evidence_id):
    with write_lock(ROOT):
        p,d=one("person",rid)
        require(revision==digest("person",d),"stale person revision; read current record")
        old=d.get("aliases",[])
        match=next((name for name in old if name.casefold()==alias.casefold()),None)
        new=normalize("person",{**d,"aliases":old if match else [*old,alias],
                               "evidence_ids":sorted(set(d["evidence_ids"]+[evidence_id]))})
        verify(new,"person")
        if new==d:
            return refresh_after_write({"result":"unchanged",**receipt("person",p,d)})
        model_store.write_model(ROOT,OWNER,new,replace=True)
        return refresh_after_write({"result":"alias recorded",**receipt("person",p,new)})

def verify_new_person_fields(changes):
    require("relationship_status" not in changes or changes["relationship_status"] is None,
            "relationship_status is legacy; use relationship_temperature and optional rationale")
    if "priority" in changes and changes["priority"] is not None:
        require(type(changes["priority"]) is str and changes["priority"] in {"H","M","L"},
                "priority must be H, M, or L")


def revise_person(rid,patch,revision):
    with write_lock(ROOT):
        p,d=one("person",rid)
        require(revision==digest("person",d),"stale person revision; read current record")
        mutable=PERSON_FIELDS | {"title","notes"}
        proof={"source_ids","evidence_ids"}
        require(isinstance(patch,dict) and patch.keys() <= mutable|proof
                and patch.keys() & mutable,"invalid person profile patch")
        verify_new_person_fields(patch)
        new={**d}
        for key in patch.keys() & mutable:
            if patch[key] is None and key in PERSON_FIELDS:
                new.pop(key,None)
            else:
                new[key]=patch[key]
        for key,pattern in (("source_ids",r"src-[0-9a-f]{24}"),("evidence_ids",r"ev-[0-9a-f]{24}")):
            new[key]=sorted(set(d[key]+ids(patch.get(key,[]),key,pattern)))
        require(patch.get("source_ids") or patch.get("evidence_ids"),
                "profile revisions require a source or evidence reference for the reviewed change")
        new=normalize("person",new)
        if "archived_on" in patch and patch["archived_on"] is not None:
            stored=models()
            for _, item in list_kind("followup",stored):
                if item["status"]=="open" and rid in item["person_ids"]:
                    require(any(pid!=rid and "archived_on" not in stored[pid] for pid in item["person_ids"]),
                            "resolve or reassign the open follow-up before archiving its last active person")
        verify(new,"person")
        result="unchanged"
        if new!=d:
            model_store.write_model(ROOT,OWNER,new,replace=True)
            result="profile revised"
        return refresh_after_write({"result":result,**receipt("person",p,new)})


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
    a=sub.add_parser("set-followup-status"); a.add_argument("id"); a.add_argument("status",choices=sorted(FOLLOWUP_STATUS))
    a.add_argument("--if-revision",required=True)
    a=sub.add_parser("add-person-alias"); a.add_argument("id"); a.add_argument("alias")
    a.add_argument("--if-revision",required=True); a.add_argument("--evidence-id",required=True)
    a=sub.add_parser("revise-person"); a.add_argument("id"); a.add_argument("input")
    a.add_argument("--if-revision",required=True)
    a=sub.add_parser("link-reporting")
    for field in ("account","report","manager"):
        a.add_argument(field)
    a.add_argument("--evidence-id",action="append",default=[])
    a.add_argument("--source-id",action="append",default=[])
    sub.add_parser("rebuild-org-chart")
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
    elif args.action=="set-followup-status":
        result=change_status(args.id,args.status,args.if_revision,"followup")
    elif args.action=="add-person-alias":
        result=add_alias(args.id,args.alias,args.if_revision,args.evidence_id)
    elif args.action=="revise-person":
        result=revise_person(args.id,load_input(args.input),args.if_revision)
    elif args.action=="link-reporting":
        result=link_reporting(args.account,args.report,args.manager,args.evidence_id,args.source_id)
    elif args.action=="rebuild-org-chart":
        with write_lock(ROOT):
            result={"view":refresh_chart(initialize=True).relative_to(ROOT).as_posix()}
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
