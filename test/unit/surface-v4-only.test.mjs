import { describe, it, expect } from 'vitest';
import { createRequire } from 'node:module';
import path from 'node:path';
import fs from 'node:fs';
import vm from 'node:vm';
const require = createRequire(import.meta.url);
const ROOT=path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/,'$1')),'..','..');
const CODE=fs.readFileSync(path.join(ROOT,'objcubed.js'),'utf8');
function load(W=16,H=16,pixels=null){
 const mod={exports:{}}; pixels=pixels||new Uint8Array(W*H*4).fill(255);
 class Image{set src(v){setTimeout(()=>this.onload&&this.onload(),0)} get naturalWidth(){return W} get naturalHeight(){return H} get width(){return W} get height(){return H}}
 const ctx={drawImage(){},getImageData(){return{data:pixels,width:W,height:H}}};
 const sandbox={console,require,module:mod,exports:mod.exports,Buffer,setTimeout,process,
  BBPlugin:{register(){}},Plugin:{register(){}},settings:{language:{value:'en'}},Image,
  document:{createElement(){return{getContext(){return ctx},set width(v){},set height(v){}}}},
  Texture:{all:[{uuid:'u',name:'t',source:'data:fake',img:{src:'data:fake'}}]},Outliner:{root:[]}};
 sandbox.globalThis=sandbox;vm.createContext(sandbox);vm.runInContext(CODE,sandbox,{filename:'objcubed.js'});return mod.exports.__test;
}
const cfg={texIndex:0,nopow:false,scale:1,offset:[0,0,0],colorbehavior:['direct','direct','direct'],duration:0,autoplay:false,easing:0,interpolation:0,noshadow:false,autorotate:0,visibility:7,displaySlots:{},flipuv:false,useAtlas:false,texAnimEnabled:false,texFrametime:1,texFade:false,staticSurface:true,exportAsEquipment:false};
const rect=['v 0 0 0','v 1 0 0','v 1 1 0','v 0 1 0','vt 0 0','vt 1 0','vt 1 1','vt 0 1','usemtl m_u','f 1/1 2/2 3/3 4/4'].join('\n');
const nonplanar=['v 0 0 0','v 1 0 0','v 1 1 0.25','v 0 1 0','vt 0 0','vt 1 0','vt 1 1','vt 0 1','usemtl m_u','f 1/1 2/2 3/3 4/4'].join('\n');

describe('surface-v4-only exporter',()=>{
 it('keeps an affine planar rectangle and selects the native face path',async()=>{const a=load();const r=await a.buildOutput({...cfg},[rect],'');expect(r.nfaces).toBe(1);expect(r.debugInfo).toContain('native 1');expect(r.debugInfo).toContain('shader 0');expect(r.rawBuf[2]).toBe(57);expect(r.rawBuf[6*4+2]).toBe(5);});
 it('splits a non-planar quad instead of falling back',async()=>{const a=load();const r=await a.buildOutput({...cfg},[nonplanar],'');expect(r.nfaces).toBe(2);expect(r.debugInfo).toContain('split +1');expect(r.debugInfo).not.toContain('full-v2');});
 it('hard-rejects geometry animation, equipment and RGB geometry controls',async()=>{const a=load();await expect(a.buildOutput({...cfg},[rect,rect],'')).rejects.toThrow(/static geometry/i);await expect(a.buildOutput({...cfg,exportAsEquipment:true},[rect],'')).rejects.toThrow(/equipment/i);await expect(a.buildOutput({...cfg,colorbehavior:['scale','direct','direct']},[rect],'')).rejects.toThrow(/RGB geometry scale/i);await expect(a.buildOutput({...cfg,colorbehavior:['time','direct','direct']},[rect],'')).rejects.toThrow(/geometry-time/i);});

it('keeps GUI q16 and texture-animation headers in the static format',async()=>{
  const a=load();const rect=['v 0 0 0','v 1 0 0','v 1 1 0','v 0 1 0','vt 0 0','vt 1 0','vt 1 1','vt 0 1','usemtl m_u','f 1/1 2/2 3/3 4/4'].join('\n');
  const gui={rotation:[15,45,90],translation:[1.25,-2.5,3.75],scale:[0.5,1.25,2.0],pivot:[0.1,0.2,0.3]};
  const r=await a.buildOutput({...cfg,displaySlots:{gui}},[rect],'');
  const px=(x,y)=>Array.from(r.rawBuf.slice((y*r.tw+x)*4,(y*r.tw+x+1)*4));
  expect(px(6,0)[2]).toBe(5);
  expect(px(8,0).slice(0,3)).not.toEqual([0,0,0]);

  const W=16,H=32,strip=new Uint8Array(W*H*4);
  for(let y=0;y<H;y++)for(let x=0;x<W;x++){const i=(y*W+x)*4;strip[i]=y<16?17:231;strip[i+3]=255;}
  const anim=load(W,H,strip);
  const ar=await anim.buildOutput({...cfg,texAnimEnabled:true,texFrametime:5,texFade:true},[rect],'');
  const apx=(x,y)=>Array.from(ar.rawBuf.slice((y*ar.tw+x)*4,(y*ar.tw+x+1)*4));
  expect(apx(3,0)[3]).toBe(2);
  expect(apx(4,1).slice(0,3)).toEqual([0,0,5]);
  expect(apx(5,1)[0]&1).toBe(1);
  expect(ar.debugInfo).toMatch(/shader 1/);
});

it('ships no subgroup shader path',()=>{const files=['item.vsh','entity.vsh','block.vsh','terrain.vsh'].map(x=>fs.readFileSync(path.join(ROOT,'objcubed/assets/minecraft/shaders/core',x),'utf8')).join('\n')+fs.readFileSync(path.join(ROOT,'objcubed/assets/minecraft/shaders/include/objmc_main.glsl'),'utf8');expect(files).not.toMatch(/subgroupQuadBroadcast|GL_KHR_shader_subgroup_quad/);expect(files).toContain('ocCorner == 0 || ocCorner == 2');expect(CODE).toContain('OC_STATIC_META_STRIDE = 9');});

it('keeps entity-only overlayColor references out of block and terrain compilation',()=>{
 const light=fs.readFileSync(path.join(ROOT,'objcubed/assets/minecraft/shaders/include/objmc_light.glsl'),'utf8');
 const guards=[];
 for(const [index,line] of light.split(/\r?\n/).entries()){
  const open=line.match(/^\s*#\s*(?:ifn?def)\s+(\w+)/);
  if(open) guards.push(open[1]);
  if(/\boverlayColor\b/.test(line)&&!/^\s*#/.test(line)) expect(guards,index+1).toContain('ENTITY');
  if(/^\s*#\s*endif\b/.test(line)) guards.pop();
 }
 const optimizer=fs.readFileSync(path.join(ROOT,'tools/macos-hybrid/optimize_surface_v4_only.py'),'utf8');
 expect(optimizer).toContain('"#ifdef ENTITY\\n    vec4 ocLightingOverlay');
});
});
