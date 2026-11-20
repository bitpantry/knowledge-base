import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "core" / "catalog.py"
EXAMPLES = ROOT / "tests" / "fixtures"

class CatalogTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.fixture = json.loads((EXAMPLES / "file-source.json").read_text())
        self.receipt = self.call("file", EXAMPLES / "file-source.json")
        self.sid = self.receipt["source_id"]
        self.note = self.root / self.receipt["note"]

    def call(self, *args, expected=0):
        p = subprocess.run([sys.executable,str(SCRIPT),"--root",str(self.root),*map(str,args)],
                           capture_output=True,text=True)
        self.assertEqual(p.returncode,expected,p.stderr or p.stdout)
        return json.loads(p.stdout) if p.stdout else p.stderr

    def candidate(self, **parts):
        path = self.root / "intake.json"
        path.write_text(json.dumps({**self.fixture, **parts}))
        return path

    def recovery(self, name):
        return EXAMPLES / "recovery" / (name + ".json")

    def test_repeat_search_cite_metadata_only(self):
        self.assertEqual(self.call("file", EXAMPLES / "file-source.json")["status"],"already filed")
        self.assertEqual(self.call("search","intake","operations")[0]["source_id"],self.sid)
        self.assertEqual(self.call("search","unmatched"),[])
        self.assertEqual(self.call("cite",self.sid)["pointer"],self.fixture["pointer"])
        self.assertEqual(self.call("check"),{"sources":1,"problems":[]})

    def test_title_only_in_body(self):
        raw=self.note.read_text(encoding="utf-8")
        _,header,body=raw.split("---\n",2)
        self.assertNotIn("title: ",header)
        self.assertEqual(body,"\n# "+self.fixture["title"]+"\n")
        self.assertEqual(self.call("cite",self.sid)["title"],self.fixture["title"])
        duplicate="title: "+json.dumps(self.fixture["title"])
        self.note.write_text(raw.replace("\n---\n","\n"+duplicate+"\n---\n",1),encoding="utf-8")
        self.assertIn("title belongs only in the body",self.call("cite",self.sid,expected=2))

    def test_concurrent_filing_and_interrupted_temp(self):
        fixture = self.candidate(native_id="concurrency-test")
        cmds = [sys.executable, str(SCRIPT), "--root", str(self.root), "file", str(fixture)]
        writers = [subprocess.Popen(cmds, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                   for _ in range(4)]
        results = []
        for writer in writers:
            out, err = writer.communicate(timeout=10)
            self.assertEqual(writer.returncode, 0, err)
            results.append(json.loads(out)["status"])
        self.assertEqual(results.count("filed"), 1)
        self.assertEqual(results.count("already filed"), 3)
        (self.note.parent/".catalog-tmp-incomplete").write_text("unfinished")
        self.assertEqual(self.call("check"), {"sources": 2, "problems": []})

    def test_no_silent_update_or_original_storage(self):
        prior = self.note.read_bytes()
        self.assertIn("same native source",self.call("file",self.candidate(title="changed"),expected=2))
        self.assertIn("metadata-only",self.call("file",self.candidate(body="raw transcript"),expected=2))
        self.assertIn("pending approval",self.call("file",self.candidate(capture="pending",pointer=None),expected=2))
        self.assertEqual(self.note.read_bytes(),prior)

    def test_metadata_revision_preserves_identity_and_requires_current_hash(self):
        path = self.root / "changes.json"
        path.write_text(json.dumps({"title":"Corrected title", "tags":["revised"], "date":"2026-10-21"}))
        result = self.call("revise",self.sid,path,"--if-revision",self.receipt["revision"])
        self.assertEqual(result["status"],"revised")
        self.assertEqual(result["source_id"],self.sid)
        self.assertEqual(result["pointer"],self.receipt["pointer"])
        self.assertNotEqual(result["revision"],self.receipt["revision"])
        self.assertEqual(self.call("search","revised")[0]["title"],"Corrected title")
        previous = self.note.read_bytes()
        self.assertIn("stale revision",self.call("revise",self.sid,path,"--if-revision",self.receipt["revision"],expected=2))
        self.assertEqual(self.call("revise",self.sid,path,"--if-revision",result["revision"])["status"],"unchanged")
        for restricted in ("pointer","native_id","namespace","kind","capture","source_id","fallback"):
            path.write_text(json.dumps({restricted:"forbidden"}))
            self.assertIn("metadata revision allows only",self.call("revise",self.sid,path,"--if-revision",result["revision"],expected=2))
        self.assertEqual(self.note.read_bytes(),previous)

    def test_separate_chat_fallback_validation_and_clear(self):
        chat = self.call("file",self.candidate(kind="chat",native_id="chat-revise"))
        self.call("set-fallback",self.sid,"--if-revision",self.receipt["revision"],"--pending",expected=2)
        pending = self.call("set-fallback",chat["source_id"],"--if-revision",chat["revision"],"--pending")
        self.call("set-fallback",chat["source_id"],"--if-revision",chat["revision"],"--clear",expected=2)
        self.call("set-fallback",chat["source_id"],"--if-revision",pending["revision"],
                  "--approve-pointer","https://example.invalid/file",expected=2)
        note = self.call("set-fallback",chat["source_id"],"--if-revision",pending["revision"],
                         "--approve-pointer","vault://keepers/example.pdf")
        self.assertEqual(note["source_id"],chat["source_id"])
        self.assertEqual(note["pointer"],chat["pointer"])
        updated = self.call("set-fallback",chat["source_id"],"--if-revision",note["revision"],"--clear")
        self.assertEqual(updated["revision"],chat["revision"])

    def test_moved_is_proposed_then_explicitly_applied(self):
        p = self.recovery("moved")
        before = self.note.read_bytes()
        draft = self.call("recover",self.sid,p)
        self.assertEqual(draft["decision"],"propose-repair")
        self.assertEqual(self.note.read_bytes(),before)
        self.call("repair",self.sid,p,"--approve-from",draft["from"],"--approve-to","https://example.invalid/wrong",expected=2)
        update = self.call("repair",self.sid,p,"--approve-from",draft["from"],"--approve-to",draft["to"])
        self.assertEqual(update["source_id"],self.sid)
        self.assertEqual(update["pointer"],draft["to"])
        self.assertEqual(self.call("check")["problems"],[])

    def test_ambiguous_offline_denied_keep(self):
        before = self.note.read_bytes()
        for status in ("ambiguous","offline","denied"):
            found = self.call("recover",self.sid,self.recovery(status))
            self.assertEqual(found["decision"],"keep")
        self.assertEqual(self.note.read_bytes(),before)

    def test_unknown_and_unauthorized_never_repair(self):
        p = self.root / "observed.json"
        moved = json.loads(self.recovery("moved").read_text())
        moved["authorized_search"] = False
        p.write_text(json.dumps(moved))
        self.assertEqual(self.call("recover",self.sid,p)["decision"],"keep")
        moved["authorized_search"] = True
        moved["candidates"][0]["native_id"] = "different-native-id"
        p.write_text(json.dumps(moved))
        self.assertEqual(self.call("recover",self.sid,p)["reason"],"no verified exact match")

    def test_chat_fallback_pending_or_approved_only(self):
        for native,status in [("chat1","pending"),("chat2","approved")]:
            fallback = {"status":status}
            if status == "approved":
                fallback["pointer"] = "vault://approved/example.pdf"
            chat = self.call("file",self.candidate(kind="chat",native_id=native,fallback=fallback))
            p = self.root / "missing.json"
            p.write_text(json.dumps({"attempted_pointer":chat["pointer"],"status":"missing","authorized_search":True}))
            result = self.call("recover",chat["source_id"],p)
            self.assertEqual(result["fallback"],fallback)
            self.assertEqual(result["decision"],"keep")
        self.assertIn("reserved",self.call("file",self.candidate(fallback={"status":"pending"}),expected=2))
        self.call("file",self.candidate(kind="chat",native_id="chat3",fallback={"status":"approved","pointer":"https://example.invalid/other"}),expected=2)

    def test_duplicate_and_broken_link_are_errors(self):
        shutil.copyfile(self.note,self.note.with_name("copy.md"))
        (self.root/"bad.md").write_text("[missing](nothing.md)")
        problems = self.call("check",expected=1)["problems"]
        self.assertTrue(any("duplicate ID" in p for p in problems),problems)
        self.assertTrue(any("broken internal link" in p for p in problems),problems)

    @unittest.skipUnless(shutil.which("git"),"Git not installed")
    def test_real_git_extension_scope_guard(self):
        def git(*args):
            subprocess.run(["git","-C",str(self.root),*args],check=True,capture_output=True)
        git("init","-q")
        git("add",".")
        git("-c","user.name=Fixture","-c","user.email=fixture@example.invalid","commit","-qm","test baseline")
        ext = self.root / "extensions" / "demo"
        ext.mkdir(parents=True)
        (ext/"EXTENSION.md").write_text("# Synthetic extension")
        self.assertEqual(self.call("check-scope","demo")["allowed"],1)
        for filename in ("core/catalog.py","START-HERE.md","AGENTS.md","tests/test_core.py",
                         "examples/new.md","catalog/foreign.md","extensions/another/EXTENSION.md"):
            p = self.root / filename
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text("out-of-scope change")
            denied = self.call("check-scope","demo",expected=2)
            self.assertIn(filename, denied)
            p.unlink()
        self.note.write_text("changed live data")
        self.assertIn("outside its boundary",self.call("check-scope","demo",expected=2))

if __name__ == "__main__":
    unittest.main()
