import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"core"))
import update
import vault

RELEASE = {"tag_name":"beta-test"}
SLUG = "account-management"


def zipped(receipt_file, receipt, files):
    data = io.BytesIO()
    with zipfile.ZipFile(data,"w") as z:
        z.writestr(receipt_file,update.encode(receipt))
        for p, v in files.items():
            z.writestr(p,v)
    return data.getvalue()


class VaultTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root/"extensions").mkdir()
        self.start = self.put("START-HERE.md",b"# Private vault\n\n## Extensions\n\nNo extensions are wired by default.\n\n## For a fresh agent\n\nKeep me.\n")
        self.core_files = {p:b"baseline" for p in update.REQUIRED}
        for p,body in self.core_files.items():
            self.put(p,body)
        self.put(update.MANIFEST,update.encode(update.manifest("1"*40,self.core_files)))
        self.ext_files = {"EXTENSION.md":b"# Account Management\n", "modules/people/MODEL.md":b"Person rules\n"}
        self.assets = {}
        self.ext_package("2"*40,self.ext_files)

    def put(self, name, data):
        p = self.root/name
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes(data)
        return p

    def ext_package(self, commit, files):
        self.assets[vault.package_name(SLUG)] = zipped(vault.RECEIPT,
            vault.extension_receipt(SLUG,commit,files),files)

    def run_vault(self, action, slug=None, token=None):
        with contextlib.redirect_stdout(io.StringIO()):
            return vault.run(self.root,action,slug,RELEASE,token,lambda _,name:self.assets[name])

    def install(self):
        self.run_vault("install",SLUG,self.run_vault("install",SLUG))

    def core_package(self):
        core = {**self.core_files,"core/catalog.py":b"updated"}
        self.assets[update.ASSET] = zipped(update.MANIFEST,update.manifest("3"*40,core),core)

    def test_install_wires_only_on_apply_and_never_matches(self):
        original = self.start.read_bytes()
        evidence = self.put("knowledge/evidence/existing.md",b"keep")
        token = self.run_vault("install",SLUG)
        self.assertEqual(self.start.read_bytes(),original)
        self.assertFalse((self.root/"extensions"/SLUG).exists())
        with self.assertRaisesRegex(ValueError,"stale"):
            self.run_vault("install",SLUG,"bad-token")
        self.run_vault("install",SLUG,token)
        self.assertIn(b"[Account Management](extensions/account-management/EXTENSION.md)",self.start.read_bytes())
        self.assertIn(b"Keep me.",self.start.read_bytes())
        self.assertNotIn(b"No extensions",self.start.read_bytes())
        self.assertEqual(evidence.read_bytes(),b"keep")
        self.assertFalse((self.root/"knowledge/interpretations").exists())
        self.assertEqual(vault.installed(self.root),[SLUG])

    def test_extension_then_combined_update_preserves_records(self):
        self.install()
        record = self.put(f"extensions/{SLUG}/records/people/person-example.md",b"private")
        local = self.put("extensions/manual/EXTENSION.md",b"# Local drop-in\n")
        self.ext_package("3"*40,{**self.ext_files,"modules/people/MODEL.md":b"revised"})
        self.run_vault("update",SLUG,self.run_vault("update",SLUG))
        self.assertEqual((self.root/"core/catalog.py").read_bytes(),b"baseline")
        self.core_package()
        self.ext_package("4"*40,{**self.ext_files,"modules/people/MODEL.md":b"last revision"})
        self.run_vault("update",None,self.run_vault("update"))
        self.assertEqual(record.read_bytes(),b"private")
        self.assertEqual(local.read_bytes(),b"# Local drop-in\n")
        self.assertEqual((self.root/f"extensions/{SLUG}/modules/people/MODEL.md").read_bytes(),b"last revision")
        self.assertEqual((self.root/"core/catalog.py").read_bytes(),b"updated")
        self.assertEqual(vault.installed(self.root),[SLUG])

    def test_local_edit_blocks_entire_combined_update(self):
        self.install()
        self.core_package()
        self.put(f"extensions/{SLUG}/modules/people/MODEL.md",b"local edit")
        with self.assertRaisesRegex(ValueError,"locally changed"):
            self.run_vault("update")
        self.assertEqual((self.root/"core/catalog.py").read_bytes(),b"baseline")

    def test_reject_package_with_live_records(self):
        self.ext_package("3"*40,{**self.ext_files,"records/person.md":b"not deployable"})
        with self.assertRaisesRegex(ValueError,"invalid extension package"):
            self.run_vault("install",SLUG)

    def test_install_rolls_back_on_write_failure(self):
        token = self.run_vault("install",SLUG)
        expected = self.start.read_bytes()
        original = vault.write
        def fail(path, data):
            if path.name == "START-HERE.md":
                raise OSError("blocked write")
            original(path,data)
        with patch.object(vault,"write",side_effect=fail):
            with self.assertRaisesRegex(OSError,"blocked write"):
                self.run_vault("install",SLUG,token)
        self.assertFalse((self.root/"extensions"/SLUG).exists())
        self.assertEqual(self.start.read_bytes(),expected)


if __name__ == "__main__":
    unittest.main()
