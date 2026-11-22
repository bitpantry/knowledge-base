"""Synthetic Canvas and stable-profile integration checks."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'core'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extensions/account-management'))
import views
import org_chart

class CanvasTests(unittest.TestCase):
    def test_hundred_profiles_and_canvas_links_rename_archive(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp)
            declaration=base/'extensions/account-management/VIEWS.md'
            declaration.parent.mkdir(parents=True)
            declaration.write_text('# Views\n- People.md\n- people/\n- Org Chart.canvas\n')
            people={f'person-{i}':dict(id=f'person-{i}',title='Duplicate Name',account='synthetic',
                                     relationship_temperature=i%7-3) for i in range(100)}
            graph=({},set(),{},set())
            with patch.object(org_chart,'reporting',return_value=graph):
                profiles=org_chart.render_profiles(base,people,[],[])
                paths=views.publish_collection(base,'account-management','people',profiles)
                stamp=paths['person-1.md'].stat().st_mtime_ns
                canvas=org_chart.render_canvas(base,people)
                cards=[n for n in canvas['nodes'] if n['type']=='file']
                self.assertEqual(len(cards),100)
                self.assertEqual(len({n['id'] for n in canvas['nodes']}),200)
                self.assertTrue(all((base/n['file']).is_file() for n in cards))
                self.assertEqual(len({n['color'] for n in cards}),7)
                people['person-0']['title']='Renamed Person'
                people['person-2']['archived_on']='2026-11-22'
                paths=views.publish_collection(base,'account-management','people',org_chart.render_profiles(base,people,[],[]))
                self.assertEqual(paths['person-1.md'].stat().st_mtime_ns,stamp)
                self.assertIn('# Renamed Person',paths['person-0.md'].read_text())
                self.assertIn('Archived',paths['person-2.md'].read_text())
                self.assertEqual(len([n for n in org_chart.render_canvas(base,people)['nodes'] if n['type']=='file']),99)
                p=views.publish_canvas(base,'account-management','Org Chart.canvas',canvas)
                stamp=p.stat().st_mtime_ns
                views.publish_canvas(base,'account-management','Org Chart.canvas',canvas)
                self.assertEqual(p.stat().st_mtime_ns,stamp)
                p.write_text('{"nodes": [], "edges": []}')
                with self.assertRaises(ValueError):
                    views.publish_canvas(base,'account-management','Org Chart.canvas',canvas)
                p.unlink()
                p.symlink_to(declaration)
                with self.assertRaises(ValueError):
                    views.publish_canvas(base,'account-management','Org Chart.canvas',canvas)

    def test_ambiguous_and_cycle_edges_omitted(self):
        people={rid:dict(id=rid,title=rid,account='synthetic') for rid in ('a','b','c','d')}
        graph=({}, {'c'}, {'a':'b','b':'a','d':'a'}, {'a','b'})
        with patch.object(org_chart,'reporting',return_value=graph):
            canvas=org_chart.render_canvas(None,people)
        self.assertEqual(len(canvas['edges']),1)
        self.assertEqual(len([n for n in canvas['nodes'] if n['type']=='file']),4)
