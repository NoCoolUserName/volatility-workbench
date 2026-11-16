import importlib.util
import base64
from contextlib import redirect_stdout
from email.message import Message
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
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


class UpdaterApiTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        record = {'version': '0.1.0', 'commit': 'b' * 40, 'eligible_series': '0.1'}
        (self.root/'core-dependency.json').write_text(json.dumps(record))
        (self.root/'pyproject.toml').write_text('[project]\ndependencies=["' + u.PREFIX + 'b' * 40 + '"]\n')
        (self.root/'requirements.lock.txt').write_text('old\n')
        self.original = self.snapshot()
        self.release = {'tag_name': 'v0.1.2'}
        self.metadata = '[project]\nname="volatility-mcp"\nversion="0.1.2"\n'
        environment = patch.dict(u.os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        network = patch.object(u.urllib.request, 'urlopen')
        self.urlopen = network.start()
        self.addCleanup(network.stop)

    def snapshot(self):
        return {p.name: p.read_bytes() for p in self.root.iterdir()}

    def run_main(self, *args):
        output = io.StringIO()
        with patch('sys.argv', ['update_core.py', '--root', str(self.root), *args]), redirect_stdout(output):
            u.main()
        return output.getvalue()

    def test_all_candidate_api_requests_are_authenticated(self):
        u.os.environ['GH_TOKEN'] = 'synthetic-test-token'
        sha = 'a' * 40
        documents = [[self.release], {'sha': sha}]
        documents += [{'content': base64.b64encode(text.encode()).decode()}
                      for text in ('mcp==2.3.0\n', self.metadata)]
        self.urlopen.side_effect = [io.StringIO(json.dumps(doc)) for doc in documents]
        result = json.loads(self.run_main())
        self.assertEqual(result['commit'], sha)
        self.assertEqual(result['version'], '0.1.2')
        paths = ['releases?per_page=100', 'commits/v0.1.2',
                 'contents/requirements.lock.txt?ref=' + sha, 'contents/pyproject.toml?ref=' + sha]
        self.assertEqual(self.urlopen.call_count, len(paths))
        for call, path in zip(self.urlopen.call_args_list, paths):
            request = call.args[0]
            self.assertEqual(request.full_url, 'https://api.github.com/repos/' + u.REPO + '/' + path)
            self.assertEqual(request.get_method(), 'GET')
            self.assertEqual(request.get_header('Authorization'), 'Bearer synthetic-test-token')
            self.assertEqual(request.get_header('Accept'), 'application/vnd.github+json')
            self.assertEqual(request.get_header('User-agent'), 'volatility-workbench-updater')
            self.assertEqual(call.kwargs, {'timeout': 30})
        self.assertNotIn('synthetic-test-token', result.values())
        for data in self.snapshot().values():
            self.assertNotIn(b'synthetic-test-token', data)
        self.assertEqual((self.root/'requirements.lock.txt').read_text(), 'mcp==2.3.0\n' + u.PREFIX + sha + '\n')

    def test_redirects_do_not_forward_the_token(self):
        u.os.environ['GH_TOKEN'] = 'synthetic-test-token'
        self.urlopen.return_value = io.StringIO('[]')
        u.get_json('releases?per_page=100')
        request = self.urlopen.call_args.args[0]
        redirected = u.urllib.request.HTTPRedirectHandler().redirect_request(
            request, None, 302, 'Found', {}, 'https://example.invalid/redirect')
        self.assertIsNone(redirected.get_header('Authorization'))

    def test_missing_or_blank_credentials_fail_before_network_or_writes(self):
        for token in (None, '', ' \t'):
            with self.subTest(token=token):
                u.os.environ.clear()
                if token is not None:
                    u.os.environ['GH_TOKEN'] = token
                with self.assertRaisesRegex(RuntimeError, 'GH_TOKEN is required'):
                    self.run_main()
                self.urlopen.assert_not_called()
                self.assertEqual(self.snapshot(), self.original)

    def test_no_update_is_a_successful_single_authenticated_read(self):
        u.os.environ['GH_TOKEN'] = 'synthetic-test-token'
        releases = [{'tag_name': 'v0.1.0'}, {'tag_name': 'v0.2.0'},
                    {'tag_name': 'v0.1.2', 'draft': True}, {'tag_name': 'v0.1.3', 'prerelease': True}]
        self.urlopen.return_value = io.StringIO(json.dumps(releases))
        self.assertEqual(self.run_main(), 'No newer eligible core release.\n')
        self.urlopen.assert_called_once()
        self.assertEqual(self.urlopen.call_args.args[0].get_header('Authorization'), 'Bearer synthetic-test-token')
        self.assertEqual(self.snapshot(), self.original)

    def test_offline_fixture_needs_no_credentials_or_network(self):
        fixture = self.root/'fixture.json'
        fixture.write_text(json.dumps({'releases': [self.release], 'commit': 'a' * 40,
                                      'lock': 'mcp==2.3.0\n', 'metadata': self.metadata}))
        original = self.snapshot()
        result = json.loads(self.run_main('--fixture', str(fixture), '--dry-run'))
        self.assertTrue(result['dry_run'])
        self.assertEqual(result['commit'], 'a' * 40)
        self.urlopen.assert_not_called()
        self.assertEqual(self.snapshot(), original)

    def test_rate_limits_fail_without_retry_no_update_message_or_writes(self):
        u.os.environ['GH_TOKEN'] = 'synthetic-test-token'
        for code, reason, values in (
                (403, 'Forbidden', {'X-RateLimit-Remaining': '0', 'X-RateLimit-Reset': '1794900000'}),
                (403, 'Forbidden', {'Retry-After': '60'}),
                (403, 'rate limit exceeded', {}),
                (429, 'Too Many Requests', {})):
            with self.subTest(code=code, reason=reason, headers=values):
                headers = Message()
                for name, value in values.items():
                    headers[name] = value
                self.urlopen.reset_mock()
                self.urlopen.side_effect = urllib.error.HTTPError('https://api.github.com/', code, reason, headers, None)
                output = io.StringIO()
                with redirect_stdout(output), self.assertRaisesRegex(RuntimeError, 'GitHub API rate limit exceeded') as caught:
                    self.run_main()
                self.assertIn(f'HTTP {code}', str(caught.exception))
                for name in ('Retry-After', 'X-RateLimit-Reset'):
                    self.assertIn(values.get(name, 'not provided'), str(caught.exception))
                self.assertNotIn('synthetic-test-token', str(caught.exception))
                self.assertEqual(output.getvalue(), '')
                self.urlopen.assert_called_once()
                self.assertEqual(self.snapshot(), self.original)

    def test_other_http_failures_are_not_misreported_as_rate_limits_or_no_update(self):
        u.os.environ['GH_TOKEN'] = 'synthetic-test-token'
        for code in (401, 403, 404, 500):
            with self.subTest(code=code):
                error = urllib.error.HTTPError('https://api.github.com/', code, 'API error', Message(), None)
                self.urlopen.reset_mock()
                self.urlopen.side_effect = error
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    self.run_main()
                self.assertIs(caught.exception, error)
                self.urlopen.assert_called_once()
                self.assertEqual(self.snapshot(), self.original)

    def test_candidate_validation_still_rejects_mutable_or_inexact_updates(self):
        for sha, lock, metadata in (
                ('main', 'mcp==2.3.0', self.metadata),
                ('a' * 40, 'mcp>=2.3.0', self.metadata),
                ('a' * 40, 'mcp==2.3.0', self.metadata.replace('0.1.2', '0.1.3'))):
            with self.subTest(sha=sha, lock=lock, metadata=metadata):
                with self.assertRaises(ValueError):
                    u.update(self.root, self.release, sha, lock, metadata)
                self.assertEqual(self.snapshot(), self.original)
