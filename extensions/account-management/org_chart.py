"""Render Account Management's reporting claims as a navigable Markdown chart."""
import html
import re

import model_store
import views

OWNER = "account-management"
FILENAME = "Org Chart.md"


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


def render(base, people, refreshed):
    lines = ["# Org Chart", "", f"Refreshed: {refreshed} (UTC).",
             "", "Read this as a view of recorded reporting claims, not a verified or complete company org chart.", ""]
    for account in sorted({p["account"] for p in people.values()}):
        scoped = {rid:p for rid,p in people.items() if p["account"] == account}
        key = lambda rid: (scoped[rid]["title"].casefold(), rid)
        def person(rid):
            return f"[{label(scoped[rid]['title'])}](../../knowledge/records/{rid}.md)"
        grouped = {}
        for edge in model_store.relationships(base, account).values():
            if edge["predicate"] == "reports-to" and edge["from_id"] in scoped and edge["to_id"] in scoped:
                grouped.setdefault(edge["from_id"], set()).add(edge["to_id"])
        conflicts = {rid for rid, choices in grouped.items() if len(choices) > 1}
        parents = {rid:next(iter(choices)) for rid, choices in grouped.items() if len(choices) == 1}
        cycles = set()
        checked = set()
        for entry in parents:
            chain = {}
            rid = entry
            while rid in parents and rid not in checked and rid not in chain:
                chain[rid] = len(chain)
                rid = parents[rid]
            if rid in chain:
                cycles.update(list(chain)[chain[rid]:])
            checked.update(chain)
        lines += [f"## {label(account)}", "", "Arrows run from manager to direct report.", ""]
        lines += diagram(scoped, key, parents, cycles)
        lines += ["Open a Person note: " + " · ".join(person(rid) for rid in sorted(scoped,key=key)), ""]
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


def refresh(base, people, refreshed, *, initialize=False):
    out = views.output(base, OWNER, FILENAME)
    if initialize or out.exists():
        return views.publish(base, OWNER, FILENAME, render(base, people, refreshed))
    return None
