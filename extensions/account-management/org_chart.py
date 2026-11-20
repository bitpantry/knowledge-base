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


def diagram(scoped, key, parents, conflicts, cycles):
    lines = ["```mermaid", "flowchart TD"]
    for rid in sorted(scoped, key=key):
        p = scoped[rid]
        name = p["title"]
        if p.get("aliases"):
            name += " (" + ", ".join(p["aliases"]) + ")"
        if rid in conflicts:
            name += " - conflicting manager claims"
        elif rid in cycles:
            name += " - circular manager claims"
        elif rid not in parents:
            name += " - manager not recorded"
        lines.append(f'  {graph_id(rid)}["{graph_label(name)}"]')
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
            p = scoped[rid]
            aliases = ", ".join(label(n) for n in p.get("aliases", []))
            return f"[{label(p['title'])}](../../knowledge/records/{rid}.md)" + (f" ({aliases})" if aliases else "")
        grouped = {}
        for edge in model_store.relationships(base, account).values():
            if edge["predicate"] != "reports-to" or edge["from_id"] not in scoped or edge["to_id"] not in scoped:
                continue
            citations = grouped.setdefault(edge["from_id"], {}).setdefault(edge["to_id"], set())
            citations.update(("evidence", eid) for eid in edge["evidence_ids"])
            citations.update(("source", sid) for sid in edge["source_ids"])
        def cites(child, parent):
            out = []
            for i,(kind,rid) in enumerate(sorted(grouped[child][parent]), 1):
                folder = "knowledge/evidence" if kind == "evidence" else "catalog"
                out.append(f"[{kind} {i}](../../{folder}/{rid}.md)")
            return ", ".join(out)
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
        children = {}
        for rid,parent in parents.items():
            if rid not in cycles:
                children.setdefault(parent, []).append(rid)
        lines += [f"## {label(account)}", "", "Arrows run from manager to direct report. Disputed and circular edges are omitted.", ""]
        lines += diagram(scoped, key, parents, conflicts, cycles)
        lines += ["**People and evidence**", ""]
        roots = sorted(set(scoped) - (set(parents) - cycles), key=key)
        queue = [(rid,0) for rid in reversed(roots)]
        while queue:
            rid, depth = queue.pop()
            tail = (" — conflicting manager claims" if rid in conflicts else
                    " — cycle in manager claims" if rid in cycles else
                    " — " + cites(rid,parents[rid]) if rid in parents else " — manager not recorded")
            lines.append("  " * depth + "- " + person(rid) + tail)
            queue.extend((child,depth+1) for child in reversed(sorted(children.get(rid,[]),key=key)))
        if conflicts or cycles:
            lines += ["", "**Claims needing review**", ""]
            for rid in sorted(conflicts | cycles, key=key):
                for manager in sorted(grouped[rid], key=key):
                    lines.append(f"- {person(rid)} reports to {person(manager)} — {cites(rid,manager)}")
        lines.append("")
    if not people:
        lines += ["No people recorded.", ""]
    return "\n".join(lines)


def refresh(base, people, refreshed, *, initialize=False):
    out = views.output(base, OWNER, FILENAME)
    if initialize or out.exists():
        return views.publish(base, OWNER, FILENAME, render(base, people, refreshed))
    return None
