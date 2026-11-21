"""Render Account Management's reporting claims as a navigable Markdown chart."""
import html
import re

import model_store
import views

OWNER = "account-management"
FILENAME = "Org Chart.md"
PEOPLE = "People.md"
ATTENTION = "Needs Attention.md"
PROFILES = "Person Details.md"


def label(value):
    return re.sub(r"([\\[`\]*_])", r"\\\1", html.escape(value, quote=False))


def graph_id(rid):
    # Core Person IDs allow lowercase ASCII, digits and dashes only.
    return "n_" + rid.replace("-", "_")


def graph_label(value):
    # Mermaid quoted-text entities are decimal #codepoint;. Encode all syntax
    # characters (including # itself) rather than passing through HTML,
    # quotes, Markdown fences, Mermaid directives, or line separators.
    return "".join(c if c in " -,.()" or c.isascii() and c.isalnum()
                   else f"#{ord(c)};" for c in value)


def diagram(scoped, key, parents, cycles):
    lines = ["```mermaid", "flowchart TD"]
    for rid in sorted(scoped, key=key):
        lines.append(f'  {graph_id(rid)}["{graph_label(scoped[rid]["title"])}"]')
    for rid in sorted(set(parents) - cycles, key=key):
        lines.append(f"  {graph_id(parents[rid])} --> {graph_id(rid)}")
    return [*lines, "```", ""]


def reporting(base,account,scoped):
    grouped = {}
    for edge in model_store.relationships(base, account).values():
        if edge["predicate"] == "reports-to" and edge["from_id"] in scoped and edge["to_id"] in scoped:
            grouped.setdefault(edge["from_id"], set()).add(edge["to_id"])
    conflicts = {rid for rid, choices in grouped.items() if len(choices) > 1}
    parents = {rid:next(iter(choices)) for rid, choices in grouped.items() if len(choices) == 1}
    cycles, checked = set(), set()
    for entry in parents:
        chain = {}
        rid = entry
        while rid in parents and rid not in checked and rid not in chain:
            chain[rid] = len(chain)
            rid = parents[rid]
        if rid in chain:
            cycles.update(list(chain)[chain[rid]:])
        checked.update(chain)
    return grouped,conflicts,parents,cycles


def render(base, people, refreshed):
    lines = [f"<!-- Refreshed {refreshed} (UTC). -->", "", "[People](People.md)", ""]
    people = {rid:p for rid,p in people.items() if "archived_on" not in p}
    accounts = sorted({p["account"] for p in people.values()})
    for account in accounts:
        scoped = {rid:p for rid,p in people.items() if p["account"] == account}
        key = lambda rid: (scoped[rid]["title"].casefold(), rid)
        def person(rid):
            return label(scoped[rid]["title"])
        grouped,conflicts,parents,cycles=reporting(base,account,scoped)
        if len(accounts) > 1:
            lines += [f"## {label(account)}", ""]
        lines += diagram(scoped, key, parents, cycles)
        if conflicts or cycles:
            lines += ["**Reporting exceptions (not drawn)**", ""]
            for rid in sorted(conflicts | cycles, key=key):
                options = ", ".join(person(manager) for manager in sorted(grouped[rid], key=key))
                reason = "conflicting manager claims" if rid in conflicts else "circular manager claims"
                lines.append(f"- {person(rid)}: {reason} ({options})")
        lines.append("")
    if not people:
        lines += ["No people recorded.", ""]
    return "\n".join(lines)


def render_people(base, people, interactions, followups, refreshed):
    lines = [f"<!-- Refreshed {refreshed} (UTC). -->", "", "[Org Chart](Org%20Chart.md) · [Person Details](Person%20Details.md) · [Needs Attention](Needs%20Attention.md)", ""]
    people = {rid:p for rid,p in people.items() if "archived_on" not in p}
    accounts = sorted({p["account"] for p in people.values()})
    last = {}
    for interaction in interactions:
        for rid in interaction["person_ids"]:
            key=(interaction["account"],rid)
            last[key]=max(last.get(key,""),interaction["date"])
    for account in accounts:
        if len(accounts) > 1:
            lines += [f"## {label(account)}", ""]
        scoped = {rid:p for rid,p in people.items() if p["account"] == account}
        _,_,parents,cycles=reporting(base,account,scoped)
        lines += ["| Name | Role | Organization / unit | Manager | Relationship owner | Relationship temperature | Priority | Last recorded contact | Follow-ups |",
                  "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        def cell(value):
            return label(value).replace("|","&#124;")
        for rid, person in sorted(scoped.items(), key=lambda pair: (pair[1]["title"].casefold(), pair[0])):
            aliases = person.get("aliases") or []
            alias_text = " (" + ", ".join(cell(a) for a in aliases) + ")" if aliases else ""
            name = f"[{cell(person['title'])}](../../knowledge/records/{rid}.md){alias_text}"
            manager = cell(scoped[parents[rid]]["title"]) if rid in parents and rid not in cycles else ""
            score = person.get("relationship_temperature")
            temp = (f"{score:+d}" if score else "0") if score is not None else ""
            unit = " / ".join(cell(person[key]) for key in ("organization","business_unit") if key in person)
            items = [f for f in followups if f["account"]==account and rid in f["person_ids"] and f["status"]=="open"]
            dates = sorted(f["due"] for f in items if "due" in f)
            count = f"[{len(items)} open](Needs%20Attention.md)" if items else ""
            if dates:
                count += " · next due " + dates[0]
            row = [name,cell(person.get("job_title","")),unit,manager,
                   cell(person.get("relationship_owner","")),temp,
                   cell(person.get("priority","")) if person.get("priority") in {"H","M","L"} else "",
                   last.get((account,rid),""),count]
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")
    if not people:
        lines.append("No people recorded.")
    return "\n".join(lines)


def person_link(person):
    return f"[{label(person['title'])}](../../knowledge/records/{person['id']}.md)"


def render_attention(people, interactions, followups, refreshed):
    lines=[f"<!-- Refreshed {refreshed} (UTC). -->","", "[People](People.md)", ""]
    meetings={item["id"]:item for item in interactions}
    ranked={"H":0,"M":1,"L":2}
    opened=[f for f in followups if f["status"]=="open"]
    by_person={rid:[f for f in opened if rid in f["person_ids"] and f["account"]==p["account"]]
               for rid,p in people.items()}
    included=[p for p in people.values()
              if "archived_on" not in p and (p.get("priority") in ranked or by_person[p["id"]])]
    def order(p):
        items=by_person[p["id"]]
        dates=[f["due"] for f in items if "due" in f]
        return (min(dates,default="9999-99-99"),not bool(items),ranked.get(p.get("priority"),3),p["title"].casefold(),p["id"])
    shown=set()
    for p in sorted(included,key=order):
        lines.extend([f"## {person_link(p)}",""])
        if p.get("priority") in ranked:
            lines.extend(["Priority: " + p["priority"],""])
        for f in sorted(by_person[p["id"]],key=lambda f:(f.get("due","9999-99-99"),f["title"].casefold(),f["id"])):
            if f["id"] in shown:
                lines.append("- Shared follow-up: "+person_link(f))
                continue
            shown.add(f["id"])
            details=[]
            if "owner_name" in f: details.append("Owner: "+label(f["owner_name"]))
            if "due" in f: details.append("Due: "+f["due"])
            if f.get("interaction_id") in meetings:
                details.append("From: "+person_link(meetings[f["interaction_id"]]))
            lines.append("- "+person_link(f)+(" · "+" · ".join(details) if details else ""))
        lines.append("")
    if not included:
        lines.append("No active people with a recorded priority or open follow-up.")
    return "\n".join(lines)


def render_profiles(base,people,interactions,refreshed):
    lines=[f"<!-- Refreshed {refreshed} (UTC). -->","","[People](People.md)",""]
    for account in sorted({p["account"] for p in people.values()}):
        scoped={rid:p for rid,p in people.items() if p["account"]==account}
        _,conflicts,parents,cycles=reporting(base,account,scoped)
        for p in sorted(scoped.values(),key=lambda p:(p["title"].casefold(),p["id"])):
            rid=p["id"]
            lines += [f"## {person_link(p)}",""]
            for key,title in (("organization","Organization"),("business_unit","Business unit"),("job_title","Role"),
                              ("strategic_value","Strategic value"),("opportunity_relevance","Opportunity relevance"),
                              ("relationship_temperature_rationale","Relationship context"),("archived_on","Archived")):
                if key in p: lines.append(f"- {title}: {label(p[key])}")
            if rid in conflicts or rid in cycles:
                lines.append("- Reporting claims unresolved; see Org Chart.")
            elif rid in parents:
                lines.append("- Manager: "+person_link(scoped[parents[rid]]))
            reports=[scoped[x] for x in parents if parents[x]==rid and x not in cycles]
            if reports:
                lines.append("- Direct reports: "+", ".join(person_link(x) for x in sorted(reports,key=lambda p:(p["title"].casefold(),p["id"]))))
            history=[e for e in interactions if e["account"]==account and rid in e["person_ids"]]
            if history:
                lines.append("- Interactions: "+", ".join(e["date"]+" "+person_link(e) for e in sorted(history,key=lambda e:(e["date"],e["id"]),reverse=True)))
            lines.append("")
    return "\n".join(lines)


def refresh(base, people, interactions, followups, refreshed, *, initialize=False):
    names=(FILENAME,PEOPLE,ATTENTION,PROFILES)
    destinations=[views.output(base,OWNER,n) for n in names]
    if initialize or any(p.exists() for p in destinations):
        for path in destinations:
            if path.exists():
                views.require(path.is_file() and path.read_text(encoding="utf-8").startswith(views.HEADER + "\n"),
                              "refusing to overwrite a non-generated document: " + str(path))
        bodies=(render(base,people,refreshed),render_people(base,people,interactions,followups,refreshed),
                render_attention(people,interactions,followups,refreshed),render_profiles(base,people,interactions,refreshed))
        for name,body in zip(names,bodies):
            views.publish(base,OWNER,name,body)
        return destinations[0]
    return None
