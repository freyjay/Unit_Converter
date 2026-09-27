# Adversarial corpus: each case = (name, settings, source text). Settings use PFU vocabulary; the runner maps to PointTruth's.
import json
C=[]
# expect: 'ok' (both convert, identical bytes and written precision), 'refuse' (both refuse; categories recorded), or
#         'policy:<name>' (a NAMED, accepted policy difference: PointTruth refuses, Python converts). Anything else is a failure.
def add(name, fmt, delim, header, text, conv=('ft','m'), dec='auto', expect='ok'): C.append({"name":name,"format":fmt,"delimiter":delim,"header":header,"text":text,"conv":conv,"decimals":dec,"expect":expect})
ws='whitespace'; cm='comma'
# lexical forms of numbers
for tok in ['+.5','5.','.5','-0','-0.0','007','1e+00','1E5','1e-30','1.5e0','0.000000000001','1'+'0'*39,'1'+'0'*40,'1.'+'1'*39,'1.'+'1'*40,'1e30','1e31','1e-31','٣','１','1_000','1,000','0x10','Infinity','NaN','--1','+-1','1..5','1.5.5']:
    add('token:'+tok,'ENZ',ws,'no',tok+' 2 3\n')
# ties and rounding at written precision
for tok in ['0.5','1.5','2.5','-0.5','-1.5','0.125','0.375','2.675','1.0049999999999','1.005']:
    add('tie:'+tok,'ENZ',ws,'no',tok+' 0 0\n',('m','ft'),2)
# whitespace/tokenizer edges
add('tabs','PENZD',ws,'no','1\t10.5\t20.5\t30.5\tA\n'); add('vt-ff','PENZD',ws,'no','1\x0b10.5\x0c20.5 30.5 A\n'); add('nbsp','PENZD',ws,'no','1 10.5\u00a020.5 30.5 A\n'); add('leading-ws','PENZD',ws,'no','   1 10.5 20.5 30.5 A\n'); add('65-tokens','PENZD',ws,'no','1 10.5 20.5 30.5 '+' '.join('d%d'%i for i in range(70))+'\n')
add('quoted-num-ws','PENZD',ws,'no','1 "10.5" 20.5 30.5 A\n'); add('quote-in-desc-ws','PENZD',ws,'no','1 10.5 20.5 30.5 12" pipe\n'); add('apostrophe','PENZD',ws,'no','1 10.5 20.5 30.5 Bob\'s\n')
# csv edges
add('csv-basic','PENZD',cm,'no','1,10.5,20.5,30.5,A\n'); add('csv-spaces','PENZD',cm,'no','1, 10.5 ,20.5,30.5, A B \n'); add('csv-quoted-num','PENZD',cm,'no','1,"10.5",20.5,30.5,A\n'); add('csv-quoted-desc-comma','PENZD',cm,'no','1,10.5,20.5,30.5,"Curb, top"\n'); add('csv-escaped-quote','PENZD',cm,'no','1,10.5,20.5,30.5,"He said ""hi"""\n'); add('csv-quote-in-unquoted','PENZD',cm,'no','1,10.5,20.5,30.5,12" pipe\n'); add('csv-trailing-comma','PENZD',cm,'no','1,10.5,20.5,30.5,\n'); add('csv-6-fields','PENZD',cm,'no','1,10.5,20.5,30.5,A,B\n'); add('csv-4-fields','PENZD',cm,'no','1,10.5,20.5,30.5\n'); add('csv-3-fields','PENZD',cm,'no','1,10.5,20.5\n'); add('csv-unterminated','PENZD',cm,'no','1,10.5,20.5,30.5,"open\n'); add('csv-empty-coord','PENZD',cm,'no','1,,20.5,30.5,A\n'); add('csv-quoted-empty-coord','PENZD',cm,'no','1,"",20.5,30.5,A\n')
# structure
add('crlf','PENZD',ws,'no','1 10.5 20.5 30.5 A\r\n'); add('cr-only','PENZD',ws,'no','1 10.5 20.5 30.5 A\r'); add('mixed','PENZD',ws,'no','1 10.5 20.5 30.5 A\r\n2 11.5 21.5 31.5 B\n3 12.5 22.5 32.5 C\r'); add('no-final-nl','PENZD',ws,'no','1 10.5 20.5 30.5 A'); add('blank-lines','PENZD',ws,'no','\n1 10.5 20.5 30.5 A\n\n\n'); add('comment-first','PENZD',ws,'no','# c\n1 10.5 20.5 30.5 A\n'); add('comment-indented','PENZD',ws,'no','   # c\n1 10.5 20.5 30.5 A\n'); add('header-first','PENZD',ws,'yes','P E N Z D\n1 10.5 20.5 30.5 A\n'); add('header-numeric-looking','PENZD',ws,'yes','1 2 3 4 5\n1 10.5 20.5 30.5 A\n'); add('empty-file','PENZD',ws,'no',''); add('only-comments','PENZD',ws,'no','# a\n# b\n'); add('bom','PENZD',ws,'no','\ufeff1 10.5 20.5 30.5 A\n'); add('double-bom','PENZD',ws,'no','\ufeff\ufeff1 10.5 20.5 30.5 A\n'); add('nul','PENZD',ws,'no','1 10.5 20.5 30.5 A\x00\n'); add('bom-mid','PENZD',ws,'no','1 10.5 20.5 30.5 A\n\ufeff2 1 2 3 B\n')
# identifiers
add('dup-ids','PENZD',ws,'no','1 10.5 20.5 30.5 A\n1 11.5 21.5 31.5 B\n'); add('empty-id','PENZD',cm,'no',',10.5,20.5,30.5,A\n'); add('id-constructor','PENZD',ws,'no','constructor 10.5 20.5 30.5 A\n'); add('int-coords-10','ENZ',ws,'no',''.join('%d %d %d\n'%(i,i+20,i+40) for i in range(1,11)))
# exponent/decimals interplay
add('sci-fine','ENZ',ws,'no','1.2345e-5 2.3456e-5 3.4567e-5\n'); add('13dp','ENZ',ws,'no','0.1234567890123 1 2\n'); add('big-int','ENZ',ws,'no','9007199254740993 1 2\n',('ft','m')); add('40dig+exp','ENZ',ws,'no','1'+'0'*39+'e-30 0 0\n')
# ---- Expectations (F11-01): every case carries a complete per-implementation expectation. ----
# 'ok'      : both convert; identical bytes and identical written precision (bytes compared as Base64 by compare.py)
# 'refuse'  : both refuse; PointTruth's stable code and the Python refusal category are pinned per case (REFUSE_CODES)
# 'policy'  : a NAMED difference from POLICIES only: PointTruth refuses with the pinned code; Python converts to the pinned
#             bytes at the pinned precision. Expected bytes were derived by hand (0.3048 x value is exact at 4 decimals),
#             not copied from either engine. Any other outcome, any unknown policy id, any ERROR kind, fails.
REFUSE_CODES={
"token:1e-30": {
"pt": "PRECISION_OR_CHECK",
"py": "ROUNDING"
},
"token:0.000000000001": {
"pt": "PRECISION_OR_CHECK",
"py": "ROUNDING"
},
"token:10000000000000000000000000000000000000000": {
"pt": "DATA",
"py": "LIMIT"
},
"token:1.111111111111111111111111111111111111111": {
"pt": "PRECISION_OR_CHECK",
"py": "ROUNDING"
},
"token:1.1111111111111111111111111111111111111111": {
"pt": "DATA",
"py": "LIMIT"
},
"token:1e31": {
"pt": "DATA",
"py": "LIMIT"
},
"token:1e-31": {
"pt": "DATA",
"py": "LIMIT"
},
"token:\u0663": {
"pt": "DATA",
"py": "DATA"
},
"token:\uff11": {
"pt": "DATA",
"py": "DATA"
},
"token:1_000": {
"pt": "DATA",
"py": "DATA"
},
"token:1,000": {
"pt": "DATA",
"py": "DATA"
},
"token:0x10": {
"pt": "DATA",
"py": "DATA"
},
"token:Infinity": {
"pt": "DATA",
"py": "DATA"
},
"token:NaN": {
"pt": "DATA",
"py": "DATA"
},
"token:--1": {
"pt": "DATA",
"py": "DATA"
},
"token:+-1": {
"pt": "DATA",
"py": "DATA"
},
"token:1..5": {
"pt": "DATA",
"py": "DATA"
},
"token:1.5.5": {
"pt": "DATA",
"py": "DATA"
},
"tie:2.675": {
"pt": "PRECISION_OR_CHECK",
"py": "ROUNDING"
},
"tie:1.0049999999999": {
"pt": "PRECISION_OR_CHECK",
"py": "ROUNDING"
},
"tie:1.005": {
"pt": "PRECISION_OR_CHECK",
"py": "ROUNDING"
},
"nbsp": {
"pt": "DATA",
"py": "DATA"
},
"csv-6-fields": {
"pt": "DATA",
"py": "DATA"
},
"csv-3-fields": {
"pt": "DATA",
"py": "DATA"
},
"csv-unterminated": {
"pt": "DATA",
"py": "DATA"
},
"csv-empty-coord": {
"pt": "DATA",
"py": "DATA"
},
"csv-quoted-empty-coord": {
"pt": "DATA",
"py": "DATA"
},
"empty-file": {
"pt": "EMPTY",
"py": "EMPTY"
},
"only-comments": {
"pt": "EMPTY",
"py": "EMPTY"
},
"double-bom": {
"pt": "ENCODING",
"py": "ENCODING"
},
"nul": {
"pt": "ENCODING",
"py": "ENCODING"
},
"bom-mid": {
"pt": "ENCODING",
"py": "ENCODING"
},
"13dp": {
"pt": "PRECISION_OR_CHECK",
"py": "ROUNDING"
}
}
POLICIES={
  "csv-quote-in-unquoted-field": {"case":"csv-quote-in-unquoted","pt_code":"DATA","py_output":"1,3.2004,6.2484,9.2964,12\" pipe\n","py_decimals":4,
      "derivation":"10.5/20.5/30.5 ft x 0.3048 = 3.2004/6.2484/9.2964 m exactly; auto precision at quantum 0.1 ft writes 4 decimals; the unquoted quote is description text and is preserved"},
  "duplicate-identifiers": {"case":"dup-ids","pt_code":"DATA","py_output":"1 3.2004 6.2484 9.2964 A\n1 3.5052 6.5532 9.6012 B\n","py_decimals":4,
      "derivation":"second row 11.5/21.5/31.5 ft x 0.3048 = 3.5052/6.5532/9.6012 m exactly; PFU converts duplicate identifiers unless a control point references one"},
  "empty-identifier": {"case":"empty-id","pt_code":"DATA","py_output":",3.2004,6.2484,9.2964,A\n","py_decimals":4,
      "derivation":"identifier field empty; PFU preserves the empty field, PointTruth refuses under its unique-identifier policy"},
}
for c in C:
    if c['name'] in REFUSE_CODES: c['expect']='refuse'; c['pt_code']=REFUSE_CODES[c['name']]['pt']; c['py_category']=REFUSE_CODES[c['name']]['py']
for pid,pol in POLICIES.items():
    for c in C:
        if c['name']==pol['case']: c['expect']='policy:'+pid
names=[c['name'] for c in C]; assert len(names)==len(set(names)), 'duplicate case ids'
with open('corpus.json','w',encoding='utf-8') as fh: json.dump({"cases":C,"policies":POLICIES},fh,ensure_ascii=False)
print(len(C),'cases;',sum(c['expect']=='ok' for c in C),'expect ok;',sum(c['expect']=='refuse' for c in C),'expect refuse (codes pinned);',sum(c['expect'].startswith('policy') for c in C),'named policy differences (bytes pinned)')
