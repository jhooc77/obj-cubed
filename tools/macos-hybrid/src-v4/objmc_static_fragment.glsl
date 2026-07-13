// obj³ static-surface fragment helpers (surface-v4).
float ocCross2(vec2 a, vec2 b) {
    return a.x * b.y - a.y * b.x;
}

bool ocBarycentric(vec2 p, vec2 a, vec2 b, vec2 c, out vec3 w) {
    vec2 e0 = b - a;
    vec2 e1 = c - a;
    float den = ocCross2(e0, e1);
    if (abs(den) < 1.0e-10) {
        w = vec3(0.0);
        return false;
    }
    float invDen = 1.0 / den;
    vec2 d = p - a;
    w.y = ocCross2(d, e1) * invDen;
    w.z = ocCross2(e0, d) * invDen;
    w.x = 1.0 - w.y - w.z;
    const float eps = 2.0e-4;
    return w.x >= -eps && w.y >= -eps && w.z >= -eps;
}

bool ocResolveStaticUv(
    vec2 p,
    vec4 p01,
    vec4 p23,
    vec4 uv01,
    vec4 uv23,
    float vertexCount,
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
    vec3 w;
    if (ocBarycentric(p, p0, p1, p2, w)) {
        uv = uv0 * w.x + uv1 * w.y + uv2 * w.z;
        return true;
    }
    if (vertexCount > 3.5 && ocBarycentric(p, p0, p2, p3, w)) {
        uv = uv0 * w.x + uv2 * w.y + uv3 * w.z;
        return true;
    }
    uv = vec2(0.0);
    return false;
}
