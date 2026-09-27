#!/usr/bin/env python3
"""Real-browser audit of PointTruth.html (Chromium via Playwright). Expects PointTruth.html, penzd.txt, penzd_m.txt (from pointfile_units.py) and big.txt in the CWD."""
import json, os, time, random
from playwright.sync_api import sync_playwright
def rd(n): return open(n,'rb').read()
if not os.path.exists('big.txt'):
    random.seed(7); open('big.txt','w',newline='').write(''.join('%d %.4f %.4f %.4f "G"\n'%(i,19800+random.random()*400,20200+random.random()*900,95+random.random()*7) for i in range(1,60001)))
res=[]
def chk(name,ok,d=''): res.append(ok); print(('PASS  ' if ok else 'FAIL  ')+name+('' if ok else '  '+str(d)[:160]))
with sync_playwright() as p:
    b=p.chromium.launch(); ctx=b.new_context(accept_downloads=True); pg=ctx.new_page(); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.goto('file://'+os.path.abspath('PointTruth.html')); pg.wait_for_timeout(800)
    pg.set_input_files('#file','penzd.txt'); pg.wait_for_timeout(500)
    pg.select_option('#mode','units'); pg.select_option('#from','ft'); pg.select_option('#to','m'); pg.select_option('#format','PENZD'); pg.select_option('#delimiter','whitespace'); pg.select_option('#header','none'); pg.check('#confirmed'); pg.click('#run')
    pg.wait_for_selector('#result:not([hidden])', timeout=15000); pg.wait_for_timeout(300)
    with pg.expect_download() as dl: pg.click('#save-points')
    dl.value.save_as('pt_out.txt'); chk('downloaded point file == pointfile_units.py bytes', rd('pt_out.txt')==rd('penzd_m.txt'))
    with pg.expect_download() as dl2: pg.click('#save-package')
    hp='handoff.pointtruth.html'; dl2.value.save_as(hp); chk('handoff saved', os.path.getsize(hp)>60000)
    pg.set_input_files('#recheck-file','pt_out.txt'); pg.wait_for_timeout(1500); chk('check saved point file: good copy', 'match this report' in pg.text_content('#recheck-status'))
    open('pt_tampered.txt','wb').write(b''.join(l.replace(b'"GRND"',b'"GRNX"') if i==2 else l for i,l in enumerate(rd('pt_out.txt').splitlines(keepends=True))))
    pg.set_input_files('#recheck-file','pt_tampered.txt'); pg.wait_for_timeout(1500); chk('check saved point file: tampered copy fails', 'FAILED' in pg.text_content('#recheck-status'))
    pg2=ctx.new_page(); pg2.goto('file://'+os.path.abspath(hp)); pg2.wait_for_selector('#result:not([hidden])', timeout=20000); pg2.wait_for_timeout(300)
    chk('handoff re-verifies on open', 'Rechecked' in pg2.text_content('#scope'))
    m=json.loads(pg2.text_content('#report')); chk('handoff manifest carries hashes and fingerprint', len(m['source']['sha256'])==64 and len(m['fingerprint'])==64)
    chk('handoff build == original build', m['tool']['build'] in pg2.text_content('#build-info'))
    h=open(hp,encoding='utf-8').read(); i=h.index('"candidateBase64":"')+len('"candidateBase64":"'); ch=h[i+40]; open('handoff_tampered.html','w',encoding='utf-8').write(h[:i+40]+('B' if ch!='B' else 'C')+h[i+41:])
    pg3=ctx.new_page(); pg3.goto('file://'+os.path.abspath('handoff_tampered.html')); pg3.wait_for_timeout(3000)
    chk('tampered handoff refused on open', pg3.is_hidden('#result') and 'error' in (pg3.get_attribute('#status','class') or ''))
    pg.set_input_files('#file','big.txt'); pg.wait_for_timeout(800); pg.select_option('#mode','units'); pg.select_option('#from','ft'); pg.select_option('#to','m'); pg.select_option('#format','PENZD'); pg.select_option('#header','none'); pg.check('#confirmed'); pg.click('#run'); pg.wait_for_timeout(200)
    busy=pg.evaluate("!document.getElementById('cancel').hidden"); pg.select_option('#to','usft'); pg.wait_for_timeout(8000)
    chk('settings change mid-run: nothing published, confirmation cleared', busy and pg.is_hidden('#result') and not pg.is_checked('#confirmed'))
    t0=time.time(); pg.check('#confirmed'); pg.click('#run'); pg.wait_for_selector('#result:not([hidden])', timeout=90000); dt=time.time()-t0
    chk('60,000-line file converts (%.1fs) with UI responsive (worker)'%dt, '60,000' in pg.text_content('#count'))
    chk('no page errors', not errs, errs[:3]); b.close()
print('\nUI: passed %d failed %d'%(sum(res),len(res)-sum(res))); import sys; sys.exit(0 if all(res) else 1)
