#!/usr/bin/env python3
"""Semantic boundary probes (F11-03, classification per F12-04: a PFU refusal is an exception with e.refused===true, a
PointTruth refusal is a Fault with an enumerated code; anything else is an ERROR with its stack), driven from tests/adapter-vectors.json (adapter-vectors/2). Every probe is executed
against the engine it names: 'pfu-browser' = this package's browser engine run in a Node vm from Point-File-Unit-Converter.html
(a corrupt HTML fails the run), 'pfu-python' = pointfile_units.py, 'pointtruth' = a PointTruth.html at $PT_HTML or beside this
script. Expected outcomes are complete (full output text and counts, or a refusal code). A missing PointTruth build marks its
probes SKIPPED, never passed. Unexpected exceptions are ERROR, distinct from refusals. These probes do not test a cross-family
serialized-record reader; none exists yet. Exit nonzero on any FAIL or ERROR."""
import json, pathlib, subprocess, sys, os, tempfile, re
HERE = pathlib.Path(__file__).resolve().parent; ROOT = HERE.parent.parent
TOOL = ROOT / 'pointfile_units.py'; PFU_HTML = ROOT / 'Point-File-Unit-Converter.html'; PT = pathlib.Path(os.environ.get('PT_HTML', HERE / 'PointTruth.html'))
CONV = {('ft', 'm'): 'IntlFeetToMeters'}
NODE_PFU = r"""const fs=require('fs'),vm=require('vm'),crypto=require('crypto');const html=fs.readFileSync(process.argv[1],'utf8');
const m=html.match(/<script id="engine">([\s\S]*?)<\/script>/); if(!m){console.log(JSON.stringify({error:'no engine script in the PFU HTML'}));process.exit(0);}
const ctx={TextDecoder,TextEncoder,Uint8Array,DataView,Int32Array,Promise,Object,Array,BigInt,Number,JSON,RegExp,Map,Set,Date,Error,Math,console,crypto:crypto.webcrypto,self:null};ctx.globalThis=ctx;ctx.self=ctx;vm.createContext(ctx);
try{vm.runInContext(m[1],ctx);}catch(e){console.log(JSON.stringify({error:'engine failed to load: '+e.message}));process.exit(0);}
const P=ctx.PFU; if(!P||!P.convertJob){console.log(JSON.stringify({error:'PFU.convertJob missing'}));process.exit(0);}
const [text,st,dec]=JSON.parse(process.argv[2]);
(async()=>{ try{ const r=await P.convertJob({bytes:new TextEncoder().encode(text),name:'in.txt',st,conversion:'IntlFeetToMeters',custom:'',decSel:String(dec),anchors:[],control:[],unitRef:'',ackWarn:true},function(){}); console.log(JSON.stringify({ok:true,text:new TextDecoder('utf-8',{ignoreBOM:true}).decode(r.bytes),header:r.rep.counts.header,data:r.rep.counts.data})); }catch(e){ if(e&&e.refused===true){ console.log(JSON.stringify({ok:false,kind:'refusal',code:'REFUSE',msg:String(e.message||'').slice(0,160)})); } else { console.log(JSON.stringify({ok:false,kind:'error',code:'EXCEPTION',msg:String(e&&e.stack||e).slice(0,300)})); } } })();"""
NODE_PT = r"""const fs=require('fs'),vm=require('vm'),crypto=require('crypto');const html=fs.readFileSync(process.argv[1],'utf8');const code=html.match(/<script id="engine">([\s\S]*?)<\/script>/)[1];
const ctx={TextDecoder,TextEncoder,Uint8Array,DataView,Int32Array,Promise,Object,Array,BigInt,Number,JSON,RegExp,Map,Set,Date,Error,Math,console,crypto:crypto.webcrypto};ctx.globalThis=ctx;vm.createContext(ctx);vm.runInContext(code,ctx);const P=ctx.PointTruth;
const CODES=new Set(['ANCHOR','BUILD','CONFIRM','CONTROL','CSV','DATA','EMPTY','ENCODING','FACTOR','FIELDS','HASH','IDENTIFIER','MAPPING','MAPPING_REVIEW','NAME','NUMBER','PACKAGE','PRECISION','PRECISION_OR_CHECK','PRESERVATION','REPORT','ROUNDING','SCHEMA','SETTINGS','SIZE']);
const [text,s]=JSON.parse(process.argv[2]);
(async()=>{ try{ const r=await P.convert(new TextEncoder().encode(text),{mode:'units',from:'ft',to:'m',custom:'',format:s.format,columns:s.columns,idColumn:s.idColumn,delimiter:s.delimiter||'whitespace',header:s.header,precision:s.precision,reference:'',anchors:[],controls:[],mappingAcknowledged:true,confirmed:true},'in.txt','a'.repeat(64)); console.log(JSON.stringify({ok:true,text:new TextDecoder('utf-8',{ignoreBOM:true}).decode(r.bytes),header:r.manifest.verification.counts.header,data:r.manifest.verification.counts.data})); }catch(e){ const isFault=e&&(e.name==='Fault'||(e.constructor&&e.constructor.name==='Fault')); console.log(JSON.stringify({ok:false,kind:(isFault&&e.code&&CODES.has(e.code))?'refusal':'error',code:e&&e.code||'EXCEPTION',msg:String(e&&(isFault?e.message:(e.stack||e))).slice(0,300)})); } })();"""
def node(script, html, arg):
    r = subprocess.run(['node', '-e', script, str(html), json.dumps(arg)], capture_output=True, text=True, encoding='utf-8', timeout=120)
    lines = [l for l in r.stdout.strip().splitlines() if l.startswith('{')]
    if r.returncode != 0 or not lines: return {'ok': False, 'kind': 'error', 'code': 'RUNNER', 'msg': (r.stderr or r.stdout)[-200:]}
    d = json.loads(lines[-1]); return {'ok': False, 'kind': 'error', 'code': 'RUNNER', 'msg': d['error']} if 'error' in d else d
def run_python(text, s):
    d = tempfile.mkdtemp(); src = os.path.join(d, 's.txt'); out = os.path.join(d, 'o.txt'); open(src, 'wb').write(text.encode('utf-8'))
    a = [sys.executable, str(TOOL), 'convert', '--in', src, '--out', out, '--format', s['format'], '--conversion', 'IntlFeetToMeters', '--delimiter', s.get('delimiter', 'whitespace'), '--header', s['header'], '--decimals', str(s['decimals']), '--force-mapping']
    if s['format'] == 'CUSTOM': a += ['--coords', ','.join(map(str, s['coords']))] + (['--id-field', str(s['id'])] if s.get('id') is not None else [])
    try: r = subprocess.run(a, capture_output=True, text=True, encoding='utf-8', errors='backslashreplace', timeout=120)
    except subprocess.TimeoutExpired: return {'ok': False, 'kind': 'error', 'code': 'TIMEOUT'}
    if r.returncode == 0 and os.path.exists(out):
        with open(out + '.manifest.json', encoding='utf-8') as fh: m = json.load(fh)
        return {'ok': True, 'text': open(out, 'rb').read().decode('utf-8'), 'header': m['counts']['header'], 'data': m['counts']['data']}
    if r.returncode == 2 and 'Traceback' not in (r.stderr + r.stdout): return {'ok': False, 'kind': 'refusal', 'code': 'REFUSE', 'msg': (r.stderr + r.stdout).strip().splitlines()[0][:160] if (r.stderr + r.stdout).strip() else ''}
    return {'ok': False, 'kind': 'error', 'code': 'EXIT%d' % r.returncode, 'msg': (r.stderr + r.stdout)[-200:]}
def judge(exp, got):
    if got.get('kind') == 'error': return 'ERROR', got.get('code', '') + ' ' + str(got.get('msg', ''))[:120]
    if exp['ok']:
        if not got['ok']: return 'FAIL', 'expected conversion, got refusal: ' + str(got.get('msg', ''))[:100]
        if got['text'] != exp['output']: return 'FAIL', 'output differs: %r' % got['text'][:80]
        if (got['header'], got['data']) != (exp['counts']['header'], exp['counts']['data']): return 'FAIL', 'counts header=%s data=%s, expected %s' % (got['header'], got['data'], exp['counts'])
        return 'PASS', ''
    if got['ok']: return 'FAIL', 'expected refusal, engine converted: %r' % got['text'][:80]
    if 'code' in exp and got.get('code') != exp['code']: return 'FAIL', 'refusal code %s, expected %s' % (got.get('code'), exp['code'])
    return 'PASS', ''
def main():
    with open(ROOT / 'tests' / 'adapter-vectors.json', encoding='utf-8') as fh: V = json.load(fh)
    assert V['contract'].startswith('adapter-vectors/2'), 'unexpected vector contract'
    print('semantic boundary probes from tests/adapter-vectors.json: pfu-browser=%s, pfu-python=%s, pointtruth=%s' % (PFU_HTML.name, TOOL.name, str(PT) if PT.exists() else 'ABSENT (its probes are SKIPPED, not passed)'))
    tally = {'PASS': 0, 'FAIL': 0, 'ERROR': 0, 'SKIPPED': 0}
    for v in V['vectors']:
        for i, p in enumerate(v['probes']):
            text = v['source'] if 'source' in v else v['source_' + p['source']]; eng = p['engine']; label = '%s[%d] %s%s' % (v['id'], i, eng, (' (' + p['note'] + ')') if p.get('note') else '')
            if eng == 'pointtruth' and not PT.exists(): verdict, why = 'SKIPPED', 'no PointTruth build'
            elif eng == 'pfu-browser': verdict, why = judge(p['expect'], node(NODE_PFU, PFU_HTML, [text, {k: p['settings'][k] for k in ('format', 'delimiter', 'header', 'coords', 'id') if k in p['settings']}, p['settings']['decimals']]))
            elif eng == 'pfu-python': verdict, why = judge(p['expect'], run_python(text, p['settings']))
            elif eng == 'pointtruth': verdict, why = judge(p['expect'], node(NODE_PT, PT, [text, p['settings']]))
            else: verdict, why = 'ERROR', 'unknown engine ' + eng
            tally[verdict] += 1; print('%-8s%s%s' % (verdict, label, ('  ' + why) if why else ''))
    print('semantic boundary probes: PASS %d  FAIL %d  ERROR %d  SKIPPED %d' % (tally['PASS'], tally['FAIL'], tally['ERROR'], tally['SKIPPED']))
    return 0 if tally['FAIL'] == 0 and tally['ERROR'] == 0 else 1
if __name__ == '__main__': sys.exit(main())
