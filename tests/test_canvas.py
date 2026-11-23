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
            people['person-0']['relationship_status']='Getting acquainted'
            graph=({},set(),{},set())
            with patch.object(org_chart,'reporting',return_value=graph):
                profiles=org_chart.render_profiles(base,people,[],[])
                self.assertIn('| Relationship Status | Getting acquainted |',profiles['person-0.md'])
                self.assertIn('| Relationship Temperature | -3 |',profiles['person-0.md'])
                fields=lambda body:[line.split('|')[1].strip() for line in body.splitlines() if line.startswith('|')]
                self.assertEqual(fields(profiles['person-0.md']),fields(profiles['person-1.md']))
                headings=lambda body:[line for line in body.splitlines() if line.startswith('## ')]
                self.assertEqual(headings(profiles['person-0.md']),headings(profiles['person-1.md']))
                self.assertIn('| Email |  |',profiles['person-1.md'])
                paths=views.publish_collection(base,'account-management','people',profiles)
                stamp=paths['person-1.md'].stat().st_mtime_ns
                canvas=org_chart.render_canvas(base,people)
                cards=[n for n in canvas['nodes'] if n['type']=='text']
                self.assertEqual(len(cards),100)
                self.assertEqual(len({n['id'] for n in canvas['nodes']}),100)
                self.assertTrue(all((base/(n['text'].split('[[',1)[1].split('|',1)[0]+'.md')).is_file() for n in cards))
                self.assertTrue(all('Relationship Temperature' in n['text'] and n['text'].count('# ')==1 for n in cards))
                self.assertFalse(any('caption_' in n['id'] for n in cards))
                self.assertEqual(len({n['color'] for n in cards}),7)
                people['person-0']['title']='Renamed Person'
                people['person-2']['archived_on']='2026-11-22'
                paths=views.publish_collection(base,'account-management','people',org_chart.render_profiles(base,people,[],[]))
                self.assertEqual(paths['person-1.md'].stat().st_mtime_ns,stamp)
                self.assertIn('# Renamed Person',paths['person-0.md'].read_text())
                self.assertIn('Archived',paths['person-2.md'].read_text())
                self.assertEqual(len([n for n in org_chart.render_canvas(base,people)['nodes'] if n['type']=='text']),99)
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
        self.assertEqual(len([n for n in canvas['nodes'] if n['type']=='text']),4)

    def test_context_layout_empty_states_linkedin_and_conservative_deduplication(self):
        import copy
        manager=dict(id='person-manager',title='Jordan Birch',aliases=['Jordy'],account='synthetic')
        profile_url='https://www.linkedin.com/in/river-finch/'
        person=dict(id='person-river',title='River Finch',account='synthetic',organization='Birch Workshop',
                    job_title='Lead',business_unit='Workshop',priority='H',relationship_temperature=2,
                    notes='User-provided information (2026-11-23): River works in the service unit, and reports to Jordy (person-manager). Organization: Birch Workshop. User-supplied LinkedIn profile: '+profile_url+' . Unique planning sponsor. Direct profile access was unavailable.')
        people={p['id']:p for p in (person,manager)};before=copy.deepcopy(people)
        with patch.object(org_chart,'reporting',return_value=({},set(),{'person-river':'person-manager'},set())):
            profiles=org_chart.render_profiles(None,people,[],[])
            canvas=org_chart.render_canvas(None,people)
        body=profiles['person-river.md'];notes=body.split('### Notes\n\n')[1].split('## Reporting')[0]
        self.assertIn('| LinkedIn | [Profile]('+profile_url+') |',body)
        self.assertEqual(body.count(profile_url),1)
        self.assertNotIn('reports to',notes);self.assertNotIn('Organization: Birch Workshop',notes)
        self.assertIn('- River works in the service unit.',notes)
        self.assertIn('- Unique planning sponsor.',notes)
        self.assertIn('- Direct profile access was unavailable.',notes)
        self.assertIn('| Reports To | [Jordan Birch](person-manager.md) |',body)
        self.assertIn('### Strategic Value\n\nNone\n\n### Opportunity Relevance\n\nNone',body)
        self.assertIn('## Open follow-ups\n\nNone',body)
        self.assertIn('## Recent interactions\n\nNone',body)
        blank=profiles['person-manager.md']
        self.assertIn('### Notes\n\nNone',blank)
        self.assertEqual(people,before)
        card=next(n for n in canvas['nodes'] if n['id']=='n_person_river')
        self.assertIn('**Title:** Lead',card['text']);self.assertIn('**Business Unit:** Workshop',card['text'])
        self.assertIn('**Priority:** H',card['text']);self.assertIn('**Needs Attention**',card['text'])
        self.assertIn('<span style="color: #318662">+2</span>',card['text'])
        self.assertEqual(org_chart.linkedin(dict(notes='A colleague profile: '+profile_url)),'')
        self.assertEqual(org_chart.linkedin(dict(notes='LinkedIn: '+profile_url+' . LinkedIn: https://linkedin.com/in/another/ .')),'')
        self.assertEqual(org_chart.linkedin(dict(notes='LinkedIn: '+profile_url+'?secret=value')),'')
        unresolved=org_chart.note_entries(person)
        self.assertTrue(any('reports to Jordy' in text for text in unresolved))
