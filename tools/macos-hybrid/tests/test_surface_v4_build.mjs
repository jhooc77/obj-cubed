import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..', '..', '..');
const src = path.join(root, 'objcubed.js');
const code = fs.readFileSync(src, 'utf8');
const TW=16,TH=16;
const pixels=new Uint8Array(TW*TH*4);
for(let i=0;i<pixels.length;i+=4){pixels[i]=128;pixels[i+1]=64;pixels[i+2]=32;pixels[i+3]=255;}
class FakeImage{set src(_v){setTimeout(()=>this.onload?.(),0);}get naturalWidth(){return TW;}get naturalHeight(){return TH;}get width(){return TW;}get height(){return TH;}}
const canvasCtx={drawImage(){},getImageData(){return{data:pixels,width:TW,height:TH};}};
const document={createElement(){return{getContext(){return canvasCtx;},set width(_v){},set height(_v){}};}};
const mod={exports:{}};
const sandbox={console,require:createRequire(import.meta.url),module:mod,exports:mod.exports,Buffer,setTimeout,process,
  BBPlugin:{register(){}},Plugin:{register(){}},settings:{language:{value:'en'}},Image:FakeImage,document,
  Texture:{all:[{uuid:'u',name:'t',source:'data:fake',img:{src:'data:fake'}}]},Outliner:{root:[]}};
sandbox.globalThis=sandbox;
vm.createContext(sandbox);
vm.runInContext(code,sandbox,{filename:src});
const api=mod.exports.__test;
const obj=['v 0 0 0','v 1 0 0','v 1 1 0','v 0 1 0','vt 0 0','vt 1 0','vt 1 1','vt 0 1','usemtl m_u','f 1/1 2/2 3/3 4/4'].join('\n');
const cfg={texIndex:0,nopow:false,scale:1,offset:[0,0,0],colorbehavior:['direct','direct','direct'],duration:0,
  autoplay:false,easing:0,interpolation:0,noshadow:false,autorotate:0,visibility:7,displaySlots:{},flipuv:false,
  useAtlas:false,texAnimEnabled:false,texFrametime:1,texFade:false,staticSurface:true,exportAsEquipment:false};
const res=await api.buildOutput(cfg,[obj],'');
const pixel=(x,y)=>{const i=(y*res.tw+x)*4;return[...res.rawBuf.slice(i,i+4)];};
assert.deepEqual(pixel(0,0),[12,34,57,255]);
assert.equal(pixel(6,0)[2],4);
assert.equal(pixel(5,0)[0]*256+pixel(5,0)[1],1);
assert.deepEqual(pixel(0,2),[0,0,0,2]);
// ids [0,1,2,3] -> owners0=5, owners1=5 -> packed=91, quad=4.
assert.deepEqual(pixel(1,2),[91,4,0,255]);
assert.equal(res.staticSurface,true);
assert.equal(res.elements.length,1);
assert.equal(res.ty,32);
assert.match(res.debugInfo,/surface-v4/);
const manifest=JSON.parse(fs.readFileSync(path.join(root,'HYBRID_SURFACE_PATCH.json'),'utf8'));
assert.equal(manifest.static_face_metadata_texels,10);
assert.equal(manifest.static_legacy_streams,false);
console.log('surface-v1.4 buildOutput smoke passed');
