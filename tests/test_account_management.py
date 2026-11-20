"""Account Management portable tests, against shared core with fictional content."""
from pathlib import Path
import json
import shutil
import subprocess
import sys
import tempfile
import unittest

ENG=Path(__file__).resolve().parent.parent

class AccountManagementTest(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.extension=self.root/"extensions"/"account-management"
        shutil.copytree(ENG/"core",self.root/"core",ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ENG/"extensions/account-management",self.extension,
                        ignore=shutil.ignore_patterns("records","__pycache__"))
        self.cli=self.extension/"account.py"
        self.serial=0

    def invoke(self,p,*args,code=0):
        result=subprocess.run([sys.executable,"-B",str(p),*map(str,args)],cwd=self.root,
                              text=True,capture_output=True)
        self.assertEqual(result.returncode,code,result.stdout or result.stderr)
        return json.loads(result.stdout) if code==0 else result.stderr.strip()

    def write(self,p,*args,d):
        self.serial+=1
        f=self.root/(f"input-{self.serial}.json")
        f.write_text(json.dumps(d))
        return self.invoke(p,*args,f)

    def record(self,kind,**overrides):
        d={"id":kind+"-fixture","title":kind.title()+" placeholder","account":"fictional-workshop"}
        if kind=="interaction":
            d.update(date="2026-11-20",person_ids=["person-fixture"])
        d.update(overrides)
        return d

    def test_playable_relationships_and_pipeline_with_shared_citation(self):
        src=self.write(self.root/"core"/"catalog.py","file",d={
            "kind":"artifact","namespace":"fictional-test","native_id":"workshop-note","title":"Workshop note",
            "date":"2026-11-20","pointer":"https://example.invalid/notes/workshop","capture":"approved"})
        ev=self.write(self.root/"core"/"concepts.py","add-evidence",d={
            "source_id":src["source_id"],"locator":{"type":"page","value":"2"},"observed_label":"Workshop renewal",
            "kind":"mention","context":"Fictional workshop fixture"})
        snapshot={p:p.read_bytes() for folder in ("catalog","knowledge") for p in (self.root/folder).rglob("*.md")}
        person=self.write(self.cli,"add","person",d=self.record("person"))
        interaction=self.write(self.cli,"add","interaction",d=self.record("interaction",evidence_ids=[ev["id"]]))
        lead_input=self.record("lead",person_ids=[person["id"]],interaction_ids=[interaction["id"]],
                               notes="Fictional renewal follow-up.",source_ids=[src["source_id"]])
        lead=self.write(self.cli,"add","lead",d=lead_input)
        self.assertEqual(self.write(self.cli,"add","lead",d=lead_input)["result"],"already filed")
        self.assertEqual(self.invoke(self.cli,"list","lead","--account","fictional-other"),[])
        self.assertEqual(self.invoke(self.cli,"list","lead","--account","fictional-workshop")[0]["id"],lead["id"])
        got=self.invoke(self.cli,"show","interaction",interaction["id"],"--trace")
        self.assertEqual(got["citations"]["evidence"][0]["locator"],{"type":"page","value":"2"})
        self.assertEqual(got["citations"]["evidence"][0]["source_pointer"],src["pointer"])
        self.assertEqual(self.invoke(self.cli,"show","lead",lead["id"],"--trace")["citations"]["source"][0]["source_id"],src["source_id"])
        updated=self.invoke(self.cli,"set-lead-status",lead["id"],"qualifying","--if-revision",lead["revision"])
        self.assertEqual(updated["status"],"qualifying")
        self.assertIn("stale",self.invoke(self.cli,"set-lead-status",lead["id"],"closed","--if-revision",lead["revision"],code=2))
        self.assertEqual(self.invoke(self.cli,"check"),{"people":1,"interactions":1,"leads":1})
        lead_md=(self.root/lead["note"]).read_text()
        self.assertEqual(lead_md.count(lead_input["notes"]),1)
        self.assertEqual(lead_md.count(lead_input["title"]),1)
        self.assertTrue(all(p.read_bytes()==old for p,old in snapshot.items()))

    def test_reject_unknown_cross_account_or_conflicting_reference(self):
        self.write(self.cli,"add","person",d=self.record("person"))
        self.write(self.cli,"add","interaction",d=self.record("interaction"))
        def reject(kind,d,piece):
            note=self.root/"rejected.json"; note.write_text(json.dumps(d))
            self.assertIn(piece,self.invoke(self.cli,"add",kind,note,code=2))
        reject("interaction",self.record("interaction",id="interaction-other",account="fictional-other"),"another account")
        reject("lead",self.record("lead",account="fictional-other",interaction_ids=["interaction-fixture"]),"another account")
        reject("lead",self.record("lead",source_ids=["src-"+("0"*24)]),"not found")
        reject("lead",self.record("lead",evidence_ids=["ev-"+("0"*24)]),"unknown core evidence")
        reject("person",self.record("person",title="Different name"),"different contents")
        self.assertEqual(self.invoke(self.cli,"check"),{"people":1,"interactions":1,"leads":0})

if __name__=="__main__":
    unittest.main()
