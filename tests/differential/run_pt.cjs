// Run each corpus case through PointTruth rc.1's engine (Node vm), record outcome class + output text.
const fs=require('fs'),vm=require('vm'),crypto=require('crypto');
const html=fs.readFileSync('PointTruth.html','utf8'); const code=html.match(/<script id="engine">([\s\S]*?)<\/script>/)[1];
const ctx={TextDecoder,TextEncoder,Uint8Array,DataView,Int32Array,Promise,Object,Array,BigInt,Number,JSON,RegExp,Map,Set,Date,Error,Math,console,crypto:crypto.webcrypto};ctx.globalThis=ctx;vm.createContext(ctx);vm.runInContext(code,ctx);const P=ctx.PointTruth;
const FMT={PENZD:{format:'PENZD'},ENZ:{format:'ENZ'}}; const HDR={no:'none',yes:'first'};
(async()=>{ const C=JSON.parse(fs.readFileSync('corpus.json','utf8')).cases;
// PointTruth 1.1.0-rc.1 fail codes, enumerated from its source: an exception with any other code is an ERROR, not a refusal
const PT_CODES=new Set(['ANCHOR','BUILD','CONFIRM','CONTROL','CSV','DATA','EMPTY','ENCODING','FACTOR','FIELDS','HASH','IDENTIFIER','MAPPING','MAPPING_REVIEW','NAME','NUMBER','PACKAGE','PRECISION','PRECISION_OR_CHECK','PRESERVATION','REPORT','ROUNDING','SCHEMA','SETTINGS','SIZE']); const out={};
  for(const c of C){ const cfg={mode:'units',from:c.conv[0],to:c.conv[1],custom:'',format:c.format,columns:[],idColumn:null,delimiter:c.delimiter,header:HDR[c.header],precision:c.decimals==='auto'?'auto':c.decimals,reference:'',anchors:[],controls:[],mappingAcknowledged:true,confirmed:true};
    try{ const r=await P.convert(new TextEncoder().encode(c.text),cfg,'in.txt','a'.repeat(64)); out[c.name]={ok:true,bytes_b64:Buffer.from(r.bytes).toString('base64'),decimals:r.manifest.rounding.decimals}; }
    catch(e){ if(e&&e.code&&PT_CODES.has(e.code)){ out[c.name]={ok:false,kind:'refusal',code:e.code,msg:(e.message||'').slice(0,160)}; } else { out[c.name]={ok:false,kind:'error',code:(e&&e.code)?'UNKNOWN_CODE:'+e.code:'EXCEPTION',msg:String(e&&e.stack||e).slice(0,300)}; } } }
  fs.writeFileSync('pt.json',JSON.stringify(out,null,1),'utf8'); console.log('pointtruth done',Object.keys(out).length); })().catch(e=>{ console.error('RUNNER ERROR',e); process.exitCode=2; });
