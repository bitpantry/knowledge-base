"""Synthetic-only tests for optional nonexclusive extension interpretation."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent.parent
CLI=ROOT/"core"/"reconcile_extension.py"

class ReconciliationTest(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.start=self.root/"START-HERE.md"
        self.start.write_text("# Test vault\n\n## For a fresh agent\n\nOriginal startup.\n")
        self.model="modules/sales/MODEL.md"
        self.plan=self.root/"plan.json"
        self.source=self.write("source.json",{"kind":"artifact","namespace":"synthetic-project",
            "native_id":"service-interview","title":"Fictional service interview","date":"2026-11-01",
            "pointer":"https://example.invalid/interview","capture":"approved"})
        source=self.run_cli(ROOT/"core"/"catalog.py","file",self.source)
        self.underlying=source
        self.record=self.root/source["note"]
        self.concept=self.run_cli(ROOT/"core"/"concepts.py","add-concept",self.write("concept.json",{
            "id":"con-equipment-renewal","name":"Equipment renewal","aliases":[],"context":"Synthetic shared workshop"}))
        self.evidence=self.run_cli(ROOT/"core"/"concepts.py","add-evidence",self.write("evidence.json",{
            "kind":"claim","source_id":source["source_id"],"observed_label":"Equipment renewal",
            "locator":{"type":"page","value":"3"},"concept_id":self.concept["id"],"scope":"workshop",
            "question":"needs-review","value":"A workshop member requested a conversation about renewal"}))

    def write(self,name,data):
        p=self.root/name; p.write_text(json.dumps(data)); return p

    def run_cli(self,tool,*args,expected=0):
        p=subprocess.run([sys.executable,"-B",str(tool),"--root",str(self.root),*map(str,args)],
                         capture_output=True,text=True)
        self.assertEqual(p.returncode,expected,p.stderr or p.stdout)
        if p.returncode:
            return p.stderr.strip()
        return json.loads(p.stdout)

    def extension(self,slug,model):
        root=self.root/"extensions"/slug
        p=root/self.model
        p.parent.mkdir(parents=True,exist_ok=True)
        (root/"EXTENSION.md").write_text("# "+slug.title()+"\n\n[Model definition]("+self.model+")\n")
        p.write_text("# "+model+"\n\nSynthetic contract.\n")
        return p

    def row(self,extension,model,state="match"):
        return {"extension":extension,"model":self.model,"model_id":model.lower(),"model_name":model,
                "record_type":"concept","record_id":self.concept["id"],"state":state,
                "reason":"Synthetic assessment cites evidence "+self.evidence["id"]}

    def run_plan(self,rows):
        self.plan.write_text(json.dumps(rows))
        return self.run_cli(CLI,"preview",self.plan)

    def apply(self,p,expected=0):
        return self.run_cli(CLI,"apply",self.plan,"--if-preview",p["preview"],expected=expected)

    def test_two_namespaces_preview_apply_and_idempotence(self):
        self.extension("service-planning","Opportunity")
        self.extension("community-support","Lead")
        baseline={p:p.read_bytes() for p in (self.record,self.root/self.concept["note"],self.root/self.evidence["note"],self.start)}
        a=self.row("service-planning","Opportunity")
        b=self.row("community-support","Lead")
        plan=self.run_plan([a,b])
        self.assertEqual(plan["new_matches"],2)
        self.assertEqual(plan["counts"]["underlying_records_with_overlap"],1)
        self.assertEqual(plan["items"][0]["overlaps"][0]["extension"],"community-support")
        self.assertFalse((self.root/"knowledge"/"interpretations").exists())
        result=self.apply(plan)
        self.assertEqual(len(result["written"]),2)
        self.assertTrue(all(p.read_bytes()==v for p,v in baseline.items()))
        shown=self.run_cli(CLI,"list","concept",self.concept["id"])
        self.assertEqual({x["model_name"] for x in shown},{"Lead","Opportunity"})
        self.assertEqual(self.run_cli(CLI,"check"),{"interpretations":2})
        self.assertFalse(self.run_cli(ROOT/"core"/"catalog.py","check")["problems"])
        cited=self.run_cli(ROOT/"core"/"concepts.py","cite",self.evidence["id"])
        self.assertEqual(cited["source_id"],self.underlying["source_id"])
        self.assertEqual(cited["locator"]["value"],"3")
        self.assertIn("preview changed",self.apply(plan,expected=2))
        new=self.run_plan([a,b])
        self.assertEqual({x["status"] for x in new["items"]},{"already-recorded"})
        self.assertEqual(self.apply(new)["written"],[])
        altered=self.run_plan([{**a,"reason":"different proposal"}])
        self.assertEqual(altered["items"][0]["status"],"needs-review-existing")
        self.assertEqual(self.apply(altered)["written"],[])

    def test_empty_ambiguous_and_no_match_do_not_write(self):
        self.extension("service-planning","Opportunity")
        row=self.row("service-planning","Opportunity")
        for items in ([], [{**row,"state":"ambiguous"}], [{**row,"state":"no-match"}]):
            before=self.start.read_bytes()
            preview=self.run_plan(items)
            self.assertEqual(preview["new_matches"],0)
            self.assertEqual(self.apply(preview)["written"],[])
            self.assertEqual(self.start.read_bytes(),before)
            self.assertFalse((self.root/"knowledge"/"interpretations").exists())

    def test_input_changes_stale_the_approval_and_bare_wire_does_not_classify(self):
        model=self.extension("service-planning","Opportunity")
        p=subprocess.run([sys.executable,"-B",str(ROOT/"core"/"wire_extension.py"),"service-planning",
                          "--root",str(self.root)],capture_output=True,text=True)
        self.assertEqual((p.returncode,p.stdout.strip()),(0,"wired"))
        self.assertFalse((self.root/"knowledge"/"interpretations").exists())
        plan=self.run_plan([self.row("service-planning","Opportunity")])
        model.write_text("# Revised model\n")
        self.assertIn("preview changed",self.apply(plan,expected=2))
        self.assertFalse((self.root/"knowledge"/"interpretations").exists())
        self.plan.write_text(json.dumps([{**self.row("service-planning","Opportunity"),
                                         "model":"../other/MODEL.md"}]))
        self.assertIn("relative",self.run_cli(CLI,"preview",self.plan,expected=2))

if __name__=="__main__":
    unittest.main()
