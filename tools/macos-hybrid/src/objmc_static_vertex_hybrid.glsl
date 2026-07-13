// OC_HYBRID_SURFACE_PATCH_v1_4
// Static surface-v4 vertex path. Compact per-face metadata replaces the
// position / UV / vertex-index streams used by surface-v3.
bool ocStaticHandled = false;
isCustom = 0;
transition = 0.0;
noshadow = 0;
ocSurfaceCoord = vec2(0.0);
ocSurfaceP01 = vec4(0.0);
ocSurfaceP23 = vec4(0.0);
ocSurfaceUV01 = vec4(0.0);
ocSurfaceUV23 = vec4(0.0);
ocSurfaceMap = vec4(0.0);

#ifdef ENTITY
isGUI = int(isgui(ProjMat));
if (isGUI == 1 && abs(ProjMat[0][0]) > 0.010) isGUI = 0;
isHand = int(ishand(ProjMat));
overlayColor = vec4(1.0);
#endif

int ocCorner = gl_VertexID % 4;
ivec2 ocAtlasSize = textureSize(Sampler0, 0);
ivec2 ocPixel = ivec2(UV0 * vec2(ocAtlasSize));
ivec4 ocOffsetPixel = ivec4(texelFetch(Sampler0, ocPixel, 0) * 255.0 + 0.5);
ivec2 ocUvOffset = ivec2(
    ocOffsetPixel.r * 256 + ocOffsetPixel.g,
    ocOffsetPixel.b * 256 + ocOffsetPixel.a
);
ivec2 ocTopLeft = ocPixel - ocUvOffset;
ivec4 ocMarker = ivec4(texelFetch(Sampler0, ocTopLeft, 0) * 255.0 + 0.5);

if (ocMarker == ivec4(12, 34, 57, 255)) {
    ocStaticHandled = true;
    isCustom = 1;

    ivec4 ocT1 = getmeta(ocTopLeft, 1);
    ivec4 ocT3 = getmeta(ocTopLeft, 3);
    ivec4 ocT5 = getmeta(ocTopLeft, 5);
    ivec4 ocT6 = getmeta(ocTopLeft, 6);
    ivec4 ocT7 = getmeta(ocTopLeft, 7);
    noshadow = getb(ocT6.r, 7, 1);

    ivec2 ocSize = ivec2(
        ocT1.r * 256 + ocT1.g,
        ocT1.b * 256 + ocT7.r
    );
    int ocNTextures = max(ocT3.a, 1);
    int ocMetaHeight = ocT5.r * 256 + ocT5.g;
    bvec3 ocVisibility = bvec3(
        getb(ocT6.r, 4),
        getb(ocT6.r, 3),
        getb(ocT6.r, 2)
    );

    bool ocVisible = true;
#ifdef BLOCK
    ocVisible = ocVisibility.x;
#endif
#ifdef ENTITY
    ocVisible = (((isGUI + isHand) == 0) && ocVisibility.x)
             || (bool(isHand) && ocVisibility.y)
             || (bool(isGUI) && ocVisibility.z);

    int ocColorBehavior = getb(ocT6.r, 0, 1) * 256 + ocT6.g;
    vec3 ocDirectColor = vec3(1.0);
    bool ocHasDirectColor = false;
    vec2 ocHue = vec2(0.0, 255.0 / 256.0);
    int ocModeR = (ocColorBehavior >> 6) & 7;
    int ocModeG = (ocColorBehavior >> 3) & 7;
    int ocModeB = ocColorBehavior & 7;
    if (ocModeR == 0) { ocDirectColor.r = Color.r; ocHasDirectColor = true; }
    else if (ocModeR == 3) { ocHue.x = Color.r * 255.0; ocHue.y *= 256.0; }
    else if (ocModeR == 4 && Color.r != 0.0) overlayColor = vec4(1.0, 0.7, 0.7, 1.0);
    if (ocModeG == 0) { ocDirectColor.g = Color.g; ocHasDirectColor = true; }
    else if (ocModeG == 3) { ocHue.x = ocHue.x * 256.0 + Color.g * 255.0; ocHue.y *= 256.0; }
    else if (ocModeG == 4 && Color.g != 0.0) overlayColor = vec4(1.0, 0.7, 0.7, 1.0);
    if (ocModeB == 0) { ocDirectColor.b = Color.b; ocHasDirectColor = true; }
    else if (ocModeB == 3) { ocHue.x = ocHue.x * 256.0 + Color.b * 255.0; ocHue.y *= 256.0; }
    else if (ocModeB == 4 && Color.b != 0.0) overlayColor = vec4(1.0, 0.7, 0.7, 1.0);
    if (ocHue.x > 0.0) overlayColor = vec4(hrgb(ocHue.x / ocHue.y), 1.0);
    if (ocHasDirectColor) overlayColor = vec4(ocDirectColor, 1.0);
#endif

    if (!ocVisible) {
        Pos = vec3(9999.0);
    } else {
        int ocLocalLinear = (ocPixel.y - ocTopLeft.y) * ocSize.x
                          + (ocPixel.x - ocTopLeft.x);
        ivec4 ocM[9];
        for (int ocI = 0; ocI < 9; ocI++) {
            int ocL = ocLocalLinear + 1 + ocI;
            ivec2 ocMetaCoord = ocTopLeft + ivec2(ocL % ocSize.x, ocL / ocSize.x);
            ocM[ocI] = ivec4(texelFetch(Sampler0, ocMetaCoord, 0) * 255.0 + 0.5);
        }

        int ocPackedFlags = ocM[0].r;
        int ocVertexCount = clamp(ocM[0].g, 3, 4);
        vec2 ocQ0 = vec2(ocM[1].r * 256 + ocM[1].g, ocM[1].b * 256 + ocM[1].a) / 65535.0;
        vec2 ocQ1 = vec2(ocM[2].r * 256 + ocM[2].g, ocM[2].b * 256 + ocM[2].a) / 65535.0;
        vec2 ocQ2 = vec2(ocM[3].r * 256 + ocM[3].g, ocM[3].b * 256 + ocM[3].a) / 65535.0;
        vec2 ocQ3 = vec2(ocM[4].r * 256 + ocM[4].g, ocM[4].b * 256 + ocM[4].a) / 65535.0;
        vec2 ocUv0 = vec2(ocM[5].r * 256 + ocM[5].g, ocM[5].b * 256 + ocM[5].a) / 65535.0;
        vec2 ocUv1 = vec2(ocM[6].r * 256 + ocM[6].g, ocM[6].b * 256 + ocM[6].a) / 65535.0;
        vec2 ocUv2 = vec2(ocM[7].r * 256 + ocM[7].g, ocM[7].b * 256 + ocM[7].a) / 65535.0;
        vec2 ocUv3 = vec2(ocM[8].r * 256 + ocM[8].g, ocM[8].b * 256 + ocM[8].a) / 65535.0;

        ocSurfaceCoord = (ocCorner == 0) ? vec2(1.0, 1.0)
                       : (ocCorner == 1) ? vec2(1.0, 0.0)
                       : (ocCorner == 2) ? vec2(0.0, 0.0)
                                         : vec2(0.0, 1.0);
        ocSurfaceP01 = vec4(ocQ0, ocQ1);
        ocSurfaceP23 = vec4(ocQ2, ocQ3);
        ocSurfaceUV01 = vec4(ocUv0, ocUv1);
        ocSurfaceUV23 = vec4(ocUv2, ocUv3);
        ocSurfaceMap = vec4(
            vec2(ocSize) / vec2(ocAtlasSize),
            float(ocVertexCount),
            float(ocPackedFlags)
        );

        float ocTexTime = GameTime * 24000.0;
#ifdef ENTITY
        if (isGUI == 1) ocTexTime = 0.0;
#endif
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

        vec2 ocBase0 = vec2(ocTopLeft.x, ocTopLeft.y + 2 + ocMetaHeight);
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
    }
} else if (ocMarker == ivec4(12, 34, 56, 255)) {
    // Stale surface-v3 carriers are incompatible with the compact layout.
    // Consume them here on subgroup backends too, so they cannot fall through
    // into full-v2 and get transformed twice. Re-export once with this plugin.
    ivec4 ocOldStaticHeader = getmeta(ocTopLeft, 6);
    if (ocOldStaticHeader.b == 3) {
        ocStaticHandled = true;
        isCustom = 1;
        Pos = vec3(9999.0);
    }
}
