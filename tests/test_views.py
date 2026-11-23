from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
import views


class ViewCollections(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        d = self.base / "extensions/account-management"
        d.mkdir(parents=True)
        (d / "VIEWS.md").write_text("# Views\n- People.md\n- people/\n")
        self.collection = self.base / "views/account-management/people"

    def publish(self, bodies):
        return views.publish_collection(self.base, "account-management", "people", bodies)

    def test_full_collection_keeps_manual_files_and_skips_unchanged_pages(self):
        bodies = {f"person-{i:03}.md": "# River Finch" for i in range(100)}
        paths = self.publish(bodies)
        stable = paths["person-001.md"]
        mtime = stable.stat().st_mtime_ns
        hand = self.collection / "handwritten.md"
        hand.write_text("a person wrote this")
        alien = self.collection / "alien.md"
        alien.write_text("<!-- Generated human view: other/people. Not canonical knowledge. -->\n")
        bodies["person-003.md"] = "# Renamed person"
        del bodies["person-000.md"]
        self.assertEqual(self.publish(bodies)["person-003.md"], paths["person-003.md"])
        self.assertFalse(paths["person-000.md"].exists())
        self.assertEqual(stable.stat().st_mtime_ns, mtime)
        self.assertIn("Renamed person", paths["person-003.md"].read_text())
        self.assertTrue(hand.is_file())
        self.assertTrue(alien.is_file())
        views.publish(self.base, "account-management", "People.md", "# People")
        index = (self.base / "views/README.md").read_text()
        self.assertIn("account-management/People.md", index)
        self.assertNotIn("person-", index)

    def test_preflight_refuses_collision_without_partial_batch(self):
        first = self.publish({"person-a.md": "# Original"})["person-a.md"]
        (self.collection / "person-b.md").write_text("manual")
        (self.collection / "PERSON-C.md").write_text("manual")
        outside = self.base / "not-for-views.md"
        outside.write_text("unchanged")
        (self.collection / "person-d.md").symlink_to(outside)
        for member in ("person-b.md", "person-c.md", "person-d.md", "../outside.md", "nested/person.md"):
            with self.subTest(member=member), self.assertRaises(ValueError):
                self.publish({"person-a.md": "# Should not write", member: "# Unsafe"})
            self.assertIn("# Original", first.read_text())
        self.assertEqual(outside.read_text(), "unchanged")

    def test_refuses_undeclared_collection_and_symlink_folder(self):
        with self.assertRaises(ValueError):
            views.publish_collection(self.base, "account-management", "other", {})
        self.collection.parent.mkdir(parents=True)
        self.collection.symlink_to(self.base / "extensions", target_is_directory=True)
        with self.assertRaises(ValueError):
            self.publish({"person-a.md": "# unsafe"})

    def test_footer_markers_regenerate_index_and_prune_only_owned_members(self):
        header = "<!-- Generated human view: account-management/people. Not canonical knowledge. -->"
        self.collection.mkdir(parents=True)
        legacy = self.collection / "person-old.md"
        legacy.write_text(header + "\n\n# Old")
        keep = self.collection / "person-new.md"
        keep.write_text("# Current\n\n" + header + "\n")
        manual = self.collection / "manual.md"
        manual.write_text("# Manual\n" + header + "\nThis is not a boundary marker.")
        binary = self.collection / "manual-binary.md"
        binary.write_bytes(b"\xff")
        self.publish({"person-new.md": "# Updated"})
        self.assertEqual(binary.read_bytes(), b"\xff")
        self.assertFalse(legacy.exists())
        self.assertTrue(manual.exists())
        self.assertTrue(keep.read_text().endswith(header + "\n"))
        views.publish(self.base, "account-management", "People.md", "# People")
        index = self.base / "views/README.md"
        self.assertTrue(index.read_text().endswith(views.HEADER + "\n"))
        views.publish(self.base, "account-management", "People.md", "# People again")
        self.assertEqual(index.read_text().count("account-management/People.md"), 1)

    def test_all_standalone_comments_default_to_footer_and_canvas_is_indexed(self):
        declaration=self.base/'extensions/account-management/VIEWS.md'
        declaration.write_text(declaration.read_text()+'- Org Chart.canvas\n')
        p=views.publish(self.base,'account-management','People.md','<!-- Refreshed today -->\n\n# Content\n\n<!-- Second comment -->\nText')
        body=p.read_text()
        self.assertTrue(body.startswith('# Content'))
        self.assertLess(body.index('Text'),body.index('<!-- Refreshed'))
        self.assertTrue(body.endswith(views.HEADER+'\n'))
        document={'nodes':[],'edges':[]}
        views.publish_canvas(self.base,'account-management','Org Chart.canvas',document)
        index=self.base/'views/README.md'
        self.assertIn('account-management/Org%20Chart.canvas',index.read_text())
        index.unlink()
        views.publish_canvas(self.base,'account-management','Org Chart.canvas',document)
        self.assertIn('account-management/Org%20Chart.canvas',index.read_text())
