"""Synthetic-only end-to-end tests: never use the live vault."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent.parent
SOURCE=ROOT/"core"/"catalog.py"
KB=ROOT/"core"/"concepts.py"

class ConceptsTest(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.serial=0
        self.con="con-system-a"
        self.scope="dispatch-intake"
        self.question="performs-routing"

    def run_cli(self,cmd,*args,expected=0):
        p=subprocess.run([sys.executable,"-B",str(cmd),"--root",str(self.root),*map(str,args)],
                         text=True,capture_output=True)
        self.assertEqual(p.returncode,expected,p.stderr or p.stdout)
        return json.loads(p.stdout) if p.stdout else p.stderr

    def input(self,d):
        self.serial+=1
        f=self.root/(str(self.serial)+".json")
        f.write_text(json.dumps(d))
        return f

    def src(self,name,when,kind="artifact"):
        return self.run_cli(SOURCE,"file",self.input({
          "kind":kind,"date":when,"title":name,"native_id":name.lower().replace(" ","-"),
          "namespace":"synthetic-lab","capture":"approved",
          "pointer":"https://example.invalid/"+name.lower().replace(" ","-")
        }))

    def c(self,cid=None,name="System A",aliases=None,context="Dispatch intake"):
        return self.run_cli(KB,"add-concept",self.input({"id":cid or self.con,"name":name,
                        "aliases":aliases or [],"context":context}))

    def e(self,src,label="System A",expected=0,**data):
        note={"source_id":src["source_id"],"observed_label":label,"kind":"mention",
              "locator":{"type":"page","value":"10"}}
        note.update(data)
        return self.run_cli(KB,"add-evidence",self.input(note),expected=expected)

    def claim(self,src,value,scope=None,question=None):
        return self.e(src,concept_id=self.con,kind="claim",scope=scope or self.scope,
                      question=question or self.question,value=value,
                      locator={"type":"timestamp","value":"00:03:15","speaker":"Synthetic Operator"})

    def view(self,mode="review",*flags):
        return self.run_cli(KB,mode,self.con,self.scope,self.question,*flags)

    def choose(self,action,when,revision,*flags,expected=0):
        return self.run_cli(KB,action,self.con,self.scope,self.question,"--date",when,
                            "--if-revision",revision,"--user-explicit",*flags,expected=expected)

    def test_day_1_to_50_full_cycle(self):
        rfp=self.src("Fictional RFP","2026-01-01")
        self.c(aliases=["SA"])
        cited=self.e(rfp,concept_id=self.con,locator={"type":"page","value":"10","section":"Operational Interfaces"})
        self.assertEqual(cited,{"status":"filed","id":cited["id"],"note":cited["note"]})
        self.assertEqual(self.run_cli(KB,"cite",cited["id"])["locator"]["section"],"Operational Interfaces")
        self.assertEqual(self.view()["claims"],[])
        self.assertEqual(self.view("answer")["status"],"open")
        day8=self.src("Operator Interview","2026-01-08",kind="transcript")
        chosen=self.claim(day8,"System A performs routing")
        self.assertEqual(self.claim(day8,"System A performs routing")["status"],"already filed")
        self.choose("skip","2026-01-09",self.view()["revision"])
        self.assertEqual(self.view()["status"],"open")
        self.assertIsNone(self.view()["current"])
        first=self.choose("confirm","2026-01-12",self.view()["revision"],"--claim-id",chosen["id"])
        answer=self.view("answer")
        self.assertNotIn("claims",answer)
        self.assertEqual(answer["current"]["claim"]["locator"]["speaker"],"Synthetic Operator")
        self.assertEqual(answer["current"]["claim"]["source_pointer"],day8["pointer"])
        note_before=(self.root/chosen["note"]).read_bytes()
        day42=self.src("Followup Interview","2026-02-11",kind="transcript")
        self.claim(day42,"Different unrelated fact",scope="billing")
        self.assertEqual(self.view("answer")["status"],"confirmed")
        latest=self.claim(day42,"System A no longer performs routing")
        open_review=self.view()
        self.assertEqual(open_review["status"],"confirmed-with-conflict")
        self.assertEqual(open_review["confirmation_id"],first["id"])
        self.assertEqual(open_review["unreviewed_disagreements"][0]["id"],latest["id"])
        self.assertIn("explicitly supersede",self.choose("confirm","2026-02-19",open_review["revision"],
                                                        "--claim-id",latest["id"],expected=2))
        final=self.choose("confirm","2026-02-19",open_review["revision"],"--claim-id",latest["id"],"--supersedes",first["id"])
        end=self.view("answer","--trace")
        self.assertEqual((end["status"],end["confirmation_id"]),("confirmed",final["id"]))
        self.assertEqual(end["current"]["claim"]["id"],latest["id"])
        self.assertIn(first["id"],end["history"])
        self.assertIn(chosen["id"],[e["id"] for e in end["claims"]])
        self.assertEqual((self.root/chosen["note"]).read_bytes(),note_before)
        self.assertEqual(self.run_cli(KB,"check"),{"concepts":1,"evidence":4,"decisions":3})
        self.assertFalse(self.run_cli(SOURCE,"check")["problems"])

    def test_compact_concept_and_evidence_store_values_once(self):
        concept=self.c(context="A single description for this concept")
        note=(self.root/concept["note"]).read_text(encoding="utf-8")
        _,header,body=note.split("---\n",2)
        self.assertEqual(body,"\n# System A\n\nA single description for this concept\n")
        self.assertNotIn("name: ",header)
        self.assertNotIn("context: ",header)
        self.assertNotIn("\nid: ",header)
        self.assertEqual(note.count(concept["id"]),1)
        self.assertEqual(self.run_cli(KB,"find","System A")["concepts"][0]["context"],
                         "A single description for this concept")
        src=self.src("Fictional Interview","2026-01-08","transcript")
        text="System A routes urgent requests via Québec"
        claim=self.claim(src,text)
        p=self.root/claim["note"]
        _,header,body=p.read_text(encoding="utf-8").split("---\n",2)
        self.assertNotIn("value: ",header)
        self.assertNotIn("00:03:15",body)
        self.assertEqual(body,"\n"+text+"\n")
        self.assertEqual(self.run_cli(KB,"cite",claim["id"])["value"],text)

    def test_reject_legacy_evidence_and_concept_headers(self):
        concept=self.c()
        src=self.src("Fictional Interview","2026-01-08","transcript")
        claim=self.claim(src,"The claim belongs in the body")
        p=self.root/claim["note"]
        compact=p.read_text(encoding="utf-8")
        p.write_text(compact.replace("\n---\n","\nvalue: \"The claim belongs in the body\"\n---\n",1),
                     encoding="utf-8")
        self.assertIn("only in the body",self.run_cli(KB,"cite",claim["id"],expected=2))
        p.write_text(compact,encoding="utf-8")
        p=self.root/concept["note"]
        p.write_text(p.read_text(encoding="utf-8").replace("\n---\n","\nname: \"System A\"\n---\n",1),
                     encoding="utf-8")
        self.assertIn("duplicate concept metadata",self.run_cli(KB,"find","System A",expected=2))

    def test_acronym_ambiguity_and_prior_link_preserved(self):
        src=self.src("Fictional Notes","2026-01-01")
        self.c("con-dcs-dispatch","Dispatch Control Service",["DCS"],"Dispatch")
        original=self.e(src,"DCS",concept_id="con-dcs-dispatch")
        self.c("con-dcs-document","Document Capture Suite",["DCS"],"Document capture")
        self.assertTrue(self.run_cli(KB,"find","DCS")["ambiguous"])
        self.assertEqual(len(self.run_cli(KB,"find","DCS","--context","Document capture")["concepts"]),1)
        self.assertIn("ambiguous label",self.e(src,"DCS",concept_id="con-dcs-document",expected=2))
        unknown=self.e(src,"DCS",candidates=["con-dcs-dispatch","con-dcs-document"])
        self.assertIsNone(self.run_cli(KB,"cite",unknown["id"])["concept_id"])
        accepted=self.e(src,"DCS",concept_id="con-dcs-document",context="Document capture")
        self.assertEqual(self.run_cli(KB,"cite",accepted["id"])["concept_id"],"con-dcs-document")
        self.assertEqual(self.run_cli(KB,"cite",original["id"])["concept_id"],"con-dcs-dispatch")
        self.assertEqual(self.run_cli(KB,"check")["evidence"],3)

    def test_novel_transcript_topic_after_only_rfp(self):
        rfp=self.src("Fictional RFP","2026-01-01")
        self.c()
        self.e(rfp,concept_id=self.con)
        src=self.src("Community Interview","2026-01-10","transcript")
        unknown=self.e(src,"Shared Tool Cage",context="Volunteer equipment checkout",
                        locator={"type":"timestamp","value":"00:07:02","speaker":"Synthetic Volunteer"})
        self.assertEqual(self.run_cli(KB,"find","Tool Cage")["evidence"][0]["id"],unknown["id"])
        self.c("con-tool-cage","Shared Tool Cage",context="Volunteer equipment checkout")
        self.e(src,"Shared Tool Cage",concept_id="con-tool-cage",kind="claim",scope="volunteer-ops",
               question="holds-equipment",value="The cage stores shared tools",
               locator={"type":"timestamp","value":"00:07:02","speaker":"Synthetic Volunteer"})
        hit=self.run_cli(KB,"find","Shared Tool Cage")
        self.assertEqual(len(hit["evidence"]),2)
        self.assertEqual(hit["concepts"][0]["id"],"con-tool-cage")

    def test_stale_review_invalid_provenance_and_scope(self):
        self.c()
        src=self.src("Fictional Interview","2026-01-01","transcript")
        self.e({"source_id":"src-000000000000000000000000"},concept_id=self.con,expected=2)
        self.e(src,concept_id=self.con,locator={"type":"page"},expected=2)
        rejected=self.e(src,concept_id=self.con,kind="mention",value="hidden claim",expected=2)
        self.assertIn("does not assert",rejected)
        mention=self.e(src,concept_id=self.con)
        first=self.claim(src,"Initial value")
        other=self.claim(src,"Not the same question",question="other-question")
        review=self.view()
        for invalid in [mention,other]:
            self.assertIn("choose a sourced claim",self.choose("confirm","2026-01-03",review["revision"],
                                                              "--claim-id",invalid["id"],expected=2))
        self.claim(src,"Disagrees")
        self.assertIn("stale",self.choose("confirm","2026-01-03",review["revision"],"--claim-id",first["id"],expected=2))
        latest=self.view()["revision"]
        self.run_cli(SOURCE,"revise",src["source_id"],self.input({"date":"2026-01-02"}),"--if-revision",src["revision"])
        self.assertIn("stale",self.choose("confirm","2026-01-03",latest,"--claim-id",first["id"],expected=2))
        self.assertEqual(self.view()["status"],"open")
        self.assertIn("user-explicit",self.run_cli(KB,"confirm",self.con,self.scope,self.question,
                     "--date","2026-01-03","--claim-id",first["id"],"--if-revision",self.view()["revision"],expected=2))

if __name__=="__main__":
    unittest.main()
