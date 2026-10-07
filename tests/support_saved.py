"""Synthetic saved records for Workbench packaging checks."""
from contextlib import contextmanager
from pathlib import Path
import json, sys, socket
from unittest.mock import patch
from volatility_mcp.api import Config, VolatilityBackend, file_fingerprint

@contextmanager
def offline_guard():
    counters={'subprocess_launches':0,'physical_volatility_invocations':0,'network_attempts':0}
    def no_process(*a,**kw):
        counters['subprocess_launches']+=1
        raise AssertionError('Offline replay forbids ALL subprocesses, including Volatility')
    def no_network(*a,**kw):
        counters['network_attempts']+=1
        raise AssertionError('Offline replay forbids network connections')
    with patch('subprocess.Popen',no_process),patch.object(socket.socket,'connect',no_network),patch('socket.create_connection',no_network):
        yield counters


class SavedFixture:
    def __init__(self, root):
        self.root=Path(root).resolve();self.evidence=self.root/'evidence';self.evidence.mkdir()
        self.image=self.evidence/'synthetic.raw';self.image.write_bytes(b'SYNTHETIC NOT A MEMORY ACQUISITION')
        self.config=Config(self.evidence,self.root/'outputs',Path(sys.executable),Path(sys.executable),cache_path=self.root/'cache',enable_xpnet=False)
        self.backend=VolatilityBackend(self.config)
        self.case=self.backend.case_directory(self.image)

    def run(self, rid, data, spec, plugin='windows.pslist.PsList',arguments=None):
        run=self.case/'runs'/rid;(run/'json').mkdir(parents=True)
        path=run/'json/stdout.json';path.write_text(spec.get('raw',json.dumps(data)))
        fp=file_fingerprint(self.image)
        record={'run_id':rid,'image':str(self.image),'image_relative_path':'synthetic.raw',
            'image_sha256_before':fp['sha256'],'image_sha256_after':fp['sha256'],'integrity_verified':True,
            'plugin':plugin,'arguments':arguments or [],'status':spec.get('status','unknown'),
            'started_at':f'2020-01-01 00:00:{int(rid[-1]):02}Z','completed_at':f'2020-01-01 00:01:{int(rid[-1]):02}Z',
            'volatility_version':'SYNTHETIC SAVED OUTPUT','volatility_python_version':'synthetic','mcp_sdk_version':'synthetic','server_version':'synthetic',
            'commands':[{'stdout_path':str(path),'argv':['SIMULATED; NEVER EXECUTED'],'returncode':spec.get('returncode'),
                'status':spec.get('status'), 'failure_category':spec.get('failure_category'),'artifacts':[file_fingerprint(path)]}]}
        if 'collection_complete' in spec:record['collection_complete']=spec['collection_complete']
        if spec.get('legacy'):record.update(commands=[],status='unknown',completed_at=None)
        if spec.get('missing'):path.unlink()
        (run/'manifest.json').write_text(json.dumps(record))
        return record
