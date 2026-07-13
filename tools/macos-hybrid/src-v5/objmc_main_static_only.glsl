// OC_SURFACE_V4_ONLY_v1_5
// Static-only, subgroup-free path. Only the provoking vertices (quad corners 0
// and 2 for both OpenGL-last and Vulkan-first conventions) fetch metadata.
isCustom = 0;
noshadow = 0;
transition = 0.0;
ocSurfaceP01 = vec4(0.0);
ocSurfaceP23 = vec4(0.0);
ocSurfaceUV01 = vec4(0.0);
ocSurfaceUV23 = vec4(0.0);
ocSurfaceMap = vec4(0.0);
ocSurfaceOverlay = vec4(1.0);

#ifdef ENTITY
isGUI = int(isgui(ProjMat));
if (isGUI == 1 && abs(ProjMat[0][0]) > 0.010) isGUI = 0;
isHand = int(ishand(ProjMat));
#endif

int ocCorner = gl_VertexID % 4;
ocSurfaceCoord = (ocCorner == 0) ? vec2(1.0, 1.0)
               : (ocCorner == 1) ? vec2(1.0, 0.0)
               : (ocCorner == 2) ? vec2(0.0, 0.0)
                                 : vec2(0.0, 1.0);

// For Minecraft's quad index order (0,1,2) (2,3,0), every triangle's
// provoking vertex is 0 or 2 under either common convention. Vertices 1/3 do
// zero model-texture fetches.
if (ocCorner == 0 || ocCorner == 2) {
    ivec2 ocAtlasSize = textureSize(Sampler0, 0);
    ivec2 ocPixel = ivec2(UV0 * vec2(ocAtlasSize));
    ivec4 ocOffsetPixel = ivec4(texelFetch(Sampler0, ocPixel, 0) * 255.0 + 0.5);
    ivec2 ocUvOffset = ivec2(
        ocOffsetPixel.r * 256 + ocOffsetPixel.g,
        ocOffsetPixel.b * 256 + ocOffsetPixel.a
    );
    ivec2 ocTopLeft = ocPixel - ocUvOffset;
    bool ocPointerPlausible = all(greaterThanEqual(ocTopLeft, ivec2(0)))
                           && all(lessThan(ocTopLeft, ocAtlasSize));
    if (ocPointerPlausible) {
        ivec4 ocMarker = ivec4(texelFetch(Sampler0, ocTopLeft, 0) * 255.0 + 0.5);
        if (ocMarker == ivec4(12, 34, 57, 255)) {
            ivec4 ocT6 = getmeta(ocTopLeft, 6);
            if (ocT6.b == 5) {
                ivec4 ocT1 = getmeta(ocTopLeft, 1);
                ivec4 ocT3 = getmeta(ocTopLeft, 3);
                ivec4 ocT5 = getmeta(ocTopLeft, 5);
                ivec4 ocT7 = getmeta(ocTopLeft, 7);
                ivec2 ocSize = ivec2(
                    ocT1.r * 256 + ocT1.g,
                    ocT1.b * 256 + ocT7.r
                );
                int ocNTextures = max(ocT3.a, 1);
                int ocMetaHeight = ocT5.r * 256 + ocT5.g;
                int ocLocalLinear = (ocPixel.y - ocTopLeft.y) * ocSize.x
                                  + (ocPixel.x - ocTopLeft.x);
                int ocMetaRelative = ocLocalLinear - 2 * ocSize.x;
                bool ocIsMetaPointer = ocMetaRelative >= 0
                    && ocMetaRelative < ocMetaHeight * ocSize.x
                    && (ocMetaRelative % 9) == 0;
                // Native rectangle faces point directly into the texture rows.
                // Even if a texture pixel accidentally resembles a header pointer,
                // only stride-aligned metadata pointers may enter the decoder.
                if (ocIsMetaPointer) {
                    isCustom = 1;
                    noshadow = getb(ocT6.r, 7, 1);

#ifdef ENTITY
                int ocColorBehavior = getb(ocT6.r, 0, 1) * 256 + ocT6.g;
                vec3 ocDirectColor = vec3(1.0);
                bool ocHasDirectColor = false;
                vec2 ocHue = vec2(0.0, 255.0 / 256.0);
                int ocModeR = (ocColorBehavior >> 6) & 7;
                int ocModeG = (ocColorBehavior >> 3) & 7;
                int ocModeB = ocColorBehavior & 7;
                if (ocModeR == 0) { ocDirectColor.r = Color.r; ocHasDirectColor = true; }
                else if (ocModeR == 3) { ocHue.x = Color.r * 255.0; ocHue.y *= 256.0; }
                else if (ocModeR == 4 && Color.r != 0.0) ocSurfaceOverlay = vec4(1.0, 0.7, 0.7, 1.0);
                if (ocModeG == 0) { ocDirectColor.g = Color.g; ocHasDirectColor = true; }
                else if (ocModeG == 3) { ocHue.x = ocHue.x * 256.0 + Color.g * 255.0; ocHue.y *= 256.0; }
                else if (ocModeG == 4 && Color.g != 0.0) ocSurfaceOverlay = vec4(1.0, 0.7, 0.7, 1.0);
                if (ocModeB == 0) { ocDirectColor.b = Color.b; ocHasDirectColor = true; }
                else if (ocModeB == 3) { ocHue.x = ocHue.x * 256.0 + Color.b * 255.0; ocHue.y *= 256.0; }
                else if (ocModeB == 4 && Color.b != 0.0) ocSurfaceOverlay = vec4(1.0, 0.7, 0.7, 1.0);
                if (ocHue.x > 0.0) ocSurfaceOverlay = vec4(hrgb(ocHue.x / ocHue.y), 1.0);
                if (ocHasDirectColor) ocSurfaceOverlay = vec4(ocDirectColor, 1.0);
#endif

                ivec4 ocM[8];
                for (int ocI = 0; ocI < 8; ocI++) {
                    int ocL = ocLocalLinear + 1 + ocI;
                    ivec2 ocMetaCoord = ocTopLeft + ivec2(ocL % ocSize.x, ocL / ocSize.x);
                    ocM[ocI] = ivec4(texelFetch(Sampler0, ocMetaCoord, 0) * 255.0 + 0.5);
                }
                int ocQRaw[8] = int[8](
                    ocM[0].r * 256 + ocM[0].g, ocM[0].b * 256 + ocM[0].a,
                    ocM[1].r * 256 + ocM[1].g, ocM[1].b * 256 + ocM[1].a,
                    ocM[2].r * 256 + ocM[2].g, ocM[2].b * 256 + ocM[2].a,
                    ocM[3].r * 256 + ocM[3].g, ocM[3].b * 256 + ocM[3].a
                );
                int ocPackedFlags = (ocQRaw[0] & 1)
                                  | ((ocQRaw[1] & 1) << 1)
                                  | ((ocQRaw[2] & 1) << 2)
                                  | ((ocQRaw[3] & 1) << 3)
                                  | ((ocQRaw[4] & 1) << 4)
                                  | ((ocQRaw[5] & 1) << 5);
                vec2 ocQ[4];
                ocQ[0] = vec2(ocQRaw[0] & 65534, ocQRaw[1] & 65534) / 65534.0;
                ocQ[1] = vec2(ocQRaw[2] & 65534, ocQRaw[3] & 65534) / 65534.0;
                ocQ[2] = vec2(ocQRaw[4] & 65534, ocQRaw[5] & 65534) / 65534.0;
                ocQ[3] = vec2(ocQRaw[6], ocQRaw[7]) / 65535.0;
                int ocShape = ocPackedFlags & 3;
                int ocVertexCount = ocShape == 1 ? 3 : 4;
                vec2 ocLocalUv[4];
                ocLocalUv[0] = vec2(ocM[4].r * 256 + ocM[4].g, ocM[4].b * 256 + ocM[4].a) / 65535.0;
                ocLocalUv[1] = vec2(ocM[5].r * 256 + ocM[5].g, ocM[5].b * 256 + ocM[5].a) / 65535.0;
                ocLocalUv[2] = vec2(ocM[6].r * 256 + ocM[6].g, ocM[6].b * 256 + ocM[6].a) / 65535.0;
                ocLocalUv[3] = vec2(ocM[7].r * 256 + ocM[7].g, ocM[7].b * 256 + ocM[7].a) / 65535.0;

                vec2 ocD1 = ocQ[1] - ocQ[0];
                vec2 ocD2 = ocQ[2] - ocQ[0];
                float ocDet = ocD1.x * ocD2.y - ocD1.y * ocD2.x;
                if (abs(ocDet) < 1.0e-10) {
                    ocPackedFlags = (ocPackedFlags & ~3) | 3;
                    ocDet = 1.0;
                }
                float ocInvDet = 1.0 / ocDet;
                vec3 ocB1 = vec3(ocD2.y, -ocD2.x,
                    -(ocD2.y * ocQ[0].x - ocD2.x * ocQ[0].y)) * ocInvDet;
                vec3 ocB2 = vec3(-ocD1.y, ocD1.x,
                    -(-ocD1.y * ocQ[0].x + ocD1.x * ocQ[0].y)) * ocInvDet;
                vec2 ocUvD1 = ocLocalUv[1] - ocLocalUv[0];
                vec2 ocUvD2 = ocLocalUv[2] - ocLocalUv[0];
                vec3 ocUC = vec3(
                    ocUvD1.x * ocB1.x + ocUvD2.x * ocB2.x,
                    ocUvD1.x * ocB1.y + ocUvD2.x * ocB2.y,
                    ocLocalUv[0].x + ocUvD1.x * ocB1.z + ocUvD2.x * ocB2.z
                );
                vec3 ocVC = vec3(
                    ocUvD1.y * ocB1.x + ocUvD2.y * ocB2.x,
                    ocUvD1.y * ocB1.y + ocUvD2.y * ocB2.y,
                    ocLocalUv[0].y + ocUvD1.y * ocB1.z + ocUvD2.y * ocB2.z
                );

                vec3 ocEdge[4];
                for (int ocI = 0; ocI < 4; ocI++) ocEdge[ocI] = vec3(0.0, 0.0, 1.0);
                if (ocShape != 0) {
                    float ocArea = 0.0;
                    for (int ocI = 0; ocI < ocVertexCount; ocI++) {
                        vec2 ocA = ocQ[ocI];
                        vec2 ocB = ocQ[(ocI + 1) % ocVertexCount];
                        ocArea += ocA.x * ocB.y - ocA.y * ocB.x;
                    }
                    float ocSign = ocArea >= 0.0 ? 1.0 : -1.0;
                    for (int ocI = 0; ocI < 4; ocI++) {
                        if (ocI >= ocVertexCount) break;
                        vec2 ocA = ocQ[ocI];
                        vec2 ocD = ocQ[(ocI + 1) % ocVertexCount] - ocA;
                        float ocELen = max(length(ocD), 1.0e-10);
                        ocEdge[ocI] = ocSign * vec3(-ocD.y, ocD.x,
                            ocD.y * ocA.x - ocD.x * ocA.y) / ocELen;
                    }
                }

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
                    float ocVmid = (ocLocalUv[0].y + ocLocalUv[2].y) * 0.5 * float(ocSize.y);
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

                vec2 ocTexScale = vec2(ocSize) / vec2(ocAtlasSize);
                ocUC.xy *= ocTexScale.x;
                ocUC.z = (ocBase0.x + ocUC.z * float(ocSize.x)) / float(ocAtlasSize.x);
                ocVC.xy *= ocTexScale.y;
                ocVC.z = (ocBase0.y + ocVC.z * float(ocSize.y)) / float(ocAtlasSize.y);
                float ocNextV = (ocBase1.y - ocBase0.y) / float(ocAtlasSize.y);

                ocSurfaceP01 = vec4(ocUC, ocVC.x);
                ocSurfaceP23 = vec4(ocVC.y, ocVC.z, ocNextV, float(ocPackedFlags));
                ocSurfaceUV01 = vec4(ocEdge[0], ocEdge[1].x);
                ocSurfaceUV23 = vec4(ocEdge[1].y, ocEdge[1].z, ocEdge[2].x, ocEdge[2].y);
                ocSurfaceMap = vec4(ocEdge[2].z, ocEdge[3]);
                }
            } else {
                isCustom = 3;
            }
        } else if (ocMarker == ivec4(12, 34, 56, 255)) {
            isCustom = 3;
        }
    }
}
