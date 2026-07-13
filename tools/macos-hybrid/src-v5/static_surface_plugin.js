// OC_SURFACE_V4_ONLY_v1_5
// Static-only, subgroup-free exporter. OBJ polygons are normalized before
// indexing: N-gons, concave quads, non-planar quads and non-affine UV quads
// are triangulated. Planar convex affine quads stay as one carrier.
const OC_STATIC_META_STRIDE = 9;
const OC_STATIC_PLANAR_EPS = 2e-4;
const OC_STATIC_EPS = 1e-8;

function oc3vSub(a,b) { return [a[0]-b[0], a[1]-b[1], a[2]-b[2]]; }
function oc3vAdd(a,b) { return [a[0]+b[0], a[1]+b[1], a[2]+b[2]]; }
function oc3vMul(a,s) { return [a[0]*s, a[1]*s, a[2]*s]; }
function oc3vDot(a,b) { return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]; }
function oc3vCross(a,b) {
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]];
}
function oc3vLen(a) { return Math.hypot(a[0],a[1],a[2]); }
function oc3vNorm(a) { const l=oc3vLen(a); return l>OC_STATIC_EPS ? oc3vMul(a,1/l) : null; }
function oc2Cross(a,b) { return a[0]*b[1]-a[1]*b[0]; }
function oc2Area(poly) {
    let a=0;
    for (let i=0;i<poly.length;i++) {
        const p=poly[i], q=poly[(i+1)%poly.length];
        a += p[0]*q[1]-p[1]*q[0];
    }
    return a*0.5;
}
function ocPointInTri2(p,a,b,c,sign) {
    const e0=sign*oc2Cross([b[0]-a[0],b[1]-a[1]],[p[0]-a[0],p[1]-a[1]]);
    const e1=sign*oc2Cross([c[0]-b[0],c[1]-b[1]],[p[0]-b[0],p[1]-b[1]]);
    const e2=sign*oc2Cross([a[0]-c[0],a[1]-c[1]],[p[0]-c[0],p[1]-c[1]]);
    return e0>=-1e-10 && e1>=-1e-10 && e2>=-1e-10;
}
function ocProjectPolygon(points) {
    let n=[0,0,0];
    for (let i=0;i<points.length;i++) {
        const p=points[i], q=points[(i+1)%points.length];
        n[0] += (p[1]-q[1])*(p[2]+q[2]);
        n[1] += (p[2]-q[2])*(p[0]+q[0]);
        n[2] += (p[0]-q[0])*(p[1]+q[1]);
    }
    let N=oc3vNorm(n);
    if (!N) {
        for (let i=1;i+1<points.length && !N;i++)
            N=oc3vNorm(oc3vCross(oc3vSub(points[i],points[0]),oc3vSub(points[i+1],points[0])));
    }
    if (!N) return null;
    const ax=Math.abs(N[0]), ay=Math.abs(N[1]), az=Math.abs(N[2]);
    const drop = ax>=ay && ax>=az ? 0 : (ay>=az ? 1 : 2);
    const q=points.map(p => drop===0 ? [p[1],p[2]] : drop===1 ? [p[0],p[2]] : [p[0],p[1]]);
    return { q, N };
}
function ocTriangulateFace(face, positions, label) {
    const refs=[];
    for (const r of face) {
        if (!refs.length || r[0]!==refs[refs.length-1][0] || r[1]!==refs[refs.length-1][1]) refs.push(r);
    }
    if (refs.length>2 && refs[0][0]===refs[refs.length-1][0] && refs[0][1]===refs[refs.length-1][1]) refs.pop();
    if (refs.length<3) return [];
    const points=refs.map(r=>positions[r[0]] || [0,0,0]);
    const proj=ocProjectPolygon(points);
    if (!proj || Math.abs(oc2Area(proj.q))<OC_STATIC_EPS) {
        console.warn(`[obj³] dropped zero-area face ${label}`);
        return [];
    }
    const sign=oc2Area(proj.q)>=0 ? 1 : -1;
    const indices=refs.map((_,i)=>i);
    const tris=[];
    let guard=0;
    while (indices.length>3 && guard++<refs.length*refs.length) {
        let cut=false;
        for (let j=0;j<indices.length;j++) {
            const ia=indices[(j+indices.length-1)%indices.length];
            const ib=indices[j];
            const ic=indices[(j+1)%indices.length];
            const a=proj.q[ia], b=proj.q[ib], c=proj.q[ic];
            if (sign*oc2Cross([b[0]-a[0],b[1]-a[1]],[c[0]-b[0],c[1]-b[1]])<=1e-10) continue;
            let contains=false;
            for (const ip of indices) {
                if (ip===ia||ip===ib||ip===ic) continue;
                if (ocPointInTri2(proj.q[ip],a,b,c,sign)) { contains=true; break; }
            }
            if (contains) continue;
            tris.push([refs[ia],refs[ib],refs[ic]]);
            indices.splice(j,1);
            cut=true;
            break;
        }
        if (!cut) throw new Error(`Cannot triangulate self-intersecting/degenerate OBJ face ${label}`);
    }
    if (indices.length===3) tris.push(indices.map(i=>refs[i]));
    return tris;
}
function ocQuadIsPlanarAffine(face,o) {
    if (face.length!==4) return false;
    const p=face.map(r=>o.positions[r[0]] || [0,0,0]);
    let n=oc3vNorm(oc3vCross(oc3vSub(p[1],p[0]),oc3vSub(p[2],p[0])));
    if (!n) return false;
    const scale=Math.max(1,oc3vLen(oc3vSub(p[1],p[0])),oc3vLen(oc3vSub(p[2],p[0])),oc3vLen(oc3vSub(p[3],p[0])));
    if (Math.abs(oc3vDot(oc3vSub(p[3],p[0]),n))>Math.max(OC_STATIC_PLANAR_EPS,scale*OC_STATIC_PLANAR_EPS)) return false;
    const U=oc3vNorm(oc3vSub(p[1],p[0]));
    const V=U && oc3vNorm(oc3vCross(U,n));
    if (!U||!V) return false;
    const q=p.map(P=>{const d=oc3vSub(P,p[0]);return [oc3vDot(d,U),oc3vDot(d,V)];});
    const area=oc2Area(q);
    if (Math.abs(area)<OC_STATIC_EPS) return false;
    const sign=area>=0?1:-1;
    for (let i=0;i<4;i++) {
        const a=q[i],b=q[(i+1)%4],c=q[(i+2)%4];
        if (sign*oc2Cross([b[0]-a[0],b[1]-a[1]],[c[0]-b[0],c[1]-b[1]])<-1e-9) return false;
    }
    const d1=[q[1][0]-q[0][0],q[1][1]-q[0][1]];
    const d2=[q[2][0]-q[0][0],q[2][1]-q[0][1]];
    const det=oc2Cross(d1,d2);
    if (Math.abs(det)<OC_STATIC_EPS) return false;
    const d3=[q[3][0]-q[0][0],q[3][1]-q[0][1]];
    const b1=oc2Cross(d3,d2)/det;
    const b2=oc2Cross(d1,d3)/det;
    const uv=face.map(r=>o.uvs[r[1]] || [0,0]);
    const pred=[uv[0][0]+b1*(uv[1][0]-uv[0][0])+b2*(uv[2][0]-uv[0][0]),
                uv[0][1]+b1*(uv[1][1]-uv[0][1])+b2*(uv[2][1]-uv[0][1])];
    return Math.hypot(pred[0]-uv[3][0],pred[1]-uv[3][1])<=2e-5;
}
function normalizeStaticObj(o) {
    const out={positions:o.positions,uvs:o.uvs,faces:[],faceMaterials:[],faceGroups:[],faceBlocks:[]};
    let split=0,dropped=0;
    const push=(f,fi)=>{
        out.faces.push(f);
        out.faceMaterials.push(o.faceMaterials[fi]);
        out.faceGroups.push(o.faceGroups[fi]);
        out.faceBlocks.push(o.faceBlocks[fi]);
    };
    for (let fi=0;fi<o.faces.length;fi++) {
        const f=o.faces[fi];
        if (f.length===3) { push(f,fi); continue; }
        if (f.length===4 && ocQuadIsPlanarAffine(f,o)) { push(f,fi); continue; }
        // Preserve Minecraft's canonical quad diagonal (0,1,2) + (2,3,0).
        // This matters for non-planar quads and UVs that are not affine across
        // the whole quad: choosing the other diagonal changes the surface.
        if (f.length===4) {
            push([f[0],f[1],f[2]],fi);
            push([f[0],f[2],f[3]],fi);
            split++;
            continue;
        }
        const tris=ocTriangulateFace(f,o.positions,`${fi}${o.faceGroups[fi]?` (${o.faceGroups[fi]})`:''}`);
        if (!tris.length) { dropped++; continue; }
        for (const t of tris) push(t,fi);
        split += Math.max(0,tris.length-1);
    }
    out.normalizationStats={sourceFaces:o.faces.length,outputFaces:out.faces.length,splitExtra:split,dropped};
    return out;
}

function ocCarrierCandidates(points) {
    let N=null;
    for (let i=1;i+1<points.length&&!N;i++)
        N=oc3vNorm(oc3vCross(oc3vSub(points[i],points[0]),oc3vSub(points[i+1],points[0])));
    if (!N) return [];
    const out=[];
    for (let i=0;i<points.length;i++) {
        const U=oc3vNorm(oc3vSub(points[(i+1)%points.length],points[i])); if (!U) continue;
        const V=oc3vNorm(oc3vCross(U,N)); if (!V) continue;
        const q=points.map(P=>{const d=oc3vSub(P,points[0]);return [oc3vDot(d,U),oc3vDot(d,V)];});
        const mn=[Math.min(...q.map(x=>x[0])),Math.min(...q.map(x=>x[1]))];
        const mx=[Math.max(...q.map(x=>x[0])),Math.max(...q.map(x=>x[1]))];
        const w=mx[0]-mn[0],h=mx[1]-mn[1],area=w*h;
        if (!(w>OC_STATIC_EPS&&h>OC_STATIC_EPS)) continue;
        out.push({U,V,N,q,mn,mx,w,h,area});
    }
    return out;
}
function ocUvAffine(q,uv) {
    const d1=[q[1][0]-q[0][0],q[1][1]-q[0][1]];
    const d2=[q[2][0]-q[0][0],q[2][1]-q[0][1]];
    const det=oc2Cross(d1,d2);
    if (Math.abs(det)<OC_STATIC_EPS) return null;
    const b1x=d2[1]/det,b1y=-d2[0]/det,b1c=-(b1x*q[0][0]+b1y*q[0][1]);
    const b2x=-d1[1]/det,b2y=d1[0]/det,b2c=-(b2x*q[0][0]+b2y*q[0][1]);
    const du1=[uv[1][0]-uv[0][0],uv[1][1]-uv[0][1]];
    const du2=[uv[2][0]-uv[0][0],uv[2][1]-uv[0][1]];
    return {
        u:[du1[0]*b1x+du2[0]*b2x,du1[0]*b1y+du2[0]*b2y,uv[0][0]+du1[0]*b1c+du2[0]*b2c],
        v:[du1[1]*b1x+du2[1]*b2x,du1[1]*b1y+du2[1]*b2y,uv[0][1]+du1[1]*b1c+du2[1]*b2c],
    };
}
function ocIsCarrierRectangle(q,count) {
    if (count!==4) return false;
    const seen=new Set();
    for (const p of q) {
        const x=Math.abs(p[0])<2e-5?0:Math.abs(p[0]-1)<2e-5?1:-1;
        const y=Math.abs(p[1])<2e-5?0:Math.abs(p[1]-1)<2e-5?1:-1;
        if (x<0||y<0) return false;
        seen.add(`${x},${y}`);
    }
    return seen.size===4;
}
function ocNativeUvRect(q,uv,count) {
    if (!ocIsCarrierRectangle(q,count)) return null;
    const a=ocUvAffine(q,uv); if (!a) return null;
    if (Math.abs(a.u[1])>2e-5 || Math.abs(a.v[0])>2e-5) return null;
    return {u0:a.u[2],u1:a.u[0]+a.u[2],v0:a.v[2],v1:a.v[1]+a.v[2]};
}

function buildStaticSurfacePlan(firstObj,data,cfg,allowNative) {
    const modelPoint=p=>[p[0]*cfg.scale+cfg.offset[0]+0.5,p[1]*cfg.scale+cfg.offset[1],p[2]*cfg.scale+cfg.offset[2]+0.5];
    const primitives=[];
    let customCount=0,nativeCount=0;
    for (let fi=0;fi<firstObj.faces.length;fi++) {
        const face=firstObj.faces[fi],count=face.length;
        const sourceP=face.map(r=>modelPoint(firstObj.positions[r[0]]));
        const uv=[]; const posIds=[];
        for (let k=0;k<count;k++) {
            const vi=data.vertices[fi*4+k];
            uv.push(data.uvs[vi[1]]||[0,0]); posIds.push(vi[0]);
        }
        const candidates=ocCarrierCandidates(sourceP);
        if (!candidates.length) throw new Error(`Normalized face ${fi} is degenerate.`);
        let best=null;
        for (const c of candidates) {
            const qn=c.q.map(v=>[(v[0]-c.mn[0])/c.w,(v[1]-c.mn[1])/c.h]);
            const nativeUv=allowNative?ocNativeUvRect(qn,uv,count):null;
            const score=nativeUv?-1:c.area;
            if (!best || score<best.score-1e-12) best={...c,qn,nativeUv,score};
        }
        const p=sourceP.slice(),q=best.qn.slice(),uv4=uv.slice(),ids=posIds.slice();
        if (count===3) { p.push(p[2]);q.push(q[2]);uv4.push(uv4[2]);ids.push(ids[2]); }
        let ownerBits=0;
        for (let k=0;k<count;k++) if (ids[k]<ids[(k+1)%count]) ownerBits|=1<<k;
        const shape=ocIsCarrierRectangle(q,count)?0:(count===3?1:2);
        const center=oc3vAdd(sourceP[0],oc3vAdd(oc3vMul(best.U,(best.mn[0]+best.mx[0])*0.5),oc3vMul(best.V,(best.mn[1]+best.mx[1])*0.5)));
        const primitive={fi,count,p,uv:uv4,q,posIds:ids,ownerBits,shape,center,U:best.U,V:best.V,N:best.N,w:best.w,h:best.h,nativeUv:best.nativeUv,native:!!best.nativeUv};
        if (primitive.native) nativeCount++; else { primitive.customIndex=customCount++; }
        primitives.push(primitive);
    }
    return {primitives,customCount,nativeCount};
}

function writeStaticSurfaceElements(plan,cfg,tw,ty,headerRows,metaH,texH,put,faceEmission) {
    const RANGE_MIN=-16,RANGE_MAX=32;
    const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
    const enc01=v=>{const u=Math.round(clamp(Number.isFinite(v)?v:0,0,1)*65535);return[(u>>8)&255,u&255];};
    const enc01Bit=(v,bit)=>{let u=Math.round(clamp(Number.isFinite(v)?v:0,0,1)*65534);u=(u&65534)|(bit&1);return[(u>>8)&255,u&255];};
    const putLinear=(linear,rgba)=>put(linear%tw,Math.floor(linear/tw),rgba[0],rgba[1],rgba[2],rgba[3]);
    const deg=r=>r*180/Math.PI;
    function eulerXYZFromColumns(c0,c1,c2){
        const r00=c0[0],r10=c0[1],r20=c0[2],r11=c1[1],r21=c1[2],r12=c2[1],r22=c2[2];
        const y=Math.asin(clamp(-r20,-1,1)),cy=Math.cos(y);let x,z;
        if(Math.abs(cy)>1e-6){x=Math.atan2(r21,r22);z=Math.atan2(r10,r00);}else{x=Math.atan2(-r12,r11);z=0;}
        const clean=v=>Math.abs(v)<1e-7?0:deg(v);return[clean(x),clean(y),clean(z)];
    }
    const elements=[];const bmin=[Infinity,Infinity,Infinity],bmax=[-Infinity,-Infinity,-Infinity];
    const textureBaseY=headerRows+metaH;
    for (const pr of plan.primitives) {
        const from=[(pr.center[0]-pr.w*0.5)*16,(pr.center[1]-pr.h*0.5)*16,pr.center[2]*16];
        const to=[(pr.center[0]+pr.w*0.5)*16,(pr.center[1]+pr.h*0.5)*16,pr.center[2]*16];
        const origin=pr.center.map(v=>v*16),rot=eulerXYZFromColumns(pr.U,pr.V,oc3vMul(pr.N,-1));
        let faceUv;
        if (pr.native) {
            faceUv=[
                pr.nativeUv.u0*16,
                (textureBaseY+pr.nativeUv.v0*texH)/ty*16,
                pr.nativeUv.u1*16,
                (textureBaseY+pr.nativeUv.v1*texH)/ty*16,
            ];
        } else {
            const metaBase=headerRows*tw+pr.customIndex*OC_STATIC_META_STRIDE;
            const px=metaBase%tw,py=Math.floor(metaBase/tw);
            put(px,py,Math.trunc(px/256)%256,px%256,Math.trunc(py/256)%256,py%256);
            const packedFlags=(pr.shape&3)|((pr.ownerBits&15)<<2);
            // Hide the six flag bits in the least-significant bit of six q16
            // coordinates. That preserves 15-bit geometry precision and removes
            // one whole metadata texel/fetch per provoking vertex.
            for(let k=0;k<4;k++){
                const bx=(k*2<6)?((packedFlags>>(k*2))&1):0;
                const by=(k*2+1<6)?((packedFlags>>(k*2+1))&1):0;
                const [qxH,qxL]=enc01Bit(pr.q[k][0],bx),[qyH,qyL]=enc01Bit(pr.q[k][1],by);
                putLinear(metaBase+1+k,[qxH,qxL,qyH,qyL]);
                const [uH,uL]=enc01(pr.uv[k][0]),[vH,vL]=enc01(pr.uv[k][1]);
                putLinear(metaBase+5+k,[uH,uL,vH,vL]);
            }
            faceUv=[(px+0.1)*16/tw,(py+0.1)*16/ty,(px+0.9)*16/tw,(py+0.9)*16/ty];
        }
        const elem={from,to,rotation:{origin,x:rot[0],y:rot[1],z:rot[2],rescale:false},faces:{north:{uv:faceUv,texture:'#0',tintindex:0}}};
        if (faceEmission[pr.fi]>0) elem.light_emission=faceEmission[pr.fi];
        if (cfg.noshadow) elem.shade=false;
        elements.push(elem);
        for(let a=0;a<3;a++){bmin[a]=Math.min(bmin[a],from[a],to[a]);bmax[a]=Math.max(bmax[a],from[a],to[a]);}
    }
    for(let a=0;a<3;a++) if(bmin[a]<RANGE_MIN-1e-4||bmax[a]>RANGE_MAX+1e-4)
        throw new Error(`Surface-v4 carrier exceeds Minecraft's [-16,32] element range on ${'XYZ'[a]} (min ${(bmin[a]/16).toFixed(3)}, max ${(bmax[a]/16).toFixed(3)} blocks). Lower export Scale or move the model toward the origin.`);
    return {elements,modelTransformation:null};
}
