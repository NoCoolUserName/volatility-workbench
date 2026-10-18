"""Security gate policy is tested without installing scanners or reading evidence."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('security_scan', ROOT / 'scripts/security_scan.py')
scan = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scan)


class SecurityGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'src').mkdir()
        (self.root / 'scripts').mkdir()
        (self.root / 'src/test.py').write_text('print("synthetic")\n')
        (self.root / 'src/test.js').write_text('console.log("synthetic");\n')
        self.expected = scan.source_files(self.root)
        self.rules = {'high':{'impact':'HIGH'},'critical':{'impact':'CRITICAL'},'medium':{'impact':'MEDIUM'}}
        self.report = {'version':'synthetic','errors':[],'paths':{'scanned':self.expected},'results':[]}

    def finding(self, rule='high'):
        return {'check_id':rule,'path':'src/test.py','start':{'line':1},
                'extra':{'severity':'WARNING','metadata':{'impact':'LOW'}}}

    def check(self, exceptions=None):
        return scan.evaluate(self.report,self.rules,self.expected,exceptions or [],self.root,'synthetic')

    def exception(self):
        return {'rule_id':'high','path':'src/test.py','line':1,
                'source_sha256':scan.sha256(self.root / 'src/test.py'),
                'reason':'Synthetic fixture reviewed for the gate test only.'}

    def test_complete_clean_scan_passes_and_warn_high_impact_blocks(self):
        self.assertFalse(self.check()['blocking'])
        self.report['results']=[self.finding('high'),self.finding('critical'),self.finding('medium')]
        result=self.check()
        self.assertEqual(len(result['blocking']),2)
        self.assertEqual(result['findings'],3)
        # Classification comes from reviewed rule metadata, not result level or confidence.
        self.assertEqual(result['blocking'][0]['extra']['severity'],'WARNING')

    def test_parser_error_or_absent_error_list_cannot_pass(self):
        self.report['errors']=[{'type':'PartialParsing','level':'warn'}]
        with self.assertRaisesRegex(ValueError,'partial parsing'):self.check()
        del self.report['errors']
        with self.assertRaises(ValueError):self.check()

    def test_missing_source_file_or_report_inventory_cannot_pass(self):
        self.report['paths']['scanned']=['src/test.py']
        with self.assertRaisesRegex(ValueError,'test.js'):self.check()
        self.report['paths']={}
        with self.assertRaises(ValueError):self.check()

    def test_unknown_engine_rule_and_missing_results_fail_closed(self):
        self.report['version']='different'
        with self.assertRaises(ValueError):self.check()
        self.report['version']='synthetic'
        self.report['results']=[self.finding('unreviewed-rule')]
        with self.assertRaisesRegex(ValueError,'unknown rule'):self.check()
        del self.report['results']
        with self.assertRaises(ValueError):self.check()

    def test_exact_exception_retains_reason_but_does_not_hide_another_call(self):
        self.report['results']=[self.finding()]
        result=self.check([self.exception()])
        self.assertEqual(len(result['reviewed']),1)
        self.assertIn('review_reason',result['reviewed'][0])
        self.assertFalse(result['blocking'])
        another=copy.deepcopy(self.finding());another['start']['line']=2
        self.report['results'].append(another)
        self.assertEqual(len(self.check([self.exception()])['blocking']),1)

    def test_any_source_file_change_invalidates_review(self):
        self.report['results']=[self.finding()]
        exception=self.exception()
        (self.root / 'src/test.py').write_text('print("synthetic")\nnew_call()\n')
        with self.assertRaisesRegex(ValueError,'stale'):self.check([exception])

    def test_unused_duplicate_or_unjustified_exception_fails(self):
        with self.assertRaisesRegex(ValueError,'Unused'):self.check([self.exception()])
        self.report['results']=[self.finding()]
        with self.assertRaisesRegex(ValueError,'duplicate'):self.check([self.exception(),self.exception()])
        bad=self.exception();bad['reason']=''
        with self.assertRaises(ValueError):self.check([bad])

    def test_wrong_rule_archive_digest_is_rejected_before_parsing(self):
        archive=self.root / 'fake.tar.gz';archive.write_bytes(b'synthetic wrong archive')
        with self.assertRaisesRegex(ValueError,'SHA-256'):
            scan.prepare_rules(archive,{'archive_sha256':'0'*64},self.root)

    def test_source_inventory_requires_both_languages_and_rejects_symlinks(self):
        (self.root / 'src/test.js').unlink()
        with self.assertRaisesRegex(ValueError,'both Python'):scan.source_files(self.root)
        (self.root / 'src/test.js').symlink_to(self.root / 'src/test.py')
        with self.assertRaisesRegex(ValueError,'symlinks'):scan.source_files(self.root)

    def test_linked_package_and_source_root_cannot_silently_omit_code(self):
        package=self.root / 'outside-package';package.mkdir()
        (package / 'runtime.py').write_text('print("synthetic linked code")\n')
        link=self.root / 'src/linked-package';link.symlink_to(package,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'symlinks'):scan.source_files(self.root)
        link.unlink()
        (self.root / 'scripts').rmdir()
        (self.root / 'scripts').symlink_to(package,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'roots'):scan.source_files(self.root)

    def test_broken_or_non_source_link_is_rejected_before_file_filtering(self):
        (self.root / 'src/broken.txt').symlink_to(self.root / 'missing')
        with self.assertRaisesRegex(ValueError,'symlinks'):scan.source_files(self.root)
