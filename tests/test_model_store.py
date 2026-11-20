"""Core storage boundaries, tested without an installed extension."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"core"))
import catalog
import model_store


class ModelStoreTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base=Path(tmp.name)
        _,_,source=catalog.file_record(self.base,dict(kind="artifact",namespace="fictional",native_id="meeting",
                 title="Fictional source",date="2026-01-01",pointer="https://example.invalid/notes",capture="approved"))
        self.source=source["source_id"]

    def model(self, rid, scope):
        return {"id":rid,"type":"sample","account":scope,"title":"A sample record","notes":None}

    def test_shared_store_ids_provenance_and_scope(self):
        a=self.model("sample-a","one")
        b=self.model("sample-b","one")
        other=self.model("sample-c","two")
        with catalog.write_lock(self.base):
            for d in (a,b,other):
                model_store.write_model(self.base,"example",d)
            self.assertEqual(model_store.read_model(self.base,a["id"],"example"),a)
            with self.assertRaisesRegex(ValueError,"different extension"):
                model_store.write_model(self.base,"another-owner",a)
            self.assertEqual(model_store.labels(self.base),{})
            with self.assertRaisesRegex(ValueError,"undefined relationship label"):
                model_store.write_relationship(self.base,"one",a["id"],"relates-to",b["id"],source_ids=[self.source])
            model_store.define_label(self.base,"relates-to","A supported connection between sample records","sample → sample")
            with self.assertRaisesRegex(ValueError,"different meaning"):
                model_store.define_label(self.base,"relates-to","A conflicting definition","sample → sample")
            with self.assertRaisesRegex(ValueError,"needs source"):
                model_store.write_relationship(self.base,"one",a["id"],"relates-to",b["id"])
            with self.assertRaisesRegex(ValueError,"crosses account"):
                model_store.write_relationship(self.base,"one",a["id"],"relates-to",other["id"],source_ids=[self.source])
            first=model_store.write_relationship(self.base,"one",a["id"],"relates-to",b["id"],source_ids=[self.source])
            second=model_store.write_relationship(self.base,"one",a["id"],"relates-to",b["id"],source_ids=[self.source])
            self.assertEqual(first,second)
        self.assertEqual(model_store.check(self.base),{"model_records":3,"relationships":1})
        self.assertIn(first.stem,model_store.relationships(self.base,"one"))
        self.assertEqual(model_store.relationships(self.base,"two"),{})

    def test_validation_rejects_an_extension_private_record_store(self):
        old=self.base/"extensions"/"sample"/"records"
        old.mkdir(parents=True)
        (old/"one.md").write_text("A note")
        with self.assertRaisesRegex(ValueError,"extension-private"):
            model_store.check(self.base)


if __name__=="__main__":
    unittest.main()
