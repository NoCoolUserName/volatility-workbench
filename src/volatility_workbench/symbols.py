"""Explicit, bounded symbol imports; no memory images or matching guesses."""
from __future__ import annotations
import base64
import hashlib
import io
import json
import lzma
import gzip
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
import urllib.request
import zipfile
from .storage import atomic_json, now, private_dir

MAX_ARCHIVE = 256 * 1024 * 1024
MAX_FILE = 256 * 1024 * 1024
MAX_TOTAL = 1024 * 1024 * 1024
MAX_MEMBERS = 2000
PROFILE = Path(__file__).parent / 'resources' / 'symbols.json'


def profile():
    return json.loads(PROFILE.read_text())


def _regular(path):
    path = Path(path).expanduser().absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Symbol paths must not contain symlinks')
    if not path.is_file() or path.stat().st_size > MAX_ARCHIVE:
        raise ValueError('Choose a regular symbol file no larger than 268.44 MB')
    return path


def _decode(name, raw):
    if name.endswith('.json.xz'):
        stream = lzma.LZMAFile(io.BytesIO(raw))
    elif name.endswith('.json.gz'):
        stream = gzip.GzipFile(fileobj=io.BytesIO(raw))
    elif name.endswith('.json'):
        stream = io.BytesIO(raw)
    else:
        raise ValueError('Only ISF .json, .json.xz or .json.gz files are supported')
    with stream:
        decoded = stream.read(MAX_FILE + 1)
    if len(decoded) > MAX_FILE:
        raise ValueError('Decompressed symbol exceeds the per-file limit')
    data = json.loads(decoded)
    if not isinstance(data, dict) or not isinstance(data.get('metadata'), dict):
        raise ValueError('Symbol is not an ISF object with metadata')
    if not all(isinstance(data.get(key), dict) for key in ('symbols','user_types','base_types')):
        raise ValueError('Symbol lacks required ISF type/symbol dictionaries')
    metadata=data['metadata']
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+',str(metadata.get('format',''))):
        raise ValueError('Symbol lacks an ISF format version')
    pdb = metadata.get('windows', {}).get('pdb', {})
    if pdb:
        guid, age, database = pdb.get('GUID',''), pdb.get('age'), pdb.get('database','')
        if not re.fullmatch('[A-Fa-f0-9]{32}',guid) or not isinstance(age,int) or isinstance(age,bool) or not 0 <= age <= 0xffffffff or not re.fullmatch(r'[A-Za-z0-9_.-]+\.pdb',database):
            raise ValueError('Windows symbol lacks a valid exact PDB identifier')
        identity={'os':'windows','pdb':database,'guid':guid.upper(),'age':age}
        relative=PurePosixPath('windows',database,f'{guid.upper()}-{age}.json')
    else:
        os_name='linux' if 'linux' in metadata else 'mac' if 'mac' in metadata else None
        symbol='linux_banner' if os_name=='linux' else 'version'
        encoded=data['symbols'].get(symbol,{}).get('constant_data')
        if not os_name or not isinstance(encoded,str):
            raise ValueError('Linux/macOS ISF must contain its exact constant banner')
        try: banner=base64.b64decode(encoded, validate=True).decode('utf-8').rstrip('\x00')
        except (ValueError,UnicodeError) as exc: raise ValueError('Invalid symbol banner') from exc
        if not banner or len(banner)>16384:
            raise ValueError('Invalid symbol banner length')
        identity={'os':os_name,'banner':banner}
        relative=PurePosixPath(os_name,hashlib.sha256(decoded).hexdigest()+'.json')
    return decoded, identity, relative


def import_symbols(source, destination, *, expected_hash=None, expected_size=None, provenance=None):
    """Stage validated data, activate one immutable directory; never overwrite files."""
    source=_regular(source)
    raw=source.read_bytes()
    digest=hashlib.sha256(raw).hexdigest()
    if expected_hash and digest!=expected_hash:
        raise ValueError('Symbol archive SHA-256 does not match the supported manifest')
    if expected_size is not None and len(raw)!=expected_size:
        raise ValueError('Symbol archive size does not match the supported manifest')
    destination=Path(destination).expanduser().absolute()
    if any(p.is_symlink() for p in (destination,*destination.parents)):
        raise ValueError('Symbol destination must not contain symlinks')
    private_dir(destination)
    targets=[destination/os_name/('managed-'+digest) for os_name in ('windows','linux','mac')]
    target=next((p for p in targets if p.exists()),None)
    if target is not None:
        receipt=json.loads((target/'.receipt').read_text())
        for item in receipt['files']:
            path=target/item['path']
            if path.is_symlink() or not path.resolve().is_relative_to(target.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:
                raise ValueError('Existing managed symbol content changed; preserve it and resolve manually')
        return receipt
    with tempfile.TemporaryDirectory(prefix='.symbol-stage-',dir=destination) as temporary:
        stage=Path(temporary)
        members=[]
        if zipfile.is_zipfile(io.BytesIO(raw)):
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                infos=archive.infolist()
                if len(infos)>MAX_MEMBERS or sum(i.file_size for i in infos)>MAX_TOTAL:
                    raise ValueError('Symbol archive exceeds entry or extraction limits')
                for info in infos:
                    name=PurePosixPath(info.filename)
                    mode=info.external_attr>>16
                    if name.is_absolute() or '..' in name.parts or '\\' in info.filename or stat.S_ISLNK(mode) or (mode and stat.S_IFMT(mode) not in (0,stat.S_IFREG,stat.S_IFDIR)):
                        raise ValueError('Unsafe symbol archive member')
                    if info.is_dir(): continue
                    if info.flag_bits & 1 or info.file_size>MAX_FILE:
                        raise ValueError('Encrypted/oversized symbol members are unsupported')
                    if not info.filename.endswith(('.json','.json.xz','.json.gz')):
                        raise ValueError('Symbol archive contains non-ISF content')
                    members.append((info.filename,archive.read(info)))
        else:
            members=[(source.name,raw)]
        files=[]; total=0; operating_system=None
        for name,content in members:
            decoded,identity,relative=_decode(name,content)
            total+=len(decoded)
            if total>MAX_TOTAL: raise ValueError('Decompressed symbols exceed total limit')
            if operating_system and identity['os']!=operating_system:
                raise ValueError('Import one OS per archive')
            operating_system=identity['os']
            relative=PurePosixPath(*relative.parts[1:])
            path=stage/relative
            path.parent.mkdir(parents=True,exist_ok=True)
            digest_isf=hashlib.sha256(decoded).hexdigest()
            if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()!=digest_isf:
                raise ValueError('Archive contains conflicting exact symbol identifiers')
            path.write_bytes(decoded)
            files.append({'path':str(relative),'sha256':digest_isf,'size':len(decoded),'identity':identity})
        if not files: raise ValueError('No usable symbol files found')
        receipt={'schema_version':1,'source_sha256':digest,'source_size':len(raw),'source':provenance or 'Explicit local import',
                 'imported_at':now(),'files':files,'validation':'ISF shape and exact identifiers; image compatibility is not established'}
        target=destination/operating_system/('managed-'+digest)
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.parent.is_symlink(): raise ValueError('Symbol destination must not be a symlink')
        atomic_json(stage/'.receipt',receipt)
        os.rename(stage,target)
    return receipt


class _HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.startswith('https://'):
            raise ValueError('Symbol download redirected away from HTTPS')
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def download_pack(pack_id, destination, download_dir, progress=lambda **kwargs: None):
    pack=next((p for p in profile()['packs'] if p['id']==pack_id),None)
    if not pack: raise ValueError('Unknown supported symbol pack')
    download_dir=private_dir(Path(download_dir))
    partial=download_dir/(pack['id']+'.zip.part')
    if partial.is_symlink(): raise ValueError('Download destination must not be a symlink')
    offset=partial.stat().st_size if partial.exists() else 0
    if offset>pack['size']: partial.unlink();offset=0
    if offset<pack['size']:
        request=urllib.request.Request(pack['url'],headers={'Range':f'bytes={offset}-'} if offset else {})
        opener=urllib.request.build_opener(_HTTPSRedirect())
        with opener.open(request,timeout=30) as response:
            if offset and response.status!=206: offset=0
            if offset and not response.headers.get('Content-Range','').startswith(f'bytes {offset}-'):
                raise ValueError('Symbol resume range does not match saved download')
            with partial.open('ab' if offset else 'wb') as output:
                while chunk:=response.read(1024*1024):
                    offset+=len(chunk)
                    if offset>pack['size']: raise ValueError('Symbol download exceeded pinned size')
                    output.write(chunk);progress(stage='Downloading symbols',completed=offset,total=pack['size'])
    try:
        return import_symbols(partial,destination,expected_hash=pack['sha256'],expected_size=pack['size'],provenance=pack)
    except ValueError:
        partial.unlink(missing_ok=True)
        raise
