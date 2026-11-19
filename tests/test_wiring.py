"""Wiring tests use disposable vaults and never touch live data."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

TOOL=Path(__file__).resolve().parent.parent/"core"/"wire_extension.py"

class WiringTest(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.start=self.root/"START-HERE.md"
        self.stub="# Start\n\n## For a fresh agent\n\nOriginal guidance.\n"
        self.start.write_text(self.stub)
        self.ext=self.root/"extensions"/"sample-kit"/"EXTENSION.md"

    def drop(self):
        self.ext.parent.mkdir(parents=True,exist_ok=True)
        self.ext.write_text("# Sample Kit\n\nFollow the module instructions.\n")

    def wire(self,expected=0,slug="sample-kit"):
        p=subprocess.run([sys.executable,"-B",str(TOOL),slug,"--root",str(self.root)],
                         text=True,capture_output=True)
        self.assertEqual(p.returncode,expected,p.stderr or p.stdout)
        return (p.stdout or p.stderr).strip()

    def test_drop_in_is_visible_without_start_page_mutation(self):
        self.drop()
        self.assertEqual(self.start.read_text(),self.stub)
        self.assertIn("Follow the module instructions.",self.ext.read_text())

    def test_named_relative_entry_and_idempotence(self):
        self.drop()
        self.assertEqual(self.wire(),"wired")
        content=self.start.read_bytes()
        self.assertEqual(content.count(b"- [Sample Kit](extensions/sample-kit/EXTENSION.md)"),1)
        self.assertIn(b"Original guidance.",content)
        self.assertEqual(self.wire(),"already wired")
        self.assertEqual(self.start.read_bytes(),content)

    def test_repair_deduplicates_without_affecting_other_entry(self):
        self.drop()
        self.start.write_text(self.stub.replace("## For a fresh agent",
            "## Extensions\n\n- [Sample Kit](extensions/old/OLD.md)\n"
            "- [Old name](./extensions/sample-kit/README.md)\n"
            "- [Another Kit](extensions/another/EXTENSION.md)\n\n## For a fresh agent"))
        self.assertEqual(self.wire(),"wired")
        page=self.start.read_text()
        self.assertEqual(page.count("- [Sample Kit](extensions/sample-kit/EXTENSION.md)"),1)
        self.assertNotIn("extensions/old/OLD.md",page)
        self.assertNotIn("extensions/sample-kit/README.md",page)
        self.assertIn("- [Another Kit](extensions/another/EXTENSION.md)",page)

    def test_missing_and_same_name_other_existing_target_stop(self):
        self.assertIn("No copied extension",self.wire(expected=2))
        self.assertEqual(self.start.read_text(),self.stub)
        self.drop()
        (self.root/"other.md").write_text("# Existing other doc\n")
        ambiguous=self.stub.replace("## For a fresh agent",
                                     "## Extensions\n\n- [Sample Kit](other.md)\n\n## For a fresh agent")
        self.start.write_text(ambiguous)
        self.assertIn("different existing file",self.wire(expected=2))
        self.assertEqual(self.start.read_text(),ambiguous)

if __name__=="__main__":
    unittest.main()
