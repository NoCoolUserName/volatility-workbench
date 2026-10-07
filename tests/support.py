"""Harmless fixture setup extracted from core at 3ecc22e; no forensic implementation."""
import sys, tempfile, unittest
from pathlib import Path
from volatility_mcp.api import Config, VolatilityBackend

class BackendFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='volatility-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.evidence = self.root / 'evidence'
        self.evidence.mkdir()
        self.fake = self.root / 'fake-python'
        self.fake.write_text('#!' + sys.executable + '\n' +
            (Path(__file__).parent / 'fixtures/fake_volatility.py').read_text())
        self.fake.chmod(0o700)
        self.config = Config(self.evidence, self.root / 'outputs', self.fake, self.fake,
                             cache_path=self.root / 'cache', command_timeout=1, enable_xpnet=False)
        self.backend = VolatilityBackend(self.config)
        self.image = self.evidence / 'example.raw'
        self.image.write_text('normal')
