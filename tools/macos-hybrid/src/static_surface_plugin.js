// OC_HYBRID_SURFACE_PATCH_v1_2
    // Static OBJ backend: each Minecraft carrier rectangle is placed on the
    // actual OBJ face plane. Minecraft then applies its complete transform to
    // the real surface directly; no subgroup lane exchange or XYZ reconstruction
    // is required. Triangles / non-rectangular quads are clipped in the fragment
    // shader using their original face-local polygon coordinates.
    function buildStaticSurfaceElements(firstObj, cfg, tw, ty, headerRows, put, faceEmission) {
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

        // JOML rotationZYX(z,y,x) == Rz * Ry * Rx. Convert a proper rotation
        // matrix (column vectors c0,c1,c2) back to the JSON Euler fields.
        function eulerXYZFromColumns(c0, c1, c2) {
            const r00=c0[0], r10=c0[1], r20=c0[2];
            const r01=c1[0], r11=c1[1], r21=c1[2];
            const r12=c2[1], r22=c2[2];
            const y = Math.asin(clamp(-r20, -1, 1));
            const cy = Math.cos(y);
            let x, z;
            if (Math.abs(cy) > 1e-6) {
                x = Math.atan2(r21, r22);
                z = Math.atan2(r10, r00);
            } else {
                // Gimbal lock: choose z=0 and absorb the remaining turn into x.
                x = Math.atan2(-r12, r11);
                z = 0;
            }
            const clean = v => Math.abs(v) < 1e-7 ? 0 : deg(v);
            return [clean(x), clean(y), clean(z)];
        }

        // Current obj³ decoded model frame + its old carrier anchor c2:
        // decoded=(p*S+offset-[0,.5,0]); anchor=[.5,.5,.5].
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
            // U x V = -N, matching a NORTH JSON face whose local normal is -Z.
            const V = norm(cross(U, N));
            if (!V) fallback(`face ${fi} has no stable plane basis`);

            if (count === 4) {
                const planeError = Math.abs(dot(sub(p[3], p[0]), N));
                const faceScale = Math.max(len(e10), len(e20), len(sub(p[3], p[0])), 1);
                if (planeError > Math.max(MAX_PLANAR_ERROR, faceScale * MAX_PLANAR_ERROR)) {
                    fallback(`face ${fi} is non-planar (error ${planeError.toFixed(6)}); triangulate that quad`);
                }
            }

            const q = p.map(P => {
                const d = sub(P, p[0]);
                return [dot(d,U), dot(d,V)];
            });
            const qmin = [Math.min(...q.map(v=>v[0])), Math.min(...q.map(v=>v[1]))];
            const qmax = [Math.max(...q.map(v=>v[0])), Math.max(...q.map(v=>v[1]))];
            const w = qmax[0]-qmin[0], h = qmax[1]-qmin[1];
            if (!(w > EPS && h > EPS)) fallback(`face ${fi} has a zero-size carrier`);

            const qm = [(qmin[0]+qmax[0])*0.5, (qmin[1]+qmax[1])*0.5];
            const center = add(p[0], add(mul(U,qm[0]), mul(V,qm[1])));
            const px = fi % tw, py = Math.floor(fi / tw) + headerRows;
            put(px, py, Math.trunc(px/256)%256, px%256, Math.trunc(py/256)%256, py%256);

            const from = [(center[0]-w*0.5)*16, (center[1]-h*0.5)*16, center[2]*16];
            const to   = [(center[0]+w*0.5)*16, (center[1]+h*0.5)*16, center[2]*16];
            const origin = center.map(v => v*16);
            const rot = eulerXYZFromColumns(U, V, mul(N,-1));
            const elem = {
                from, to,
                // Always emit a rotation object, including [0,0,0]. FaceBakery
                // then preserves the original c0..c3 order instead of re-winding.
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

        // Cuboid JSON validates from/to against [-16,32].  Do not hide a
        // compensating translation in the 26.2 item wrapper: that wrapper does
        // not exist for placed blocks.  When a surface cannot fit exactly, fall
        // back to the original full carrier backend so item/block behaviour
        // remains identical instead of silently diverging.
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
