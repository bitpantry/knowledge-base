# Generated views contract

Use `views/` for reproducible, human-facing Markdown only. Canonical catalog,
model and evidence lookup does not read that tree. Generated output must not be
ingested, indexed, hand-edited, or shipped with releases. It can expose private
facts and inherits the audience limits of its inputs.

An installed extension with ID `owner-id` declares its outputs in
`extensions/owner-id/VIEWS.md`: a heading followed by one `- Filename.md`
per line. Filenames are flat within `views/owner-id/`. Core rejects duplicate
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
