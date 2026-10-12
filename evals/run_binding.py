"""Immutable run origin; resume may not relabel old rows as a new experiment."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def _tree(root):
    root=Path(root).resolve()
    return {str(p.relative_to(root)):_sha(p) for p in sorted(root.rglob('*'))
            if p.is_file() and '.git' not in p.relative_to(root).parts
            and '__pycache__' not in p.relative_to(root).parts}

def capture(repo,cache,revision,types,suite):
    repo=Path(repo).resolve();cache=Path(cache).resolve()
    if cache.is_relative_to(repo):
        raise ValueError('Benchmark cache must be outside the source checkout')
    prepared=cache/'prepared.json'
    names=subprocess.check_output(['git','-C',str(repo),'ls-files','-z','--cached','--others','--exclude-standard']).decode().split('\0')
    sources={n:_sha(repo/n) for n in sorted(set(names)) if n and (repo/n).is_file()}
    if not sources:raise ValueError('Empty actual source snapshot')
    data=json.loads(prepared.read_text())
    return {'schema_version':1,'suite':suite,'revision':revision,'types':list(types),
            'repo':str(repo),'cache':str(cache),
            'HEAD':subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip(),
            'source_bytes':sources,'prepared_sha256':_sha(prepared),
            'input_fingerprint':data.get('incremental_input_fingerprint'),
            'cache_bytes':_tree(cache)}

def open_run(out,binding,resume=False):
    out=Path(out).resolve()
    if out.is_relative_to(Path(binding['repo'])):
        raise ValueError('Benchmark output must be outside the source checkout')
    target=out/'run-binding.json'
    if resume:
        # Check before touching run-metadata, cached summaries, matrix or baseline.
        if not target.is_file():raise ValueError('Resume output has no immutable run binding; use a new output')
        try:original=json.loads(target.read_text())
        except (ValueError,OSError) as error:raise ValueError('Unreadable immutable run binding') from error
        if original!=binding:raise ValueError('Resume run binding differs; use a new output')
    else:
        out.mkdir(parents=True,exist_ok=False)
        with target.open('x') as handle:
            json.dump(binding,handle,sort_keys=True,ensure_ascii=False,indent=2);handle.write('\n')
    return {'path':str(target),'sha256':_sha(target)}

def validate_run(out,repo,cache,revision,types,suite,initial_receipt=None):
    if initial_receipt is not None and _sha(Path(out)/'run-binding.json')!=initial_receipt['sha256']:
        raise ValueError('Immutable run binding changed during execution')
    receipt=open_run(out,capture(repo,cache,revision,types,suite),resume=True)
    return {**receipt,'verified':True,'initial_receipt_verified':initial_receipt is not None,'scope':'Actual HEAD/source/cache snapshots, revision, fingerprint and types match the exclusive initial binding at resume and before final summary; immutable binding SHA checked against the starting receipt. Workflow must keep source locked during execution.'}
