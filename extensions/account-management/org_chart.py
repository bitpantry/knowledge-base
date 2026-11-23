"""Render Account Management profiles, Roster, attention and reporting Canvas."""
import html
import re
from urllib.parse import urlsplit
from collections import defaultdict

import model_store
import views

OWNER = "account-management"
FILENAME = "Org Chart.canvas"
PEOPLE = "Roster.md"
ATTENTION = "Needs Attention.md"
PROFILES = "people"
PROFILE_LIMIT = 5


def label(value):
    return re.sub(r"([\\[`\]*_])", r"\\\1", html.escape(value, quote=False))


def graph_id(rid):
    # Core Person IDs allow lowercase ASCII, digits and dashes only.
    return "n_" + rid.replace("-", "_")


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


def open_followups(person, followups):
    return [f for f in followups if f["account"] == person["account"]
            and person["id"] in f["person_ids"] and f["status"] == "open"]


def needs_attention(person, followups):
    return "archived_on" not in person and (person.get("priority") in {"H", "M", "L"}
                                            or bool(open_followups(person, followups)))


def render_people(base, people, interactions, followups, refreshed):
    lines = ["---", "cssclasses: account-management-people", "---", "", "[Org Chart](Org%20Chart.canvas) · [Needs Attention](Needs%20Attention.md)", ""]
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
            items = open_followups(person, followups)
            dates = sorted(f["due"] for f in items if "due" in f)
            count = f"[{len(items)} open](Needs%20Attention.md)" if items else ""
            if dates:
                count += " · next due " + dates[0]
            attention = "**Needs Attention**" if needs_attention(person, followups) else ""
            state = " · ".join(part for part in (count, attention) if part)
            row = [name,cell(person.get("job_title","")),unit,manager,
                   cell(person.get("relationship_owner","")),temp,
                   cell(person.get("priority","")) if person.get("priority") in {"H","M","L"} else "",
                   last.get((account,rid),""),state]
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")
    if not people:
        lines.append("No people recorded.")
    lines += ["", f"<!-- Refreshed {refreshed} (UTC). -->"]
    return "\n".join(lines)


def record_link(record, *, depth=2):
    return f"[{label(record['title'])}]({'../' * depth}knowledge/records/{record['id']}.md)"


def profile_link(person, *, inside=False):
    prefix = "" if inside else "people/"
    return f"[{label(person['title'])}]({prefix}{person['id']}.md)"


def render_attention(people, interactions, followups, refreshed):
    lines=["[Roster](Roster.md)", ""]
    meetings={item["id"]:item for item in interactions}
    ranked={"H":0,"M":1,"L":2}
    opened=[f for f in followups if f["status"]=="open"]
    by_person={rid:[f for f in opened if rid in f["person_ids"] and f["account"]==p["account"]]
               for rid,p in people.items()}
    included=[p for p in people.values()
              if needs_attention(p, followups)]
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
    lines += ["", f"<!-- Refreshed {refreshed} (UTC). -->"]
    return "\n".join(lines)


def linkedin(person):
    """Use an explicit field or one unambiguous clean URL already recorded in this person's notes."""
    if person.get("linkedin_url"):
        return person["linkedin_url"]
    candidates = set()
    for raw in re.findall(r"(?:^|(?<=[.!?])\s+)(?:User-supplied\s+)?LinkedIn(?:\s+profile)?:\s*(https://(?:www\.)?linkedin\.com/in/[^\s<>]+)", person.get("notes") or "", re.I):
        target = raw.rstrip(".,;)")
        parsed = urlsplit(target)
        if re.fullmatch(r"/in/[A-Za-z0-9_%.-]+/?", parsed.path) and not parsed.query and not parsed.fragment:
            candidates.add(target)
    return next(iter(candidates)) if len(candidates) == 1 else ""


def note_entries(person, manager=None):
    """Suppress exact displayed duplicates only; preserve unique context and source wording."""
    value = re.sub(r"^User-provided information \(\d{4}-\d{2}-\d{2}\):\s*", "", person.get("notes") or "")
    profile = linkedin(person)
    result = []
    for entry in re.split(r"(?<=[.!?])\s+|\n+", value):
        entry = entry.strip()
        if not entry:
            continue
        if profile and re.fullmatch(r"(?:User-supplied\s+)?LinkedIn(?:\s+profile)?:\s*" + re.escape(profile) + r"\s*[.]?", entry, re.I):
            continue
        if manager:
            names = "(?:" + "|".join(re.escape(name) for name in sorted([manager["title"], *manager.get("aliases", [])],key=len,reverse=True)) + ")"
            clause = r"(?:reports to|reporting to)\s+" + names + r"(?:\s*\(" + re.escape(manager["id"]) + r"\))?"
            entry = re.sub(r"(?:,?\s+and\s+|[,;]\s*)" + clause + r"(?=[.;]|$)", "", entry, flags=re.I)
            subjects = [person["title"], *person.get("aliases", []), "she", "he", "they"]
            if re.fullmatch(r"(?:" + "|".join(re.escape(name) for name in subjects) + r")\s+" + clause + r"[.]?", entry, re.I):
                continue
            if re.fullmatch(r"(?:Reports to|Manager):?\s*" + names + r"[.]?", entry, re.I):
                continue
        duplicates = [("Organization",person.get("organization")), ("Title",person.get("job_title")),
                      ("Business Unit",person.get("business_unit")), ("Email",person.get("work_email")),
                      ("Phone",person.get("work_phone")), ("Priority",person.get("priority"))]
        if any(value and entry.rstrip(".").casefold() == (caption+": "+value).casefold()
               for caption,value in duplicates):
            continue
        if entry not in result:
            result.append(entry)
    return result


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
            lines = [f"# {label(p['title'])}", ""]
            if needs_attention(p, followups):
                lines += ["**Needs Attention**", ""]
            def cell(value):
                return label(value or "").replace("|", "&#124;")
            temperature = p.get("relationship_temperature")
            score = "" if temperature is None else f"{temperature:+d}" if temperature else "0 (neutral)"
            profile_url = linkedin(p)
            linked_in = f"[Profile]({profile_url})" if profile_url else ""
            lines += ["| Field | Value |", "| --- | --- |"]
            fields = [("ID", cell(rid)), ("Organization", cell(p.get("organization"))),
                      ("Business Unit", cell(p.get("business_unit"))), ("Title", cell(p.get("job_title"))),
                      ("Email", cell(p.get("work_email"))), ("Phone", cell(p.get("work_phone"))),
                      ("LinkedIn", linked_in), ("Relationship Owner", cell(p.get("relationship_owner"))),
                      ("Relationship Status", cell(p.get("relationship_status"))),
                      ("Relationship Temperature", score),
                      ("Temperature Rationale", cell(p.get("relationship_temperature_rationale"))),
                      ("Priority", cell(p.get("priority"))), ("Archived", cell(p.get("archived_on"))),
                      ("Also known as", ", ".join(cell(a) for a in p.get("aliases", [])))]
            lines += [f"| {caption} | {value} |" for caption,value in fields]
            lines += ["", "## Relationship context", ""]
            for field, caption in (("strategic_value","Strategic Value"),
                                   ("opportunity_relevance","Opportunity Relevance"), ("notes","Notes")):
                manager_record = scoped[parents[rid]] if rid in parents and rid not in cycles else None
                fragments = note_entries(p, manager_record) if field == "notes" else [x for x in re.split(r"(?<=[.!?])\s+", p.get(field) or "") if x]
                lines += [f"### {caption}", ""]
                lines += ["- " + label(fragment) for fragment in fragments] if fragments else ["None"]
                lines += [""]
            manager = profile_link(scoped[parents[rid]], inside=True) if rid in parents and rid not in cycles else ""
            reports = ", ".join(profile_link(x, inside=True) for x in reports_by_manager.get(rid, ()))
            lines += ["", "## Reporting", "", "| Field | Value |", "| --- | --- |",
                      f"| Reports To | {manager or 'None'} |", f"| Direct Reports | {reports or 'None'} |", ""]
            if rid in conflicts or rid in cycles:
                lines += ["Reporting claims unresolved.", ""]
            active = actions_by_person.get((account,rid),())
            lines += ["## Open follow-ups", ""]
            if active:
                for f in active[:PROFILE_LIMIT]:
                    detail = [label(f["owner_name"])] if f.get("owner_name") else []
                    if f.get("due"): detail.append("Due " + f["due"])
                    lines.append("- " + record_link(f, depth=3) + (" · " + " · ".join(detail) if detail else ""))
                if len(active) > PROFILE_LIMIT:
                    lines += ["", "[See all open follow-ups](../Needs%20Attention.md)"]
                lines += [""]
            else:
                lines += ["None", ""]
            recent = interactions_by_person.get((account,rid),())
            lines += ["## Recent interactions", ""]
            if recent:
                lines.extend(f"- {e['date']} · {record_link(e, depth=3)}" for e in recent[:PROFILE_LIMIT])
                lines += [""]
            else:
                lines += ["None", ""]
            lines.append(f"[Canonical Person record](../../../knowledge/records/{rid}.md)")
            bodies[rid + ".md"] = "\n".join(lines)
    return bodies


def refresh(base, people, interactions, followups, refreshed, *, initialize=False):
    names = (PEOPLE, ATTENTION)
    destinations = [views.output(base, OWNER, name) for name in names]
    canvas = views.output(base, OWNER, FILENAME)
    if initialize or canvas.exists() or any(p.exists() for p in destinations):
        for path in destinations:
            if path.exists():
                views.require(path.is_file() and views.marked(path.read_text(encoding="utf-8")),
                              "refusing to overwrite a non-generated document: " + str(path))
        views.index(base)
        profiles = render_profiles(base, people, interactions, followups)
        views.publish_collection(base, OWNER, PROFILES, profiles)
        views.publish_canvas(base, OWNER, FILENAME, render_canvas(base, people, followups))
        bodies = (render_people(base, people, interactions, followups, refreshed),
                  render_attention(people, interactions, followups, refreshed))
        for name, body in zip(names, bodies):
            views.publish(base, OWNER, name, body)
        return canvas
    return None


PALETTE = {-3: "#BC3B46", -2: "#D16345", -1: "#DC923E", 0: "#687482",
           1: "#67A278", 2: "#318662", 3: "#106748"}


def render_canvas(base, people, followups=()):
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
                caption = "" if score is None else f"{score:+d}" if score else "0 (neutral)"
                # One text card, with a name-only linked title and no detached metadata nodes.
                title = label(scoped[rid]["title"]).replace("|", "&#124;")
                text = f"# [[views/{OWNER}/people/{rid}|{title}]]\n\n"
                for field, caption_label in (("job_title", "Title"), ("business_unit", "Business Unit"), ("priority", "Priority")):
                    text += f"**{caption_label}:** " + label(scoped[rid].get(field, "")) + "\n\n"
                colored = f'<span style="color: {PALETTE[score]}">{caption}</span>' if score is not None else ""
                text += "**Relationship Temperature:** " + colored
                if needs_attention(scoped[rid], followups):
                    text += "\n\n**Needs Attention**"
                if rid in conflicts: text += "\n\nConflicting manager claims"
                if rid in cycles: text += "\n\nCircular manager claims"
                card = dict(id=graph_id(rid), type="text", x=col*370, y=account_y+depth*380,
                            width=340, height=330, text=text)
                if score is not None:
                    card["color"] = PALETTE[score]
                nodes.append(card)
        edges.extend(dict(id="edge_"+rid,fromNode=graph_id(manager),fromSide="bottom",
                          toNode=graph_id(rid),toSide="top",toEnd="arrow")
                     for rid,manager in sorted(parents.items()))
        account_y += (max(levels,default=0)+1)*380 + 100
    return dict(nodes=nodes,edges=edges)
