#!/usr/bin/env python3
"""Drives Point-File-Unit-Converter.html headlessly (Playwright + Chromium) through the audit cases
and checks that every produced output is byte-identical to the Python engine's output for the same fixture.
Usage: cd tests && bash run_python_tests.sh && python3 run_browser_tests.py"""
import json, os, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright
HERE=os.path.dirname(os.path.abspath(__file__))
ROOT=os.path.dirname(HERE) if os.path.exists(os.path.join(os.path.dirname(HERE),'Point-File-Unit-Converter.html')) else HERE
def file_uri(path):
    """The one way this runner turns a local path into a navigable file URI (spaces, '#', Windows drives)."""
    return Path(path).resolve().as_uri()
APP=file_uri(Path(ROOT)/'Point-File-Unit-Converter.html')
import tempfile, subprocess
W=tempfile.mkdtemp(prefix='pfu-browser.'); os.chdir(W)
subprocess.run([sys.executable, os.path.join(HERE,'make_fixtures.py')], check=True, capture_output=True)
TOOL=os.path.join(ROOT,'pointfile_units.py')
def py(src,out,fmt,conv,*extra):
    r=subprocess.run([sys.executable,TOOL,'convert','--in',src,'--out',out,'--format',fmt,'--conversion',conv,*extra],capture_output=True,text=True); assert r.returncode==0, r.stdout+r.stderr
for a in [('penzd.txt','penzd_m.txt','PENZD','IntlFeetToMeters'),('sci.txt','b.txt','ENZ','IntlFeetToMeters'),('gapped.txt','d.txt','PENZD','IntlFeetToMeters'),('bigint.txt','e.txt','ENZ','Custom','--custom-factor','1'),('mixednl.txt','g.txt','PENZD','IntlFeetToMeters'),('spaces.txt','h.txt','PENZD','IntlFeetToMeters'),('quoted.csv','j.csv','PENZD','IntlFeetToMeters'),('neg.txt','o.txt','PENZD','Custom','--custom-factor','1'),('lf.csv','lf_ft.csv','ENZ','MetersToIntlFeet','--header','auto'),('bom.txt','bom_m.txt','PENZD','IntlFeetToMeters')]:
    py(*a)
open('tampered.txt','wb').write(b''.join(l.replace(b'"GRND"',b'"GRNX"') if i==2 else l for i,l in enumerate(open('penzd_m.txt','rb').read().splitlines(keepends=True))))
def rd(n): return open(n,'rb').read()
def strip_bom(b): return b[3:] if b.startswith(b'\xef\xbb\xbf') else b
results=[]
def check(name, ok, detail=''): ok=bool(ok); results.append(ok); print(('PASS  ' if ok else 'FAIL  ')+name+(('  '+str(detail)[:200]) if detail and not ok else ''))
with sync_playwright() as p:
    b=p.chromium.launch(); ctx=b.new_context(viewport={'width':1100,'height':900},bypass_csp=True,accept_downloads=True); pg=ctx.new_page(); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e))); ctx.add_init_script('window.PFU_TEST_FULL_DIAGNOSTICS=true')   # F11-04: the full byte copy in window._lastRun is test-only
    pg.goto(APP); pg.wait_for_timeout(400)
    UNITS={'IntlFeetToMeters':('ft','m'),'MetersToIntlFeet':('m','ft'),'USFeetToMeters':('usft','m'),'MetersToUSFeet':('m','usft'),'USFeetToIntlFeet':('usft','ft'),'IntlFeetToUSFeet':('ft','usft')}
    def setconv(conv):
        if conv=='Custom': pg.select_option('#mode','custom')
        else: pg.select_option('#mode','units'); pg.select_option('#from',UNITS[conv][0]); pg.select_option('#to',UNITS[conv][1])
    def load(name, fmt=None, conv=None, custom=None):
        pg.evaluate("window._loadBytes(%s, %s)"%(json.dumps(name), list(rd(name)))); pg.wait_for_timeout(250); pg.select_option('#decimals','auto'); pg.evaluate("document.getElementById('control').value=''"); pg.select_option('#header','no')
        if fmt: pg.select_option('#format',fmt)
        if conv: setconv(conv)
        if custom is not None: pg.fill('#customFactor',custom)
        if fmt and conv: pg.check('#confirm')
    def settled():
        t0=time.time()
        while time.time()-t0<60:
            st=pg.text_content('#hdrStatus')
            if st.startswith('working'): pg.wait_for_timeout(100); continue
            return
    def go(dry=False):
        pg.evaluate("window._lastRun=null"); pg.click('#previewBtn' if dry else '#convertBtn'); pg.wait_for_timeout(300); settled(); pg.wait_for_timeout(200)
        return pg.text_content('#status').replace('\n',' '), (pg.evaluate('window._lastRun') or {})
    def same(pyfile, r): return r.get('bytes') is not None and bytes(r['bytes'])==rd(pyfile)   # full bytes, BOM included
    check('buttons disabled until confirmed', pg.is_disabled('#convertBtn'))
    load('penzd.txt','PENZD','IntlFeetToMeters'); s,r=go(); check('T1 verified and == python bytes', 'checks passed' in s and same('penzd_m.txt',r))
    check('pass message names the declared source (international feet), no bare Verified', 'Arithmetic and preservation checks passed' in s and 'really in international feet.' in s and 'Verified' not in s and pg.text_content('#hdrStatus')=='checks passed')
    pg.select_option('#to','usft'); pg.wait_for_timeout(100); check('3.5 settings change invalidates result', pg.is_hidden('#dlBtn') and not pg.is_checked('#confirm'))
    load('penzd.txt','PENZD','IntlFeetToMeters'); pg.evaluate("(function(b){ window._lastRun=null; document.getElementById('convertBtn').click(); window._loadBytes('sci.txt', b); })(%s)"%list(rd('sci.txt'))); pg.wait_for_timeout(1200)   # one step: A is guaranteed to be running when B loads
    check('3.5 loading B mid-run cannot publish A', pg.evaluate('window._lastRun')==None and pg.is_hidden('#dlBtn') and 'sci.txt' in pg.text_content('#fileMeta'))
    load('penzd.txt','PENZD','Custom','1'); pg.evaluate("window._lastRun=null; document.getElementById('convertBtn').click(); var cf=document.getElementById('customFactor'); cf.value='2'; cf.dispatchEvent(new Event('input'));"); pg.wait_for_timeout(1200)
    check('R2 settings change while the worker runs publishes nothing', pg.evaluate('window._lastRun')==None and pg.is_hidden('#dlBtn') and not pg.is_checked('#confirm') and pg.is_hidden('#cancelBtn'))
    r1=pg.evaluate("(function(){var d=window._dbg; return d.verifyBytes(new TextEncoder().encode('1 2 3\\n'),new TextEncoder().encode('1.4000 2.0000 3.0000\\n'),{format:'ENZ',delimiter:'whitespace',header:'no'},d.R(1n),4,[],[]);})()")
    check('R1 verifier rejects wrong rounding', not r1['pass'] and any('nearest-ties-to-even' in f for f in r1['failures']))
    r3=pg.evaluate("(function(){var d=window._dbg; return d.verifyBytes(new TextEncoder().encode('A 999 999 999\\nA 10 20 30\\n'),new TextEncoder().encode('A 999.0000 999.0000 999.0000\\nA 10.0000 20.0000 30.0000\\n'),{format:'PENZD',delimiter:'whitespace',header:'no'},d.R(1n),4,[],[{id:'A',values:[d.R(10n),d.R(20n),d.R(30n)],tol:d.R(0n)}]);})()")
    check('R3 duplicate control id is ambiguous', not r3['pass'] and any('ambiguous' in f for f in r3['failures']))
    pg.evaluate("window._loadBytes('dbom.txt', %s)"%list(b'\xef\xbb\xbf\xef\xbb\xbf# c\n1 2 3\n')); pg.wait_for_timeout(300)
    check('R9 stray U+FEFF refused at load', 'U+FEFF' in pg.text_content('#status'))
    load('nonfinite.txt','ENZ','IntlFeetToMeters'); s,r=go(); check('3.1 non-finite refused', 'exponent exceeds' in s)
    load('sci.txt','ENZ','IntlFeetToMeters'); s,r=go(); check('3.2 sci notation == python', same('b.txt',r))
    load('onebad.txt','PENZD','IntlFeetToMeters'); s,r=go(); check('3.3 one bad row refused', 'line 100' in s and 'out' not in r)
    load('gapped.txt','PENZD','IntlFeetToMeters'); s,r=go(); check('3.4 gapped ids == python', same('d.txt',r))
    load('bigint.txt','ENZ','Custom','1'); s,r=go(); check('3.8 big int == python', same('e.txt',r))
    load('gapped.txt','PENZD','Custom','2'); s,r=go(); a=r['out']
    pg.evaluate("window._loadText('f.txt', %s)"%json.dumps(a)); pg.wait_for_timeout(200); pg.select_option('#header','no'); pg.select_option('#format','PENZD'); setconv('Custom'); pg.fill('#customFactor','1/2'); pg.check('#confirm'); s,r2=go()
    check('3.6 custom factor 2 then exact reciprocal 1/2 (manual)', r2['out'].splitlines()[0].startswith('1 100.250000 200.250000 10.250000'))
    load('mixednl.txt','PENZD','IntlFeetToMeters'); s,r=go(); check('3.7 mixed newlines == python', same('g.txt',r))
    load('spaces.txt','PENZD','IntlFeetToMeters'); s,r=go(); check('3.7 spaces == python', same('h.txt',r))
    load('latin1.txt'); check('3.7 latin-1 refused', 'not valid UTF-8' in pg.text_content('#status'))
    load('quoted.csv','PENZD','IntlFeetToMeters'); s,r=go(); check('4.6 quoted csv == python', same('j.csv',r))
    load('deccomma.txt','PENZD','IntlFeetToMeters'); s,r=go(); check('4.5 decimal comma ws refused', 'Refused' in s)
    load('deccomma2.csv','PENZD','IntlFeetToMeters'); s,r=go(); check('4.5 decimal comma csv refused', 'found 8' in s)
    load('intcoords.txt','ENZ','IntlFeetToMeters'); s,r=go(); check('integer coords need acknowledgement', 'mapping warning' in s and not pg.is_hidden('#ackWrap'))
    pg.check('#ackWarn'); s,r=go(); check('integer coords pass after acknowledgement', 'checks passed' in s)
    load('neg.txt','PENZD','Custom','1'); s,r=go(); check('negatives == python', same('o.txt',r))
    load('penzd.txt','PENZD','IntlFeetToMeters'); pg.select_option('#decimals','4'); pg.check('#confirm'); s,r=go(); check('too few decimals refused (4-dp feet to 4-dp metres)', 'verification failed' in s)
    load('penzd_m.txt','PENZD','MetersToIntlFeet'); pg.select_option('#decimals','4'); pg.check('#confirm'); s,r=go(); check('exact round trip reproduces source bytes', 'checks passed' in s and r['out'].encode()==rd('penzd.txt'))
    check('pass message names the declared source (metres)', 'really in metres.' in s)
    load('penzd.txt','PENZD','IntlFeetToMeters'); pg.click('#ctrlFold summary'); pg.fill('#anchors input[data-a="max-3"]','20'); pg.check('#confirm'); s,r=go(); check('anchor miss refused', 'anchor field 3 failed' in s)
    pg.fill('#anchors input[data-a="max-3"]',''); pg.fill('#control','6 6065.5576 6187.6131 30.48 0.001'); pg.check('#confirm'); s,r=go(); check('control point recorded with exact fields', 'Control point 6 : pass' in r['report'] and r['manifest']['control_points'][0]['tolerance']=='0.001' and r['manifest']['control_points'][0]['checked_fields']==[1,2,3])
    load('lf.csv','ENZ','MetersToIntlFeet'); pg.select_option('#header','yes'); pg.check('#confirm'); s,r=go(); check('csv header == python', same('lf_ft.csv',r) and r['manifest']['counts']['header']==1)
    load('bom.txt','PENZD','IntlFeetToMeters'); s,r=go(); check('bom == python', same('bom_m.txt',r) and r['manifest']['source']['encoding']=='utf-8-bom')
    load('penzd.txt','PENZD','IntlFeetToMeters'); s,r=go()
    check('R10/N7 execution id and content fingerprint present, schema 3', len(r['manifest']['run_id'])==16 and len(r['manifest']['content_fingerprint'])==16 and r['manifest']['schema']=='pointfile-units-report/3')
    up=lambda arr: pg.evaluate("""(function(a){var f=new File([new Uint8Array(a)],'x.txt');var dt=new DataTransfer();dt.items.add(f);var i=document.getElementById('reupInput');i.files=dt.files;i.dispatchEvent(new Event('change'));})(%s)"""%arr)
    up(list(rd('penzd_m.txt'))); pg.wait_for_timeout(700); pg.wait_for_timeout(600); check('re-upload of good copy verifies', 'Saved file verified' in pg.text_content('#reupResult'), pg.text_content('#reupResult')[:120])
    up(list(rd('tampered.txt'))); pg.wait_for_timeout(700); check('re-upload of tampered copy fails', 'FAILED' in pg.text_content('#reupResult'))
    with pg.expect_download() as dl: pg.click('#dlBtn')
    check('download offered with expected name', dl.value.suggested_filename=='penzd-M.txt')
    # third review
    pg.evaluate("window._loadBytes('n2.txt', %s)"%list(b'1 2 3\n')); pg.wait_for_timeout(200); pg.select_option('#decimals','auto'); pg.select_option('#header','no'); pg.select_option('#format','ENZ'); setconv('Custom'); pg.fill('#customFactor','1'); pg.check('#confirm'); pg.evaluate("window._lastRun=null")
    pg.evaluate("(function(){ var orig=crypto.subtle.digest.bind(crypto.subtle); window._origDigest=orig; window._held=null; crypto.subtle.digest=function(n,b){ var t=new TextDecoder().decode(b); if(t.startsWith('{\"anchors\":')){ return new Promise(function(res){ window._held=function(){ orig(n,b).then(res); }; }); } return orig(n,b); }; })()")
    pg.click('#convertBtn'); pg.wait_for_timeout(900); held=pg.evaluate("!!window._held")
    pg.fill('#customFactor','2'); pg.wait_for_timeout(100); pg.evaluate("window._held && window._held()"); pg.wait_for_timeout(600)
    check('N2 settings change while the final fingerprint hash is pending publishes nothing', held and pg.evaluate('window._lastRun')==None and pg.is_hidden('#dlBtn'))
    pg.evaluate("window._loadBytes('n2b.txt', %s)"%list(b''.join(b'%d %d %d\n'%(i+1,i+21,i+41) for i in range(10)))); pg.wait_for_timeout(200); pg.select_option('#header','no'); pg.select_option('#format','ENZ'); setconv('Custom'); pg.fill('#customFactor','1'); pg.check('#confirm'); pg.click('#convertBtn'); pg.wait_for_timeout(800); pg.check('#ackWarn'); pg.evaluate("window._lastRun=null")
    pg.click('#convertBtn'); pg.wait_for_timeout(900); held=pg.evaluate("!!window._held"); pg.uncheck('#ackWarn'); pg.evaluate("window._held && window._held()"); pg.wait_for_timeout(600)
    check('N2 acknowledgement withdrawn while pending publishes nothing', held and pg.evaluate('window._lastRun')==None and pg.is_hidden('#dlBtn'))
    pg.evaluate("(function(){ crypto.subtle.digest=window._origDigest; })()")   # restore: later cases hash normally
    v1=pg.evaluate("(function(){ try{ window._dbg.validateSettings({format:'CUSTOM',delimiter:'whitespace',header:'no',coords:[0],id:0}); return 'accepted'; }catch(e){ return e.message; } })()"); check('N1 identifier == coordinate refused', 'both' in v1)
    v2=pg.evaluate("(function(){ try{ window._dbg.validateSettings({format:'CUSTOM',delimiter:'whitespace',header:'no',coords:[1.5],id:null}); return 'accepted'; }catch(e){ return e.message; } })()"); check('N1 fractional index refused', 'nonnegative integers' in v2)
    r6=pg.evaluate("(function(){ var d=window._dbg; var e=new TextEncoder(); return d.verifyBytes(e.encode('constructor 1 2 3\\n'),e.encode('constructor 1.0000 2.0000 3.0000\\n'),{format:'PENZD',delimiter:'whitespace',header:'no'},d.R(1n),4,[],[{id:'constructor',values:[d.R(1n),d.R(2n),d.R(3n)],tol:d.R(0n)}]); })()"); check('N6 reserved-name identifier handled', r6['pass'], r6['failures'])
    check('N6 Unicode digit rejected', pg.evaluate("window._dbg.parseToken('\u0661')")==None)
    st=pg.evaluate("window._selfTest()"); check('self-test passes in page (%d checks)'%(st['pass']+st['fail']), st['fail']==0, [l for l in st['text'].splitlines() if l.startswith('FAIL')])
    py('penzd.txt','penzd_m_v.txt','PENZD','IntlFeetToMeters'); import shutil
    pg.click('#modeVerify'); pg.set_input_files('#vSrc','penzd.txt'); pg.set_input_files('#vOut','penzd_m_v.txt'); pg.set_input_files('#vMan','penzd_m_v.txt.manifest.json'); pg.click('#vRun'); pg.wait_for_timeout(1500); check('verify mode accepts CLI artefacts', 'VERIFY PASS' in pg.text_content('#vLog'), pg.text_content('#vStatus')[:120])
    bad=json.load(open('penzd_m_v.txt.manifest.json')); bad['counts']['data']=999; json.dump(bad,open('bad.json','w')); pg.set_input_files('#vMan','bad.json'); pg.click('#vRun'); pg.wait_for_timeout(1500); check('verify mode detects fabricated statistics', 'recorded counts' in pg.text_content('#vLog'))
    # v3.3: second rounding procedure, handoff round-trip, cancel, strict CSP
    pg.click('#modeConvert')
    tie=pg.evaluate("(function(){var d=window._dbg; var ok=true; [['2.5',0,'2'],['-2.5',0,'-2'],['3.5',0,'4'],['-3.5',0,'-4'],['0.125',2,'0.12']].forEach(function(t){ var v=d.parseToken(t[0]).v; if(d.serialize(d.roundHalfEven(v,t[1]),t[1])!==t[2]||d.serialize(d.nearestFloor(d.R(v.n*(10n**BigInt(t[1])),v.d)),t[1])!==t[2])ok=false; }); return ok; })()"); check('two rounding procedures agree on ties, both signs', tie)
    load('penzd.txt','PENZD','IntlFeetToMeters'); s,r=go()
    with pg.expect_download() as dl: pg.click('#dlHandoffBtn')
    hp=os.path.join(W,'t.handoff.html'); dl.value.save_as(hp); check('complete handoff saved', os.path.getsize(hp)>100000)
    pg2=ctx.new_page(); pg2.goto(file_uri(hp)); t0=time.time()
    while time.time()-t0<30 and not pg2.text_content('#hdrStatus').startswith('handoff'): pg2.wait_for_timeout(100)
    check('handoff re-verifies on open and restores settings', pg2.text_content('#hdrStatus').startswith('handoff verified') and pg2.input_value('#from')=='ft' and pg2.evaluate('bytes(window._lastRun.bytes)' if False else 'window._lastRun.bytes.length')==len(rd('penzd_m.txt')))
    h=open(hp,encoding='utf-8').read(); i=h.index('"outputBase64":"')+len('"outputBase64":"'); ch=h[i+40]; open(os.path.join(W,'t2.html'),'w',encoding='utf-8').write(h[:i+40]+('B' if ch!='B' else 'C')+h[i+41:])
    pg3=ctx.new_page(); pg3.goto(file_uri(os.path.join(W,'t2.html'))); t0=time.time()
    while time.time()-t0<30 and not pg3.text_content('#hdrStatus').startswith('handoff'): pg3.wait_for_timeout(100)
    check('tampered handoff refused on open', pg3.text_content('#hdrStatus').startswith('handoff failed') and pg3.is_hidden('#dlBtn'))
    pg.set_input_files('#fileInput',hp); t0=time.time()
    while time.time()-t0<30 and not pg.text_content('#hdrStatus').startswith('handoff'): pg.wait_for_timeout(100)
    check('handoff dropped on the loader re-verifies', pg.text_content('#hdrStatus').startswith('handoff verified'))
    big=b''.join(b'%d %.4f %.4f %.4f "G"\n'%(i,19800+i*0.01,20200+i*0.02,95+i*0.0001) for i in range(1,30001)); open(os.path.join(W,'big.txt'),'wb').write(big)
    pg.set_input_files('#fileInput',os.path.join(W,'big.txt')); pg.wait_for_timeout(1500); pg.select_option('#format','PENZD'); pg.select_option('#header','no'); setconv('IntlFeetToMeters'); pg.check('#confirm'); pg.click('#convertBtn'); pg.wait_for_timeout(150); busy=not pg.is_hidden('#cancelBtn'); pg.click('#cancelBtn'); pg.wait_for_timeout(300)
    check('cancel stops a running worker', busy and pg.is_hidden('#cancelBtn') and pg.text_content('#hdrStatus').startswith('cancelled'))
    strict=b.new_context(); ps=strict.new_page(); cspErr=[]; ps.on('console',lambda m: cspErr.append(m.text) if m.type=='error' else None); ps.goto(APP); ps.wait_for_timeout(600); ps.set_input_files('#fileInput',os.path.join(W,'penzd.txt')); ps.wait_for_timeout(400); ps.select_option('#mode','units'); ps.select_option('#from','ft'); ps.select_option('#to','m'); ps.check('#confirm'); ps.click('#convertBtn'); t0=time.time()
    while time.time()-t0<30 and not ps.text_content('#hdrStatus').startswith('checks passed'): ps.wait_for_timeout(100)
    check('strict CSP: blob worker runs, conversion verifies, no CSP console errors', ps.text_content('#hdrStatus').startswith('checks passed') and not [x for x in cspErr if 'Content Security' in x], cspErr[:2]); strict.close()
    # ---- round 4 (review of v3.2) ----
    pg.click('#modeVerify')
    py('penzd.txt','q4v_m.txt','PENZD','IntlFeetToMeters'); open('wrong.out','wb').write(b'9 9 9 9 nope\n')
    # #1: change the output selection while reads are pending -> nothing displayed for the old selection
    pg.evaluate("(function(){ var orig=FileReader.prototype.readAsArrayBuffer; window._heldReads=[]; FileReader.prototype.readAsArrayBuffer=function(f){ var self=this; window._heldReads.push(function(){ orig.call(self,f); }); }; window._restoreReader=function(){ FileReader.prototype.readAsArrayBuffer=orig; }; })()")
    pg.set_input_files('#vSrc','penzd.txt'); pg.set_input_files('#vOut','q4v_m.txt'); pg.set_input_files('#vMan','q4v_m.txt.manifest.json'); pg.click('#vRun'); pg.wait_for_timeout(300)
    pending=pg.evaluate("window._heldReads.length"); pg.set_input_files('#vOut','wrong.out'); pg.wait_for_timeout(100); pg.evaluate("window._heldReads.splice(0).forEach(function(f){f();})"); pg.wait_for_timeout(1500)
    check('Q4#1 verify: selection changed while reads pending -> no verdict shown for the old files', pending==3 and pg.evaluate('window._lastVerify')==None and pg.is_hidden('#vLog'), (pending, pg.text_content('#vStatus')[:80]))
    pg.evaluate("window._restoreReader()")
    pg.set_input_files('#vOut','q4v_m.txt'); pg.click('#vRun'); t0=time.time()
    while time.time()-t0<20 and not pg.text_content('#vStatus').startswith('Verified'): pg.wait_for_timeout(100)
    ok1='VERIFY PASS' in pg.text_content('#vLog') and 'penzd.txt' in pg.text_content('#vLog') and 'SHA-256' in pg.text_content('#vLog')
    pg.set_input_files('#vSrc','wrong.out'); pg.wait_for_timeout(200)
    check('Q4#1 verify: verdict shows checked names+hashes and is cleared on any later selection change', ok1 and pg.is_hidden('#vLog') and pg.text_content('#vStatus')=='')
    # #1b: source-selection race: first.txt read completes last -> latest.txt must win
    pg.click('#modeConvert'); open('first.txt','wb').write(b'1 2 3\n'); open('latest.txt','wb').write(b'4 5 6\n')
    pg.evaluate("(function(){ var orig=FileReader.prototype.readAsArrayBuffer; window._q=[]; FileReader.prototype.readAsArrayBuffer=function(f){ var self=this; window._q.push([f.name,function(){ orig.call(self,f); }]); }; window._restoreReader=function(){ FileReader.prototype.readAsArrayBuffer=orig; }; })()")
    pg.set_input_files('#fileInput','first.txt'); pg.wait_for_timeout(100); pg.set_input_files('#fileInput','latest.txt'); pg.wait_for_timeout(100)
    pg.evaluate("(function(){ var q=window._q.splice(0); q.filter(function(x){return x[0]==='latest.txt';}).forEach(function(x){x[1]();}); q.filter(function(x){return x[0]==='first.txt';}).forEach(function(x){x[1]();}); })()"); pg.wait_for_timeout(800)
    check('Q4#1b source race: the latest selection wins even when its read completes first', 'latest.txt' in pg.text_content('#fileMeta') and pg.evaluate("window._S.name")=='latest.txt'); pg.evaluate("window._restoreReader()")
    # #3 Unicode manifest from Python verifies in the browser; #3b sorted keys
    py('penzd.txt','q3u.txt','PENZD','IntlFeetToMeters','--source-unit-reference','caf\u00e9 survey notes / \u6e2c\u91cf \U0001F600')
    r3=pg.evaluate("(function(a,b,m){ return window._standaloneVerify(new Uint8Array(a),new Uint8Array(b),m,null).then(function(r){return {ok:r.ok,fresh:r.fresh,cons:r.consistency};}); })(%s,%s,%s)"%(list(rd('penzd.txt')),list(rd('q3u.txt')),open('q3u.txt.manifest.json',encoding='utf-8').read()))
    check('Q4#3 Python manifest with Unicode reference verifies in the browser (fingerprint agrees)', r3['ok'], r3)
    def sorted_obj(o):
        if isinstance(o,dict): return {k:sorted_obj(o[k]) for k in sorted(o)}
        if isinstance(o,list): return [sorted_obj(x) for x in o]
        return o
    r3b=pg.evaluate("(function(a,b,m){ return window._standaloneVerify(new Uint8Array(a),new Uint8Array(b),m,null).then(function(r){return r.ok;}); })(%s,%s,%s)"%(list(rd('penzd.txt')),list(rd('q3u.txt')),json.dumps(sorted_obj(json.load(open('q3u.txt.manifest.json',encoding='utf-8'))))))
    check('Q4#3b re-serialized manifest with sorted keys still verifies', r3b)
    cf=json.load(open(os.path.join(HERE,'canonical-fixtures.json'),encoding='utf-8'))['cases']
    r3c=pg.evaluate("(function(cs){ return cs.every(function(c){ return window._dbg.canonicalJson(c.input)===c.canonical; }); })(%s)"%json.dumps(cf))
    check('Q4#3 canonical-form contract fixtures (%d) reproduce byte-for-byte in the browser'%len(cf), r3c)
    # #2 mutations must fail in the browser too
    py('penzd.txt','q2ac.txt','PENZD','IntlFeetToMeters','--anchor','3:25:35','--control-point','6 6065.5576 6187.6131 30.48 0.001'); base=json.load(open('q2ac.txt.manifest.json',encoding='utf-8')); import copy
    muts={'anchor_observation':lambda m:m['anchors'][0].update(observed_min='999',observed_max='999'),'control_observation':lambda m:m['control_points'][0].update(written=['999','999','999'],line=999,checked_fields=[63]),'file_metadata':lambda m:m['source'].update(bytes=999),'checks':lambda m:m['checks'].update(non_coordinate_preservation='fail'),'failures':lambda m:m.update(failures=['x'])}
    allrefused=True
    for k,fn in muts.items():
        m=copy.deepcopy(base); fn(m)
        r=pg.evaluate("(function(a,b,m){ return window._standaloneVerify(new Uint8Array(a),new Uint8Array(b),m,null).then(function(r){return r.ok;},function(e){return 'refused';}); })(%s,%s,%s)"%(list(rd('penzd.txt')),list(rd('q2ac.txt')),json.dumps(m)))
        if r is True: allrefused=False; print('   mutation passed:',k)
    check('Q4#2 observation-field mutations refused in the browser', allrefused)
    r8=pg.evaluate("(function(m){ try{ window._validateManifest(m); return 'accepted'; }catch(e){ return e.message; } })(%s)"%json.dumps(dict(base, max_error_at=1)))
    check('Q4#8 max_error_at scalar refused with a message', 'max_error_at' in r8)
    r6=pg.evaluate("(function(m){ return window._standaloneVerify(new Uint8Array(%s),new Uint8Array(%s),m,null).then(function(r){return r.ok;},function(e){return 'refused';}); })(%s)"%(list(rd('penzd.txt')),list(rd('q3u.txt')),json.dumps(dict(base, units=dict(base['units'],conversion='Custom',custom_factor_input='1/1/999')))))
    check('Q4#6 custom_factor_input 1/1/999 refused in the browser', r6 is not True)
    # ---- round 5 (review of v3.3.1) ----
    pg.click('#modeConvert'); load('penzd.txt','PENZD','IntlFeetToMeters'); s,r=go()
    with pg.expect_download() as dl: pg.click('#dlHandoffBtn')
    hp5=os.path.join(W,'r5.handoff.html'); dl.value.save_as(hp5); h=open(hp5,encoding='utf-8').read()
    check('R5-01 envelope carries no free text (now /3 with exact record text)', '"format":"pfu-handoff/3"' in h and '"report":' not in h.split('<script id="savedPackage"')[1].split('</script>')[0])
    # forge an envelope /1 with false prose around a valid record: the displayed report must be regenerated from the record
    i=h.index('<script id="savedPackage" type="application/json">')+len('<script id="savedPackage" type="application/json">'); j=h.index('</script>',i)
    pkg=json.loads(h[i:j].replace('\\u003c','<')); pkg={'format':'pfu-handoff/1','sourceBase64':pkg['sourceBase64'],'outputBase64':pkg['outputBase64'],'manifest':json.loads(pkg['recordText']),'report':'Records       : data 999999\nUnits         : factor 1000/1\nStatus        : FAKE'}
    forged=h[:i]+json.dumps(pkg).replace('<','\\u003c')+h[j:]; fp=os.path.join(W,'r5_forged.html'); open(fp,'w',encoding='utf-8').write(forged)
    pgf=ctx.new_page(); pgf.goto(file_uri(fp)); t0=time.time()
    while time.time()-t0<30 and not pgf.text_content('#hdrStatus').startswith('handoff'): pgf.wait_for_timeout(100)
    shown=pgf.text_content('#log'); check('R5-01 forged prose is discarded; displayed report regenerated from the verified record', pgf.text_content('#hdrStatus').startswith('handoff verified') and 'data 40' in shown and '999999' not in shown and 'FAKE' not in shown and 'free text' in shown)
    with pgf.expect_download() as dlr: pgf.click('#dlRepBtn')
    rp=os.path.join(W,'r5_report.txt'); dlr.value.save_as(rp); check('R5-01 downloaded report is the regenerated one', '999999' not in open(rp,encoding='utf-8').read() and 'data 40' in open(rp,encoding='utf-8').read())
    # R5-03: settings edit during handoff replay retires the restoration
    pgf2=ctx.new_page(); pgf2.goto(APP); pgf2.wait_for_timeout(400); pgf2.evaluate("window._loadBytes('penzd.txt', %s)"%list(rd('penzd.txt'))); pgf2.wait_for_timeout(300)
    pgf2.evaluate("(function(){ var orig=crypto.subtle.digest.bind(crypto.subtle); window._orig=orig; window._held=[]; crypto.subtle.digest=function(n,b){ return new Promise(function(res){ window._held.push(function(){ orig(n,b).then(res); }); }); }; })()")
    pgf2.set_input_files('#fileInput',hp5); pgf2.wait_for_timeout(600); pgf2.select_option('#mode','custom'); pgf2.fill('#customFactor','999'); pgf2.wait_for_timeout(100)
    pgf2.evaluate("(function(){ crypto.subtle.digest=window._orig; window._held.splice(0).forEach(function(f){f();}); })()"); pgf2.wait_for_timeout(1500)
    check('R5-03 settings edit during handoff replay: nothing restored or published', pgf2.input_value('#customFactor')=='999' and pgf2.evaluate('window._S.out===null') and pgf2.is_hidden('#dlBtn'))
    # R5-03: a new selection retires the old result immediately, before its bytes are read
    load('penzd.txt','PENZD','IntlFeetToMeters'); s,r=go(); pg.evaluate("(function(){ var orig=FileReader.prototype.readAsArrayBuffer; window._held2=[]; FileReader.prototype.readAsArrayBuffer=function(f){ var self=this; window._held2.push(function(){ orig.call(self,f); }); }; window._restore2=function(){ FileReader.prototype.readAsArrayBuffer=orig; }; })()")
    pg.set_input_files('#fileInput','sci.txt'); pg.wait_for_timeout(200)
    check('R5-03 selection start retires the previous result (downloads hidden, confirmation cleared) while the read is pending', pg.evaluate('window._S.out===null') and pg.is_hidden('#dlBtn') and not pg.is_checked('#confirm'))
    pg.evaluate("window._held2.splice(0).forEach(function(f){f();}); window._restore2();"); pg.wait_for_timeout(400)
    # R5-03: a conversion whose final hash completes after a new selection must not publish
    load('penzd.txt','PENZD','Custom','1'); pg.evaluate("(function(){ var orig=crypto.subtle.digest.bind(crypto.subtle); window._orig3=orig; window._held3=[]; crypto.subtle.digest=function(n,b){ var t=new TextDecoder().decode(b); if(t.startsWith('{\"anchors\":')){ return new Promise(function(res){ window._held3.push(function(){ orig(n,b).then(res); }); }); } return orig(n,b); }; })()")
    pg.evaluate("window._lastRun=null"); pg.click('#convertBtn'); pg.wait_for_timeout(900); held=pg.evaluate("window._held3.length>0")
    pg.set_input_files('#fileInput','sci.txt'); pg.wait_for_timeout(200); pg.evaluate("(function(){ crypto.subtle.digest=window._orig3; window._held3.splice(0).forEach(function(f){f();}); })()"); pg.wait_for_timeout(800)
    check('R5-03 late final hash after a new selection publishes nothing', held and pg.evaluate('window._lastRun')==None and pg.evaluate('window._S.out===null'))
    # R5-02: re-upload race: older correct read completing after a newer wrong check must not replace the newer verdict
    load('penzd.txt','PENZD','IntlFeetToMeters'); s,r=go(); good=os.path.join(W,'r5_good.txt'); open(good,'wb').write(bytes(r['bytes'])); bad=os.path.join(W,'r5_bad.txt'); open(bad,'wb').write(b'wrong data\n')
    pg.evaluate("(function(){ var orig=FileReader.prototype.readAsArrayBuffer; window._q5=[]; FileReader.prototype.readAsArrayBuffer=function(f){ var self=this; window._q5.push([f.name,function(){ orig.call(self,f); }]); }; window._restore5=function(){ FileReader.prototype.readAsArrayBuffer=orig; }; })()")
    pg.set_input_files('#reupInput',good); pg.wait_for_timeout(100); pg.set_input_files('#reupInput',bad); pg.wait_for_timeout(100)
    pg.evaluate("(function(){ var q=window._q5.splice(0); q.filter(function(x){return x[0]==='r5_bad.txt';}).forEach(function(x){x[1]();}); })()"); pg.wait_for_timeout(900); mid=pg.text_content('#reupResult')
    pg.evaluate("(function(){ var q=window._q5.splice(0); q.forEach(function(x){x[1]();}); window._restore5(); })()"); pg.wait_for_timeout(900); fin=pg.text_content('#reupResult')
    check('R5-02 older good read cannot overwrite the newer wrong-file verdict', 'FAILED' in mid and 'r5_bad.txt' in mid and 'FAILED' in fin and 'r5_bad.txt' in fin, (mid[:80], fin[:80]))
    # R5-04: entered limits are uniform (40 digits); a boundary control converts and its record re-verifies (self-replay ran before publish)
    load('penzd.txt','PENZD','IntlFeetToMeters'); pg.evaluate("document.getElementById('ctrlFold').open=true"); pg.fill('#control','6 6065.5576 6187.6131 30.48 '+'1'*40+'e30'); pg.check('#confirm'); s,r=go(); check('R5-04 max entered tolerance converts and self-replays', 'checks passed' in s, s[:120])
    pg.fill('#control','6 6065.5576 6187.6131 30.48 '+'1'*41); pg.check('#confirm'); s,r=go(); check('R5-04 41-digit control refused at entry', 'Refused' in s and '40 digits' in s)
    # R5-05/06/07 in the browser verifier
    pg.fill('#control',''); pg.check('#confirm'); s,r=go(); m5=r['manifest']
    def sv(m): return pg.evaluate("(function(a,b,m){ return window._standaloneVerify(new Uint8Array(a),new Uint8Array(b),m,null).then(function(r){return {ok:r.ok,u:r.unsupported,c:r.consistency};}); })(%s,%s,%s)"%(list(rd('penzd.txt')),list(bytes(r['bytes'])),json.dumps(m)))
    x=sv(dict(m5,rounding=dict(m5['rounding'],finest_source_decimals=999))); check('R5-05 finest_source_decimals mutation refused in the browser', not x['ok'] and any('finest' in c for c in x['c']))
    x=sv(dict(m5,grammar=dict(m5['grammar'],comment_prefix=';'))); check("R5-05 comment_prefix ';' unsupported", not x['ok'] and x['u'] and 'comment_prefix' in x['u'])
    x=sv(dict(m5,grammar=dict(m5['grammar'],identifier_policy='silently-renumber'))); check('R5-05 unknown grammar key unsupported', not x['ok'] and x['u'] and 'unknown field' in x['u'])
    x=sv(dict(m5,source=dict(m5['source'],sha256=m5['source']['sha256'].upper()),output=dict(m5['output'],sha256=m5['output']['sha256'].upper()))); check('R5-07 uppercase digest spelling still verifies', x['ok'], x)
    x=pg.evaluate("(function(){ try{ window._dbg.canonicalJson({}); PFU.refuseNonIntegerNumbers('{\"a\":\"1.0\",\"b\":1}'); PFU.refuseNonIntegerNumbers('{\"a\":1.0}'); return 'accepted'; }catch(e){ return e.message; } })()"); check('R5-06 float literal in a record is unsupported (lexical check; strings untouched)', 'non-integer JSON number' in x)
    v2=json.load(open(os.path.join(HERE,'canonical-v2-fixtures.json'),encoding='utf-8')); r2=pg.evaluate("(function(fx){ var ok=fx.cases.every(function(c){ return window._dbg.canonicalJson2(c.input)===c.canonical; }); var ref=fx.refused.every(function(c){ try{ window._dbg.canonicalJson2(JSON.parse(c.input_json)); return false; }catch(e){ return true; } }); return ok&&ref; })(%s)"%json.dumps(v2)); check('R5-06 canonical-json/2 candidate fixtures + refusals reproduce in the browser', r2)
    check('R5-07 manifest digests are lowercase', m5['source']['sha256']==m5['source']['sha256'].lower() and m5['content_fingerprint']==m5['content_fingerprint'].lower())
    # ---- round 6 (review of v3.3.2) ----
    def svb(m, src=None, out=None): return pg.evaluate("(function(a,b,m){ return window._standaloneVerify(new Uint8Array(a),new Uint8Array(b),m,null,new Uint8Array(m.__raw||[])).then(function(r){return {ok:r.ok,u:r.unsupported,c:r.consistency,adapter:r.adapter,text:r.text};}); })(%s,%s,%s)"%(list(src if src is not None else rd('penzd.txt')),list(out if out is not None else bytes(r['bytes'])),json.dumps(m)))
    LR=os.path.join(HERE,'legacy-records')
    for d,nm,adapter in [('v3.3.1-python','base','legacy adapter A'),('v3.3.1-python','cross-unicode','legacy adapter A'),('v3.2.0-browser','cross','legacy adapter A'),('v3.1.0-browser','record',None),('v3.3.2-python-handoff','handoff',None)]:
        bp=os.path.join(LR,d,nm); m=json.load(open(bp+'.out.manifest.json',encoding='utf-8')); x=svb(m, open(bp+'.src','rb').read(), open(bp+'.out','rb').read())
        check('R6-02 immutable %s/%s verifies in the browser%s'%(d,nm,' via '+adapter if adapter else ''), x['ok'] and (adapter is None or (x['adapter'] or '')!='' and adapter in x['adapter']), (x['u'],x['c'][:2]))
    x=svb(dict(m5,rounding=dict(m5['rounding'],acceptance='some other sentence'))); check('R6-02 unknown acceptance text stays unsupported in the browser', not x['ok'] and x['u'])
    for name,mut,needle in [('anchor unknown key',lambda m:m['anchors'].append({'field':1,'min':None,'max':None,'min_exact':None,'max_exact':None,'observed_min':None,'observed_max':None,'pass':True,'unimplemented_selector':'first-match'}),'unknown field(s) in anchor'),('control unknown key',lambda m:m['control_points'].append({'id':'6','expected':['1','2','3'],'expected_exact':['1','2','3'],'tolerance':'0','tolerance_exact':'0','checked_fields':[1,2,3],'written':None,'line':None,'pass':True,'unimplemented_selector':'x'}),'unknown field(s) in control point'),('source.path object',lambda m:m['source'].update(path={'not':'a filename'}),'source.path'),('100000-char reference',lambda m:m['units'].update(source_unit_reference='X'*100000),'longer than 2000')]:
        mm=json.loads(json.dumps(m5)); mut(mm); x=svb(mm); check('R6-04 %s -> unsupported in the browser'%name, not x['ok'] and x['u'] and needle in x['u'], x)
    dupt=json.dumps(m5).replace('"schema":','"schema":"x","schema":',1); x=pg.evaluate("(function(t){ try{ window._dbg.loadRecordText(t); return 'accepted'; }catch(e){ return e.message; } })(%s)"%json.dumps(dupt)); check('R6-04 duplicate key refused by the browser scanner', 'duplicate key' in x, x)
    x=pg.evaluate("(function(t){ try{ window._dbg.loadRecordText(t); return 'accepted'; }catch(e){ return e.message; } })(%s)"%json.dumps('{"a":"has \\"quote\\" and {brace}","a2":1,"b":{"a":1}}')); check('R6-04 duplicate-key scanner tolerates braces/quotes inside strings and same key in different objects', x=='accepted', x)
    x=pg.evaluate("(function(){ try{ window._dbg.checkBounds([[[[[[[[[[1]]]]]]]]]]); return 'accepted'; }catch(e){ return e.message; } })()"); check('R6-04 nesting deeper than 8 refused in the browser', 'nesting deeper' in x)
    pg.click('#modeVerify'); py('penzd.txt','r6v.txt','PENZD','IntlFeetToMeters'); pg.set_input_files('#vSrc','penzd.txt'); pg.set_input_files('#vOut','r6v.txt'); pg.set_input_files('#vMan','r6v.txt.manifest.json'); pg.click('#vRun'); t0=time.time()
    while time.time()-t0<20 and not pg.text_content('#vStatus').startswith('Verified'): pg.wait_for_timeout(100)
    import hashlib; fh=hashlib.sha256(open('r6v.txt.manifest.json','rb').read()).hexdigest(); check('R6-03 verify mode shows the received manifest file digest and a named canonical digest', ('file SHA-256 '+fh) in pg.text_content('#vLog') and 'record canonical sha256 (canonical-json/1)' in pg.text_content('#vLog'))
    pg.click('#modeConvert')
    # ---- round 7 (review of v3.3.3): boundaries as workflows ----
    import hashlib
    def wait_hdr(page,prefix,timeout=30):
        t0=time.time()
        while time.time()-t0<timeout and not page.text_content('#hdrStatus').startswith(prefix): page.wait_for_timeout(100)
        return page.text_content('#hdrStatus').startswith(prefix)
    # R7-03 + lifecycle: convert -> Manifest download bytes == embedded record bytes == stated digest; reopen; downloads equal
    load('penzd.txt','PENZD','IntlFeetToMeters'); s,r=go()
    with pg.expect_download() as d1: pg.click('#dlManBtn')
    mp7=os.path.join(W,'r7.manifest.json'); d1.value.save_as(mp7); mh=hashlib.sha256(rd(mp7)).hexdigest()
    with pg.expect_download() as d2: pg.click('#dlHandoffBtn')
    hp7=os.path.join(W,'r7.handoff.html'); d2.value.save_as(hp7); h=open(hp7,encoding='utf-8').read(); i=h.index('<script id="savedPackage" type="application/json">')+len('<script id="savedPackage" type="application/json">'); j=h.index('</script>',i); pkg=json.loads(h[i:j].replace('\\u003c','<'))
    check('R7-03 envelope /3 embeds the exact record text; its bytes == the Manifest download', pkg['format']=='pfu-handoff/3' and pkg['recordText'].encode('utf-8')==rd(mp7))
    pg7=ctx.new_page(); pg7.goto(file_uri(hp7)); ok7=wait_hdr(pg7,'handoff verified')
    log7=pg7.text_content('#log'); check('R7-03 reopened handoff: stated record file digest == download digest, provenance labelled exact', ok7 and ('record file sha256: '+mh) in log7 and ('manifest download sha256 (exact embedded record bytes): '+mh) in log7, log7[-300:])
    with pg7.expect_download() as d3: pg7.click('#dlManBtn')
    mp7b=os.path.join(W,'r7b.manifest.json'); d3.value.save_as(mp7b); check('R7-03 Manifest download from the reopened handoff is byte-identical to the original download', rd(mp7b)==rd(mp7))
    with pg7.expect_download() as d4: pg7.click('#dlBtn')
    o7=os.path.join(W,'r7.out'); d4.value.save_as(o7); check('lifecycle: converted file downloaded from the reopened handoff == original bytes', rd(o7)==bytes(r['bytes']))
    # R7-01 through the real handoff path: inherited names and wrong types in rounding.acceptance must refuse the handoff
    for name,val in [('toString','toString'),('constructor','constructor'),('__proto__','__proto__'),('object',{}),('array',[]),('number',1)]:
        mm=json.loads(pkg['recordText']); mm['rounding']['acceptance']=val; forged=dict(pkg, recordText=json.dumps(mm))
        fp7=os.path.join(W,'r7_forged_%s.html'%name); open(fp7,'w',encoding='utf-8').write(h[:i]+json.dumps(forged).replace('<','\\u003c')+h[j:])
        pgx=ctx.new_page(); pgx.goto(file_uri(fp7)); wait_hdr(pgx,'handoff',20); st7=pgx.text_content('#hdrStatus'); pgx.close()
        check('R7-01 handoff with acceptance=%s is refused (not verified)'%name, st7.startswith('handoff failed'), st7)
    # R7-02: a valid 1.6 MB comment-heavy source converts, saves a handoff, and the handoff reopens with the same verdict
    big7=os.path.join(W,'r7_big.txt'); open(big7,'wb').write(('#'+'x'*78+'\n').encode()*20000+b'A 1 2 3\n')
    pg.set_input_files('#fileInput',big7); pg.wait_for_timeout(1500); pg.select_option('#format','PENZD'); pg.select_option('#header','no'); setconv('Custom'); pg.fill('#customFactor','1'); pg.check('#confirm'); s,r=go(); check('R7-02 1.6 MB comment-heavy source converts', 'checks passed' in s, s[:100])
    with pg.expect_download() as d5: pg.click('#dlHandoffBtn')
    hp7b=os.path.join(W,'r7_big.handoff.html'); d5.value.save_as(hp7b); pg7b=ctx.new_page(); pg7b.goto(file_uri(hp7b)); ok7b=wait_hdr(pg7b,'handoff verified',40); lg7b=pg7b.text_content('#log'); check('R7-02 its 4.3 MB handoff reopens and re-verifies (record budget applies to the record only)', ok7b and 'data 1' in lg7b and 'comment 20000' in lg7b and 'VERIFY PASS' in lg7b, lg7b[-200:]); pg7b.close()
    # R7-02: over-budget is refused at save time, before a handoff is offered (budget lowered through the test hook)
    pg.evaluate("window._setEnvelopeBudget({envelopeBytes: 1024*1024})"); pg.click('#dlHandoffBtn'); pg.wait_for_timeout(300); st8=pg.text_content('#hdrStatus'); msg8=pg.text_content('#status')
    check('R7-02 over-budget handoff refused at save with the layer named; other downloads stay available', st8.startswith('handoff not saved') and 'encoded envelope' in msg8 and not pg.is_hidden('#dlBtn'), msg8[:160]); pg.evaluate("window._setEnvelopeBudget({envelopeBytes: 400*1024*1024})")
    # R7-04: text bounds count Unicode scalar values in the browser exactly as Python does
    ok4=True
    for label,ch in [('ASCII','x'),('BMP','\u6e2c'),('astral','\U0001F4CD')]:
        for n,want in [(1999,True),(2000,True),(2001,False)]:
            mm=json.loads(pkg['recordText']); mm['units']['source_unit_reference']=ch*n; got=pg.evaluate("(function(m){ try{ window._validateManifest(m); return true; }catch(e){ return false; } })(%s)"%json.dumps(mm,ensure_ascii=True))
            if got!=want: ok4=False; print('   R7-04 mismatch',label,n,got)
    check('R7-04 reference bounds at 1999/2000/2001 scalar values agree for ASCII, BMP and astral text', ok4)
    mm=json.loads(pkg['recordText']); mm['units']['source_unit_reference']='ok\ud800'; got=pg.evaluate("(function(t){ try{ window._validateManifest(window._dbg.loadRecordText(t)); return 'accepted'; }catch(e){ return e.message; } })(%s)"%json.dumps(json.dumps(mm,ensure_ascii=True))); check('R7-04 lone surrogate refused in the browser', 'surrogate' in got, got)
    # ---- round 9 (review of files-9): repeat-save lifecycle and restored-controls truth ----
    load('penzd.txt','PENZD','IntlFeetToMeters'); s,r=go(); outA=bytes(r['bytes'])
    with pg.expect_download() as dA: pg.click('#dlHandoffBtn')
    hA=os.path.join(W,'r9_A.html'); dA.value.save_as(hA); pgA=ctx.new_page(); pgA.goto(file_uri(hA)); okA=wait_hdr(pgA,'handoff verified')
    with pgA.expect_download() as dB: pgA.click('#dlHandoffBtn')
    hB=os.path.join(W,'r9_B.html'); dB.value.save_as(hB); pgB=ctx.new_page(); pgB.goto(file_uri(hB)); okB=wait_hdr(pgB,'handoff verified')
    with pgB.expect_download() as dBo: pgB.click('#dlBtn')
    oB=os.path.join(W,'r9_B.out'); dBo.value.save_as(oB)
    with pgB.expect_download() as dBm: pgB.click('#dlManBtn')
    mB=os.path.join(W,'r9_B.manifest.json'); dBm.value.save_as(mB); hb=open(hB,encoding='utf-8').read(); i9=hb.index('<script id="savedPackage" type="application/json">')+len('<script id="savedPackage" type="application/json">'); j9=hb.index('</script>',i9); pkgB=json.loads(hb[i9:j9].replace('\\u003c','<'))
    check('R9-01 fresh -> save A -> reopen A -> save B -> reopen B: output and manifest downloads identical to the embedded bytes', okA and okB and rd(oB)==outA and pkgB['recordText'].encode('utf-8')==rd(mB))
    pgA.set_input_files('#fileInput','sci.txt'); pgA.wait_for_timeout(500); pgA.select_option('#format','ENZ'); pgA.select_option('#header','no'); pgA.select_option('#mode','units'); pgA.select_option('#from','ft'); pgA.select_option('#to','m'); pgA.select_option('#decimals','auto'); pgA.check('#confirm'); pgA.click('#convertBtn'); okC1=wait_hdr(pgA,'checks passed',20)
    with pgA.expect_download() as dC: pgA.click('#dlHandoffBtn')
    hC=os.path.join(W,'r9_C.html'); dC.value.save_as(hC); pgC=ctx.new_page(); pgC.goto(file_uri(hC)); okC=wait_hdr(pgC,'handoff verified'); check('R9-01 reopen A -> different source -> convert -> save C -> reopen C', okC1 and okC and 'sci' in pgC.text_content('#log')); pgA.close(); pgB.close(); pgC.close()
    # R9-02: a CLI record with header auto and 8 written decimals, wrapped as a /3 envelope
    open(os.path.join(W,'r9_hdr.src'),'wb').write(b'E N Z\n10.0000 20.0000 30.0000\n'); py(os.path.join(W,'r9_hdr.src'),os.path.join(W,'r9_hdr.out'),'ENZ','IntlFeetToMeters','--header','auto','--decimals','8')
    import base64; pkgH={'format':'pfu-handoff/3','sourceBase64':base64.b64encode(rd(os.path.join(W,'r9_hdr.src'))).decode(),'outputBase64':base64.b64encode(rd(os.path.join(W,'r9_hdr.out'))).decode(),'recordText':open(os.path.join(W,'r9_hdr.out.manifest.json'),encoding='utf-8').read()}
    ha=open(hA,encoding='utf-8').read(); ia=ha.index('<script id="savedPackage" type="application/json">')+len('<script id="savedPackage" type="application/json">'); ja=ha.index('</script>',ia); hH=os.path.join(W,'r9_hdr.handoff.html'); open(hH,'w',encoding='utf-8').write(ha[:ia]+json.dumps(pkgH).replace('<','\\u003c')+ha[ja:])
    pgH=ctx.new_page(); pgH.goto(file_uri(hH)); okH=wait_hdr(pgH,'handoff verified'); stH=pgH.text_content('#status') or ''
    check('R9-02 restored editor shows the resolved header (yes) and the written decimals (8), confirmation cleared, and says the editor is for a NEW run', okH and pgH.input_value('#header')=='yes' and pgH.input_value('#decimals')=='8' and not pgH.is_checked('#confirm') and 'NEW run' in stH and 'auto' in stH, (pgH.input_value('#header'),pgH.input_value('#decimals'),pgH.is_checked('#confirm'),stH[-200:]))
    pgH.check('#confirm'); pgH.click('#convertBtn'); check('R9-02 a new run with the pre-filled editor reproduces the recorded operation (header row skipped, 8 decimals)', wait_hdr(pgH,'checks passed',15) and 'data 1' in pgH.text_content('#log') and 'header 1' in pgH.text_content('#log')); pgH.close()
    # ---- guidance (owner, 2026-09-29): readiness, declaration summary, unit clues from the file's own text, before/after example ----
    SIXROWS=['101,19857.2577,20260.4556,100.3058,PT_BASE','102,19875.4801,20207.7198,101.0929,PT_CHECK','110,1000000.0000,2000000.0000,0.0000,UNIT_CHECK','150,-100.0000,250.0000,-5.0000,NEGATIVE_TEST','201,123.4567,765.4321,0.1250,AXIS_CHECK','901,0.0000,10.0000,1.0000,ORIGIN_CHECK']
    def gbytes(lines): return ('\r\n'.join(lines)+'\r\n').encode()
    pgG=ctx.new_page(); pgG.goto(APP); pgG.wait_for_timeout(400)
    gt=lambda sel: ' '.join((pgG.text_content(sel) or '').split())
    def gload(name, lines, src=None, dst=None, dec='8'):
        pgG.evaluate("window._loadBytes(%r, %s)" % (name, list(gbytes(lines)))); pgG.wait_for_timeout(250); pgG.select_option('#mode','units')
        if src is not None: pgG.select_option('#from',src)
        if dst is not None: pgG.select_option('#to',dst)
        pgG.select_option('#decimals',dec); pgG.wait_for_timeout(80)
    def grun(dry=False):
        pgG.check('#confirm'); pgG.click('#previewBtn' if dry else '#convertBtn'); t0=time.time()
        while time.time()-t0<20 and not (pgG.text_content('#hdrStatus') or '').startswith(('checks passed','dry run passed','refused')): pgG.wait_for_timeout(100)
        return gt('#status')
    gclass=lambda: pgG.get_attribute('#unitClue','class') or ''
    gbtns=lambda: [x.strip() for x in pgG.eval_on_selector_all('#unitClue button','e=>e.map(b=>b.textContent)')]
    check('G1 fresh page: readiness asks for a file', gt('#readyHint')=='Load a point file to begin.')
    gload('six.csv', SIXROWS, '', ''); check('G2 no units: readiness names them', gt('#readyHint').startswith('Choose the source units and the target units'))
    pgG.select_option('#from','ft'); pgG.select_option('#to','ft'); check('G2b same units: readiness names the problem', gt('#readyHint')=='Source and target are both international feet. Choose a different target unit.')
    pgG.select_option('#to','m'); check('G3 summary shows the exact factor', '381/1250 = 0.3048 exactly' in gt('#declSummary') and 'international feet \u2192 metres' in gt('#declSummary'), gt('#declSummary'))
    check('G3b unticked: readiness says to tick', 'tick the confirmation box' in gt('#readyHint')); pgG.check('#confirm'); check('G3c ticked: ready', gt('#readyHint').startswith('Ready'))
    s=grun(); check('G4 pass: reminder names the source and the example uses the written value', 'really in international feet.' in s and 'Example (largest value): point 110, Northing (column 3): 2000000.0000 international feet \u2192 609600.00000000 metres.' in s, s[:300])
    pgG.select_option('#decimals','6'); check('G4b settings change: the message says to tick again', 'tick the confirmation box again' in gt('#status'))
    gload('six-M-FT.csv', SIXROWS, 'm', 'ft'); check('G5 owner incident, unlabelled file declared metres: no clue notice (file name ignored)', 'hidden' in gclass())
    s=grun(); check('G5b owner incident: the example makes the 3.28x jump visible', 'point 110, Northing (column 3): 2000000.0000 metres \u2192 6561679.79002625 international feet.' in s and pgG.text_content('#hdrStatus')=='checks passed', s[:300])
    HFT=['Point,Easting (ft),Northing (ft),Elevation (ft),Description']+SIXROWS
    gload('hft.csv', HFT, 'm', 'ft'); check('G6 feet header, declared metres: warning with explicit choices', 'against' in gclass() and gbtns()==['Use international feet as source','Use U.S. survey feet as source','Keep my choice'] and 'can be outdated' in gt('#unitClue'), (gclass(), gbtns()))
    pgG.click('#unitClue button:has-text("Use international feet as source")'); pgG.wait_for_timeout(100)
    check('G6b [Use ...] changes only the source and clears the tick', pgG.input_value('#from')=='ft' and pgG.input_value('#to')=='ft' and not pgG.is_checked('#confirm') and 'agree' in gclass())
    gload('hft.csv', HFT, 'ft', 'm'); check('G7 feet header, declared feet: calm agreement', 'agree' in gclass() and not gbtns())
    s=grun(); check('G7b result: agreement and the preserved-label note', 'labels agree' in s and 'still says feet' in s and 'coordinates are now in metres' in s, s[:400])
    gload('hm.csv', ['Point,Easting (m),Northing (m),Elevation (m),Description']+SIXROWS, 'ft', 'm'); check('G8 metre header, declared feet: one explicit choice', 'against' in gclass() and gbtns()==['Use metres as source','Keep my choice'], gbtns())
    gload('hmix.csv', ['Point,Easting (m),Northing (m),Elevation (ft),Description']+SIXROWS, 'ft', 'm'); check('G9 mixed labels: neutral note, no suggestion', 'mixed' in gclass() and not gbtns())
    gload('cf.csv', ['# units: feet']+SIXROWS, 'm', 'ft'); check('G10 "# units: feet" comment counts', 'against' in gclass())
    gload('ct.csv', ['# target units: metres','# converted from ft to m']+SIXROWS, 'ft', 'm'); check('G10b other comments do not count', 'hidden' in gclass())
    gload('cd.csv', ['Point,Easting,Northing,Elevation,Description (ft)']+SIXROWS, 'm', 'ft'); check('G10c a description column does not count', 'hidden' in gclass())
    gload('hft.csv', HFT, 'm', 'ft'); pgG.click('#unitClue button:has-text("Keep my choice")'); hid='hidden' in gclass()
    pgG.select_option('#to','usft'); back='against' in gclass(); pgG.select_option('#to','ft')
    check('G11 Keep my choice hides; a units change ends the dismissal for good', hid and back and 'against' in gclass())
    gload('hft.csv', HFT, 'usft', 'm'); check('G12 bare "ft" is compatible with the U.S. survey foot', 'agree' in gclass())
    gload('hft.csv', HFT, 'm', 'usft'); check('G13 legacy note and a non-terminating factor', pgG.is_visible('#legacyHint') and '3937/1200 \u2248 3.28083333' in gt('#declSummary'), gt('#declSummary'))
    gload('hx.csv', ['Point,<b>E</b> (m),Northing (m),Elevation (m),Description']+SIXROWS, 'ft', 'm')
    check('G14 label text is shown literally, never as markup', '<b>E</b> (m)' in pgG.text_content('#unitClue') and pgG.query_selector('#unitClue b') is None)
    # 1.3 (owner, 2026-09-29): the mixed-label note explains that one factor applies to every coordinate column
    gload('hmix.csv', ['Point,Easting (m),Northing (m),Elevation (ft),Description']+SIXROWS, 'ft', 'm')
    check('G20 mixed labels: the note says one factor applies to every coordinate column', 'same factor is applied to every coordinate column' in gt('#unitClue'))
    # source unit reference help (owner, 2026-09-30): optional, folded by default, keyboard-operable, never moves the layout
    gload('six.csv', SIXROWS, '', '')
    lab=pgG.text_content('label[for="unitRef"]') or ''; folded=not pgG.eval_on_selector('#refHelp','e=>e.open')
    geo=lambda: pgG.evaluate("()=>['unitRef','decimals','from'].map(function(i){var q=document.getElementById(i).closest('.field').getBoundingClientRect(); return [Math.round(q.x),Math.round(q.y+scrollY),Math.round(q.width),Math.round(q.height)];})")
    g1=geo(); pgG.focus('#refHelp summary'); pgG.keyboard.press('Enter'); pgG.wait_for_timeout(120); opened=pgG.eval_on_selector('#refHelp','e=>e.open'); g2=geo()
    items=pgG.eval_on_selector_all('#refHelp li','e=>e.map(x=>x.textContent)')
    check('G21 unit reference: labelled optional, help folded by default, opens with Enter, four examples, layout unchanged', 'optional' in lab and folded and opened and len(items)==4 and 'LandXML file header: linear unit = USSurveyFoot' in items and g1==g2, (lab, folded, opened, len(items), g1==g2))
    pgG.click('#refHelp summary')
    # ---- Windows review of ff68746 (2026-10-01): F1-F5, S1, S2, S4, S5; expected values computed here with exact fractions ----
    from fractions import Fraction as _Fr
    _ftusft=_Fr(381,1250)/_Fr(1200,3937); _n110_usft=_Fr(2000000)*_ftusft; assert _n110_usft==_Fr(1999996)
    gload('amb.csv', ['# units: international feet / U.S. survey feet']+SIXROWS, 'ft', 'm')
    check('G22 F1 a comment naming both feet is ambiguous, with no suggestion', 'mixed' in gclass() and not gbtns(), (gclass(), gbtns()))
    gload('amb-h.csv', ['Point,Easting (international ft / US survey ft),Northing,Elevation,Description']+SIXROWS, 'ft', 'm')
    check('G22b F1 a header naming both feet is ambiguous, with no suggestion', 'mixed' in gclass() and not gbtns(), (gclass(), gbtns()))
    gload('ift.csv', ['# units: international feet']+SIXROWS, 'ft', 'usft'); s=grun()
    check('G23 F2 international-feet label on U.S. survey foot output is flagged; exact value', 'still says international feet; the coordinates are now in U.S. survey feet.' in s and 'Northing (column 3): 2000000.0000 international feet \u2192 %d.00000000 U.S. survey feet.' % int(_n110_usft) in s, s[:400])
    gload('usf.csv', ['# units: U.S. survey feet']+SIXROWS, 'usft', 'ft'); s=grun()
    check('G23b F2 the reverse direction is flagged too', 'still says U.S. survey feet; the coordinates are now in international feet.' in s, s[:300])
    gload('bft.csv', ['# units: feet']+SIXROWS, 'ft', 'usft'); s=grun()
    check('G23c F2 a bare "feet" label stays unresolved: no foot-definition warning', 'still says' not in s, s[:300])
    LATE=['# units: metres']+['%d,%d.0000,%d.0000,0.0000,P' % (1000+i, i, i) for i in range(520)]+['# units: international feet']
    gload('late.csv', LATE, 'm', 'ft')
    check('G24 F3 the notice discloses that only the first 500 non-blank lines were checked', 'agree' in gclass() and 'Only the first 500 non-blank lines were checked for unit labels' in gt('#unitClue'), gt('#unitClue')[:200])
    gload('sci.csv', ['1,9007199254740992,9007199254740993e0,0,TEST'], 'ft', 'm'); s=grun()
    check('G25 F4 exact selection: the example names the larger scientific-notation Northing', 'Northing (column 3): 9007199254740993e0 international feet' in s, s[:300])
    pgW=ctx.new_page(); pgW.goto(APP); pgW.wait_for_timeout(400)
    pgW.evaluate("window._loadBytes('six.csv', %s)" % list(gbytes(SIXROWS))); pgW.wait_for_timeout(250)
    for _s,_v in (('#mode','units'),('#from','ft'),('#to','m')): pgW.select_option(_s,_v)
    pgW.check('#confirm'); pgW.evaluate("window.Worker=function(u){ this.postMessage=function(){}; this.terminate=function(){}; this.addEventListener=function(){}; }")
    pgW.click('#convertBtn'); pgW.wait_for_timeout(200)
    busy=(' '.join((pgW.text_content('#readyHint') or '').split()), pgW.is_disabled('#convertBtn'), pgW.is_disabled('#previewBtn'))
    pgW.select_option('#decimals','6'); pgW.wait_for_timeout(150); after=' '.join((pgW.text_content('#readyHint') or '').split())
    check('G26 F5 a held run shows Working and disables Convert and Preview; a settings change ends it', busy==('Working\u2026', True, True) and 'tick the confirmation box' in after, (busy, after)); pgW.close()
    gload('six.csv', SIXROWS, 'ft', 'm'); s=grun()
    with pgG.expect_download() as _d: pgG.click('#dlBtn')
    req=gt('#dlStatus'); pgG.select_option('#decimals','6'); cleared=gt('#dlStatus')
    check('G27 S1 "Download requested: name" appears, and clears on a settings change', req=='Download requested: '+_d.value.suggested_filename and cleared=='', (req, cleared))
    pgK=ctx.new_page(); pgK.goto(APP); pgK.wait_for_timeout(400); found=False
    for _i in range(40):
        pgK.keyboard.press('Tab')
        if pgK.evaluate("document.activeElement&&document.activeElement.id")=='fileInput': found=True; break
    ring=pgK.eval_on_selector('#drop','e=>{var c=getComputedStyle(e);return [c.outlineStyle,c.outlineColor]}') if found else None
    opened=False
    if found:
        with pgK.expect_file_chooser(timeout=5000) as _fc: pgK.keyboard.press('Enter')
        opened=_fc.value is not None
    unl=pgK.evaluate("['format','delim','header','mode','from','to','decimals','unitRef','customFactor'].filter(function(i){var e=document.getElementById(i);return !(e&&e.labels&&e.labels.length);})")
    check('G28 S2 the file chooser is reachable by Tab and opens with Enter; the drop box shows focus; every setting has a label', found and opened and ring==['solid','rgb(255, 91, 4)'] and unl==[], (found, opened, ring, unl)); pgK.close()
    gload('six.csv', SIXROWS, 'm', 'usft')
    check('G29 S4 S5 legacy and source-drawing wording', gt('#legacyHint')=='U.S. survey foot (legacy): deprecated since 1 January 2023; retain it for historical and legacy data that uses it.' and 'Settings of the source drawing that produced this point file' in (pgG.text_content('#refHelp') or ''))
    pgG.close()
    # ---- owner decisions D1-D3 and gap closures (2026-09-29.2) ----
    pgD=ctx.new_page(); pgD.goto(APP); pgD.wait_for_timeout(400)
    dcss=lambda sel: pgD.eval_on_selector(sel,'e=>{var c=getComputedStyle(e);return [c.borderTopColor,c.fontWeight]}')
    check('G15 fresh page starts at 8 decimals', pgD.input_value('#decimals')=='8')
    check('G15b precision note under the decimals field', 'Written decimals are output precision, not survey accuracy.' in (pgD.text_content('.dechint') or ''))
    check('G16 before a file is loaded, unit fields are not highlighted', dcss('#from')[0]!='rgb(255, 91, 4)')
    pgD.evaluate("window._loadBytes('six.csv', %s)" % list(gbytes(SIXROWS))); pgD.wait_for_timeout(250)
    for s_,v_ in (('#format','PENZD'),('#header','no'),('#mode','units'),('#from',''),('#to','')): pgD.select_option(s_,v_)
    check('G16b unchosen unit fields stand out (orange edge, bold)', dcss('#from')==['rgb(255, 91, 4)','700'] and dcss('#to')==['rgb(255, 91, 4)','700'], (dcss('#from'), dcss('#to')))
    pgD.select_option('#from','ft'); pgD.select_option('#to','m')
    check('G16c chosen unit fields return to normal', dcss('#from')[0]!='rgb(255, 91, 4)' and dcss('#to')[0]!='rgb(255, 91, 4)')
    def drun():
        pgD.check('#confirm'); pgD.click('#convertBtn'); t0=time.time()
        while time.time()-t0<20 and not (pgD.text_content('#hdrStatus') or '').startswith(('checks passed','refused')): pgD.wait_for_timeout(100)
        return ' '.join((pgD.text_content('#status') or '').split())
    s=drun(); check('G17 no control point: the result says so', 'No control point was entered, so the units were not checked against an independently known point.' in s, s[:200])
    pgD.evaluate("document.getElementById('control').value='110 304800 609600 0 0.001'; document.getElementById('control').dispatchEvent(new Event('input'))")
    s=drun(); check('G18 control point within tolerance: the result names it', 'Control point check: 1 point within tolerance (110).' in s, s[:260])
    pgD.select_option('#from','m'); pgD.select_option('#to','ft'); s=drun()
    check('G18b the same control point refuses the wrong declaration', pgD.text_content('#hdrStatus').startswith('refused') and pgD.is_hidden('#dlBtn'), s[:160])
    pgD.evaluate("document.getElementById('control').value=''; document.getElementById('control').dispatchEvent(new Event('input'))")
    pgD.select_option('#from','ft'); pgD.select_option('#to','m'); pgD.select_option('#decimals','5'); drun()
    with pgD.expect_download() as dD: pgD.click('#dlHandoffBtn')
    hD=os.path.join(W,'g19_handoff.html'); dD.value.save_as(hD); pgE=ctx.new_page(); pgE.goto(file_uri(hD)); okE=wait_hdr(pgE,'handoff verified')
    check('G19 a reopened handoff keeps its own 5 decimals, not the new default of 8', okE and pgE.input_value('#decimals')=='5', pgE.input_value('#decimals'))
    pgE.close(); pgD.close()
    # ---- slow lifecycle at scale (PFU_SLOW=1): the construction defect found at the 64 MiB cap is only visible at scale ----
    if os.environ.get('PFU_SLOW')=='1':
        import random; random.seed(5); parts=[]; size=0; i=0
        while size<16*1024*1024: i+=1; ln='%d %.4f %.4f %.4f "G"\n'%(i,19800+random.random()*400,20200+random.random()*900,95+random.random()*7); parts.append(ln); size+=len(ln)
        big16=os.path.join(W,'big16.txt'); open(big16,'w',newline='').write(''.join(parts)); crashed=[]; pg.on('crash',lambda: crashed.append('crash'))
        pg.set_input_files('#fileInput',big16); pg.wait_for_timeout(2500); pg.select_option('#format','PENZD'); pg.select_option('#header','no'); setconv('IntlFeetToMeters'); pg.check('#confirm'); pg.click('#convertBtn'); t0=time.time()
        while time.time()-t0<300 and not pg.text_content('#hdrStatus').startswith(('checks passed','refused')): pg.wait_for_timeout(500)
        check('SLOW 16 MiB source converts and verifies', pg.text_content('#hdrStatus').startswith('checks passed'), pg.text_content('#hdrStatus'))
        with pg.expect_download(timeout=300000) as dls: pg.click('#dlHandoffBtn')
        hps=os.path.join(W,'big16.handoff.html'); dls.value.save_as(hps); check('SLOW 16 MiB handoff saved without crashing the tab (%d MB)'%(os.path.getsize(hps)//1000000), not crashed and os.path.getsize(hps)>40000000)
        pgs=ctx.new_page(); pgs.goto(file_uri(hps), timeout=1800000); t0=time.time()
        while time.time()-t0<300 and not pgs.text_content('#hdrStatus').startswith('handoff'): pgs.wait_for_timeout(1000)
        check('SLOW 16 MiB handoff reopens and re-verifies', pgs.text_content('#hdrStatus').startswith('handoff verified'), pgs.text_content('#hdrStatus'))
        # identity is measured between two browser downloads; never pull megabytes through the automation channel (it crashes the driver)
        with pg.expect_download(timeout=300000) as dco: pg.click('#dlBtn')
        co=os.path.join(W,'big16.converted.out'); dco.value.save_as(co)
        with pgs.expect_download(timeout=300000) as dso: pgs.click('#dlBtn')
        so=os.path.join(W,'big16.reopened.out'); dso.value.save_as(so); import hashlib as _h; check('SLOW 16 MiB reopened handoff: downloaded output identical to the conversion output', os.path.getsize(so)>16000000 and _h.sha256(rd(so)).hexdigest()==_h.sha256(rd(co)).hexdigest()); pgs.close()
    else: print('SKIP  slow 16 MiB lifecycle (set PFU_SLOW=1; the release gate does)')
    check('no page errors', not errs, str(errs))
    b.close()
print('\npassed %d  failed %d'%(sum(results), len(results)-sum(results))); sys.exit(0 if all(results) else 1)
