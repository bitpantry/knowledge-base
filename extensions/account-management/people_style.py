"""Install opt-in Obsidian styling scoped exclusively to the generated People note."""
import json
import views
from catalog import publish_note, require

SLUG = "account-management-people"
MARKER = "/* Generated Account Management People styling. */"
CSS = MARKER + """
.markdown-preview-view.account-management-people,
.markdown-source-view.mod-cm6.account-management-people {
  --file-line-width: 100%;
  overflow-x: auto;
}
.markdown-preview-view.account-management-people .markdown-preview-sizer,
.markdown-source-view.mod-cm6.account-management-people .cm-sizer {
  max-width: none;
}
.markdown-preview-view.account-management-people .el-table,
.markdown-preview-view.account-management-people .table-wrapper,
.markdown-preview-view.account-management-people .markdown-preview-section > div:has(table),
.markdown-source-view.account-management-people .cm-table-widget {
  overflow-x: auto;
  max-width: 100%;
  min-width: 0;
  width: 100%;
}
.markdown-preview-view.account-management-people table,
.markdown-source-view.account-management-people table {
  display: block;
  width: 100%;
  overflow-x: auto;
  max-width: 100%;
}
 .markdown-preview-view.account-management-people :is(table, .table-wrapper, .el-table)::-webkit-scrollbar {
  height: 10px;
}
.markdown-preview-view.account-management-people :is(table, .table-wrapper, .el-table)::-webkit-scrollbar-thumb {
  background: var(--text-faint);
  border-radius: 5px;
}
.markdown-preview-view.account-management-people :is(table, .table-wrapper, .el-table)::-webkit-scrollbar-track {
  background: var(--background-secondary);
}
.markdown-preview-view.account-management-people .metadata-container {
  display: none;
}
.markdown-preview-view.account-management-people :is(th, td),
.markdown-source-view.account-management-people :is(th, td) {
  padding: 0.65em 1em;
  white-space: nowrap;
}
"""


def install(base):
    """Explicit command only; preserve all unrelated appearance settings and snippets."""
    settings = views.safe_child(base, ".obsidian")
    snippets = views.safe_child(settings, "snippets")
    target = views.safe_child(snippets, SLUG + ".css")
    appearance = views.safe_child(settings, "appearance.json")
    if target.exists():
        require(target.is_file() and target.read_text().startswith(MARKER + "\n"),
                "refusing to overwrite a manual People stylesheet")
    config = json.loads(appearance.read_text()) if appearance.exists() else {}
    require(isinstance(config, dict), "invalid appearance settings")
    enabled = config.get("enabledCssSnippets", [])
    require(isinstance(enabled, list) and all(isinstance(x, str) for x in enabled),
            "invalid enabled CSS snippets")
    snippets.mkdir(parents=True, exist_ok=True)
    if not target.exists() or target.read_text() != CSS:
        publish_note(target, CSS, replace=target.exists())
    if SLUG not in enabled:
        config["enabledCssSnippets"] = [*enabled, SLUG]
        publish_note(appearance, json.dumps(config, indent=2) + "\n", replace=appearance.exists())
    return {"stylesheet": target.relative_to(base).as_posix(), "enabled": True}
