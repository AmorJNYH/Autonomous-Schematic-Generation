"""Hash-pinned own deliveries, cached outside Git; no archived generator execution."""
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
from bench_common import sha, put


def safe_relative(relative):
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('Unsafe frozen relative path')
    return path


def copy_source(source, destination):
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Incremental cache must be fresh')
    destination.mkdir(parents=True)
    if source['source_kind'] == 'tar_delivery':
        archive = Path(source['archive'])
        if sha(archive) != source['archive_sha256']:
            raise ValueError('Archive SHA mismatch')
        with tarfile.open(archive) as tar:
            frozen = tar.extractfile(source['freeze_member']).read()
            if hashlib.sha256(frozen).hexdigest() != source['freeze_manifest_sha256']:
                raise ValueError('Tar freeze SHA mismatch')
            for relative, digest in source['files'].items():
                member = tar.getmember(source['archive_prefix'] + str(safe_relative(relative)))
                if not member.isfile():
                    raise ValueError('Frozen archive member is not a regular file')
                data = tar.extractfile(member).read()
                if hashlib.sha256(data).hexdigest() != digest:
                    raise ValueError('Frozen payload SHA mismatch: ' + relative)
                target = destination/safe_relative(relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
    else:
        for field, digest_field in (('freeze_manifest', 'freeze_manifest_sha256'),
                                    ('outer_freeze_manifest', 'outer_freeze_sha256')):
            if sha(source[field]) != source[digest_field]:
                raise ValueError('Freeze provenance SHA mismatch')
        for relative, digest in source['files'].items():
            path = Path(source['source_directory'])/safe_relative(relative)
            if sha(path) != digest:
                raise ValueError('Frozen payload SHA mismatch: ' + relative)
            target = destination/safe_relative(relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
    if any(sha(destination/safe_relative(k)) != v for k, v in source['files'].items()):
        raise ValueError('Copied frozen payload differs')
    return {**source, 'cache': str(destination), 'status': 'READY',
            'hash_verified': True, 'generator_build': 'NOT_RUN'}


def prepare_incremental(metadata, cache):
    return [copy_source(source, Path(cache)/source['id']) for source in metadata['new_sources']]


def working_copy(entry, output):
    """Normalize existing project layout only; inputs remain untouched and pinned."""
    source = Path(entry['cache'])
    for relative, digest in entry['files'].items():
        if sha(source/relative) != digest:
            raise ValueError('Cache changed: ' + relative)
    output = Path(output)
    shutil.copytree(source, output)
    root = safe_relative(entry['root'])
    if root.parent != Path('.'):
        shutil.copytree(output/root.parent, output, dirs_exist_ok=True)
    return output


def fingerprint(entries):
    payload = [{k: e.get(k) for k in ('id', 'files', 'archive_sha256', 'freeze_manifest_sha256',
                                     'outer_freeze_sha256', 'root', 'frozen_xml', 'functional_native',
                                     'missing_frozen_files')} for e in entries]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def require_cache_revision(cache, revision):
    prepared = json.loads((Path(cache)/'prepared.json').read_text())
    if prepared.get('benchmark_revision', 2) != revision:
        raise ValueError('Prepared cache revision differs from requested runner revision')


def replay_frozen(entries, output, verify, native):
    results = {}
    for entry in entries:
        key = entry['id']
        result = {'generator_build': 'NOT_RUN', 'mode': 'frozen_native_replay',
                  'functional_native': entry['functional_native'],
                  'source_fingerprint': fingerprint([entry]),
                  'frozen_native_comparison': None, 'comparison_status': 'NOT_RUN'}
        if entry['functional_native'] == 'NOT_RUN':
            result['reason'] = entry['not_run_reason']
        else:
            directory = Path(output)/key
            delivery = working_copy(entry, directory/'delivery')
            summary = verify(delivery, directory/'verify')
            frozen = Path(entry['cache'])/entry['frozen_xml']
            rebuilt = directory/'verify/netlist.xml'
            result['gates'] = summary.get('gates', {})
            result['missing_frozen_dependencies'] = entry.get('missing_frozen_files', {})
            if rebuilt.is_file() and frozen.is_file():
                before, after = native(frozen), native(rebuilt)
                result['comparison_status'] = 'MEASURED'
                result['frozen_native_comparison'] = {'component_identity_equal': before['components'] == after['components'],
                    'physical_partition_equal': before['partitions'] == after['partitions'],
                    'frozen_sha256': sha(frozen), 'rebuilt_sha256': sha(rebuilt),
                    'frozen_xml': str(frozen), 'rebuilt_xml': str(rebuilt)}
        results[key] = result
    return results
