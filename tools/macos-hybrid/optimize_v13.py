#!/usr/bin/env python3
"""Upgrade the hybrid static-surface backend from v1.2 to v1.3.

Goals:
* remove the fixed conservative overlap that can z-fight on NVIDIA GPUs;
* allow only a deterministic edge owner to extend across tiny interpolation error;
* clamp accepted edge barycentrics so UVs never sample outside the source face;
* skip duplicate P3/UV3 fetches for triangle-heavy meshes;
* avoid second texture samples when cross-fade is inactive;
* avoid unused static header/texture metadata fetches.

This script edits the patch tooling. The normal installer is then run against a
clean upstream checkout to regenerate objcubed.js and the resource-pack shaders.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools" / "macos-hybrid"
SRC = TOOLS / "src"
OLD_TAG = "OC_HYBRID_SURFACE_PATCH_v1_2"
NEW_TAG = "OC_HYBRID_SURFACE_PATCH_v1_3"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def sub_once(text: str, pattern: str, repl: str, label: str) -> str:
    out, count = re.subn(pattern, repl, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"{label}: expected one regex match, found {count}")
    return out


STATIC_FRAGMENT = r'''// obj³ static-surface fragment helpers — v1.3.
// Resolves a point on the rectangular carrier back into the source OBJ face.
//
// NVIDIA seam fix:
// v1.2 expanded every triangle by a fixed epsilon. Adjacent coplanar carriers
// therefore overlapped along every mesh edge and some drivers resolved the
// equal-depth fragments as a dotted/wireframe-looking z-fight. v1.3 only lets
// one deterministic owner expand across a slightly-negative edge. Accepted
// weights are clamped back onto the polygon before UV reconstruction.

float ocCross2(vec2 a, vec2 b) {
    return a.x * b.y - a.y * b.x;
}

bool ocBarycentricOwned(vec2 p, vec2 a, vec2 b, vec2 c, int ownerBits, out vec3 w) {
    float den = ocCross2(b - a, c - a);
    if (abs(den) < 1.0e-10) {
        w = vec3(0.0);
        return false;
    }

    vec3 raw;
    raw.x = ocCross2(b - p, c - p) / den;
    raw.y = ocCross2(c - p, a - p) / den;
    raw.z = 1.0 - raw.x - raw.y;

    // Roughly half a fragment footprint. A value farther outside is definitely
    // not covered. Inside the tiny uncertainty band only the edge owner may
    // extend, avoiding both cracks and coplanar overlap/z-fighting.
    vec3 tol = max(fwidth(raw) * 0.55, vec3(1.0e-7));
    if (any(lessThan(raw, -tol))) {
        w = vec3(0.0);
        return false;
    }
    if (raw.x < 0.0 && (ownerBits & 1) == 0) return false;
    if (raw.y < 0.0 && (ownerBits & 2) == 0) return false;
    if (raw.z < 0.0 && (ownerBits & 4) == 0) return false;

    // Never extrapolate UVs outside the source polygon. Besides avoiding atlas
    // bleed this also makes the owner overlap visually identical to the edge.
    w = max(raw, vec3(0.0));
    float sumW = w.x + w.y + w.z;
    if (sumW <= 1.0e-12) {
        w = vec3(0.0);
        return false;
    }
    w /= sumW;
    return true;
}

bool ocResolveStaticUv(
    vec2 p,
    vec4 p01,
    vec4 p23,
    vec4 uv01,
    vec4 uv23,
    float vertexCount,
    float packedFlags,
    out vec2 uv
) {
    vec2 p0 = p01.xy;
    vec2 p1 = p01.zw;
    vec2 p2 = p23.xy;
    vec2 p3 = p23.zw;
    vec2 uv0 = uv01.xy;
    vec2 uv1 = uv01.zw;
    vec2 uv2 = uv23.xy;
    vec2 uv3 = uv23.zw;

    // bit 0 = active; bits 1..3 = triangle 0 edge owners;
    // bits 4..6 = triangle 1 edge owners.
    int flags = int(floor(packedFlags + 0.5));
    int owners0 = (flags >> 1) & 7;
    int owners1 = (flags >> 4) & 7;

    vec3 w;
    if (ocBarycentricOwned(p, p0, p1, p2, owners0, w)) {
        uv = uv0 * w.x + uv1 * w.y + uv2 * w.z;
        return true;
    }
    if (vertexCount > 3.5 && ocBarycentricOwned(p, p0, p2, p3, owners1, w)) {
        uv = uv0 * w.x + uv2 * w.y + uv3 * w.z;
        return true;
    }
    uv = vec2(0.0);
    return false;
}
'''


def patch_vertex() -> None:
    path = SRC / "objmc_static_vertex_hybrid.glsl"
    text = path.read_text(encoding="utf-8")
    if NEW_TAG in text:
        return
    if OLD_TAG not in text:
        raise RuntimeError("static vertex source is neither v1.2 nor v1.3")
    text = text.replace(OLD_TAG, NEW_TAG)
    text = replace_once(text, "    ivec4 ocT4 = getmeta(ocTopLeft, 4);\n", "", "remove unused t4")

    old_fetch = '''            ivec2 ocI0 = getvert(ocTopLeft, ocSize.x, ocDataHeight + ocVph + ocVth, ocVertexBase + 0);
            ivec2 ocI1 = getvert(ocTopLeft, ocSize.x, ocDataHeight + ocVph + ocVth, ocVertexBase + 1);
            ivec2 ocI2 = getvert(ocTopLeft, ocSize.x, ocDataHeight + ocVph + ocVth, ocVertexBase + 2);
            ivec2 ocI3 = getvert(ocTopLeft, ocSize.x, ocDataHeight + ocVph + ocVth, ocVertexBase + 3);

            vec3 ocP0 = getpos(ocTopLeft, ocSize.x, ocDataHeight, ocI0.x);
            vec3 ocP1 = getpos(ocTopLeft, ocSize.x, ocDataHeight, ocI1.x);
            vec3 ocP2 = getpos(ocTopLeft, ocSize.x, ocDataHeight, ocI2.x);
            vec3 ocP3 = getpos(ocTopLeft, ocSize.x, ocDataHeight, ocI3.x);

            vec2 ocUv0 = getuv(ocTopLeft, ocSize.x, ocDataHeight + ocVph, ocI0.y);
            vec2 ocUv1 = getuv(ocTopLeft, ocSize.x, ocDataHeight + ocVph, ocI1.y);
            vec2 ocUv2 = getuv(ocTopLeft, ocSize.x, ocDataHeight + ocVph, ocI2.y);
            vec2 ocUv3 = getuv(ocTopLeft, ocSize.x, ocDataHeight + ocVph, ocI3.y);'''
    new_fetch = '''            ivec2 ocI0 = getvert(ocTopLeft, ocSize.x, ocDataHeight + ocVph + ocVth, ocVertexBase + 0);
            ivec2 ocI1 = getvert(ocTopLeft, ocSize.x, ocDataHeight + ocVph + ocVth, ocVertexBase + 1);
            ivec2 ocI2 = getvert(ocTopLeft, ocSize.x, ocDataHeight + ocVph + ocVth, ocVertexBase + 2);
            ivec2 ocI3 = getvert(ocTopLeft, ocSize.x, ocDataHeight + ocVph + ocVth, ocVertexBase + 3);
            bool ocTriangle = all(equal(ocI2, ocI3));

            vec3 ocP0 = getpos(ocTopLeft, ocSize.x, ocDataHeight, ocI0.x);
            vec3 ocP1 = getpos(ocTopLeft, ocSize.x, ocDataHeight, ocI1.x);
            vec3 ocP2 = getpos(ocTopLeft, ocSize.x, ocDataHeight, ocI2.x);
            vec3 ocP3 = ocTriangle ? ocP2 : getpos(ocTopLeft, ocSize.x, ocDataHeight, ocI3.x);

            vec2 ocUv0 = getuv(ocTopLeft, ocSize.x, ocDataHeight + ocVph, ocI0.y);
            vec2 ocUv1 = getuv(ocTopLeft, ocSize.x, ocDataHeight + ocVph, ocI1.y);
            vec2 ocUv2 = getuv(ocTopLeft, ocSize.x, ocDataHeight + ocVph, ocI2.y);
            vec2 ocUv3 = ocTriangle ? ocUv2 : getuv(ocTopLeft, ocSize.x, ocDataHeight + ocVph, ocI3.y);'''
    text = replace_once(text, old_fetch, new_fetch, "triangle fetch fast path")

    old_flags = '''            bool ocTriangle = all(equal(ocI2, ocI3));
            ocSurfaceMap.z = ocTriangle ? 3.0 : 4.0;
            ocSurfaceMap.w = 1.0;'''
    new_flags = '''            // One directed owner per source edge. The fragment shader uses these
            // bits only when interpolation places a sample microscopically outside;
            // this closes cracks without overlapping both coplanar faces.
            int ocOwners0 = ((ocI1.x < ocI2.x) ? 1 : 0)
                          | ((ocI2.x < ocI0.x) ? 2 : 0)
                          | ((ocI0.x < ocI1.x) ? 4 : 0);
            int ocOwners1 = ((ocI2.x < ocI3.x) ? 1 : 0)
                          | ((ocI3.x < ocI0.x) ? 2 : 0)
                          | ((ocI0.x < ocI2.x) ? 4 : 0);
            int ocPackedFlags = 1 | (ocOwners0 << 1) | (ocOwners1 << 4);
            ocSurfaceMap.z = ocTriangle ? 3.0 : 4.0;
            ocSurfaceMap.w = float(ocPackedFlags);'''
    text = replace_once(text, old_flags, new_flags, "edge owner flags")

    texture_pattern = r'''            float ocTexTime = GameTime \* 24000\.0;.*?            ocSurfaceMap\.xy = vec2\(ocSize\) / vec2\(ocAtlasSize\);'''
    texture_repl = '''            float ocTexTime = GameTime * 24000.0;
#ifdef ENTITY
            // GUI icons are baked once. Pin texture animation to frame zero so
            // a reload cannot freeze an arbitrary frame into the GUI atlas.
            if (isGUI == 1) ocTexTime = 0.0;
#endif
            // x=5 is the cheap gate. The x=4 clock pixel is fetched only when a
            // whole-texture animation or atlas band actually exists.
            ivec4 ocTexFlags = ivec4(texelFetch(Sampler0, ocTopLeft + ivec2(5, 1), 0) * 255.0 + 0.5);
            int ocBandCount = min(ocTexFlags.g, 15);
            bool ocTexAnimated = ocNTextures > 1 || ocBandCount > 0;
            float ocTexFrameTime = 1.0;
            bool ocTexFade = false;
            if (ocTexAnimated) {
                ivec4 ocTexMeta = ivec4(texelFetch(Sampler0, ocTopLeft + ivec2(4, 1), 0) * 255.0 + 0.5);
                ocTexFrameTime = max(float(ocTexMeta.r * 65536 + ocTexMeta.g * 256 + ocTexMeta.b), 1.0);
                ocTexFade = (ocTexFlags.r & 1) == 1;
            }

            vec2 ocBase0 = vec2(ocTopLeft.x, ocTopLeft.y + ocHeaderHeight);
            vec2 ocBase1 = ocBase0;
            if (ocNTextures > 1) {
                int ocFrame0 = int(ocTexTime / ocTexFrameTime) % ocNTextures;
                int ocFrame1 = (ocFrame0 + 1) % ocNTextures;
                ocBase0.y += float(ocFrame0 * ocSize.y);
                ocBase1.y += float(ocFrame1 * ocSize.y);
                transition = ocTexFade ? fract(ocTexTime / ocTexFrameTime) : 0.0;
            } else if (ocBandCount > 0) {
                float ocVmid = (ocUv0.y + ocUv2.y) * 0.5 * float(ocSize.y);
                for (int ocB = 0; ocB < 15; ocB++) {
                    if (ocB >= ocBandCount) break;
                    ivec4 ocB0 = ivec4(texelFetch(Sampler0, ocTopLeft + ivec2(6 + 2 * ocB, 1), 0) * 255.0 + 0.5);
                    ivec4 ocB1 = ivec4(texelFetch(Sampler0, ocTopLeft + ivec2(7 + 2 * ocB, 1), 0) * 255.0 + 0.5);
                    int ocY0 = ocB0.r * 256 + ocB0.g;
                    int ocFrameH = ocB0.b * 256 + ocB1.r;
                    int ocFrameCount = max(ocB1.g, 1);
                    if (ocVmid > float(ocY0) && ocVmid < float(ocY0 + ocFrameH)) {
                        int ocF0 = int(ocTexTime / ocTexFrameTime) % ocFrameCount;
                        int ocF1 = (ocF0 + 1) % ocFrameCount;
                        ocBase0.y -= float(ocF0 * ocFrameH);
                        ocBase1.y -= float(ocF1 * ocFrameH);
                        transition = ocTexFade ? fract(ocTexTime / ocTexFrameTime) : 0.0;
                        break;
                    }
                }
            }

            texCoord = ocBase0 / vec2(ocAtlasSize);
            texCoord2 = ocBase1 / vec2(ocAtlasSize);
            ocSurfaceMap.xy = vec2(ocSize) / vec2(ocAtlasSize);'''
    text = sub_once(text, texture_pattern, texture_repl, "texture metadata fast path")
    path.write_text(text, encoding="utf-8")


def patch_installer() -> None:
    path = TOOLS / "install.py"
    text = path.read_text(encoding="utf-8")
    if NEW_TAG in text:
        return
    if OLD_TAG not in text:
        raise RuntimeError("installer is neither v1.2 nor v1.3")
    text = text.replace(OLD_TAG, NEW_TAG)
    text = text.replace("surface carrier format v3", "surface carrier format v3.1")
    text = text.replace('"static_non_equipment": "surface-v3"', '"static_non_equipment": "surface-v3.1"')
    text = text.replace("surface-v3 PNGs", "surface-v3.1 PNGs")

    static_block_pattern = r'''def static_sample_block\(legacy: str\) -> str:\n.*?\n\n\ndef patch_fsh'''
    static_block_repl = '''def static_sample_block(legacy: str) -> str:
    return f\'''vec4 color;
    if (ocSurfaceMap.w > 0.5) {{
        vec2 ocLocalUv;
        if (!ocResolveStaticUv(ocSurfaceCoord, ocSurfaceP01, ocSurfaceP23,
                               ocSurfaceUV01, ocSurfaceUV23, ocSurfaceMap.z,
                               ocSurfaceMap.w, ocLocalUv)) discard;
        vec2 ocSample0 = texCoord  + ocLocalUv * ocSurfaceMap.xy;
        vec4 ocColor0 = texture(Sampler0, ocSample0);
        if (transition > 0.0) {{
            vec2 ocSample1 = texCoord2 + ocLocalUv * ocSurfaceMap.xy;
            color = mix(ocColor0, texture(Sampler0, ocSample1), transition);
        }} else {{
            color = ocColor0;
        }}
    }} else {{
        color = {legacy};
    }}\'''


def patch_fsh'''
    text = sub_once(text, static_block_pattern, static_block_repl, "single-sample static fragment")

    text = text.replace(
        'static_sample_block("mix(texture(Sampler0, texCoord), texture(Sampler0, texCoord2), transition)")',
        'static_sample_block("transition > 0.0 ? mix(texture(Sampler0, texCoord), texture(Sampler0, texCoord2), transition) : texture(Sampler0, texCoord)")'
    )

    old_terrain = '''        if (!ocResolveStaticUv(ocSurfaceCoord, ocSurfaceP01, ocSurfaceP23,
                               ocSurfaceUV01, ocSurfaceUV23, ocSurfaceMap.z, ocLocalUv)) discard;
        vec2 ocSample0 = texCoord  + ocLocalUv * ocSurfaceMap.xy;
        vec2 ocSample1 = texCoord2 + ocLocalUv * ocSurfaceMap.xy;
        color = mix(texture(Sampler0, ocSample0), texture(Sampler0, ocSample1), transition);'''
    new_terrain = '''        if (!ocResolveStaticUv(ocSurfaceCoord, ocSurfaceP01, ocSurfaceP23,
                               ocSurfaceUV01, ocSurfaceUV23, ocSurfaceMap.z,
                               ocSurfaceMap.w, ocLocalUv)) discard;
        vec2 ocSample0 = texCoord + ocLocalUv * ocSurfaceMap.xy;
        vec4 ocColor0 = texture(Sampler0, ocSample0);
        if (transition > 0.0) {
            vec2 ocSample1 = texCoord2 + ocLocalUv * ocSurfaceMap.xy;
            color = mix(ocColor0, texture(Sampler0, ocSample1), transition);
        } else {
            color = ocColor0;
        }'''
    text = replace_once(text, old_terrain, new_terrain, "terrain single sample")
    path.write_text(text, encoding="utf-8")


def patch_tag_file(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if NEW_TAG in text:
        return
    if OLD_TAG not in text:
        raise RuntimeError(f"{path} missing v1.2 tag")
    path.write_text(text.replace(OLD_TAG, NEW_TAG), encoding="utf-8")


def main() -> None:
    (SRC / "objmc_static_fragment.glsl").write_text(STATIC_FRAGMENT, encoding="utf-8")
    patch_vertex()
    patch_installer()
    patch_tag_file(SRC / "static_surface_plugin.js")
    patch_tag_file(TOOLS / "validate_actual.py")
    print("hybrid static-surface tooling upgraded to v1.3")


if __name__ == "__main__":
    main()
