// obj³ static-surface fragment helpers — v1.3.
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
