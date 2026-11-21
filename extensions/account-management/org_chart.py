"""Render Account Management's reporting claims as a navigable Markdown chart."""
import html
import re

import model_store
import views

OWNER = "account-management"
FILENAME = "Org Chart.md"
PEOPLE = "People.md"


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


def render_people(base, people, interactions, refreshed):
    lines = [f"<!-- Refreshed {refreshed} (UTC). -->", "", "[Org Chart](Org%20Chart.md)", ""]
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
        for rid, person in sorted(scoped.items(), key=lambda pair: (pair[1]["title"].casefold(), pair[0])):
            aliases = person.get("aliases") or []
            alias_text = " (" + ", ".join(label(a) for a in aliases) + ")" if aliases else ""
            details = [label(person[key]) for key in ("job_title","organization","business_unit") if key in person]
            if rid in parents and rid not in cycles:
                details.append("Reports to " + label(scoped[parents[rid]]["title"]))
            if (account,rid) in last:
                details.append("Last recorded contact: " + last[account,rid])
            for key, prefix in (("relationship_owner","Owner: "),("relationship_status","Relationship: "),("priority","Priority: ")):
                if key in person:
                    details.append(prefix + label(person[key]))
            suffix = " · " + " · ".join(details) if details else ""
            lines.append(f"- [{label(person['title'])}](../../knowledge/records/{rid}.md){alias_text}{suffix}")
        lines.append("")
    if not people:
        lines.append("No people recorded.")
    return "\n".join(lines)


def refresh(base, people, interactions, refreshed, *, initialize=False):
    chart = views.output(base, OWNER, FILENAME)
    roster = views.output(base, OWNER, PEOPLE)
    if initialize or chart.exists() or roster.exists():
        for path in (chart, roster):
            if path.exists():
                views.require(path.is_file() and path.read_text(encoding="utf-8").startswith(views.HEADER + "\n"),
                              "refusing to overwrite a non-generated document: " + str(path))
        views.publish(base, OWNER, PEOPLE, render_people(base, people, interactions, refreshed))
        return views.publish(base, OWNER, FILENAME, render(base, people, refreshed))
    return None
