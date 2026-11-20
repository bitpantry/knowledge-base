#!/usr/bin/env python3
"""Core-owned Markdown storage for typed model records and sourced relationships."""
import argparse
import json
from pathlib import Path
import re
import sys

from catalog import ROOT, clean_text, decode, publish_note, require, write_lock
from concepts import ID, encode, keyed, read_record

TOKEN = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")
KEY = re.compile(r"[a-z][a-z0-9_]*\Z")
REL = re.compile(r"rel-[a-f0-9]{24}\Z")
SOURCE = re.compile(r"src-[a-f0-9]{24}\Z")
MODEL_KEYS = {"id","type","account","title","notes"}
LABELS = "relationship-labels.md"
LABEL_HEADER = "# Relationship labels\n"
LABEL_PATTERN = re.compile(r"\n## ([^\n]+)\n\nDefinition: ([^\n]+)\nDirection: ([^\n]+)\n")


def token(value, label):
    clean_text(value,label,120)
    require(TOKEN.fullmatch(value),"invalid "+label)
    return value


def folder(base,*parts):
    p = base/"knowledge"
    for part in (None,*parts):
        if part is not None:
            p /= part
        require(not p.is_symlink() and (not p.exists() or p.is_dir()),"unsafe knowledge directory")
    return p


def path(base,rid):
    token(rid,"model record ID")
    require(not any(rid.startswith(prefix) for prefix in ("src-","con-","ev-","dec-","int-","rel-")),
            "model record ID uses a reserved core prefix")
    return folder(base,"records")/(rid+".md")


def canonical_fields(d):
    require(isinstance(d,dict) and all(KEY.fullmatch(k) for k in d),"invalid model metadata")
    for v in d.values():
        require(v is None or type(v) in {str,int,bool,list},"metadata requires scalar fields or lists")
        for item in (v if isinstance(v,list) else [v]):
            require(item is None or type(item) in {str,int,bool},"metadata lists must be flat")
            if isinstance(item,str):
                clean_text(item,"metadata",2000)
    return d


def front(data, body):
    return "\n".join(["---",*[k+": "+encode(v) for k,v in sorted(data.items())],"---","",*body,""])


def parse(p):
    require(p.is_file() and not p.is_symlink(),"record missing or not regular: "+p.name)
    raw=p.read_bytes().decode("utf-8")
    parts=raw.split("---\n",2)
    require(len(parts)==3 and not parts[0],"invalid record front matter")
    pairs=[s.split(": ",1) for s in parts[1].splitlines()]
    require(all(len(v)==2 for v in pairs),"invalid record header")
    head={k:json.loads(v) for k,v in pairs}
    require(len(head)==len(pairs),"duplicate record field")
    return raw,head,parts[2]


def render_model(owner,d):
    token(owner,"model owner")
    require(MODEL_KEYS <= d.keys() and "owner" not in d,"missing or unexpected model fields")
    kind=token(d["type"],"model type")
    require(token(d["id"],"model ID").startswith(kind+"-"),"model ID must start with the type")
    token(d["account"],"model scope")
    title=clean_text(d["title"],"model title",200)
    notes=d["notes"]
    if notes is not None:
        clean_text(notes,"model notes",2000)
    return front({"owner":owner,**canonical_fields({k:v for k,v in d.items() if k not in {"title","notes"}})},
                 ["# "+title]+(["",notes] if notes is not None else []))


def model_entry(base,p):
    raw,head,body=parse(p)
    owner=head.pop("owner",None)
    match=re.fullmatch(r"\n# ([^\n]+)(?:\n\n([^\n]+))?\n",body)
    require(match and not {"title","notes"} & head.keys(),"invalid model body")
    d={**head,"title":match[1],"notes":match[2]}
    require(path(base,d["id"])==p and render_model(owner,d)==raw,"noncanonical or mismatched model record")
    return owner,d


def read_model(base,rid,owner):
    actual,d=model_entry(base,path(base,rid))
    require(actual==owner,"model belongs to a different extension")
    return d


def records(base,owner):
    result={}
    for p in sorted(folder(base,"records").glob("*.md")):
        current,d=model_entry(base,p)
        if current==owner:
            result[d["id"]]=d
    return result


def write_model(base,owner,record,replace=False):
    """Persist through the core. Caller validates domain semantics and holds the vault lock."""
    p=path(base,record["id"])
    raw=render_model(owner,record)
    if p.exists() or p.is_symlink():
        existing=read_model(base,record["id"],owner)
        if existing==record:
            return p
        require(replace,"ID already exists with different contents")
        require(existing["type"]==record["type"] and existing["account"]==record["account"],
                "model type and scope cannot be reassigned")
    else:
        require(not replace,"cannot replace a missing model record")
    p.parent.mkdir(exist_ok=True,parents=True)
    publish_note(p,raw,replace=replace)
    return p


def references(values, pattern, label):
    require(isinstance(values,(tuple,list)),label+" must be a list")
    for item in values:
        clean_text(item,label,100)
        require(pattern.fullmatch(item),"invalid "+label)
    require(len(set(values))==len(values),"duplicate "+label)
    return sorted(values)


def evidence(base,rid):
    require(ID["evidence"].fullmatch(rid),"invalid evidence reference")
    p=folder(base,"evidence")/(rid+".md")
    require(p.is_file() and not p.is_symlink(),"unknown core evidence: "+rid)
    return read_record(p,"evidence",p.read_bytes().decode("utf-8"))[1]


def source_exists(base,rid):
    p=base/"catalog"/(rid+".md")
    require(SOURCE.fullmatch(rid) and p.is_file() and not p.is_symlink() and not p.parent.is_symlink(),
            "unknown core source: "+rid)
    require(decode(p)["source_id"]==rid,"source ID mismatch")


def label_path(base):
    p=folder(base)/LABELS
    require(not p.is_symlink() and (not p.exists() or p.is_file()),"unsafe relationship labels document")
    return p


def label_data(label,definition,direction):
    token(label,"relationship label")
    return {"definition":clean_text(definition,"label definition",240),
            "direction":clean_text(direction,"label direction",160)}


def label_document(rows):
    return LABEL_HEADER+"".join("\n## "+label+"\n\nDefinition: "+d["definition"]+
                               "\nDirection: "+d["direction"]+"\n"
                               for label,d in sorted(rows.items()))


def labels(base):
    p=label_path(base)
    if not p.exists():
        return {}
    raw=p.read_bytes().decode("utf-8")
    require(raw.startswith(LABEL_HEADER),"invalid relationship labels document")
    rows={}
    for label,definition,direction in LABEL_PATTERN.findall(raw[len(LABEL_HEADER):]):
        require(label not in rows,"duplicate relationship label: "+label)
        rows[label]=label_data(label,definition,direction)
    require(raw==label_document(rows),"invalid relationship labels document")
    return rows


def initialize_labels(base):
    p=label_path(base)
    if not p.exists():
        p.parent.mkdir(exist_ok=True,parents=True)
        publish_note(p,LABEL_HEADER)
    return p


def define_label(base,label,definition,direction):
    """Add a vault-local label. Caller holds the shared vault lock."""
    row=label_data(label,definition,direction)
    rows=labels(base)
    if label in rows:
        require(rows[label]==row,"relationship label already has a different meaning: "+label)
        return {"label":label,**row}
    p=label_path(base)
    p.parent.mkdir(exist_ok=True,parents=True)
    rows[label]=row
    publish_note(p,label_document(rows),replace=p.exists())
    return {"label":label,**row}


def relation_data(base,account,from_id,predicate,to_id,evidence_ids,source_ids,known_labels=None):
    token(account,"relationship scope")
    token(predicate,"relationship predicate")
    require(predicate in (labels(base) if known_labels is None else known_labels),
            "undefined relationship label; check labels and define it if needed: "+predicate)
    es=references(evidence_ids,ID["evidence"],"relationship evidence ID")
    ss=references(source_ids,SOURCE,"relationship source ID")
    require(es or ss,"a relationship needs source or evidence provenance")
    for sid in ss:
        source_exists(base,sid)
    for eid in es:
        item=evidence(base,eid)
        source_exists(base,item["source_id"])
    for rid in (from_id,to_id):
        token(rid,"relationship endpoint")
        if ID["evidence"].fullmatch(rid):
            evidence(base,rid)
            require(rid in es,"an evidence endpoint must also be cited")
        elif SOURCE.fullmatch(rid):
            require(rid in ss,"a source endpoint must also be cited")
        elif ID["concept"].fullmatch(rid):
            p=folder(base,"concepts")/(rid+".md")
            require(p.is_file() and not p.is_symlink(),"unknown core concept: "+rid)
            read_record(p,"concept",p.read_bytes().decode("utf-8"))
        else:
            _, d=model_entry(base,path(base,rid))
            require(d["account"]==account,"relationship crosses account scope")
    data={"account":account,"from_id":from_id,"predicate":predicate,"to_id":to_id,
          "evidence_ids":es,"source_ids":ss}
    return {"id":keyed("rel-",data),**data}


def write_relationship(base,account,source_id,relation,target_id,*,evidence_ids=(),source_ids=()):
    """Write an explicit edge, never infer identities or predicates."""
    d=relation_data(base,account,source_id,relation,target_id,evidence_ids,source_ids)
    parent=folder(base,"relationships",account)
    p=parent/(d["id"]+".md")
    raw=front(d,[])
    if p.exists() or p.is_symlink():
        require(not p.is_symlink() and p.is_file() and p.read_bytes().decode()==raw,"existing relationship differs")
    else:
        parent.mkdir(exist_ok=True,parents=True)
        publish_note(p,raw)
    return p


def relationships(base,account=None):
    root=folder(base,"relationships")
    if account is not None:
        scopes=[folder(base,"relationships",token(account,"relationship scope"))]
    else:
        scopes=sorted(root.iterdir()) if root.exists() else []
    out={}
    for scope in scopes:
        if not scope.is_dir():
            require(not scope.is_symlink(),"unsafe relationship directory")
            continue
        require(not scope.is_symlink(),"unsafe relationship directory")
        token(scope.name,"relationship scope")
        for p in sorted(scope.glob("*.md")):
            raw,d,_=parse(p)
            require(set(d)=={"id","account","from_id","predicate","to_id","evidence_ids","source_ids"},
                    "unexpected relationship fields")
            before={k:v for k,v in d.items() if k!="id"}
            require(p.stem==d["id"]==keyed("rel-",before) and REL.fullmatch(p.stem)
                    and scope.name==d["account"] and raw==front(d,[]),"invalid relationship record")
            out[p.stem]=d
    return out


def check(base):
    known_labels=labels(base)
    parent=base/"extensions"
    require(not parent.is_symlink(),"unsafe extension directory")
    for ext in parent.iterdir() if parent.is_dir() else ():
        old=ext/"records"
        require(not old.is_symlink() and not (old.is_dir() and any(old.iterdir())),
                "extension-private model store is not allowed: "+ext.name+"/records")
    model_count=sum(1 for p in sorted(folder(base,"records").glob("*.md")) if model_entry(base,p))
    edges=relationships(base)
    for d in edges.values():
        require(relation_data(base,d["account"],d["from_id"],d["predicate"],d["to_id"],
                              d["evidence_ids"],d["source_ids"],known_labels)==d,"invalid relationship references")
    return {"model_records":model_count,"relationships":len(edges)}


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--root",type=Path,default=ROOT)
    sub=cli.add_subparsers(dest="command",required=True)
    sub.add_parser("check")
    sub.add_parser("labels",help="read reusable relationship labels")
    a=sub.add_parser("define-label",help="add a new label only if no existing meaning fits")
    a.add_argument("label")
    a.add_argument("--definition",required=True)
    a.add_argument("--direction",required=True)
    a=sub.add_parser("link",help="record a sourced relationship the agent identified")
    for field in ("account","from_id","predicate","to_id"):
        a.add_argument(field)
    a.add_argument("--evidence-id",action="append",default=[])
    a.add_argument("--source-id",action="append",default=[])
    a=sub.add_parser("links",help="find relationships involving one ID in a scope")
    a.add_argument("account")
    a.add_argument("endpoint")
    a=cli.parse_args()
    base=a.root.resolve()
    require(base.is_dir(),"vault root must exist")
    if a.command=="check":
        result=check(base)
    elif a.command=="labels":
        result=labels(base)
    elif a.command=="define-label":
        with write_lock(base):
            result=define_label(base,a.label,a.definition,a.direction)
    elif a.command=="link":
        with write_lock(base):
            p=write_relationship(base,a.account,a.from_id,a.predicate,a.to_id,
                                 evidence_ids=a.evidence_id,source_ids=a.source_id)
            _,result,_=parse(p)
    else:
        token(a.endpoint,"relationship endpoint")
        result=[d for d in relationships(base,a.account).values()
                if a.endpoint in (d["from_id"],d["to_id"])]
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":
    try:
        main()
    except (ValueError,KeyError,OSError) as exc:
        print(str(exc),file=sys.stderr)
        sys.exit(2)
