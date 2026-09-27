#!/usr/bin/env python3
"""Runs the corpus through pointfile_units.py. A refusal is exit 2 without a traceback (the CLI's documented contract); its
category is derived from the message text and pinned per case by corpus.py - a heuristic label, not a machine boundary (a stable
refusal class in the CLI output is proposed for 3.4). A traceback, timeout or any other exit is an ERROR."""
import json, tempfile, subprocess, sys, os, pathlib, base64
HERE=pathlib.Path(__file__).resolve().parent; TOOL=HERE.parent.parent/'pointfile_units.py' if (HERE.parent.parent/'pointfile_units.py').exists() else HERE/'pointfile_units.py'
CONV={('ft','m'):'IntlFeetToMeters',('m','ft'):'MetersToIntlFeet'}
def category(text):
    t=text.lower()
    for k,c in [('not numeric','DATA'),('invalid data row','DATA'),('exceeds 40 digits','LIMIT'),('exponent','LIMIT'),('decimal','ROUNDING'),('half quantum','ROUNDING'),('reconstruct','ROUNDING'),('csv','CSV'),('quote','CSV'),('field count','FIELDS'),('fields','FIELDS'),('nul','ENCODING'),('u+feff','ENCODING'),('bom','ENCODING'),('utf-8','ENCODING'),('empty','EMPTY'),('no data','EMPTY'),('column','MAPPING'),('identifier','IDENTIFIER'),('ambiguous','IDENTIFIER'),('too many','LIMIT')]:
        if k in t: return c
    return 'OTHER'
with open(HERE/'corpus.json',encoding='utf-8') as fh: C=json.load(fh)['cases']
out={}; d=tempfile.mkdtemp()
for c in C:
    src=os.path.join(d,'s.txt'); o=os.path.join(d,'o.txt'); open(src,'wb').write(c['text'].encode('utf-8','surrogatepass'))
    for f in (o,o+'.manifest.json',o+'.report.txt'):
        if os.path.exists(f): os.remove(f)
    args=[sys.executable,str(TOOL),'convert','--in',src,'--out',o,'--format',c['format'],'--conversion',CONV[tuple(c['conv'])],'--delimiter',c['delimiter'],'--header',c['header'],'--force-mapping']
    if c['decimals']!='auto': args+=['--decimals',str(c['decimals'])]
    try: r=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='backslashreplace',timeout=120)
    except subprocess.TimeoutExpired: out[c['name']]={'ok':False,'kind':'error','code':'TIMEOUT','msg':'timeout'}; continue
    text=(r.stderr+r.stdout)
    if r.returncode==0 and os.path.exists(o):
        with open(o+'.manifest.json',encoding='utf-8') as fh: dec=json.load(fh)['rounding']['decimals']
        out[c['name']]={'ok':True,'bytes_b64':base64.b64encode(open(o,'rb').read()).decode('ascii'),'decimals':dec}
    elif r.returncode==2 and 'Traceback' not in text: out[c['name']]={'ok':False,'kind':'refusal','code':category(text),'exit':2,'msg':text.strip().splitlines()[0][:160] if text.strip() else ''}
    else: out[c['name']]={'ok':False,'kind':'error','code':'EXIT%d'%r.returncode,'msg':text[-300:]}
with open(HERE/'py.json','w',encoding='utf-8') as fh: json.dump(out,fh,indent=1,ensure_ascii=True)
print('python done',len(out))
