// OC_HYBRID_SURFACE_PATCH_v1_3
// obj³ static-surface backend.
// This file is inserted at the beginning of objmc_main.glsl by the patcher.
// It is included INSIDE main(), so it intentionally contains statements only.
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

if (ocMarker == ivec4(12, 34, 56, 255)) {
    ivec4 ocT1 = getmeta(ocTopLeft, 1);
    ivec4 ocT2 = getmeta(ocTopLeft, 2);
    ivec4 ocT3 = getmeta(ocTopLeft, 3);
    ivec4 ocT5 = getmeta(ocTopLeft, 5);
    ivec4 ocT6 = getmeta(ocTopLeft, 6);
    ivec4 ocT7 = getmeta(ocTopLeft, 7);

    // Header version 3 marks an OBJ whose JSON carriers already lie on the
    // real, static face planes. A legacy PNG must stay on the legacy shader.
    if (ocT6.b == 3) {
        ocStaticHandled = true;
        isCustom = 1;
        noshadow = getb(ocT6.r, 7, 1);

        ivec2 ocSize = ivec2(
            ocT1.r * 256 + ocT1.g,
            ocT1.b * 256 + ocT7.r
        );
        int ocNVertices = ocT2.r * 16777216 + ocT2.g * 65536 + ocT2.b * 256 + ocT7.g;
        int ocNTextures = max(ocT3.a, 1);
        int ocVph = ocT5.r * 256 + ocT5.g;
        int ocVth = ocT5.b * 256 + ocT7.b;
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

        // Preserve the existing direct / overlay / hurt colour paths. The old
        // colour-controlled *geometry scale* mode is deliberately not applied:
        // static-surface geometry receives its exact transform from Minecraft.
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
            int ocFace = (ocUvOffset.y - 2) * ocSize.x + ocUvOffset.x;
            int ocVertexBase = ocFace * 4;
            int ocHeaderHeight = 2 + int(ceil(float(ocNVertices) * 0.25 / float(ocSize.x)));
            int ocDataHeight = ocHeaderHeight + ocSize.y * ocNTextures;

            ivec2 ocI0 = getvert(ocTopLeft, ocSize.x, ocDataHeight + ocVph + ocVth, ocVertexBase + 0);
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
            vec2 ocUv3 = ocTriangle ? ocUv2 : getuv(ocTopLeft, ocSize.x, ocDataHeight + ocVph, ocI3.y);

            vec3 ocE10 = ocP1 - ocP0;
            vec3 ocE20 = ocP2 - ocP0;
            float ocE10Len = max(length(ocE10), 1.0e-12);
            vec3 ocU = ocE10 / ocE10Len;
            vec3 ocNRaw = cross(ocE10, ocE20);
            vec3 ocN = ocNRaw / max(length(ocNRaw), 1.0e-12);
            vec3 ocV = normalize(cross(ocU, ocN));

            vec2 ocQ0 = vec2(0.0);
            vec2 ocQ1 = vec2(dot(ocP1 - ocP0, ocU), dot(ocP1 - ocP0, ocV));
            vec2 ocQ2 = vec2(dot(ocP2 - ocP0, ocU), dot(ocP2 - ocP0, ocV));
            vec2 ocQ3 = vec2(dot(ocP3 - ocP0, ocU), dot(ocP3 - ocP0, ocV));
            vec2 ocQMin = min(min(ocQ0, ocQ1), min(ocQ2, ocQ3));
            vec2 ocQMax = max(max(ocQ0, ocQ1), max(ocQ2, ocQ3));
            vec2 ocQExtent = max(ocQMax - ocQMin, vec2(1.0e-12));

            ocQ0 = (ocQ0 - ocQMin) / ocQExtent;
            ocQ1 = (ocQ1 - ocQMin) / ocQExtent;
            ocQ2 = (ocQ2 - ocQMin) / ocQExtent;
            ocQ3 = (ocQ3 - ocQMin) / ocQExtent;

            ocSurfaceCoord = (ocCorner == 0) ? vec2(1.0, 1.0)
                           : (ocCorner == 1) ? vec2(1.0, 0.0)
                           : (ocCorner == 2) ? vec2(0.0, 0.0)
                                             : vec2(0.0, 1.0);
            ocSurfaceP01 = vec4(ocQ0, ocQ1);
            ocSurfaceP23 = vec4(ocQ2, ocQ3);
            ocSurfaceUV01 = vec4(ocUv0, ocUv1);
            ocSurfaceUV23 = vec4(ocUv2, ocUv3);

            // One directed owner per source edge. The fragment shader uses these
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
            ocSurfaceMap.w = float(ocPackedFlags);

            float ocTexTime = GameTime * 24000.0;
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
            ocSurfaceMap.xy = vec2(ocSize) / vec2(ocAtlasSize);
        }
    }
}
