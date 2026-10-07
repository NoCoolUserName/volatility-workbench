import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('update_core',ROOT/'scripts/update_core.py')
u=importlib.util.module_from_spec(spec);spec.loader.exec_module(u)

class UpdaterTests(unittest.TestCase):
    def test_selection_and_generation_are_pinned_and_dry_run_is_inert(self):
        releases=[{'tag_name':tag} for tag in ('v0.1.0','v0.1.2','v0.2.0','v0.1.1','main','v0.1.4-rc1')]
        releases.append({'tag_name':'v0.1.3','draft':True})
        selected=u.select_release(releases,'0.1.0','0.1')
        self.assertEqual(selected['tag_name'],'v0.1.2')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            record={'repository':u.REPO,'version':'0.1.0','commit':'b'*40,'api_revision':1,'eligible_series':'0.1'}
            (root/'core-dependency.json').write_text(json.dumps(record))
            (root/'pyproject.toml').write_text('[project]\ndependencies=["'+u.PREFIX+'b'*40+'"]\n')
            (root/'requirements.lock.txt').write_text('old')
            original={p.name:p.read_bytes() for p in root.iterdir()}
            metadata='[project]\nname="volatility-mcp"\nversion="0.1.2"\n'
            u.update(root,selected,'a'*40,'mcp==2.3.0\n',metadata,True)
            self.assertEqual(original,{p.name:p.read_bytes() for p in root.iterdir()})
            u.update(root,selected,'a'*40,'mcp==2.3.0\n',metadata)
            self.assertIn('a'*40,(root/'pyproject.toml').read_text())
            self.assertEqual(json.loads((root/'core-dependency.json').read_text())['version'],'0.1.2')
            self.assertTrue((root/'requirements.lock.txt').read_text().endswith('a'*40+'\n'))
            self.assertIsNone(u.select_release(releases,'0.1.2','0.1'))
            with self.assertRaises(ValueError):u.update(root,{'tag_name':'v0.2.0'},'c'*40,'mcp==2.3.0','[project]\nname="volatility-mcp"\nversion="0.2.0"')
