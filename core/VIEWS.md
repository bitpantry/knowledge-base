# Generated views contract

Use `views/` for reproducible, human-facing Markdown and explicitly declared experimental Canvas. Canonical catalog,
model and evidence lookup does not read that tree. Generated output must not be
ingested, indexed, hand-edited, or shipped with releases. It can expose private
facts and inherits the audience limits of its inputs.

An installed extension with ID `owner-id` declares its outputs in
`extensions/owner-id/VIEWS.md`: a heading followed by one `- Filename.md`
per line for entry views. Entry filenames are flat within `views/owner-id/`. Core rejects duplicate
or case-colliding names, paths outside the declared namespace, symlinks, and
attempts to overwrite a manually authored file. This is a writer contract,
not a sandbox for arbitrary extension code.

The extension owns why and how the view is rendered. Under the shared catalog
lock, call `views.publish(base, owner, declared_filename, body)`. Core publishes
the marked Markdown and maintains the human index at `views/README.md`, generated
on first publish. The extension should explain normal refresh triggers and a
manual rebuild route. It must preserve canonical writes and report refresh
failure separately. Each output is written atomically; a subsequent rebuild
can repair an interrupted output/index refresh. Core never runs foreign
extension renderers on a generic write.

## Collections

For a collection of related pages, declare `- folder-name/` in `VIEWS.md`
and call `views.publish_collection(base, owner, "folder-name", bodies)` under
the same catalog lock. Supply the complete desired mapping of stable, lowercase
Markdown filenames to bodies. There is one subfolder level, inside the owning
extension only. The core preflights the batch, skips byte-identical output and
removes obsolete files only when the same collection's generation marker is
present. Handwritten files are never replaced or pruned. Names are for identity,
not display; put a readable title in each page. Link from a flat roster or
overview, rather than registering every collection member in the Views index.

## Experimental Canvas

An extension may explicitly declare a flat `.canvas` output and publish it with
`views.publish_canvas` under the catalog lock. The JSON contains a `generatedBy`
owner/path marker; only a file with that exact marker may be replaced. The same
namespace, collision and symlink guards apply. Canvas is excluded from the shared
index and linked from a Markdown overview. It remains derived and must never be
ingested, indexed, or packaged. Markdown remains the independently usable fallback.
