// obj³ static-surface fragment helpers (surface-v4 compact metadata).
float ocCross2(vec2 a, vec2 b) {
    return a.x * b.y - a.y * b.x;
}

bool ocBarycentricOwned(vec2 p, vec2 a, vec2 b, vec2 c, int ownerBits, out vec3 w) {
    vec2 e0 = b - a;
    vec2 e1 = c - a;
    float den = ocCross2(e0, e1);
    if (abs(den) < 1.0e-10) {
        w = vec3(0.0);
        return false;
    }

    float invDen = 1.0 / den;
    vec2 d = p - a;
    vec3 raw;
    raw.y = ocCross2(d, e1) * invDen;
    raw.z = ocCross2(e0, d) * invDen;
    raw.x = 1.0 - raw.y - raw.z;

    // Only one deterministic owner may fill a sub-pixel edge uncertainty band.
    // This avoids both cracks and the coplanar overlap/z-fight seen on NVIDIA.
    vec3 tol = max(fwidth(raw) * 0.55, vec3(1.0e-7));
    if (any(lessThan(raw, -tol))) {
        w = vec3(0.0);
        return false;
    }
    if (raw.x < 0.0 && (ownerBits & 1) == 0) return false;
    if (raw.y < 0.0 && (ownerBits & 2) == 0) return false;
    if (raw.z < 0.0 && (ownerBits & 4) == 0) return false;

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
