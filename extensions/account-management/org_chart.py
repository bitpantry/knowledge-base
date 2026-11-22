"""Render Account Management's reporting claims as a navigable Markdown chart."""
import html
import re
from collections import defaultdict

import model_store
import views

OWNER = "account-management"
FILENAME = "Org Chart.md"
PEOPLE = "People.md"
ATTENTION = "Needs Attention.md"
PROFILES = "people"
PROFILE_LIMIT = 5


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
    lines = [f"<!-- Refreshed {refreshed} (UTC). -->", "", "[People](People.md) · [Experimental Canvas](Org%20Chart.canvas)", ""]
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
    lines = [f"<!-- Refreshed {refreshed} (UTC). -->", "", "[Org Chart](Org%20Chart.md) · [Needs Attention](Needs%20Attention.md)", ""]
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
            name = f"[{cell(person['title'])}](people/{rid}.md){alias_text}"
            manager = f"[{cell(scoped[parents[rid]]['title'])}](people/{parents[rid]}.md)" if rid in parents and rid not in cycles else ""
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


def record_link(record, *, depth=2):
    return f"[{label(record['title'])}]({'../' * depth}knowledge/records/{record['id']}.md)"


def profile_link(person, *, inside=False):
    prefix = "" if inside else "people/"
    return f"[{label(person['title'])}]({prefix}{person['id']}.md)"


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
        lines.extend([f"## {profile_link(p)}",""])
        if p.get("priority") in ranked:
            lines.extend(["Priority: " + p["priority"],""])
        for f in sorted(by_person[p["id"]],key=lambda f:(f.get("due","9999-99-99"),f["title"].casefold(),f["id"])):
            if f["id"] in shown:
                lines.append("- Shared follow-up: "+record_link(f))
                continue
            shown.add(f["id"])
            details=[]
            if "owner_name" in f: details.append("Owner: "+label(f["owner_name"]))
            if "due" in f: details.append("Due: "+f["due"])
            if f.get("interaction_id") in meetings:
                details.append("From: "+record_link(meetings[f["interaction_id"]]))
            lines.append("- "+record_link(f)+(" · "+" · ".join(details) if details else ""))
        lines.append("")
    if not included:
        lines.append("No active people with a recorded priority or open follow-up.")
    return "\n".join(lines)


def render_profiles(base, people, interactions, followups, refreshed=None):
    # No timestamp in a profile body: leave identical generated files untouched.
    bodies = {}
    interactions_by_person, actions_by_person = defaultdict(list), defaultdict(list)
    for item in sorted(interactions, key=lambda item:(item["date"],item["id"]), reverse=True):
        for rid in item["person_ids"]:
            interactions_by_person[(item["account"],rid)].append(item)
    pending = (f for f in followups if f["status"] == "open")
    for item in sorted(pending,key=lambda f:(f.get("due","9999-99-99"),f["title"].casefold(),f["id"])):
        for rid in item["person_ids"]:
            actions_by_person[(item["account"],rid)].append(item)
    for account in sorted({p["account"] for p in people.values()}):
        scoped = {rid:p for rid,p in people.items() if p["account"] == account}
        _, conflicts, parents, cycles = reporting(base, account, scoped)
        reports_by_manager = defaultdict(list)
        for report in sorted(set(parents) - cycles,key=lambda rid:(scoped[rid]["title"].casefold(),rid)):
            reports_by_manager[parents[report]].append(scoped[report])
        for rid, p in sorted(scoped.items()):
            lines = [f"# {label(p['title'])}", "",
                     "[People](../People.md) · [Org Chart](../Org%20Chart.md)", ""]
            info = []
            for field, caption in (
                ("job_title","Role"), ("organization","Organization"), ("business_unit","Business unit"),
                ("relationship_owner","Relationship owner"), ("priority","Priority"), ("archived_on","Archived"),
                ("work_email","Work email"), ("work_phone","Work phone")
            ):
                if field in p:
                    info.append(f"- **{caption}:** {label(p[field])}")
            if p.get("linkedin_url"):
                info.append(f"- **LinkedIn:** [Profile]({p['linkedin_url']})")
            if p.get("aliases"):
                info.append("- **Also known as:** " + ", ".join(label(a) for a in p["aliases"]))
            if "relationship_temperature" in p:
                value = p["relationship_temperature"]
                score = f"{value:+d}" if value else "0 (neutral)"
                note = " · " + label(p["relationship_temperature_rationale"]) if p.get("relationship_temperature_rationale") else ""
                info.append("- **Relationship temperature:** " + score + note)
            if info:
                lines += info + [""]
            context = []
            for field, caption in (("strategic_value","Strategic value"), ("opportunity_relevance","Opportunity relevance")):
                if p.get(field):
                    context.append(f"- **{caption}:** {label(p[field])}")
            if p.get("notes"):
                context += ([""] if context else []) + [label(p["notes"])]
            if context:
                lines += ["## Relationship context", "", *context, ""]
            org = []
            if rid in conflicts or rid in cycles:
                org.append("- Reporting claims unresolved; see the Org Chart.")
            elif rid in parents:
                org.append("- **Manager:** " + profile_link(scoped[parents[rid]], inside=True))
            reports = reports_by_manager.get(rid,())
            if reports:
                org.append("- **Direct reports:** " + ", ".join(profile_link(x, inside=True) for x in reports))
            if org:
                lines += ["## Reporting", "", *org, ""]
            active = actions_by_person.get((account,rid),())
            if active:
                lines += ["## Open follow-ups", ""]
                for f in active[:PROFILE_LIMIT]:
                    detail = [label(f["owner_name"])] if f.get("owner_name") else []
                    if f.get("due"): detail.append("Due " + f["due"])
                    lines.append("- " + record_link(f, depth=3) + (" · " + " · ".join(detail) if detail else ""))
                if len(active) > PROFILE_LIMIT:
                    lines += ["", "[See all open follow-ups](../Needs%20Attention.md)"]
                lines += [""]
            recent = interactions_by_person.get((account,rid),())
            if recent:
                lines += ["## Recent interactions", ""]
                lines.extend(f"- {e['date']} · {record_link(e, depth=3)}" for e in recent[:PROFILE_LIMIT])
                lines += [""]
            lines.append(f"[Canonical Person record](../../../knowledge/records/{rid}.md)")
            bodies[rid + ".md"] = "\n".join(lines)
    return bodies


def refresh(base, people, interactions, followups, refreshed, *, initialize=False):
    names = (FILENAME, PEOPLE, ATTENTION)
    destinations = [views.output(base, OWNER, n) for n in names]
    if initialize or any(p.exists() for p in destinations):
        for path in destinations:
            if path.exists():
                views.require(path.is_file() and path.read_text(encoding="utf-8").startswith(views.HEADER + "\n"),
                              "refusing to overwrite a non-generated document: " + str(path))
        views.index(base)  # Validate the shared index before updating collection files.
        profiles = render_profiles(base, people, interactions, followups)
        views.publish_collection(base, OWNER, PROFILES, profiles)
        bodies = (render(base, people, refreshed), render_people(base, people, interactions, followups, refreshed),
                  render_attention(people, interactions, followups, refreshed))
        for name, body in zip(names, bodies):
            views.publish(base, OWNER, name, body)
        views.publish_canvas(base, OWNER, "Org Chart.canvas", render_canvas(base, people))
        return destinations[0]
    return None


PALETTE = {-3: "#BC3B46", -2: "#D16345", -1: "#DC923E", 0: "#687482",
           1: "#67A278", 2: "#318662", 3: "#106748"}


def render_canvas(base, people):
    """File cards open stable generated profiles; ambiguous/cyclic edges stay omitted."""
    nodes, edges = [], []
    active = {rid:p for rid,p in people.items() if "archived_on" not in p}
    account_y = 0
    for account in sorted({p["account"] for p in active.values()}):
        scoped = {rid:p for rid,p in active.items() if p["account"] == account}
        key = lambda rid:(scoped[rid]["title"].casefold(),rid)
        _, conflicts, parents, cycles = reporting(base, account, scoped)
        parents = {rid:manager for rid,manager in parents.items() if rid not in cycles}
        children = defaultdict(list)
        for rid, manager in parents.items():
            children[manager].append(rid)
        levels = defaultdict(list)
        stack = [(rid,0) for rid in reversed(sorted(set(scoped)-set(parents),key=key))]
        while stack:
            rid, depth = stack.pop()
            levels[depth].append(rid)
            stack.extend((child,depth+1) for child in reversed(sorted(children[rid],key=key)))
        for depth, level in sorted(levels.items()):
            for col, rid in enumerate(level):
                score = scoped[rid].get("relationship_temperature")
                card = dict(id=graph_id(rid), type="file", x=col*330, y=account_y+depth*290,
                            width=300, height=190, file=f"views/{OWNER}/people/{rid}.md")
                if score is not None:
                    card["color"] = PALETTE[score]
                nodes.append(card)
                caption = "Unknown" if score is None else f"{score:+d}"
                if rid in conflicts: caption += " · conflicting manager claims"
                if rid in cycles: caption += " · circular manager claims"
                nodes.append(dict(id="caption_"+rid,type="text",x=col*330,y=account_y+depth*290+195,
                                  width=300,height=65,text="Temperature: "+caption))
        edges.extend(dict(id="edge_"+rid,fromNode=graph_id(manager),fromSide="bottom",
                          toNode=graph_id(rid),toSide="top",toEnd="arrow")
                     for rid,manager in sorted(parents.items()))
        account_y += (max(levels,default=0)+1)*290 + 100
    return dict(nodes=nodes,edges=edges)
