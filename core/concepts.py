#!/usr/bin/env python3
"""Domain-neutral concepts, sourced evidence, and dated user judgments."""
import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sys

from catalog import ROOT, clean_text, load_json, lookup, publish_note, require, write_lock

VERSION = "1.3.0-beta"
FOLDERS = {"concept":"concepts", "evidence":"evidence", "decision":"decisions"}
ID = {
    "concept": re.compile(r"con-[a-z0-9]+(?:-[a-z0-9]+)*\Z"),
    "evidence": re.compile(r"ev-[a-f0-9]{24}\Z"),
    "decision": re.compile(r"dec-[a-f0-9]{24}\Z"),
}
TOKEN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
LOCATOR_TYPES = {"page","section","timestamp","message","sheet","paragraph","line","other"}

def encode(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def keyed(prefix, obj):
    return prefix + hashlib.sha256(encode(obj).encode("utf-8")).hexdigest()[:24]

def exact(d, required, allowed):
    require(isinstance(d,dict) and required <= set(d) <= allowed, "unexpected or missing fields")

def ident(value, kind):
    clean_text(value, kind + " ID", 100)
    require(ID[kind].fullmatch(value), "invalid " + kind + " ID")
    return value

def field(value, name, maximum=200):
    return clean_text(value,name,maximum)

def token(value, name):
    field(value,name,100)
    require(TOKEN.fullmatch(value),name+" must be a lower-kebab-case key")
    return value

def datestring(value):
    field(value,"date",10)
    require(date.fromisoformat(value).isoformat() == value,"use YYYY-MM-DD")
    return value

def labels(r):
    return [r["name"],*r["aliases"]]

def norm(s):
    return " ".join(s.casefold().split())

def concept(d):
    keys={"id","name","aliases","context"}
    exact(d,keys,keys)
    ident(d["id"],"concept")
    field(d["name"],"concept name")
    field(d["context"],"context")
    require(isinstance(d["aliases"],list) and len(d["aliases"]) <= 30,"invalid aliases")
    for alias in d["aliases"]:
        field(alias,"alias")
    require(len({norm(x) for x in labels(d)}) == len(labels(d)), "duplicate alias or name")
    return d

def evidence(d):
    required={"source_id","locator","observed_label","kind"}
    keys=required|{"concept_id","context","candidates","scope","question","value"}
    exact(d,required,keys)
    field(d["source_id"],"source ID",40)
    require(re.fullmatch(r"src-[a-f0-9]{24}", d["source_id"]), "invalid source ID")
    field(d["observed_label"],"observed label")
    loc=d["locator"]
    exact(loc,{"type","value"},{"type","value","speaker","section"})
    require(loc["type"] in LOCATOR_TYPES,"invalid locator type")
    for k,v in loc.items():
        field(v,"locator "+k)
    require(d["kind"] in {"mention","claim"},"evidence kind must be mention or claim")
    d={**d,"concept_id":d.get("concept_id"),"candidates":d.get("candidates",[])}
    require(isinstance(d["candidates"],list),"candidates must be a list")
    for candidate in d["candidates"]:
        ident(candidate,"concept")
    require(len(d["candidates"])==len(set(d["candidates"])),"duplicate candidate")
    d["candidates"]=sorted(d["candidates"])
    if "context" in d:
        field(d["context"], "observed context")
    if d["concept_id"] is not None:
        ident(d["concept_id"],"concept")
        require(not d["candidates"],"unresolved evidence cannot have a resolved link")
    elif not d["candidates"]:
        require("context" in d,"standalone unresolved evidence needs context")
    if d["kind"]=="claim":
        require({"scope","question","value"} <= set(d),"claim requires scope, question and value")
        token(d["scope"],"scope")
        token(d["question"],"question")
        field(d["value"],"short claim",500)
    else:
        require(not {"scope","question","value"} & set(d),"bare mention does not assert a claim")
    return d

def decision(d):
    required={"concept_id","scope","question","date","action"}
    allowed=required|{"claim_id","supersedes","reviewed","actor"}
    exact(d,required,allowed)
    ident(d["concept_id"],"concept")
    token(d["scope"],"scope")
    token(d["question"],"question")
    datestring(d["date"])
    require(d["action"] in {"confirm","skip"},"invalid decision action")
    if d["action"]=="confirm":
        require({"claim_id","reviewed","actor"} <= set(d) and d["actor"]=="user","confirmation requires explicit user action")
        ident(d["claim_id"],"evidence")
        require(isinstance(d["reviewed"],list),"reviewed must be a list")
        for item in d["reviewed"]:
            ident(item,"evidence")
        require(d["reviewed"] == sorted(set(d["reviewed"])) and d["claim_id"] in d["reviewed"],"reviewed set must include the chosen claim")
    else:
        require(d.get("actor")=="user" and set(d)==required|{"actor"},"skip only records explicit user choice")
    if d.get("supersedes"):
        ident(d["supersedes"],"decision")
    return d

NORMALIZE={"concept":concept,"evidence":evidence,"decision":decision}

def safe_dir(base, kind):
    root=base/"knowledge"
    parent=root/FOLDERS[kind]
    require(not root.is_symlink() and not parent.is_symlink(),"knowledge folders cannot be symlinks")
    return parent

def render(record_id, kind, d):
    excluded = {"concept": {"id","name","context"}, "evidence": {"value"}, "decision": set()}[kind]
    meta = {k:v for k,v in d.items() if k not in excluded}
    lines=["---","record_id: "+encode(record_id),"record_type: "+encode(kind)]
    lines += [k+": "+encode(v) for k,v in sorted(meta.items())]
    if kind == "concept":
        content=["# "+d["name"],"",d["context"]]
    elif kind == "evidence":
        content = [d["value"]] if d["kind"] == "claim" else []
    else:
        content=["[Concept](../concepts/"+d["concept_id"]+".md)"]
        if d["action"]=="confirm":
            content += ["","[Chosen claim](../evidence/"+d["claim_id"]+".md)"]
    return "\n".join(lines+["---","",*content,""])

def record_id(kind,d):
    return d["id"] if kind=="concept" else keyed("ev-" if kind=="evidence" else "dec-",d)

def read_record(p, kind, raw):
    parts=raw.split("---\n",2)
    require(len(parts)==3 and parts[0]=="",str(p)+": missing metadata")
    pairs=[line.split(": ",1) for line in parts[1].splitlines()]
    require(all(len(pair)==2 for pair in pairs),str(p)+": invalid metadata")
    values={k:json.loads(v) for k,v in pairs}
    require(len(values)==len(pairs),str(p)+": repeated key")
    rid=values.pop("record_id",None)
    require(values.pop("record_type",None)==kind,str(p)+": wrong type")
    body=parts[2]
    if kind=="concept":
        require(not {"id","name","context"} & values.keys(),str(p)+": duplicate concept metadata")
        lines=body.split("\n")
        require(len(lines)==5 and lines[1].startswith("# "),str(p)+": invalid concept body")
        values.update(id=rid,name=lines[1][2:],context=lines[3])
    elif kind=="evidence" and values.get("kind")=="claim":
        require("value" not in values,str(p)+": claim value belongs only in the body")
        require(body.startswith("\n") and body.endswith("\n"),str(p)+": invalid claim body")
        values["value"]=body[1:-1]
    d=NORMALIZE[kind](values)
    require(rid==p.stem==record_id(kind,d),str(p)+": record ID does not match content")
    require(raw==render(rid,kind,d),str(p)+": invalid/noncanonical record")
    return rid,d


def record_paths(base, kind):
    for p in sorted(safe_dir(base,kind).glob("*.md")):
        require(not p.is_symlink() and p.is_file(),"knowledge record must be a regular file")
        yield p


def records(base, kind):
    result={}
    for p in record_paths(base,kind):
        rid,d=read_record(p,kind,p.read_bytes().decode("utf-8"))
        result[rid]=d
    return result


def put(base, kind, records_for_kind, d):
    rid=record_id(kind,d)
    parent=safe_dir(base,kind)
    path=parent/(rid+".md")
    status="already filed"
    if rid in records_for_kind:
        require(records_for_kind[rid]==d,"record ID already exists with different contents")
    else:
        parent.mkdir(exist_ok=True,parents=True)
        publish_note(path,render(rid,kind,d))
        status="filed"
    return {"status":status,"id":rid,"note":path.relative_to(base).as_posix()}

def assert_references(d, concepts, *, check_ambiguity=True):
    linked=([d["concept_id"]] if d["concept_id"] else d["candidates"])
    require(all(c in concepts for c in linked),"evidence references missing concept")
    if d["concept_id"] and check_ambiguity:
        selected=concepts[d["concept_id"]]
        matches=[cid for cid,c in concepts.items() if norm(d["observed_label"]) in {norm(v) for v in labels(c)}]
        require(len(matches)<2 or ("context" in d and norm(d["context"])==norm(selected["context"])),
                "ambiguous label: record candidates or explicitly match context")

def cite_evidence(base,rid,d):
    p, source=lookup(base,d["source_id"])
    return {"id":rid,"source_id":d["source_id"],"source_title":source["title"],
            "source_note":p.relative_to(base).as_posix(),"source_pointer":source["pointer"],
            "source_date":source["date"],"locator":d["locator"],"kind":d["kind"],
            "concept_id":d["concept_id"],"candidates":d["candidates"],"observed_label":d["observed_label"],
            **{k:d[k] for k in ("context","scope","question","value") if k in d}}

def packet(base, cid, scope, question, *, data=None):
    concepts, evid, ds=data or tuple(records(base,k) for k in FOLDERS)
    require(cid in concepts,"unknown concept")
    token(scope,"scope"); token(question,"question")
    eligible={rid:d for rid,d in evid.items() if d["concept_id"]==cid and d["kind"]=="claim"
              and d["scope"]==scope and d["question"]==question}
    history={rid:d for rid,d in ds.items() if d["concept_id"]==cid and d["scope"]==scope and d["question"]==question}
    confirmations={rid:d for rid,d in history.items() if d["action"]=="confirm"}
    used={d.get("supersedes") for d in confirmations.values()}
    latest=[(rid,d) for rid,d in confirmations.items() if rid not in used]
    require(len(latest)<=1,"multiple active confirmations")
    current_id,current=latest[0] if latest else (None,None)
    require(not current or current["claim_id"] in eligible,"confirmation points to ineligible claim")
    provenance={sid: lookup(base,sid)[1] for sid in sorted({d["source_id"] for d in eligible.values()})}
    rev=keyed("review-",[cid,scope,question,eligible,history,provenance])
    conflicts=[]
    if current:
        chosen=eligible[current["claim_id"]]
        conflicts=[rid for rid,d in eligible.items() if rid not in current["reviewed"] and norm(d["value"])!=norm(chosen["value"])]
    return {"concept_id":cid,"scope":scope,"question":question,"revision":rev,
            "eligible":eligible, "history":history,"confirmation_id":current_id,
            "confirmation":current,"conflicts":conflicts}

def result_packet(base, p, trace):
    current=p["confirmation"]
    receipt={k:p[k] for k in ("concept_id","scope","question","revision","confirmation_id")}
    receipt["status"]="confirmed-with-conflict" if p["conflicts"] else ("confirmed" if current else "open")
    receipt["current"]=None
    if current:
        receipt["current"]={"confirmed_on":current["date"],
                            "claim":cite_evidence(base,current["claim_id"],p["eligible"][current["claim_id"]])}
    if not current or trace or p["conflicts"]:
        receipt["unreviewed_disagreements"]=[cite_evidence(base,r,p["eligible"][r]) for r in p["conflicts"]]
    if trace:
        receipt["claims"]=[cite_evidence(base,r,d) for r,d in sorted(p["eligible"].items())]
        receipt["history"]=p["history"]
    return receipt

def adjudicate(base, a):
    with write_lock(base):
        ds=records(base,"decision")
        p=packet(base,a.concept_id,a.scope,a.question)
        require(p["revision"]==a.if_revision,"stale evidence or decision; review again")
        d={"concept_id":a.concept_id,"scope":a.scope,"question":a.question,
           "date":datestring(a.date),"action":a.command,"actor":"user"}
        if a.command=="confirm":
            require(a.claim_id in p["eligible"],"choose a sourced claim resolved to this concept, scope and question")
            require(a.supersedes==p["confirmation_id"],"explicitly supersede the active confirmation, if any")
            _, chosen_source=lookup(base,p["eligible"][a.claim_id]["source_id"])
            require(a.date>=chosen_source["date"],"confirmation cannot predate its source")
            d.update(claim_id=a.claim_id,reviewed=sorted(p["eligible"]))
            if a.supersedes:
                require(a.date>=p["confirmation"]["date"],"supersession cannot predate active confirmation")
                d["supersedes"]=a.supersedes
        else:
            require(not p["confirmation"],"skip does not clear an existing confirmation")
        item=put(base,"decision",ds,decision(d))
        return {**item,"status":item["status"],"state":"open" if a.command=="skip" else "confirmed"}

def check_knowledge(base):
    cs, es, ds=tuple(records(base,k) for k in FOLDERS)
    for d in es.values():
        assert_references(d,cs,check_ambiguity=False)
        lookup(base,d["source_id"])
    groups = {(d["concept_id"],d["scope"],d["question"]) for d in ds.values()}
    for cid,scope,question in groups:
        p=packet(base,cid,scope,question,data=(cs,es,ds))
        conf={rid:d for rid,d in p["history"].items() if d["action"]=="confirm"}
        for rid,d in conf.items():
            require(d["claim_id"] in p["eligible"] and set(d["reviewed"]) <= set(p["eligible"]),
                    "decision cites claim outside its scope")
            if d.get("supersedes"):
                require(d["supersedes"] in conf and conf[d["supersedes"]]["date"]<=d["date"],
                        "supersedes must point to earlier confirmation in the same scope")
        if conf:
            seen=set()
            rid=p["confirmation_id"]
            while rid:
                require(rid not in seen,"confirmation cycle")
                seen.add(rid)
                rid=conf[rid].get("supersedes")
            require(seen==set(conf),"disconnected confirmation history")
    return {"concepts":len(cs),"evidence":len(es),"decisions":len(ds)}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,default=ROOT)
    p.add_argument("--version",action="version",version=VERSION)
    sub=p.add_subparsers(dest="command",required=True)
    sub.add_parser("check")
    for kind in ("concept","evidence"):
        x=sub.add_parser("add-"+kind); x.add_argument("input")
    x=sub.add_parser("find"); x.add_argument("query"); x.add_argument("--context")
    x=sub.add_parser("cite"); x.add_argument("evidence_id")
    for command in ("review","answer","confirm","skip"):
        x=sub.add_parser(command)
        x.add_argument("concept_id"); x.add_argument("scope"); x.add_argument("question")
        if command in {"confirm","skip"}:
            x.add_argument("--date",required=True); x.add_argument("--if-revision",required=True)
            x.add_argument("--user-explicit",action="store_true",required=True)
        if command=="confirm":
            x.add_argument("--claim-id",required=True); x.add_argument("--supersedes")
        if command=="answer":
            x.add_argument("--trace",action="store_true")
    a=p.parse_args()
    base=a.root.resolve()
    require(base.is_dir(),"root must exist")
    if a.command.startswith("add-"):
        kind=a.command[4:]
        with write_lock(base):
            d=NORMALIZE[kind](load_json(a.input))
            cs=records(base,"concept")
            if kind=="evidence":
                assert_references(d,cs); lookup(base,d["source_id"])
            result=put(base,kind,cs if kind=="concept" else records(base,kind),d)
    elif a.command=="find":
        q=norm(a.query)
        require(q,"nonblank query required")
        cs=records(base,"concept")
        hits={rid:c for rid,c in cs.items() if any(q in norm(x) for x in labels(c))
              and (not a.context or norm(a.context)==norm(c["context"]))}
        evid={rid:d for rid,d in records(base,"evidence").items()
              if (q in norm(d["observed_label"]+" "+d.get("value","")+" "+d.get("context",""))
                  or d["concept_id"] in hits or set(d["candidates"]) & set(hits))
              and (not a.context or d["concept_id"] in hits
                   or norm(a.context)==norm(d.get("context","")) or set(d["candidates"]) & set(hits))}
        result={"concepts":[{"id":rid,**c} for rid,c in hits.items()],"ambiguous":len(hits)>1,
                "evidence":[cite_evidence(base,rid,d) for rid,d in evid.items()]}
    elif a.command=="cite":
        d=records(base,"evidence").get(a.evidence_id)
        require(d is not None,"unknown evidence ID")
        result=cite_evidence(base,a.evidence_id,d)
    elif a.command in {"review","answer"}:
        result=result_packet(base,packet(base,a.concept_id,a.scope,a.question),
                             a.command=="review" or a.trace)
    elif a.command in {"confirm","skip"}:
        result=adjudicate(base,a)
    else:
        result=check_knowledge(base)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0

if __name__=="__main__":
    try:
        sys.exit(main())
    except (ValueError,KeyError,OSError) as e:
        print(str(e),file=sys.stderr)
        sys.exit(2)
