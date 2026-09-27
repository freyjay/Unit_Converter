const fs=require('fs'),vm=require('vm'),crypto=require('crypto');
const html=fs.readFileSync('PointTruth.html','utf8'); const code=html.match(/<script id="engine">([\s\S]*?)<\/script>/)[1];
const ctx={TextDecoder,TextEncoder,Uint8Array,DataView,Int32Array,Promise,Object,Array,BigInt,Number,JSON,RegExp,Map,Set,Date,Error,Math,console,crypto:{subtle:{digest:(n,b)=>Promise.resolve(crypto.createHash('sha256').update(Buffer.from(b)).digest().buffer)}}};
ctx.globalThis=ctx; vm.createContext(ctx); vm.runInContext(code,ctx); const P=ctx.PointTruth; const enc=s=>new TextEncoder().encode(s), dec=b=>new TextDecoder().decode(b);
const res=[]; const rec=(n,ok,d)=>{res.push(ok);console.log((ok?'PASS  ':'FAIL  ')+n+(ok?'':'  '+String(d).slice(0,140)));};
const cfg=o=>Object.assign({mode:'custom',from:null,to:null,custom:'1',format:'ENZ',columns:[],idColumn:null,delimiter:'whitespace',header:'none',precision:'auto',reference:'',anchors:[],controls:[],mappingAcknowledged:false,confirmed:true},o);
async function conv(src,o){ try{ const r=await P.convert(src instanceof Uint8Array?src:enc(src),cfg(o),'in.txt','a'.repeat(64)); return {ok:true,out:dec(r.bytes),m:r.manifest}; }catch(e){ return {ok:false,code:e.code,msg:e.message}; } }
(async()=>{
  // SHA-256 fallback vs Node on padding boundaries
  let shaOk=true; for(const n of [0,1,55,56,57,63,64,65,119,120,121,1000,4097]){ const d=crypto.randomBytes(n); if(P.shaFallback(new Uint8Array(d))!==crypto.createHash('sha256').update(d).digest('hex')){shaOk=false;console.log('  sha mismatch at',n);} } rec('SHA-256 fallback matches Node at 13 padding boundaries',shaOk);
  // ties-to-even, both signs, both rounding procedures agree
  const ties=[['2.5',0,'2'],['3.5',0,'4'],['-2.5',0,'-2'],['-3.5',0,'-4'],['0.125',2,'0.12'],['0.375',2,'0.38'],['-0.125',2,'-0.12']]; let tOk=true;
  for(const [s,d,e] of ties){ const v=P.number(s).v; const a=P.fixed(P.roundProduct(v,d),d), b=P.fixed(P.nearest(P.mul(v,P.R(10n**BigInt(d)))),d); if(a!==e||b!==e){tOk=false;console.log('  tie',s,d,a,b,'want',e);} } rec('ties to even: converter and verifier agree, both signs',tOk);
  let r;
  r=await conv('1,2,3,\n',{delimiter:'comma'}); rec('trailing comma = empty 4th field, preserved',r.ok&&r.out==='1.0000,2.0000,3.0000,\n',r.ok?JSON.stringify(r.out):r.msg);
  r=await conv('# note\nE N Z\n1 2 3\n',{header:'first'}); rec('header=first skips the first data-kind line after comments',r.ok&&r.out==='# note\nE N Z\n1.0000 2.0000 3.0000\n',r.ok?JSON.stringify(r.out):r.msg);
  r=await conv('1 2 3\n',{header:'first'}); rec('header=first with a single line -> EMPTY refusal',!r.ok&&r.code==='EMPTY',r.msg);
  r=await conv('1e100 2 3\n',{}); rec('exponent 100 refused',!r.ok,r.msg);
  r=await conv('1 2 3 '+'x '.repeat(70)+'\n',{}); rec('70 trailing description tokens preserved',r.ok&&r.out.endsWith('x '.repeat(70)+'\n'),r.ok?r.out.length:r.msg);
  r=await conv('1,2,3,"a\nb"\n',{delimiter:'comma'}); rec('multiline quoted CSV refused',!r.ok,r.msg);
  r=await conv('1 2 3\x00\n',{}); rec('NUL refused',!r.ok,r.msg);
  r=await conv('1 2 3\n\n\n',{}); rec('blank lines preserved',r.ok&&r.out==='1.0000 2.0000 3.0000\n\n\n',r.ok?JSON.stringify(r.out):r.msg);
  r=await conv('1 2 3',{}); rec('no trailing newline preserved',r.ok&&r.out==='1.0000 2.0000 3.0000',r.ok?JSON.stringify(r.out):r.msg);
  r=await conv('1 2 3\r',{}); rec('CR-only line ending preserved',r.ok&&r.out==='1.0000 2.0000 3.0000\r',r.ok?JSON.stringify(r.out):r.msg);
  r=await conv('P1 1 2 3\nP1 4 5 6\n',{format:'PENZD'}); rec('duplicate point numbers refused even without control points (strict)',!r.ok&&r.code==='DATA',r.msg);
  r=await conv('1 2 3\n',{mode:'units',from:'m',to:'m',custom:''}); rec('same source and target units refused',!r.ok,r.msg);
  r=await conv('"12.5" 2 3\n',{}); rec('quoted numeric coordinate in whitespace mode: quotes preserved',r.ok&&r.out==='"12.5000" 2.0000 3.0000\n',r.ok?JSON.stringify(r.out):r.msg);
  // precision auto when finest > 12 (13-decimal source)
  r=await conv('0.1234567890123 1 2\n',{}); rec('13-decimal source: refused (cannot reconstruct within 0-12)',!r.ok&&/precision/i.test(r.msg),r.msg);
  // fingerprint canonical: same run twice -> different createdAt -> different fingerprint (expected), config equal
  const a=await conv('1 2 3\n',{}), b=await conv('1 2 3\n',{}); rec('fingerprint binds full manifest (createdAt differs)',a.m.fingerprint!==b.m.fingerprint||a.m.createdAt===b.m.createdAt);
  const failed=res.filter(x=>!x).length; console.log('\npassed',res.filter(Boolean).length,'failed',failed); process.exitCode=failed?1:0;
})().catch(e=>{ console.error('HARNESS ERROR',e); process.exitCode=2; });
