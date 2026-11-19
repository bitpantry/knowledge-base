#!/usr/bin/env python3
"""Preview and record optional extension interpretations without moving core data."""
import argparse
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import sys
from catalog import ROOT, clean_text, load_json, lookup, publish_note, require, write_lock
from concepts import FOLDERS, encode, keyed, records
from wire_extension import SLUG, attached_path

TYPES={"source","concept","evidence","decision"}
ID=re.compile(r"int-[0-9a-f]{24}\Z")
FIELDS={"extension","model","model_id","model_name","record_type","record_id","state","reason"}

def normalized_row(d):
    require(isinstance(d,dict) and set(d)==FIELDS,"each interpretation needs the eight documented fields")
    for f in FIELDS:
        clean_text(d[f],f,500 if f=="reason" else 160)
    require(SLUG.fullmatch(d["extension"]),"invalid extension name")
    require(SLUG.fullmatch(d["model_id"]),"invalid stable model ID")
    require(d["record_type"] in TYPES,"invalid core record type")
    require(d["state"] in {"match","ambiguous","no-match"},"invalid preview state")
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._-]{0,79}",d["model_name"]),"use a short plain model name")
    p=PurePosixPath(d["model"])
    require(not p.is_absolute() and p.as_posix()==d["model"] and
            p.suffix==".md" and p.name!="EXTENSION.md"
            and all(re.fullmatch(r"[A-Za-z0-9._-]+",x) and not x.startswith(".") for x in p.parts),
            "model must be a Markdown file relative to the extension folder")
    return d

def location(base,d):
    t,rid=d["record_type"],d["record_id"]
    if t=="source":
        return lookup(base,rid)[0]
    require(rid in records(base,t),"unknown core record: "+rid)
    return base/"knowledge"/FOLDERS[t]/(rid+".md")

def model_location(base,d):
    attached_path(base,d["extension"])
    p=base/"extensions"/d["extension"]/d["model"]
    require(p.is_file() and not any(pp.is_symlink() for pp in (*p.parents,p) if pp.is_relative_to(base)),
            "model definition missing or unsafe: "+d["extension"]+"/"+d["model"])
    return p

def ident(d):
    return keyed("int-",[d[k] for k in ("extension","model","model_name","record_type","record_id")])

def identity(d):
    return d["record_type"],d["record_id"]

def overlay_dir(base):
    p=base/"knowledge"/"interpretations"
    require(not p.is_symlink() and not p.parent.is_symlink(),"unsafe interpretations folder")
    return p

def render(d):
    rid=ident(d)
    t=d["record_type"]
    ref=f"../../catalog/{d['record_id']}.md" if t=="source" else f"../{FOLDERS[t]}/{d['record_id']}.md"
    model=f"../../extensions/{d['extension']}/{d['model']}"
    meta=["---","interpretation_id: "+encode(rid)]+[k+": "+encode(v) for k,v in sorted(d.items())]+["---"]
    return "\n".join([*meta,"",f"# {d['model_name']} · {d['extension']}","",d["reason"],"",
                    f"[Underlying {t}]({ref}) · [Model definition]({model})",""])

def existing(base):
    rows={}
    for p in sorted(overlay_dir(base).glob("*.md")):
        require(not p.is_symlink() and ID.fullmatch(p.stem),"unexpected interpretation file: "+p.name)
        raw=p.read_text(encoding="utf-8")
        front=raw.split("---\n",2)
        require(len(front)==3 and not front[0],"malformed interpretation: "+p.name)
        rows_raw=[s.split(": ",1) for s in front[1].splitlines()]
        require(all(len(line)==2 for line in rows_raw),"malformed interpretation metadata")
        d={k:json.loads(v) for k,v in rows_raw}
        require(len(d)==len(rows_raw),"duplicate metadata")
        require(d.pop("interpretation_id",None)==p.stem,"mismatched interpretation ID")
        d=normalized_row(d)
        require(d["state"]=="match" and ident(d)==p.stem and raw==render(d),"noncanonical interpretation")
        rows[p.stem]=d
    return rows

def fingerprint(path):
    return sha256(path.read_bytes()).hexdigest()

def preview(base, plan):
    require(isinstance(plan,list),"plan must be an array (use [] for no applicable items)")
    saved=existing(base)
    keys=set()
    candidates=[]
    targets={}
    for d in plan:
        d=normalized_row(d)
        source=location(base,d)
        contract=model_location(base,d)
        rid=ident(d)
        require(rid not in keys,"duplicate interpretation candidate")
        keys.add(rid)
        candidates.append((d,rid))
        targets[rid]=[fingerprint(source),fingerprint(contract),
                      fingerprint(base/"extensions"/d["extension"]/"EXTENSION.md")]
    planned={rid:d for d,rid in candidates if d["state"]=="match"}
    rows=[]
    for d,rid in candidates:
        status=d["state"]
        if rid in saved and status=="match":
            status="already-recorded" if saved[rid]==d else "needs-review-existing"
        overlaps=[]
        for other,old in {**planned,**saved}.items():
            if other!=rid and identity(old)==identity(d):
                overlaps.append({"id":other,"extension":old["extension"],"model_id":old["model_id"],"model_name":old["model_name"],
                                 "status":"existing" if other in saved else "proposed"})
        rows.append({**d,"id":rid,"status":status,"overlaps":sorted(overlaps,key=lambda o:o["id"])})
    # Approval binds both the semantic proposal and the exact local inputs it referred to.
    states={rid:saved[rid] for rid in sorted(saved) if any(identity(saved[rid])==identity(d) for d,_ in candidates)}
    counts={status:sum(d["status"]==status for d in rows)
            for status in ("match","ambiguous","no-match","already-recorded","needs-review-existing")}
    counts["underlying_records_with_overlap"]=len({identity(d) for d in rows if d["overlaps"]})
    return {"preview":keyed("plan-",[plan,targets,states]),"items":rows,"counts":counts,
            "new_matches":counts["match"]}

def apply(base,plan,approval):
    with write_lock(base):
        report=preview(base,plan)
        require(report["preview"]==approval,"preview changed; review the current plan before applying")
        written=[]
        for item in report["items"]:
            if item["status"]!="match":
                continue
            d={k:item[k] for k in FIELDS}
            p=overlay_dir(base)/(item["id"]+".md")
            p.parent.mkdir(parents=True,exist_ok=True)
            publish_note(p,render(d))
            written.append(p.relative_to(base).as_posix())
        return {"written":written,**report}

def listing(base, t=None, rid=None):
    if t is not None:
        location(base,{"record_type":t,"record_id":rid})
    return [{"id":key,**d,"note":f"knowledge/interpretations/{key}.md"}
            for key,d in existing(base).items() if t is None or identity(d)==(t,rid)]

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root",type=Path,default=ROOT)
    sub=ap.add_subparsers(dest="cmd",required=True)
    p=sub.add_parser("preview"); p.add_argument("plan")
    p=sub.add_parser("apply"); p.add_argument("plan"); p.add_argument("--if-preview",required=True)
    p=sub.add_parser("list"); p.add_argument("record_type",nargs="?",choices=sorted(TYPES)); p.add_argument("record_id",nargs="?")
    sub.add_parser("check")
    a=ap.parse_args()
    base=a.root.resolve()
    require(base.is_dir(),"vault root does not exist")
    if a.cmd=="preview":
        out=preview(base,load_json(a.plan))
    elif a.cmd=="apply":
        out=apply(base,load_json(a.plan),a.if_preview)
    elif a.cmd=="list":
        require((a.record_type is None)==(a.record_id is None),"provide both type and ID, or neither")
        out=listing(base,a.record_type,a.record_id)
    else:
        items=existing(base)
        for d in items.values():
            location(base,d); model_location(base,d)
        out={"interpretations":len(items)}
    print(json.dumps(out,indent=2,ensure_ascii=False))

if __name__=="__main__":
    try:
        main()
    except (ValueError,TypeError,KeyError,OSError) as e:
        print(str(e),file=sys.stderr)
        sys.exit(2)
