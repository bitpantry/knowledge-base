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

    def test_generic_relationship_trace_from_different_sources(self):
        def source(native,kind):
            return self.write(self.root/"core/catalog.py","file",d={
              "kind":kind,"namespace":"fictional-test","native_id":native,"title":native,
              "date":"2026-11-20","pointer":"https://example.invalid/"+native,"capture":"approved"})
        def evidence(src,locator):
            return self.write(self.root/"core/concepts.py","add-evidence",d={
              "source_id":src["source_id"],"locator":locator,"observed_label":"Workshop renewal",
              "kind":"mention","context":"Fictional workshop fixture"})
        mail=source("fictional-introduction","email")
        memo=source("fictional-scope-note","artifact")
        introduction=evidence(mail,{"type":"message","value":"message-01"})
        confirmation=evidence(memo,{"type":"page","value":"3"})
        snapshot={p:p.read_bytes() for area in ("catalog","knowledge/evidence") for p in (self.root/area).rglob("*.md")}
        person=self.write(self.cli,"add","person",d=self.record("person",title="Fictional Coordinator"))
        interaction=self.write(self.cli,"add","interaction",d=self.record("interaction",source_ids=[mail["source_id"]]))
        lead=self.write(self.cli,"add","lead",d=self.record("lead",person_ids=[person["id"]]))
        tool=self.root/"core/model_store.py"
        account=person["account"]
        self.assertEqual(person["note"],"knowledge/records/person-fixture.md")
        self.assertEqual(self.invoke(tool,"check"),{"model_records":3,"relationships":0})
        self.assertEqual(self.invoke(self.cli,"show","person",person["id"],"--trace")["relationships"],[])
        self.invoke(tool,"define-label","introduced","--definition","One person introduced a follow-up in an interaction.",
                    "--direction","Person to Interaction")
        self.invoke(tool,"define-label","supports-need","--definition","A lead note supports a person's stated need.",
                    "--direction","Lead to Person")
        for _ in range(2):
            self.invoke(tool,"link",account,person["id"],"introduced",interaction["id"],
                        "--evidence-id",introduction["id"],"--source-id",mail["source_id"])
            self.invoke(tool,"link",account,lead["id"],"supports-need",person["id"],
                        "--evidence-id",confirmation["id"],"--source-id",memo["source_id"])
        trace=self.invoke(self.cli,"show","person",person["id"],"--trace")
        self.assertEqual(trace["interactions"],[{k:interaction[k] for k in ("id","date","title")}])
        links={x["predicate"]:x for x in trace["relationships"]}
        self.assertEqual(set(links),{"introduced","supports-need"})
        self.assertEqual(links["introduced"]["direction"],"outgoing")
        self.assertEqual(links["introduced"]["citations"]["evidence"][0]["locator"],
                         {"type":"message","value":"message-01"})
        self.assertEqual(links["introduced"]["citations"]["source"][0]["source_id"],mail["source_id"])
        self.assertEqual(links["supports-need"]["direction"],"incoming")
        self.assertEqual(links["supports-need"]["citations"]["evidence"][0]["locator"],
                         {"type":"page","value":"3"})
        self.assertEqual(links["supports-need"]["citations"]["source"][0]["source_id"],memo["source_id"])
        self.assertEqual(self.invoke(self.cli,"show","interaction",interaction["id"],"--trace")["relationships"][0]["direction"],
                         "incoming")
        self.assertEqual(self.invoke(self.cli,"show","lead",lead["id"],"--trace")["relationships"][0]["direction"],
                         "outgoing")
        self.assertFalse((self.extension/"records").exists())
        self.assertEqual(self.invoke(tool,"check"),{"model_records":3,"relationships":2})
        self.assertTrue(all(p.read_bytes()==old for p,old in snapshot.items()))

    def test_explicit_reporting_direction_and_alias_are_traceable(self):
        folder=self.root/"core"
        src=self.write(folder/"catalog.py","file",d={
            "kind":"artifact","namespace":"fictional-test","native_id":"user-statement",
            "title":"Fictional user statement","date":"2026-11-20",
            "pointer":"https://example.invalid/user-statement","capture":"approved"})
        ev=self.write(folder/"concepts.py","add-evidence",d={
            "source_id":src["source_id"],"locator":{"type":"message","value":"example-01"},
            "observed_label":"Fictional user identifies the manager and alternate name",
            "kind":"mention","context":"Fictional workshop fixture"})
        eid=ev["id"]
        report=self.write(self.cli,"add","person",d=self.record("person",title="River Finch"))
        manager=self.write(self.cli,"add","person",d=self.record("person",id="person-jordan",title="Jordan Birch"))
        aid=manager["id"]
        args=("add-person-alias",aid,"Jordy","--evidence-id",eid,"--if-revision")
        updated=self.invoke(self.cli,*args,manager["revision"])
        self.assertEqual(updated["aliases"],["Jordy"])
        self.assertEqual(self.invoke(self.cli,*args,updated["revision"])["result"],"unchanged")
        self.assertIn("stale", self.invoke(self.cli,*args,manager["revision"],code=2))
        tool=folder/"model_store.py"
        self.invoke(tool,"define-label","reports-to","--definition","A person's direct organizational reporting line to their manager.","--direction","Direct report to manager")
        for _ in range(2):
            self.invoke(tool,"link",report["account"],report["id"],"reports-to",aid,"--evidence-id",eid)
        rt=self.invoke(self.cli,"show","person",report["id"],"--trace")
        mt=self.invoke(self.cli,"show","person",aid,"--trace")
        self.assertEqual([(x["predicate"],x["direction"],x["to_id"]) for x in rt["relationships"]],
                         [("reports-to","outgoing",aid)])
        self.assertEqual([(x["direction"],x["from_id"]) for x in mt["relationships"]],[("incoming",report["id"])])
        self.assertEqual(mt["citations"]["evidence"][0]["source_id"],src["source_id"])
        self.assertEqual(rt["relationships"][0]["citations"]["evidence"][0]["locator"]["value"],"example-01")

    def test_org_chart_groups_sources_and_refreshes_without_canonical_output_ingestion(self):
        folder=self.root/"core"
        def source(native):
            return self.write(folder/"catalog.py","file",d={
                "kind":"artifact","namespace":"fictional-test","native_id":native,
                "title":native,"date":"2026-11-20","pointer":"https://example.invalid/"+native,
                "capture":"approved"})["source_id"]
        one,two=source("meeting"),source("follow-up")
        people={k:self.write(self.cli,"add","person",d=self.record("person",id="person-"+k,title=v))
                for k,v in {"river":"River [Finch]","jordan":"Jordan Birch","sam":"Sam Pine",
                            "avery":"Avery Ash","blair":"Blair Oak","terry":"Terry Elm"}.items()}
        scope=people["river"]["account"]
        def link(a,b,src=one):
            return self.invoke(self.cli,"link-reporting",scope,people[a]["id"],people[b]["id"],"--source-id",src)
        link("river","jordan")
        self.assertFalse((self.root/"views").exists())
        out=self.root/self.invoke(self.cli,"rebuild-org-chart")["view"]
        self.assertTrue(out.is_file())
        self.assertIn("account-management/Org%20Chart.md",(self.root/"views/README.md").read_text())
        link("river","jordan",two)
        line=next(line for line in out.read_text().splitlines() if "person-river.md" in line)
        self.assertTrue(line.startswith("  - "))
        self.assertIn("River",line)
        self.assertIn(one,line); self.assertIn(two,line)
        self.assertEqual(out.read_text().count("person-river.md"),1)
        link("river","sam"); link("avery","blair"); link("blair","avery")
        body=out.read_text()
        self.assertIn("conflicting manager claims",body)
        self.assertIn("cycle in manager claims",body)
        self.assertIn("person-terry.md) — manager not recorded",body)
        self.assertIn("River \\[Finch\\]",body)
        self.write(self.cli,"add","person",d=self.record("person",id="person-post",title="Later Person"))
        self.assertIn("Later Person",out.read_text())
        (self.root/"catalog/README.md").write_text("# Test catalog")
        (self.root/"examples").mkdir()
        (self.root/"examples/recovery-observation.json").write_text("{}")
        (self.root/"views/ignored.md").write_text("[MUST NOT BE INDEXED](absent.md)")
        proc=subprocess.run([sys.executable,"-B",str(folder/"catalog.py"),"check"],cwd=self.root,capture_output=True,text=True)
        self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
        self.assertFalse(self.invoke(folder/"concepts.py","find","MUST NOT BE INDEXED")["evidence"])

    def test_view_contract_rejects_wrong_owner_escaping_collisions_and_symlinks(self):
        module=self.root/"core"
        script=r"""
from pathlib import Path
import sys
sys.path.insert(0, sys.argv[1])
import views
base=Path.cwd()
def reject(owner,name):
    try: views.output(base,owner,name)
    except ValueError: return
    raise AssertionError((owner,name))
reject('account-management','../outside.md')
reject('account-management','../../other/Org Chart.md')
reject('different-extension','Org Chart.md')
declare=base/'extensions/account-management/VIEWS.md'
original=declare.read_text()
declare.write_text(original+'- org chart.md\n')
reject('account-management','Org Chart.md')
declare.write_text(original)
(base/'views').symlink_to(base/'extensions',target_is_directory=True)
reject('account-management','Org Chart.md')
"""
        p=subprocess.run([sys.executable,"-B","-c",script,str(module)],cwd=self.root,
                         text=True,capture_output=True)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)

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
