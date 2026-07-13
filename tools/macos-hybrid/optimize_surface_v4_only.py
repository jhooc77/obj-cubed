#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

OLD_TAG = "OC_HYBRID_SURFACE_PATCH_v1_4"
NEW_TAG = "OC_SURFACE_V4_ONLY_v1_5"
HERE = Path(__file__).resolve().parent
SRC = HERE / "src-v5"


def fail(msg: str) -> None:
    raise RuntimeError(msg)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        fail(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def sub_once(text: str, pattern: str, repl: str, label: str, flags: int = 0) -> str:
    out, count = re.subn(pattern, repl, text, count=1, flags=flags)
    if count != 1:
        fail(f"{label}: expected one match, found {count}")
    return out


def replace_between(text: str, start: str, end: str, replacement: str, label: str) -> str:
    i = text.find(start)
    if i < 0:
        fail(f"{label}: start marker missing")
    j = text.find(end, i)
    if j < 0:
        fail(f"{label}: end marker missing")
    return text[:i] + replacement.rstrip() + "\n\n" + text[j:]


def template(name: str) -> str:
    p = SRC / name
    if not p.exists():
        fail(f"missing template: {p}")
    return p.read_text(encoding="utf-8").rstrip()


STATIC_BUILD_VERTEX_DATA = r'''    function buildVertexData(objContents, atlasInfo) {
        if (!objContents || objContents.length !== 1)
            throw new Error('Surface-v4-only export requires exactly one static OBJ frame.');
        const count = [0, 0];
        const mem   = { pos: Object.create(null), uv: Object.create(null) };
        const data  = { positions: [], uvs: [], vertices: [] };
        let uvClamped = false;

        function remapUV(uv, material) {
            if (!atlasInfo) return uv;
            const texIdx = atlasInfo.materialToTexIdx.get(material);
            const off = texIdx !== undefined ? atlasInfo.offsets.get(texIdx) : null;
            if (!off) return uv;
            const u = Math.max(0, Math.min(1, uv[0]));
            const v = Math.max(0, Math.min(1, uv[1]));
            if (Math.abs(u - uv[0]) > 1e-6 || Math.abs(v - uv[1]) > 1e-6) uvClamped = true;
            const uvh = off.uvh || off.h;
            return [
                u * off.w / atlasInfo.width,
                (v * uvh + off.y + off.h - uvh) / atlasInfo.height
            ];
        }
        function indexVert(o, vert, material) {
            const pos = o.positions[vert[0]] || [0,0,0];
            const rawUv = o.uvs[vert[1]] || [0,0];
            const uv = remapUV(rawUv, material);
            const pk = pos.join(',');
            const uk = uv[0].toFixed(8)+','+uv[1].toFixed(8);
            let pi=mem.pos[pk];
            if (pi===undefined) { pi=count[0]++;mem.pos[pk]=pi;data.positions.push(pos); }
            let ui=mem.uv[uk];
            if (ui===undefined) { ui=count[1]++;mem.uv[uk]=ui;data.uvs.push(uv); }
            data.vertices.push([pi,ui]);
        }
        const firstObj = normalizeStaticObj(parseObj(objContents[0],0));
        for (let fi=0;fi<firstObj.faces.length;fi++) {
            const face=firstObj.faces[fi],mtl=firstObj.faceMaterials[fi];
            for (const vert of face) indexVert(firstObj,vert,mtl);
            if (face.length===3) indexVert(firstObj,face[2],mtl);
        }
        return {
            data,
            firstObj,
            nfaces:firstObj.faces.length,
            faceGroups:firstObj.faceGroups,
            faceBlocks:firstObj.faceBlocks,
            uvClamped,
            normalizationStats:firstObj.normalizationStats,
        };
    }'''


def patch_plugin(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if NEW_TAG in text:
        section6 = "    // =========================================================\n    // Section 6: Pixel Encoding"
        text = replace_between(text, "// " + NEW_TAG, section6, template("static_surface_plugin.js"), "refresh static exporter helper")
        path.write_text(text, encoding="utf-8")
        print("[ok] refreshed surface-v4-only exporter helper")
        return
    if OLD_TAG not in text:
        fail("objcubed.js is not the expected v1.4 source")

    helper_start = text.index("// " + OLD_TAG)
    section6 = "    // =========================================================\n    // Section 6: Pixel Encoding"
    helper_end = text.index(section6, helper_start)
    text = text[:helper_start] + template("static_surface_plugin.js") + "\n\n" + text[helper_end:]

    fn_start = text.index("    function buildVertexData(")
    fn_end = text.index("\n\n// " + NEW_TAG, fn_start)
    text = text[:fn_start] + STATIC_BUILD_VERTEX_DATA + text[fn_end:]

    text = replace_once(
        text,
        """        const nframes   = objContents.length;
        if (cfg.staticSurface && nframes !== 1)
            throw new Error('Static surface export requires one geometry frame.');
        if (cfg.staticSurface && cfg.exportAsEquipment)
            throw new Error('Equipment automatically uses the full carrier backend.');
        const staticFirstObj = cfg.staticSurface ? parseObj(objContents[0], 0) : null;
""",
        """        const nframes = objContents.length;
        if (nframes !== 1)
            throw new Error('This Surface-v4-only build supports static geometry only; disable Geometry Animation.');
        if (cfg.exportAsEquipment)
            throw new Error('Worn equipment/armor needs live limb pose data and is unavailable in the subgroup-free Surface-v4-only build.');
        if ((cfg.colorbehavior || []).includes('scale'))
            throw new Error('RGB geometry scale is unavailable; use item_display transformation.scale instead.');
        if ((cfg.colorbehavior || []).includes('time'))
            throw new Error('RGB geometry-time control requires geometry animation and is unavailable in this static-only build.');
        cfg.staticSurface = true;
""",
        "static-only build guards",
    )

    text = sub_once(
        text,
        r"        // Armor only: re-center each part's geometry.*?"
        r"        const \{ data, nfaces, faceGroups, faceBlocks, uvClamped \} = buildVertexData\(objContents, atlasInfo, partRef, faceToPart\);",
        """        const { data, firstObj, nfaces, faceGroups, faceBlocks, uvClamped, normalizationStats } = buildVertexData(objContents, atlasInfo);
        const faceToPart = null;""",
        "remove equipment re-centering",
        re.S,
    )

    text = replace_once(
        text,
        """        // Surface-v4 stores compact face metadata only. Full-v2 keeps
        // the original position / UV / vertex-index streams byte-for-byte.
        const uvH  = Math.ceil((cfg.staticSurface ? nfaces * OC_STATIC_META_STRIDE : nfaces) / tw);
        const texH = th;
        const vpH  = cfg.staticSurface ? 0 : Math.ceil(data.positions.length * 3 / tw);
        const vtH  = cfg.staticSurface ? 0 : Math.ceil(data.uvs.length * 2 / tw);
        const vH   = cfg.staticSurface ? 0 : Math.ceil(data.vertices.length * 2 / tw); // includes all frames
""",
        """        const texH = th;
        const vpH = 0, vtH = 0, vH = 0;
""",
        "remove legacy stream sizes",
    )

    text = sub_once(
        text,
        r"        // --- Encoder safety guards: fail loudly.*?"
        r"        if \(vpH > 65535 \|\| vtH > 65535\)\n"
        r"            throw new Error\(`Encoded data section too tall.*?\);\n",
        """        if (!Number.isFinite(cfg.scale) || cfg.scale <= 0) cfg.scale = 1;
        if (!Array.isArray(cfg.offset) || !cfg.offset.every(Number.isFinite))
            throw new Error(`Offset X/Y/Z must be finite numbers (got ${cfg.offset && cfg.offset.join(', ')}).`);
""",
        "remove full-v2 codec limits",
        re.S,
    )

    text = sub_once(
        text,
        r"        const headerRows = 2;\n"
        r"        let ty = headerRows \+ uvH \+ texH \+ vpH \+ vtH \+ vH;\n"
        r"        if \(!cfg\.nopow\) ty = 1 << Math\.ceil\(Math\.log2\(ty \|\| 1\)\);\n\n\n"
        r"        const cbArr = \['direct','time','scale','overlay','hurt'\];\n"
        r"        const ca = cfg\.colorbehavior\.map\(x => \{.*?"
        r"        const dur = cfg\.duration === 0 \? nframes : cfg\.duration;",
        """        const cbArr = ['direct','time','scale','overlay','hurt'];
        const ca = cfg.colorbehavior.map(x => {
            const idx = cbArr.indexOf(x);
            if (idx < 0) throw new Error('Unknown colorbehavior: ' + x);
            return idx;
        });
        const cb = (ca[0]<<6)|(ca[1]<<3)|ca[2];
        const dur = 1;
        const staticTexAnimActive = ntextures > 1 || atlasBands.length > 0;
        const allowNative = !staticTexAnimActive && cb === 0 && !cfg.noshadow;
        const surfacePlan = buildStaticSurfacePlan(firstObj, data, cfg, allowNative);
        if (surfacePlan.primitives.length !== nfaces)
            throw new Error(`Surface planning lost faces (${surfacePlan.primitives.length}/${nfaces}).`);
        const uvH = Math.ceil(surfacePlan.customCount * OC_STATIC_META_STRIDE / tw);
        const headerRows = 2;
        let ty = headerRows + uvH + texH;
        if (!cfg.nopow) ty = 1 << Math.ceil(Math.log2(ty || 1));""",
        "surface plan/layout",
        re.S,
    )

    text = replace_once(text, "put(0, 0, 12, 34, cfg.staticSurface ? 57 : 56, 255);", "put(0, 0, 12, 34, 57, 255);", "static marker")
    text = replace_once(
        text,
        """        put(5, 0, Math.trunc((cfg.staticSurface ? uvH : vpH)/256)%256,
                  (cfg.staticSurface ? uvH : vpH)%256, Math.trunc(vtH/256)%256, 255);""",
        """        put(5, 0, Math.trunc(uvH/256)%256, uvH%256, 0, 255);""",
        "metadata height header",
    )
    text = replace_once(text, "cb%256, cfg.staticSurface ? 4 : 2, 255);", "cb%256, 5, 255);", "header version 5")
    text = replace_once(text, "put(7, 0, frameH%256, nvertices%256, cfg.staticSurface ? 0 : vtH%256, 255);", "put(7, 0, frameH%256, nvertices%256, 0, 255);", "no uv stream")
    text = replace_once(
        text,
        """        const { dynamics } = cfg.staticSurface
            ? { dynamics: [] }
            : assignSlotMarkers(buildDisplayTransforms(cfg));""",
        "        const dynamics = [];",
        "remove legacy slot markers",
    )

    text = sub_once(
        text,
        r"        // UV header \+ JSON elements\n"
        r"        const elements = \[\];\n"
        r"        let staticSurfaceMeta = null;\n"
        r"        if \(cfg\.staticSurface\) \{.*?"
        r"        \}\n\n"
        r"        // Texture rows",
        """        // Surface-v4-only elements. Exact rectangular faces with simple
        // static UVs bypass the custom shader; the remainder use compact metadata.
        const staticSurfaceMeta = writeStaticSurfaceElements(
            surfacePlan, cfg, tw, ty, headerRows, uvH, texH, put, faceEmission
        );
        const elements = staticSurfaceMeta.elements;

        // Texture rows""",
        "surface-only elements",
        re.S,
    )

    # Delete full-v2 position/UV/index stream writer, preserving the UV warning.
    text = sub_once(
        text,
        r"        if \(cfg\.staticSurface && \(uvClamped.*?"
        r"        // Round-trip verification",
        """        if (uvClamped || data.uvs.some(uv => uv.some(v => v < -1e-6 || v > 1 + 1e-6)))
            surfaceWarning('some UVs fall outside the 0..1 frame (tiling/negative) and were clamped — those faces may look wrong. Keep the model UV-mapped inside the texture frame.');

        // Round-trip verification""",
        "remove legacy streams",
        re.S,
    )

    text = replace_once(
        text,
        "if (mk[0]!==12||mk[1]!==34||mk[2]!==(cfg.staticSurface?57:56)||mk[3]!==255) {",
        "if (mk[0]!==12||mk[1]!==34||mk[2]!==57||mk[3]!==255) {",
        "verify marker",
    )

    # Keep only the static verifier branch.
    text = sub_once(
        text,
        r"            if \(cfg\.staticSurface\) \{(.*?)"
        r"            \} else \{.*?"
        r"            \}\n"
        r"        \} catch\(e\)",
        lambda m: m.group(1) + "        } catch(e)",
        "static verifier only",
        re.S,
    )
    text = replace_once(
        text,
        """                const m0 = rd(0, headerRows);
                const mx = m0[0] * 256 + m0[1];
                const my = m0[2] * 256 + m0[3];
                if (mx !== 0 || my !== headerRows) {
                    verifyWarns.push('static metadata pointer mismatch');
                    console.error(`[obj3-verify] static pointer: enc=[${mx},${my}] expected=[0,${headerRows}]`);
                }""",
        """                if (surfacePlan.customCount > 0) {
                    const m0 = rd(0, headerRows);
                    const mx = m0[0] * 256 + m0[1];
                    const my = m0[2] * 256 + m0[3];
                    if (mx !== 0 || my !== headerRows) {
                        verifyWarns.push('static metadata pointer mismatch');
                        console.error(`[obj3-verify] static pointer: enc=[${mx},${my}] expected=[0,${headerRows}]`);
                    }
                }""",
        "optional pointer verify",
    )

    text = replace_once(
        text,
        "(cfg.staticSurface ? ' · surface-v4' : ' · full-v2')",
        "` · surface-v4-only · native ${surfacePlan.nativeCount} · shader ${surfacePlan.customCount} · split +${normalizationStats.splitExtra}`",
        "debug backend label",
    )
    text = text.replace("staticSurface: !!cfg.staticSurface,", "staticSurface: true,", 1)

    text = sub_once(
        text,
        r"        let result;\n"
        r"        try \{\n"
        r"            result = await buildOutput\(cfg, objs, mtl\);\n"
        r"        \} catch \(e\) \{.*?"
        r"        \}\n"
        r"        onStatus",
        "        const result = await buildOutput(cfg, objs, mtl);\n        onStatus",
        "remove export fallback",
        re.S,
    )

    text = replace_once(
        text,
        """                                // Backend is automatic; the UI and export flow stay unchanged.
                                staticSurface: !(this.hasAnims && this.animationEnabled) && !this.exportAsEquipment
                                    && !cbParts.includes('scale'),""",
        """                                // This fork intentionally has one backend only.
                                staticSurface: true,""",
        "force v4-only",
    )
    cb_anchor = """                        const cbParts = wantDatapack
                            ? ['time', 'time', 'time']
                            : [this.cbR, this.cbG, this.cbB];"""
    text = replace_once(
        text,
        cb_anchor,
        cb_anchor,
        "UI preflight",
    )
    text = replace_once(
        text,
        """                        try {
                            const cfg = {""",
        """                        try {
                            if (this.hasAnims && this.animationEnabled)
                                throw new Error('Geometry Animation is disabled in the subgroup-free Surface-v4-only build.');
                            if (this.exportAsEquipment)
                                throw new Error('Equipment/armor export is disabled in the subgroup-free Surface-v4-only build.');
                            if (cbParts.includes('scale'))
                                throw new Error('RGB geometry scale is disabled; use item_display transformation.scale.');
                            if (cbParts.includes('time'))
                                throw new Error('RGB geometry-time control is disabled because this build has no geometry animation.');
                            const cfg = {""",
        "UI hard-error placement",
    )

    # Expose normalization helpers to the test harness.
    text = replace_once(
        text,
        "            buildVertexData, buildDisplayTransforms, hasStaticWorldDisplay,",
        "            buildVertexData, normalizeStaticObj, buildStaticSurfacePlan, buildDisplayTransforms, hasStaticWorldDisplay,",
        "test exports",
    )

    path.write_text(text, encoding="utf-8")
    print("[ok] patched static-only exporter")


def patch_vsh(path: Path) -> None:
    s = path.read_text(encoding="utf-8")
    if NEW_TAG in s:
        return
    # Remove conditional subgroup block.
    s, count = re.subn(
        r"^#version 410\n// Ask for subgroup quad operations only when the driver advertises them\..*?^#endif\n",
        "#version 410\n",
        s,
        count=1,
        flags=re.M | re.S,
    )
    if count != 1 and NEW_TAG not in s:
        fail(f"{path.name}: subgroup header not found")
    s = re.sub(r"(?m)^out float transition;$", "flat out float transition;", s)
    if "flat out vec4 ocSurfaceOverlay;" not in s:
        s = s.replace("flat out vec4 ocSurfaceMap;", "flat out vec4 ocSurfaceMap;\nflat out vec4 ocSurfaceOverlay;")
    if "ocSurfaceOverlay = vec4(1.0);" not in s:
        s = s.replace("    ocSurfaceMap = vec4(0.0);", "    ocSurfaceMap = vec4(0.0);\n    ocSurfaceOverlay = vec4(1.0);")
    s = s.replace("OC_HYBRID_SURFACE_PATCH_v1_3", NEW_TAG).replace(OLD_TAG, NEW_TAG)
    path.write_text(s, encoding="utf-8")


def static_fragment_body(name: str) -> str:
    if name == "terrain.fsh":
        fallback = "transition > 0.0 ? mix(sampleColor(texCoord), sampleColor(texCoord2), transition) : sampleColor(texCoord)"
    else:
        fallback = "transition > 0.0 ? mix(texture(Sampler0, texCoord), texture(Sampler0, texCoord2), transition) : texture(Sampler0, texCoord)"
    return f'''    vec4 color;
    if (isCustom == 1) {{
        vec2 ocUv;
        float ocNextV;
        if (!ocResolveStaticUvFast(ocSurfaceCoord, ocSurfaceP01, ocSurfaceP23,
                                   ocSurfaceUV01, ocSurfaceUV23, ocSurfaceMap,
                                   ocUv, ocNextV)) discard;
        vec4 ocColor0 = texture(Sampler0, ocUv);
        color = transition > 0.0
            ? mix(ocColor0, texture(Sampler0, ocUv + vec2(0.0, ocNextV)), transition)
            : ocColor0;
    }} else if (isCustom == 3) {{
        discard;
    }} else {{
        color = {fallback};
    }}

'''


def patch_fsh(path: Path) -> None:
    s = path.read_text(encoding="utf-8")
    if NEW_TAG in s:
        return
    s = re.sub(r"(?m)^in float transition;$", "flat in float transition;", s)
    if "flat in vec4 ocSurfaceOverlay;" not in s:
        s = s.replace("flat in vec4 ocSurfaceMap;", "flat in vec4 ocSurfaceMap;\nflat in vec4 ocSurfaceOverlay;")
    s = s.replace(OLD_TAG, NEW_TAG)
    start = s.find("    vec4 color;")
    end = s.find("    //custom lighting", start)
    if start < 0 or end < 0:
        fail(f"{path.name}: sample block not found")
    s = s[:start] + static_fragment_body(path.name) + s[end:]
    path.write_text(s, encoding="utf-8")


def patch_shaders(repo: Path) -> None:
    shader = repo / "objcubed/assets/minecraft/shaders"
    (shader / "include/objmc_main.glsl").write_text(template("objmc_main_static_only.glsl") + "\n", encoding="utf-8")
    (shader / "include/objmc_static_fragment.glsl").write_text(template("objmc_static_fragment.glsl") + "\n", encoding="utf-8")
    for name in ("item.vsh", "entity.vsh", "block.vsh", "terrain.vsh"):
        patch_vsh(shader / "core" / name)
    for name in ("item.fsh", "entity.fsh", "block.fsh", "terrain.fsh"):
        patch_fsh(shader / "core" / name)

    light = shader / "include/objmc_light.glsl"
    s = light.read_text(encoding="utf-8")
    if "ocLightingOverlay" not in s:
        s = s.replace(
            "    //normal from position derivatives\n",
            "#ifdef ENTITY\n    vec4 ocLightingOverlay = (isCustom == 1) ? ocSurfaceOverlay : overlayColor;\n#endif\n    //normal from position derivatives\n",
            1,
        )
        s = s.replace(
            "minecraft_mix_light(Light0_Direction, Light1_Direction, normal, overlayColor)",
            "minecraft_mix_light(Light0_Direction, Light1_Direction, normal, ocLightingOverlay)",
        )
        s = s.replace(
            "    color *= overlayColor;\n#endif\n#endif\n\n    color *= lightColor;",
            "    color *= ocLightingOverlay;\n#endif\n#endif\n\n    color *= lightColor;",
            1,
        )
    light.write_text(s, encoding="utf-8")
    print("[ok] patched subgroup-free shaders")


def patch_manifest(repo: Path) -> None:
    p = repo / "HYBRID_SURFACE_PATCH.json"
    obj = {
        "patch": NEW_TAG,
        "upstream": "JagerMeistars/obj-cubed",
        "upstream_ref_tested": "6a85a1f30f5dd0843c656838c5ebca13f0e029ed",
        "backend": "surface-v4-only-static",
        "shader_version": 410,
        "subgroup": False,
        "fallback": False,
        "native_rectangle_fast_path": True,
        "provoking_vertex_metadata_fetch": True,
        "non_planar_quad_policy": "automatic triangulation",
        "unsupported": ["geometry animation", "worn equipment/armor", "RGB geometry scale", "RGB geometry-time control"],
    }
    p.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def patch_readme(repo: Path) -> None:
    p = repo / "README.md"
    s = p.read_text(encoding="utf-8")
    note = """
## Surface-v4-only performance branch

This branch intentionally ships one subgroup-free static backend. Static OBJ
items, item displays, blocks, display transforms (including independent Z scale
and both rotations), textures/atlases, texture animation, tinting, and emissive
faces remain available. Non-planar/concave/non-affine quads and N-gons are
triangulated automatically during export.

Geometry animation, worn equipment/armor, RGB geometry scale, and RGB geometry-
time control are rejected with a clear export error; there is no legacy/full-v2
fallback. The runtime shaders are GLSL 4.10 and contain no subgroup extension or
`subgroupQuadBroadcast` call.

The renderer uses three static fast paths: exact rectangular faces can bypass
the custom decoder entirely, other rectangles skip fragment clipping, and
remaining triangles/convex quads use precomputed affine UV and edge equations.
Only the two possible provoking vertices fetch per-face metadata.
""".strip()
    section = re.compile(r"## Surface-v4-only performance branch.*?(?=\n## Features)", re.S)
    if section.search(s):
        s = section.sub(note + "\n", s, count=1)
    else:
        idx = s.find("## Features")
        s = s[:idx] + note + "\n\n" + s[idx:] if idx >= 0 else note + "\n\n" + s
    for bullet in (
        "- **Armor / equipment export** — render a model as worn armor; one piece can span several body parts (a chestplate = torso + both arms), each following its own bone on the player/armor stand\n",
        "- **Keyframe animation baking** — BB animations are baked frame-by-frame into the encoded texture\n",
        "- **Armature & bone skinning** — weighted vertex skinning from BB Generic Model rigs\n",
        "- **Datapack generation** — animation control functions (play, stop, play_once, etc.) with GameTime sync\n",
    ):
        s = s.replace(bullet, "")
    s = s.replace("with per-frame tick rate and optional cross-fade; works standalone or inside an atlas", "with per-frame tick rate and optional cross-fade; works standalone or inside an atlas")
    s = s.replace("- Armor export additionally needs the entity equipment pipeline (included in the pack)\n", "")
    p.write_text(s, encoding="utf-8")


def cleanup_obsolete_tools(repo: Path) -> None:
    base = repo / "tools/macos-hybrid"
    for name in ("src", "src-v4"):
        path = base / name
        if path.exists():
            shutil.rmtree(path)
    for name in ("optimize_v13.py", "optimize_surface_v4.py", "static_v5_helper.js"):
        path = base / name
        if path.exists():
            path.unlink()
    tests = base / "tests"
    if tests.exists():
        for name in ("test_surface_helper.mjs", "test_surface_v4_build.mjs"):
            path = tests / name
            if path.exists():
                path.unlink()
    print("[ok] removed obsolete hybrid/full-v2 tooling")


def validate(repo: Path) -> None:
    plugin = (repo / "objcubed.js").read_text(encoding="utf-8")
    shaders = repo / "objcubed/assets/minecraft/shaders"
    main = (shaders / "include/objmc_main.glsl").read_text(encoding="utf-8")
    frag = (shaders / "include/objmc_static_fragment.glsl").read_text(encoding="utf-8")
    all_shader = "\n".join(p.read_text(encoding="utf-8") for p in shaders.rglob("*.glsl")) + "\n" + "\n".join(p.read_text(encoding="utf-8") for p in (shaders / "core").glob("*.*sh"))
    checks = {
        "new tag": NEW_TAG in plugin and NEW_TAG in main,
        "no subgroup": "subgroupQuadBroadcast" not in all_shader and "GL_KHR_shader_subgroup_quad" not in all_shader,
        "one backend": "cfg.staticSurface = true" in plugin and "const result = await buildOutput(cfg, objs, mtl);" in plugin,
        "triangulation": "normalizeStaticObj" in plugin and "ocTriangulateFace" in plugin,
        "provoking fetch": "ocCorner == 0 || ocCorner == 2" in main,
        "fast fragment": "ocResolveStaticUvFast" in frag and "fwidth(" not in frag,
        "native rectangles": "nativeCount" in plugin and "bypass the custom shader" in plugin,
        "hard equipment error": "Equipment/armor export is disabled" in plugin,
    }
    bad = [k for k, v in checks.items() if not v]
    if bad:
        fail("validation failed: " + ", ".join(bad))
    print("[ok] structural validation")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", nargs="?", type=Path, default=Path.cwd())
    repo = ap.parse_args().repo.resolve()
    patch_plugin(repo / "objcubed.js")
    patch_shaders(repo)
    patch_manifest(repo)
    patch_readme(repo)
    cleanup_obsolete_tools(repo)
    validate(repo)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}")
        raise
