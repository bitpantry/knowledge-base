import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
import update as updater


def bundle(commit, files, extra=None):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr(updater.MANIFEST, updater.encode(updater.manifest(commit, files)))
        for name, data in files.items():
            z.writestr(name, data)
        if extra:
            z.writestr(*extra)
    return out.getvalue()


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.old = {name: b"original" for name in updater.REQUIRED}
        self.new = dict(self.old, **{"core/catalog.py": b"updated", "core/extra.md": b"added"})
        self.receipt = self.root / updater.MANIFEST
        for name, data in self.old.items():
            self.put(name, data)
        self.receipt.write_bytes(updater.encode(updater.manifest("a" * 40, self.old)))

    def put(self, name, data):
        p = self.root / name
        p.parent.mkdir(exist_ok=True, parents=True)
        p.write_bytes(data)

    def run_update(self, apply=False, asset=None):
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            updater.update(self.root, asset if asset is not None else bundle("b" * 40, self.new), apply)
        return stdout.getvalue()

    def test_preview_and_apply_preserve_live_content(self):
        vault_files = ["catalog/source.md", "knowledge/concepts/concept.md", "extensions/x/EXTENSION.md",
                       ".obsidian/settings.json", "README.md", "START-HERE.md", ".gitignore"]
        for name in vault_files:
            self.put(name, b"custom")
        old_receipt = self.receipt.read_bytes()
        self.assertIn("UPDATE core/catalog.py", self.run_update())
        self.assertEqual((self.root / "core/catalog.py").read_bytes(), b"original")
        self.assertEqual(self.receipt.read_bytes(), old_receipt)
        self.run_update(apply=True)
        self.assertEqual((self.root / "core/catalog.py").read_bytes(), b"updated")
        self.assertEqual(updater.decode(self.receipt.read_bytes())["commit"], "b" * 40)
        self.assertIn("Already up to date", self.run_update())
        for name in vault_files:
            self.assertEqual((self.root / name).read_bytes(), b"custom")

    def test_local_changes_block_entire_update(self):
        self.put("AGENTS.md", b"local edit")
        with self.assertRaisesRegex(ValueError, "AGENTS.md"):
            self.run_update(apply=True)
        self.assertEqual((self.root / "core/catalog.py").read_bytes(), b"original")
        self.assertFalse((self.root / "core/extra.md").exists())

    def test_reject_release_writing_live_data(self):
        with self.assertRaisesRegex(ValueError, "unexpected file"):
            self.run_update(apply=True, asset=bundle("b" * 40, self.new, ("catalog/source.md", b"bad")))
        self.assertFalse((self.root / "catalog").exists())

    def test_missing_baseline_stops(self):
        self.receipt.unlink()
        with self.assertRaisesRegex(ValueError, "no installed-core manifest"):
            self.run_update(apply=True)

    def test_reject_symlink_to_non_vault_file(self):
        p = self.root / "core/catalog.py"
        p.unlink()
        p.symlink_to(self.receipt)
        with self.assertRaisesRegex(ValueError, "regular vault file"):
            self.run_update(apply=True)

    def test_rollback_if_second_write_fails(self):
        original = updater.write
        def failing(path, data):
            if path.name == "extra.md":
                raise OSError("test write failure")
            return original(path, data)
        with patch.object(updater, "write", side_effect=failing):
            with self.assertRaisesRegex(OSError, "test write failure"):
                self.run_update(apply=True)
        self.assertEqual((self.root / "core/catalog.py").read_bytes(), b"original")
        self.assertEqual(updater.decode(self.receipt.read_bytes())["commit"], "a" * 40)


if __name__ == "__main__":
    unittest.main()
