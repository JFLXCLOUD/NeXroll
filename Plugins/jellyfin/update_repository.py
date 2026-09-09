"""Publish catalog packages from released ZIPs, then update Jellyfin manifests.

Only meta.json is changed: catalog installations opt into automatic updates.
Original release assets and already advertised catalog versions are immutable.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

GUID = 'a1b2c3d4-e5f6-7890-abcd-ae0c01100001'
VARIANTS = [('NeXroll.Jellyfin12', '12.0.0.0', 'manifest.json'),
            ('NeXroll.Jellyfin', '10.11.0.0', 'manifest-10.11.json')]


def version_key(version):
    if not re.fullmatch(r'\d+\.\d+\.\d+\.\d+', version):
        raise ValueError(f'Invalid plugin version: {version}')
    return tuple(map(int, version.split('.')))


def inspect_package(blob, abi, expected_version):
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        if sorted(archive.namelist()) != ['NeXroll.Jellyfin.dll', 'meta.json', 'thumb.png']:
            raise ValueError('Package must contain exactly the plugin DLL, metadata, and thumbnail')
        files = {name: archive.read(name) for name in archive.namelist()}
    meta = json.loads(files['meta.json'].decode('utf-8-sig'))
    if (meta['guid'], meta['version'], meta['targetAbi']) != (GUID, expected_version, abi):
        raise ValueError('Package identity/version/ABI mismatch')
    version_key(meta['version'])
    return meta, files


def catalog_package(blob, abi, version):
    meta, files = inspect_package(blob, abi, version)
    meta['autoUpdate'] = True
    files['meta.json'] = (json.dumps(meta, indent=2) + '\n').encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files):
            entry = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, files[name])
    return output.getvalue()


def gh(*args):
    return subprocess.check_output(['gh', *args], text=True, encoding='utf-8')


def publish(repository, tag, output):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('Invalid GitHub repository')
    if not re.fullmatch(r'v[0-9][A-Za-z0-9._-]*', tag):
        raise ValueError('Invalid release tag')
    release = json.loads(gh('api', f'repos/{repository}/releases/tags/{tag}'))
    if release['draft']:
        raise ValueError('Publish the GitHub release before updating the catalog')
    assets = {a['name']: a for a in release['assets']}
    pending = []
    with tempfile.TemporaryDirectory() as temp:
        temp = Path(temp)

        def download(name):
            gh('release', 'download', tag, '--repo', repository, '--pattern', name,
               '--dir', str(temp), '--clobber')
            return (temp / name).read_bytes()

        for prefix, abi, filename in VARIANTS:
            names = [name for name in assets if re.fullmatch(re.escape(prefix) + r'-\d+\.\d+\.\d+\.\d+\.zip', name)]
            if len(names) != 1:
                raise ValueError(f'Expected one released {prefix} ZIP, found {names}')
            original_name = names[0]
            version = original_name[len(prefix) + 1:-4]
            original = download(original_name)
            meta, files = inspect_package(original, abi, version)
            target = output / filename
            catalog = json.loads(target.read_text()) if target.exists() else [{
                'guid': GUID, 'name': 'NeXroll Intros', 'description': meta['description'],
                'overview': f'NeXroll prerolls for Jellyfin {abi.split(".0.0")[0]}',
                'owner': 'JFLXCLOUD', 'category': 'General', 'versions': []}]
            if len(catalog) != 1 or catalog[0]['guid'] != GUID:
                raise ValueError('Unexpected catalog identity')
            versions = catalog[0]['versions']
            if any(v['targetAbi'] != abi for v in versions):
                raise ValueError('Do not mix server ABI families in a catalog')
            if any(v['version'] == version for v in versions):
                print(f'{filename}: {version} already published; preserving its URL and checksum')
                continue
            name = original_name[:-4] + '-repository.zip'
            expected = catalog_package(original, abi, version)
            if name not in assets:
                (temp / name).write_bytes(expected)
                gh('release', 'upload', tag, str(temp / name), '--repo', repository)
            published = download(name)
            published_meta, published_files = inspect_package(published, abi, version)
            if published_meta.get('autoUpdate') is not True:
                raise ValueError('Catalog package must enable automatic updates')
            for key in ('NeXroll.Jellyfin.dll', 'thumb.png'):
                if published_files[key] != files[key]:
                    raise ValueError('Published catalog asset differs from released plugin')
            versions.append({
                'version': version, 'targetAbi': abi,
                'sourceUrl': f'https://github.com/{repository}/releases/download/{tag}/{name}',
                'checksum': hashlib.md5(published).hexdigest(),
                'timestamp': release['published_at'],
                'changelog': f'NeXroll Intros {version}. Repository package enables automatic plugin updates.'})
            versions.sort(key=lambda v: version_key(v['version']), reverse=True)
            pending.append((target, catalog))
        # Write pointers only after both families have been validated and uploaded.
        output.mkdir(parents=True, exist_ok=True)
        for target, catalog in pending:
            target.write_text(json.dumps(catalog, indent=2) + '\n', encoding='utf-8')
            print(f'Updated {target}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--output', type=Path, default=Path('Plugins/jellyfin'))
    args = parser.parse_args()
    publish(args.repository, args.tag, args.output)
