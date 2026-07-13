// OC_HYBRID_SURFACE_PATCH_v1_4
    // Static surface-v4: the carrier is the real face plane, while compact
    // face-local polygon + UV metadata replaces the legacy position/index
    // streams. Each face uses 10 texels: pointer + flags + 4 local points + 4 UVs.
    const OC_STATIC_META_STRIDE = 10;

    function buildStaticSurfaceElements(firstObj, data, cfg, tw, ty, headerRows, put, faceEmission) {
        const EPS = 1e-8;
        const MAX_PLANAR_ERROR = 2e-4;
        const RANGE_MIN = -16.0, RANGE_MAX = 32.0;

        const fallback = message => {
            const e = new Error('OC_STATIC_FALLBACK: ' + message);
            e.ocStaticFallback = true;
            throw e;
        };
        const add = (a,b) => [a[0]+b[0], a[1]+b[1], a[2]+b[2]];
        const sub = (a,b) => [a[0]-b[0], a[1]-b[1], a[2]-b[2]];
        const mul = (a,s) => [a[0]*s, a[1]*s, a[2]*s];
        const dot = (a,b) => a[0]*b[0] + a[1]*b[1] + a[2]*b[2];
        const cross = (a,b) => [
            a[1]*b[2]-a[2]*b[1],
            a[2]*b[0]-a[0]*b[2],
            a[0]*b[1]-a[1]*b[0],
        ];
        const len = a => Math.hypot(a[0], a[1], a[2]);
        const norm = a => { const l = len(a); return l > EPS ? mul(a, 1/l) : null; };
        const clamp = (v,a,b) => Math.max(a, Math.min(b, v));
        const deg = r => r * 180 / Math.PI;
        const enc01 = v => {
            const u = Math.round(clamp(Number.isFinite(v) ? v : 0, 0, 1) * 65535);
            return [(u >> 8) & 255, u & 255];
        };
        const putLinear = (linear, rgba) => put(
            linear % tw, Math.floor(linear / tw), rgba[0], rgba[1], rgba[2], rgba[3]
        );

        function eulerXYZFromColumns(c0, c1, c2) {
            const r00=c0[0], r10=c0[1], r20=c0[2];
            const r11=c1[1], r21=c1[2];
            const r12=c2[1], r22=c2[2];
            const y = Math.asin(clamp(-r20, -1, 1));
            const cy = Math.cos(y);
            let x, z;
            if (Math.abs(cy) > 1e-6) {
                x = Math.atan2(r21, r22);
                z = Math.atan2(r10, r00);
            } else {
                x = Math.atan2(-r12, r11);
                z = 0;
            }
            const clean = v => Math.abs(v) < 1e-7 ? 0 : deg(v);
            return [clean(x), clean(y), clean(z)];
        }

        // Match the full-v2 decoded frame plus its old centre anchor.
        const modelPoint = p => [
            p[0] * cfg.scale + cfg.offset[0] + 0.5,
            p[1] * cfg.scale + cfg.offset[1],
            p[2] * cfg.scale + cfg.offset[2] + 0.5,
        ];

        const raw = [];
        const bmin = [ Infinity, Infinity, Infinity ];
        const bmax = [-Infinity,-Infinity,-Infinity ];

        for (let fi = 0; fi < firstObj.faces.length; fi++) {
            const face = firstObj.faces[fi];
            const count = Math.min(4, face.length);
            if (count < 3) fallback(`face ${fi} has fewer than 3 vertices`);
            const p = [];
            for (let k = 0; k < count; k++) {
                const src = firstObj.positions[face[k][0]];
                if (!src) fallback(`face ${fi} references a missing position`);
                p.push(modelPoint(src));
            }
            if (count === 3) p.push(p[2]);

            const e10 = sub(p[1], p[0]);
            const e20 = sub(p[2], p[0]);
            const U = norm(e10);
            const N = norm(cross(e10, e20));
            if (!U || !N) fallback(`face ${fi} is degenerate; triangulate or clean the OBJ`);
            const V = norm(cross(U, N));
            if (!V) fallback(`face ${fi} has no stable plane basis`);

            if (count === 4) {
                const planeError = Math.abs(dot(sub(p[3], p[0]), N));
                const faceScale = Math.max(len(e10), len(e20), len(sub(p[3], p[0])), 1);
                if (planeError > Math.max(MAX_PLANAR_ERROR, faceScale * MAX_PLANAR_ERROR))
                    fallback(`face ${fi} is non-planar (error ${planeError.toFixed(6)}); triangulate that quad`);
            }

            const q = p.map(P => {
                const d = sub(P, p[0]);
                return [dot(d,U), dot(d,V)];
            });
            const qmin = [Math.min(...q.map(v=>v[0])), Math.min(...q.map(v=>v[1]))];
            const qmax = [Math.max(...q.map(v=>v[0])), Math.max(...q.map(v=>v[1]))];
            const w = qmax[0]-qmin[0], h = qmax[1]-qmin[1];
            if (!(w > EPS && h > EPS)) fallback(`face ${fi} has a zero-size carrier`);
            const qn = q.map(v => [(v[0]-qmin[0])/w, (v[1]-qmin[1])/h]);

            const qm = [(qmin[0]+qmax[0])*0.5, (qmin[1]+qmax[1])*0.5];
            const center = add(p[0], add(mul(U,qm[0]), mul(V,qm[1])));

            const metaBase = headerRows * tw + fi * OC_STATIC_META_STRIDE;
            const px = metaBase % tw, py = Math.floor(metaBase / tw);
            put(px, py, Math.trunc(px/256)%256, px%256, Math.trunc(py/256)%256, py%256);

            // Preserve the v1.3 deterministic edge-owner rule without carrying
            // the legacy index stream. One compact flags texel is cheaper than
            // re-fetching four position indices in every vertex invocation.
            const posIds = [];
            for (let k = 0; k < 4; k++) {
                const vi = data.vertices[fi * 4 + k];
                posIds.push(vi ? vi[0] : 0);
            }
            const owners0 = ((posIds[1] < posIds[2]) ? 1 : 0)
                          | ((posIds[2] < posIds[0]) ? 2 : 0)
                          | ((posIds[0] < posIds[1]) ? 4 : 0);
            const owners1 = ((posIds[2] < posIds[3]) ? 1 : 0)
                          | ((posIds[3] < posIds[0]) ? 2 : 0)
                          | ((posIds[0] < posIds[2]) ? 4 : 0);
            const packedFlags = 1 | (owners0 << 1) | (owners1 << 4);
            putLinear(metaBase + 1, [packedFlags, count, 0, 255]);

            for (let k = 0; k < 4; k++) {
                const [qxH,qxL] = enc01(qn[k][0]);
                const [qyH,qyL] = enc01(qn[k][1]);
                putLinear(metaBase + 2 + k, [qxH,qxL,qyH,qyL]);

                const vi = data.vertices[fi * 4 + k];
                const sourceUv = vi && data.uvs[vi[1]] ? data.uvs[vi[1]] : [0,0];
                const [uH,uL] = enc01(sourceUv[0]);
                const [vH,vL] = enc01(sourceUv[1]);
                putLinear(metaBase + 6 + k, [uH,uL,vH,vL]);
            }

            const from = [(center[0]-w*0.5)*16, (center[1]-h*0.5)*16, center[2]*16];
            const to   = [(center[0]+w*0.5)*16, (center[1]+h*0.5)*16, center[2]*16];
            const origin = center.map(v => v*16);
            const rot = eulerXYZFromColumns(U, V, mul(N,-1));
            const elem = {
                from, to,
                rotation: { origin, x: rot[0], y: rot[1], z: rot[2], rescale: false },
                faces: { north: {
                    uv: [(px+0.1)*16/tw, (py+0.1)*16/ty,
                         (px+0.9)*16/tw, (py+0.9)*16/ty],
                    texture: '#0', tintindex: 0,
                }},
            };
            if (faceEmission[fi] > 0) elem.light_emission = faceEmission[fi];
            raw.push(elem);
            for (let a=0;a<3;a++) {
                bmin[a] = Math.min(bmin[a], from[a], to[a]);
                bmax[a] = Math.max(bmax[a], from[a], to[a]);
            }
        }

        for (let a=0; a<3; a++) {
            if (bmin[a] < RANGE_MIN - 1e-4 || bmax[a] > RANGE_MAX + 1e-4) {
                fallback(
                    `carriers exceed Minecraft's [-16,32] element range on ${'XYZ'[a]} ` +
                    `(min ${(bmin[a]/16).toFixed(3)}, max ${(bmax[a]/16).toFixed(3)} blocks)`
                );
            }
        }
        return { elements: raw, modelTransformation: null };
    }
