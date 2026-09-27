// Audit harness for PointTruth 1.0.0 engine. Runs the engine in a Node vm context; no browser.
const fs=require('fs'),vm=require('vm'),crypto=require('crypto');
const html=fs.readFileSync('PointTruth.html','utf8'); const code=html.match(/<script id="engine">([\s\S]*?)<\/script>/)[1];
const ctx={TextDecoder,TextEncoder,Uint8Array,DataView,Int32Array,Promise,Object,Array,BigInt,Number,JSON,RegExp,Map,Set,Date,Error,Math,console,crypto:{subtle:{digest:(n,b)=>Promise.resolve(crypto.createHash('sha256').update(Buffer.from(b)).digest().buffer)}}};
ctx.globalThis=ctx; vm.createContext(ctx); vm.runInContext(code,ctx); const P=ctx.PointTruth;
const enc=s=>new TextEncoder().encode(s); const dec=b=>new TextDecoder().decode(b);
const results=[]; function rec(name,ok,detail){results.push(ok);console.log((ok?'PASS  ':'FAIL  ')+name+(ok?'':'  '+String(detail).slice(0,150)));}
const BUILD='a'.repeat(64);
function cfg(o){ return Object.assign({mode:'custom',from:null,to:null,custom:'1',format:'ENZ',columns:[],idColumn:null,delimiter:'whitespace',header:'none',precision:'auto',reference:'',anchors:[],controls:[],mappingAcknowledged:false,confirmed:true},o); }
async function conv(src,o){ try{ const r=await P.convert(src instanceof Uint8Array?src:enc(src),cfg(o),'in.txt',BUILD); return {ok:true,out:dec(r.bytes),bytes:r.bytes,m:r.manifest}; }catch(e){ return {ok:false,code:e.code,msg:e.message,d:e.details}; } }
(async()=>{
  // 1. independent fixtures (36)
  const fx=[...JSON.parse(fs.readFileSync('fx1.json')).cases,...JSON.parse(fs.readFileSync('fx2.json')).cases];
  const map={IntlFeetToMeters:['ft','m'],MetersToIntlFeet:['m','ft'],USFeetToMeters:['usft','m'],MetersToUSFeet:['m','usft'],USFeetToIntlFeet:['usft','ft'],IntlFeetToUSFeet:['ft','usft']};
  let ok=0; for(const c of fx){ const [f,t]=map[c.conversion]; const r=await conv(c.source,{mode:'units',from:f,to:t,custom:'',precision:c.decimals}); if(r.ok&&r.out===c.expected)ok++; else console.log('   fixture mismatch',c.conversion,r.ok?r.out.trim():r.msg); }
  rec('36 independent oracle fixtures exact ('+ok+'/36)',ok===36);
  // 2. adversarial: earlier review reproductions
  let r;
  r=await conv('1e309 20.25 30.75\n',{}); rec('non-finite token refused',!r.ok,r.msg);
  r=await conv('1.2345e-5 2.3456e-5 3.4567e-5\n',{mode:'units',from:'ft',to:'m',custom:''}); rec('sci notation precision kept',r.ok&&r.out.startsWith('0.00000376276'),r.ok?r.out:r.msg);
  r=await conv(Array.from({length:99},(_,i)=>`${i+1} ${19800+i*1.5} ${20200+i*2.5} ${95+i*.01}`).join('\n')+'\n100 19900 x 96\n',{format:'PENZD',mode:'units',from:'ft',to:'m',custom:''}); rec('one malformed row refuses whole file',!r.ok&&r.code==='DATA'&&/100/.test(JSON.stringify(r.d)),r.msg);
  r=await conv('1 100.25 200.25 10.25 GRND\n3 101.25 201.25 11.25 GRND\n7 102.25 202.25 12.25 GRND\n',{format:'PENZD',mode:'units',from:'ft',to:'m',custom:''}); rec('gapped ids with explicit PENZD convert Z',r.ok&&r.out.split('\n')[0].endsWith('3.1242 GRND'),r.ok?r.out:r.msg);
  r=await conv('9007199254740993 1 2\n',{}); rec('large integer exact',r.ok&&r.out.startsWith('9007199254740993.0000'),r.ok?r.out:r.msg);
  r=await conv('1 100.25 200.25 10.25 A\n',{format:'PENZD',custom:'2'}); const back=r.ok?await conv(r.out,{format:'PENZD',custom:'1/2'}):null; rec('custom 2 then exact 1/2 reproduces',back&&back.ok&&back.out.startsWith('1 100.250000 200.250000 10.250000'),back&&back.out);
  r=await conv(new Uint8Array([...enc('1 10.5 20.5 30.5 A\r\n2 11.5 21.5 31.5 B\n3 12.5 22.5 32.5 C\r\n')]),{format:'PENZD'}); rec('mixed line endings preserved per line',r.ok&&r.out==='1 10.5000 20.5000 30.5000 A\r\n2 11.5000 21.5000 31.5000 B\n3 12.5000 22.5000 32.5000 C\r\n',r.ok?JSON.stringify(r.out):r.msg);
  r=await conv('  1   10.5   20.5   30.5   "TOP OF  CURB"  \n',{format:'PENZD'}); rec('surrounding whitespace preserved',r.ok&&r.out==='  1   10.5000   20.5000   30.5000   "TOP OF  CURB"  \n',r.ok?JSON.stringify(r.out):r.msg);
  r=await conv(new Uint8Array([49,32,49,48,46,53,32,50,48,46,53,32,51,48,46,53,32,67,97,102,0xe9,10]),{format:'PENZD'}); rec('latin-1 refused',!r.ok&&r.code==='ENCODING',r.msg);
  r=await conv('1,"10.5",20.5,30.5,"Curb, top"\n2,11.5,21.5,31.5,"He said ""hi"""\n',{format:'PENZD',delimiter:'comma'}); rec('quoted csv preserved',r.ok&&r.out==='1,"10.5000",20.5000,30.5000,"Curb, top"\n2,11.5000,21.5000,31.5000,"He said ""hi"""\n',r.ok?r.out:r.msg);
  r=await conv('1 19857,2577 20260,4556 100,3058 GRND\n',{format:'PENZD'}); rec('decimal comma (ws) refused',!r.ok,r.msg);
  r=await conv('1,19857,2577,20260,4556,100,3058,GRND\n',{format:'PENZD',delimiter:'comma'}); rec('decimal comma (csv) refused',!r.ok,r.msg);
  r=await conv(Array.from({length:14},(_,i)=>`${i+1} ${1000+i+1} ${2000+i+1} 10`).join('\n')+'\n',{format:'ENZ'}); rec('integer coordinate column needs acknowledgement',!r.ok&&r.code==='MAPPING_REVIEW',r.msg);
  r=await conv('1 0.5 1.5 2.5\n',{format:'PENZD',precision:0}); rec('tie at 0 decimals refused (reconstruction)',!r.ok,r.ok?r.out:r.msg);
  r=await conv('1 -0.00001 -10.25 +5\n',{format:'PENZD'}); rec('negatives',r.ok&&r.out==='1 -0.0000100 -10.2500000 5.0000000\n',r.ok?r.out:r.msg);
  r=await conv(new Uint8Array([0xef,0xbb,0xbf,0xef,0xbb,0xbf,...enc('# c\n1 2 3\n')]),{}); rec('double BOM refused by name',!r.ok&&/U\+FEFF/.test(r.msg),r.msg);
  r=await conv('\u0661 \u0662 \u0663\n',{}); rec('Unicode digits refused',!r.ok,r.msg);
  r=await conv('constructor 1 2 3\n',{format:'PENZD',controls:[{id:'constructor',values:['1','2','3'],tolerance:'0'}]}); rec('reserved-name identifier handled',r.ok,r.msg);
  r=await conv('A 10 999 888\n',{format:'PENZD',controls:[{id:'A',values:['10'],tolerance:'0'}]}); rec('short control refused',!r.ok&&r.code==='CONTROL',r.msg);
  r=await conv('A 999 999 999\nA 10 20 30\n',{format:'PENZD',controls:[{id:'A',values:['10','20','30'],tolerance:'0'}]}); rec('duplicate id refused',!r.ok,r.msg);
  r=await conv('A 10 20 30\n',{format:'PENZD',controls:[{id:'A',values:['10','20','30'],tolerance:'-1'}]}); rec('negative tolerance refused',!r.ok,r.msg);
  r=await conv('1 10 20\n',{format:'CUSTOM',columns:[1],idColumn:1,custom:'2'}); rec('identifier==coordinate refused',!r.ok&&r.code==='MAPPING',r.msg);
  r=await conv('A 2 3\n',{format:'CUSTOM',columns:[-1],custom:'2'}); rec('negative column refused',!r.ok,r.msg);
  r=await conv('A 2 3\n',{format:'CUSTOM',columns:[2],idColumn:99}); rec('identifier column 99 refused as a MAPPING error (columns are 1..64), no crash',!r.ok&&r.code==='MAPPING',r.msg);
  r=await conv('1 2 3\n',{custom:'1/0'}); rec('zero denominator refused',!r.ok,r.msg);
  r=await conv('0.12345678901 1 2\n',{}); rec('11-dp source accepted on auto',r.ok,r.msg);
  r=await conv('1 2 3\n',{custom:'1/3',anchors:[{column:1,min:'0.33332',max:null}]}); rec('anchor passes after raising precision',r.ok&&r.out.startsWith('0.33333'),r.ok?r.out:r.msg);
  r=await conv('12345678901234567890123456789012345678 1 2\n',{}); rec('38-digit integer accepted on auto',r.ok,r.msg);
  r=await conv('1 2\u00a03\n',{}); rec('NBSP is content, refused',!r.ok,r.msg);
  // 3. verifier attacks
  const c1=P.config(cfg({})); const st=(s,o)=>{ try{ P.verifyCandidate(enc(s),enc(o),c1,4); return 'PASS'; }catch(e){ return e.code; } };
  rec('verifier rejects wrong rounding 1.4000',st('1 2 3\n','1.4000 2.0000 3.0000\n')==='ROUNDING');
  rec('verifier rejects non-fixed 14000e-4',st('1 2 3\n','14000e-4 2.0000 3.0000\n')!=='PASS');
  rec('verifier accepts correct candidate',st('1 2 3\n','1.0000 2.0000 3.0000\n')==='PASS');
  rec('verifier catches description tamper',st('1 2 3 A\n','1.0000 2.0000 3.0000 B\n')==='PRESERVATION');
  rec('verifier catches added line',st('1 2 3\n','1.0000 2.0000 3.0000\n4.0000 5.0000 6.0000\n')==='PRESERVATION');
  // 4. manifest attacks via verifyPackage
  const base=await conv('A 10 20 30\nB 11 21 31\n',{format:'PENZD',anchors:[{column:2,min:'9.5',max:'12'}],controls:[{id:'B',values:['11','21','31'],tolerance:'0.0001'}]}); rec('baseline run with anchor+control',base.ok,base.msg);
  async function vp(mut){ const m=JSON.parse(JSON.stringify(base.m)); mut(m); try{ await P.verifyPackage(enc('A 10 20 30\nB 11 21 31\n'),base.bytes,m,BUILD); return 'PASS'; }catch(e){ return e.code+': '+e.message; } }
  rec('verifyPackage passes untouched',await vp(()=>{})==='PASS');
  rec('mutated control expected refused',(await vp(m=>{m.config.controls[0].values=['999','999','999'];})).startsWith('REPORT')||(await vp(m=>{m.config.controls[0].values=['999','999','999'];})).startsWith('PRECISION'));
  rec('mutated counts refused',(await vp(m=>{m.verification.counts.data=999;})).startsWith('REPORT'));
  rec('mutated custom factor input refused',(await vp(m=>{m.config.custom='999';})).startsWith('FACTOR')||(await vp(m=>{m.config.custom='999';})).startsWith('SCHEMA'));
  rec('unknown manifest key refused',(await vp(m=>{m.extra=1;})).startsWith('SCHEMA'));
  rec('null anchors refused',(await vp(m=>{m.config.anchors=[null];})).startsWith('SCHEMA'));
  rec('zero denominator in manifest refused',(await vp(m=>{m.config.factor.denominator='0';})).startsWith('FACTOR')||(await vp(m=>{m.config.factor.denominator='0';})).startsWith('SCHEMA')||(await vp(m=>{m.config.factor.denominator='0';})).startsWith('NUMBER'));
  rec('fingerprint mismatch refused',(await vp(m=>{m.fingerprint='0'.repeat(64);})).startsWith('REPORT'));
  rec('different build refused',(await (async()=>{ try{ await P.verifyPackage(enc('A 10 20 30\nB 11 21 31\n'),base.bytes,base.m,'b'.repeat(64)); return 'PASS'; }catch(e){ return e.code; } })())==='BUILD');
  // 5. cross-check: their bytes vs my Python engine on the same file
  fs.writeFileSync('x_src.txt','1 19857.2577 20260.4556 100.3058 "GRND"\r\n2 19875.4801 20207.7198 101.0929 "GRND"\r\n'); const rr=await conv(fs.readFileSync('x_src.txt'),{format:'PENZD',mode:'units',from:'ft',to:'m',custom:''}); fs.writeFileSync('x_pt.txt',Buffer.from(rr.bytes));
  // cross-engine byte comparison with pointfile_units.py, when a Python engine is reachable (PFU_PY env var, or ../../pointfile_units.py, or ./pointfile_units.py)
  const cands=[process.env.PFU_PY, require('path').join(__dirname,'..','..','pointfile_units.py'), require('path').join(__dirname,'pointfile_units.py')].filter(Boolean).filter(p=>fs.existsSync(p));
  if(cands.length){ try{ fs.rmSync('x_py.txt',{force:true}); fs.rmSync('x_py.txt.manifest.json',{force:true}); fs.rmSync('x_py.txt.report.txt',{force:true}); const py=require('child_process').spawnSync(process.platform==='win32'?'py':'python3',[cands[0],'convert','--in','x_src.txt','--out','x_py.txt','--format','PENZD','--conversion','IntlFeetToMeters','--header','no'],{encoding:'utf8'}); if(py.status===0&&fs.existsSync('x_py.txt')){ rec('PointTruth output byte-identical to pointfile_units.py on the shared PENZD file', Buffer.from(rr.bytes).equals(fs.readFileSync('x_py.txt'))); } else { console.log('SKIP  Python comparison (python engine not runnable here: '+(py.stderr||'').slice(0,80)+')'); } }catch(e){ console.log('SKIP  Python comparison ('+e.message+')'); } }
  else console.log('SKIP  Python comparison (pointfile_units.py not found; set PFU_PY)');
  const failed=results.filter(x=>!x).length; console.log('\npassed',results.filter(Boolean).length,'failed',failed); process.exitCode=failed?1:0;
})().catch(e=>{ console.error('HARNESS ERROR',e); process.exitCode=2; });
