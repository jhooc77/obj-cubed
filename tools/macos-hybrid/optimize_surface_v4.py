#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

TAG2 = 'OC_HYBRID_SURFACE_PATCH_v1_2'
TAG3 = 'OC_HYBRID_SURFACE_PATCH_v1_3'
TAG4 = 'OC_HYBRID_SURFACE_PATCH_v1_4'
HERE = Path(__file__).resolve().parent


def fail(msg: str) -> None:
    raise RuntimeError(msg)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        fail(f'{label}: expected 1 match, found {count}')
    return text.replace(old, new, 1)


def replace_between(text: str, start: str, end: str, replacement: str, label: str) -> str:
    i = text.find(start)
    if i < 0:
        fail(f'{label}: start marker missing')
    j = text.find(end, i)
    if j < 0:
        fail(f'{label}: end marker missing')
    return text[:i] + replacement.rstrip() + '\n\n' + text[j:]


def template(name: str) -> str:
    path = HERE / 'src-v4' / name
    if not path.exists():
        fail(f'missing template: {path}')
    return path.read_text(encoding='utf-8')


def old_tag(text: str) -> str | None:
    if TAG3 in text:
        return TAG3
    if TAG2 in text:
        return TAG2
    return None


def patch_plugin(path: Path) -> None:
    text = path.read_text(encoding='utf-8')
    if TAG4 in text:
        print('[skip] objcubed.js already uses surface-v4')
        return
    previous = old_tag(text)
    if previous is None:
        fail('objcubed.js is not an expected surface-v1.2/v1.3 source')

    section6 = '    // =========================================================\n    // Section 6: Pixel Encoding'
    text = replace_between(
        text,
        '// ' + previous,
        section6,
        template('static_surface_plugin.js'),
        'replace static exporter helper',
    )

    text = replace_once(
        text,
        '''        const uvH  = Math.ceil(nfaces / tw);
        const texH = th;
        const vpH  = Math.ceil(data.positions.length * 3 / tw);
        const vtH  = Math.ceil(data.uvs.length * 2 / tw);
        const vH   = Math.ceil(data.vertices.length * 2 / tw); // includes all frames''',
        '''        // Surface-v4 stores compact face metadata only. Full-v2 keeps
        // the original position / UV / vertex-index streams byte-for-byte.
        const uvH  = Math.ceil((cfg.staticSurface ? nfaces * OC_STATIC_META_STRIDE : nfaces) / tw);
        const texH = th;
        const vpH  = cfg.staticSurface ? 0 : Math.ceil(data.positions.length * 3 / tw);
        const vtH  = cfg.staticSurface ? 0 : Math.ceil(data.uvs.length * 2 / tw);
        const vH   = cfg.staticSurface ? 0 : Math.ceil(data.vertices.length * 2 / tw); // includes all frames''',
        'compact static layout',
    )
    text = replace_once(
        text,
        '        put(0, 0, 12, 34, 56, 255);',
        '        put(0, 0, 12, 34, cfg.staticSurface ? 57 : 56, 255);',
        'surface-v4 marker',
    )
    text = replace_once(
        text,
        '        put(5, 0, Math.trunc(vpH/256)%256, vpH%256, Math.trunc(vtH/256)%256, 255);',
        '''        put(5, 0, Math.trunc((cfg.staticSurface ? uvH : vpH)/256)%256,
                  (cfg.staticSurface ? uvH : vpH)%256, Math.trunc(vtH/256)%256, 255);''',
        'compact metadata height',
    )
    text = replace_once(
        text,
        '            cb%256, cfg.staticSurface ? 3 : 2, 255);',
        '            cb%256, cfg.staticSurface ? 4 : 2, 255);',
        'surface-v4 header version',
    )
    text = replace_once(
        text,
        '        put(7, 0, frameH%256, nvertices%256, vtH%256, 255);',
        '        put(7, 0, frameH%256, nvertices%256, cfg.staticSurface ? 0 : vtH%256, 255);',
        'surface-v4 vt height',
    )
    text = replace_once(
        text,
        '        const { dynamics } = assignSlotMarkers(buildDisplayTransforms(cfg));',
        '''        const { dynamics } = cfg.staticSurface
            ? { dynamics: [] }
            : assignSlotMarkers(buildDisplayTransforms(cfg));''',
        'skip static slot marker table',
    )
    text = replace_once(
        text,
        '                staticFirstObj, cfg, tw, ty, headerRows, put, faceEmission',
        '                staticFirstObj, data, cfg, tw, ty, headerRows, put, faceEmission',
        'pass indexed data to compact exporter',
    )

    text = replace_once(
        text,
        '        // Position data\n        let ybase = headerRows+uvH+texH;',
        '''        if (cfg.staticSurface && (uvClamped || data.uvs.some(uv => uv.some(v => v < -1e-6 || v > 1 + 1e-6))))
            surfaceWarning('some UVs fall outside the 0..1 frame (tiling/negative) and were clamped — those faces may look wrong. Keep the model UV-mapped inside the texture frame.');

        // Position data
        let ybase = headerRows+uvH+texH;''',
        'static UV warning',
    )
    bake = '        const bakeOffset = [cfg.offset[0], cfg.offset[1] - 0.5, cfg.offset[2]];\n'
    text = replace_once(text, bake, bake + '        if (!cfg.staticSurface) {\n', 'open full-v2 stream guard')
    stream_end = '''        for (let i = 0; i < data.vertices.length; i++) {
            const pixels = vertPixels(data.vertices[i]);
            for (const [j, pxArr] of pixels.entries()) {
                const p = i*2+j;
                put(p%tw, ybase+Math.floor(p/tw), ...pxArr);
            }
        }

        // Round-trip verification'''
    text = replace_once(
        text,
        stream_end,
        stream_end.replace('\n\n        // Round-trip verification', '\n        }\n\n        // Round-trip verification'),
        'close full-v2 stream guard',
    )

    text = replace_once(
        text,
        "            if (mk[0]!==12||mk[1]!==34||mk[2]!==56||mk[3]!==255) {",
        "            if (mk[0]!==12||mk[1]!==34||mk[2]!==(cfg.staticSurface?57:56)||mk[3]!==255) {",
        'verify marker',
    )
    verify_start = '            // Verify first position (shader decodes as v*scale+offset)\n'
    text = replace_once(
        text,
        verify_start,
        '''            if (cfg.staticSurface) {
                const m0 = rd(0, headerRows);
                const mx = m0[0] * 256 + m0[1];
                const my = m0[2] * 256 + m0[3];
                if (mx !== 0 || my !== headerRows) {
                    verifyWarns.push('static metadata pointer mismatch');
                    console.error(`[obj3-verify] static pointer: enc=[${mx},${my}] expected=[0,${headerRows}]`);
                }
            } else {
''' + verify_start,
        'split static/full verifier',
    )
    verify_end = '''            // Verify last frame's first vertex
            if (nframes > 1) {
                const lastIdx = (nframes-1) * nvertices;
                const lp = lastIdx * 2;
                const la = rd(lp%tw, vtxBase+Math.floor(lp/tw));
                const decLPi = la[0]*65536+la[1]*256+la[2];
                const srcLast = data.vertices[lastIdx];
                if (srcLast) {
                    if (decLPi !== srcLast[0]) { verifyWarns.push('last frame mismatch'); console.error(`[obj3-verify] vert[${lastIdx}].pos: enc=${decLPi} exp=${srcLast[0]}`); }
                }
            }
        } catch(e)'''
    text = replace_once(
        text,
        verify_end,
        verify_end.replace('\n        } catch(e)', '\n            }\n        } catch(e)'),
        'close verifier split',
    )
    text = text.replace("' · surface-v3'", "' · surface-v4'")
    path.write_text(text, encoding='utf-8')
    print('[ok] compact surface-v4 exporter installed')


def patch_main(path: Path) -> None:
    text = path.read_text(encoding='utf-8')
    if TAG4 in text:
        print('[skip] objmc_main.glsl already uses surface-v4')
        return
    if old_tag(text) is None:
        fail('objmc_main.glsl is not an expected surface-v1.2/v1.3 source')

    split = text.find('#if OC_HAS_SUBGROUP')
    if split < 0:
        fail('missing OC_HAS_SUBGROUP split')
    text = template('objmc_static_vertex_hybrid.glsl').rstrip() + '\n\n' + text[split:]

    legacy_probe = '''int corner = gl_VertexID % 4;
ivec2 atlasSize = textureSize(Sampler0, 0);
vec2 onepixel = 1./atlasSize;
ivec2 uv = ivec2((UV0 * atlasSize));
vec3 posoffset = vec3(0);
float scale = 1;
vec3 rotation = vec3(0);
int headerheight = 0;
ivec4 t[16];
//read uv offset
t[0] = ivec4(texelFetch(Sampler0, uv, 0) * 255.0 + 0.5);
ivec2 uvoffset = ivec2(t[0].r*256 + t[0].g, t[0].b*256 + t[0].a);
//find and read topleft pixel
ivec2 topleft = uv - uvoffset;
//if topleft marker is correct
ivec4 marker = ivec4(texelFetch(Sampler0, topleft, 0)*255.0+0.5);'''
    text = replace_once(
        text,
        legacy_probe,
        '''int corner = ocCorner;
ivec2 atlasSize = ocAtlasSize;
vec2 onepixel = 1.0 / vec2(atlasSize);
ivec2 uv = ocPixel;
vec3 posoffset = vec3(0);
float scale = 1;
vec3 rotation = vec3(0);
int headerheight = 0;
ivec4 t[16];
t[0] = ocOffsetPixel;
ivec2 uvoffset = ocUvOffset;
ivec2 topleft = ocTopLeft;
ivec4 marker = ocMarker;''',
        'reuse initial legacy probe',
    )

    fallback_probe = re.compile(
        r'    ivec2 ocFallbackAtlasSize = textureSize\(Sampler0, 0\);.*?'
        r'    ivec4 ocFallbackMarker = ivec4\(texelFetch\(Sampler0, ocFallbackTopLeft, 0\) \* 255\.0 \+ 0\.5\);',
        re.S,
    )
    text, count = fallback_probe.subn(
        '    ivec2 ocFallbackTopLeft = ocTopLeft;\n    ivec4 ocFallbackMarker = ocMarker;',
        text,
        count=1,
    )
    if count != 1:
        fail(f'reuse no-subgroup probe: expected 1 match, found {count}')

    text = re.sub(
        r'''    if \(ocFallbackMarker == ivec4\(12, 34, 56, 255\)\) \{\n        ivec4 ocFallbackHeader6 = getmeta\(ocFallbackTopLeft, 6\);\n        if \(ocFallbackHeader6\.b != 3\) \{\n            isCustom = 1;\n            Pos = vec3\(9999\.0\);\n        \}\n    \}''',
        '''    if (ocFallbackMarker == ivec4(12, 34, 56, 255)) {
        isCustom = 1;
        Pos = vec3(9999.0);
    }''',
        text,
        count=1,
    )
    path.write_text(text, encoding='utf-8')
    print('[ok] compact surface-v4 shader path installed')


def patch_fragment_text(text: str, name: str) -> str:
    text = text.replace(TAG3, TAG4).replace(TAG2, TAG4)

    seven_arg = 'ocSurfaceUV01, ocSurfaceUV23, ocSurfaceMap.z, ocLocalUv'
    if seven_arg in text:
        text = text.replace(
            seven_arg,
            'ocSurfaceUV01, ocSurfaceUV23, ocSurfaceMap.z,\n                               ocSurfaceMap.w, ocLocalUv',
            1,
        )

    static_mix = '        color = mix(texture(Sampler0, ocSample0), texture(Sampler0, ocSample1), transition);'
    if static_mix in text:
        text = text.replace(
            static_mix,
            '''        vec4 ocColor0 = texture(Sampler0, ocSample0);
        if (transition > 0.0) {
            vec2 ocSample1 = texCoord2 + ocLocalUv * ocSurfaceMap.xy;
            color = mix(ocColor0, texture(Sampler0, ocSample1), transition);
        } else {
            color = ocColor0;
        }''',
            1,
        )
        text = text.replace('        vec2 ocSample1 = texCoord2 + ocLocalUv * ocSurfaceMap.xy;\n', '', 1)

    if name == 'item.fsh':
        old = '        color = mix(texture(Sampler0, texCoord), texture(Sampler0, texCoord2), transition);'
        if old in text:
            text = text.replace(old, '        color = transition > 0.0 ? mix(texture(Sampler0, texCoord), texture(Sampler0, texCoord2), transition) : texture(Sampler0, texCoord);', 1)
    elif name == 'terrain.fsh':
        text = text.replace(
            '        color = mix(sampleColor(texCoord), sampleColor(texCoord2), transition);',
            '        color = transition > 0.0 ? mix(sampleColor(texCoord), sampleColor(texCoord2), transition) : sampleColor(texCoord);',
            1,
        )
    return text


def patch_fragments(core: Path, include: Path) -> None:
    shutil.copy2(HERE / 'src-v4' / 'objmc_static_fragment.glsl', include / 'objmc_static_fragment.glsl')
    for name in ('item.fsh', 'entity.fsh', 'block.fsh', 'terrain.fsh'):
        path = core / name
        text = path.read_text(encoding='utf-8')
        if TAG4 not in text:
            text = patch_fragment_text(text, name)
            path.write_text(text, encoding='utf-8')
    print('[ok] fragment helpers/single-sample paths installed')


def patch_tools(repo: Path) -> None:
    src = repo / 'tools' / 'macos-hybrid' / 'src'
    src.mkdir(parents=True, exist_ok=True)
    for name in ('static_surface_plugin.js', 'objmc_static_vertex_hybrid.glsl', 'objmc_static_fragment.glsl'):
        shutil.copy2(HERE / 'src-v4' / name, src / name)

    manifest_path = repo / 'HYBRID_SURFACE_PATCH.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
    manifest.update({
        'patch': TAG4,
        'static_backend': 'surface-v4-compact-metadata',
        'static_face_metadata_texels': 10,
        'static_legacy_streams': False,
    })
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')


def validate(repo: Path) -> None:
    plugin = (repo / 'objcubed.js').read_text(encoding='utf-8')
    main = (repo / 'objcubed/assets/minecraft/shaders/include/objmc_main.glsl').read_text(encoding='utf-8')
    prefix, legacy = main.split('#if OC_HAS_SUBGROUP', 1)
    item_fsh = (repo / 'objcubed/assets/minecraft/shaders/core/item.fsh').read_text(encoding='utf-8')
    checks = {
        'surface-v4 tag': TAG4 in plugin and TAG4 in main,
        'compact stride': 'OC_STATIC_META_STRIDE = 10' in plugin,
        'static streams removed': 'cfg.staticSurface ? 0 : Math.ceil(data.positions.length * 3 / tw)' in plugin,
        'marker 57': 'ivec4(12, 34, 57, 255)' in prefix,
        'no getvert in static path': 'getvert(' not in prefix,
        'no getpos in static path': 'getpos(' not in prefix,
        'no getuv in static path': 'getuv(' not in prefix,
        'edge flags preserved': 'ocPackedFlags' in prefix,
        'legacy subgroup preserved': 'subgroupQuadBroadcast' in legacy,
        'single texture sample fast path': 'vec4 ocColor0 = texture(Sampler0, ocSample0);' in item_fsh,
    }
    missing = [name for name, ok in checks.items() if not ok]
    if missing:
        fail('surface-v4 validation failed: ' + ', '.join(missing))
    print('[ok] surface-v4 structural validation')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('repo', nargs='?', type=Path, default=Path.cwd())
    repo = parser.parse_args().repo.resolve()
    patch_plugin(repo / 'objcubed.js')
    patch_main(repo / 'objcubed/assets/minecraft/shaders/include/objmc_main.glsl')
    patch_fragments(
        repo / 'objcubed/assets/minecraft/shaders/core',
        repo / 'objcubed/assets/minecraft/shaders/include',
    )
    patch_tools(repo)
    validate(repo)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        raise
