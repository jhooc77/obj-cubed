import fs from 'node:fs';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..');
const source = fs.readFileSync(path.join(root, 'src/static_surface_plugin.js'), 'utf8');
const build = new Function(`${source}\nreturn buildStaticSurfaceElements;`)();

function rx(a) { const c=Math.cos(a),s=Math.sin(a); return [[1,0,0],[0,c,-s],[0,s,c]]; }
function ry(a) { const c=Math.cos(a),s=Math.sin(a); return [[c,0,s],[0,1,0],[-s,0,c]]; }
function rz(a) { const c=Math.cos(a),s=Math.sin(a); return [[c,-s,0],[s,c,0],[0,0,1]]; }
function mul(A,B) { return A.map((r,i)=>B[0].map((_,j)=>r.reduce((v,_,k)=>v+A[i][k]*B[k][j],0))); }
function mv(A,v) { return A.map(r=>r[0]*v[0]+r[1]*v[1]+r[2]*v[2]); }
function add(a,b) { return a.map((v,i)=>v+b[i]); }
function sub(a,b) { return a.map((v,i)=>v-b[i]); }
function near(a,b,eps=2e-5) { assert.equal(a.length,b.length); for(let i=0;i<a.length;i++) assert.ok(Math.abs(a[i]-b[i])<eps, `${a} != ${b}`); }
function indexedData(obj) {
  const uvs = [[0,0],[1,0],[1,1],[0,1]];
  const vertices=[];
  for (const face of obj.faces) {
    for (let i=0;i<Math.min(4,face.length);i++) vertices.push([face[i][0], Math.min(i,3)]);
    if (face.length===3) vertices.push([face[2][0],2]);
  }
  return {positions:obj.positions, uvs, vertices};
}

function elementVertices(el, modelTransformation) {
  const f=el.from.map(v=>v/16), t=el.to.map(v=>v/16), o=el.rotation.origin.map(v=>v/16);
  const base=[ [t[0],t[1],f[2]], [t[0],f[1],f[2]], [f[0],f[1],f[2]], [f[0],t[1],f[2]] ];
  const d=Math.PI/180;
  const R=mul(mul(rz(el.rotation.z*d),ry(el.rotation.y*d)),rx(el.rotation.x*d));
  const translation=modelTransformation?.translation ?? [0,0,0];
  return base.map(p=>add(add(o,mv(R,sub(p,o))),translation));
}

function runTriangle() {
  const obj={
    positions:[[0,0,0],[1,0,0],[0,1,0]],
    faces:[[[0,0],[1,1],[2,2]]],
  };
  const puts=[];
  const out=build(obj,indexedData(obj),{scale:1,offset:[0,0,0]},16,64,2,(...a)=>puts.push(a),[0]);
  assert.equal(out.elements.length,1);
  assert.equal(out.modelTransformation, null);
  assert.equal(puts.length,9);
  // Face pointer plus 8 compact q16 point/UV texels.
  assert.deepEqual(puts[0],[0,2,0,0,0,2]);
  const verts=elementVertices(out.elements[0],out.modelTransformation);
  const expected=[[1.5,0,0.5],[1.5,1,0.5],[0.5,1,0.5],[0.5,0,0.5]];
  verts.forEach((v,i)=>near(v,expected[i]));
}

function runTiltedQuad() {
  const obj={
    positions:[[0,0,0],[1,0,1],[1,1,1],[0,1,0]],
    faces:[[[0,0],[1,1],[2,2],[3,3]]],
  };
  const out=build(obj,indexedData(obj),{scale:0.75,offset:[0.1,-0.2,0.3]},32,128,2,()=>{},[12]);
  assert.equal(out.elements[0].light_emission,12);
  const verts=elementVertices(out.elements[0],out.modelTransformation);
  const p0=[0.5+0.1, -0.2, 0.5+0.3];
  const p1=[0.5+0.1+0.75, -0.2, 0.5+0.3+0.75];
  const p3=[0.5+0.1, -0.2+0.75, 0.5+0.3];
  const e1=sub(p1,p0), e2=sub(p3,p0);
  const n=[e1[1]*e2[2]-e1[2]*e2[1],e1[2]*e2[0]-e1[0]*e2[2],e1[0]*e2[1]-e1[1]*e2[0]];
  for(const p of verts) assert.ok(Math.abs(n[0]*(p[0]-p0[0])+n[1]*(p[1]-p0[1])+n[2]*(p[2]-p0[2]))<2e-5);
}

function runMetadataWrap() {
  const obj={positions:[[0,0,0],[1,0,0],[0,1,0]],faces:[[[0,0],[1,1],[2,2]]]};
  const puts=[];
  build(obj,indexedData(obj),{scale:1,offset:[0,0,0]},8,64,2,(...a)=>puts.push(a),[0]);
  assert.deepEqual(puts[0],[0,2,0,0,0,2]);
  // Nine texels from linear 16..24: the final metadata texel wraps to row 3.
  assert.deepEqual(puts.at(-1).slice(0,2),[0,3]);
}

function runOutOfRangeFallback() {
  const obj={positions:[[3,0,0],[4,0,0],[3,1,0]],faces:[[[0,0],[1,1],[2,2]]]};
  assert.throws(
    ()=>build(obj,indexedData(obj),{scale:1,offset:[0,0,0]},16,64,2,()=>{},[0]),
    e => e && e.ocStaticFallback === true && /element range/.test(e.message)
  );
}

function runNonPlanarReject() {
  const obj={positions:[[0,0,0],[1,0,0],[1,1,0],[0,1,0.1]],faces:[[[0,0],[1,1],[2,2],[3,3]]]};
  assert.throws(()=>build(obj,indexedData(obj),{scale:1,offset:[0,0,0]},16,64,2,()=>{},[0]),/non-planar/);
}

runTriangle();
runTiltedQuad();
runMetadataWrap();
runOutOfRangeFallback();
runNonPlanarReject();
console.log('Static surface-v4 helper geometry/metadata tests passed.');
