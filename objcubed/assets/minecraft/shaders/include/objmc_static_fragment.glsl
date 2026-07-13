// OC_SURFACE_V4_ONLY_v1_5
// UV and edge coefficients are precomputed in provoking vertices. Rectangles
// take the zero-clip path; triangles evaluate three edges; quads evaluate four.
bool ocResolveStaticUvFast(
    vec2 p,
    vec4 uvA,
    vec4 uvB,
    vec4 edge01,
    vec4 edge12,
    vec4 edge23,
    out vec2 uv,
    out float nextV
) {
    int flags = int(floor(uvB.w + 0.5));
    int shape = flags & 3;            // 0 rectangle, 1 triangle, 2 convex quad, 3 hidden
    int owners = (flags >> 2) & 15;
    if (shape == 3) { uv=vec2(0.0); nextV=0.0; return false; }

    if (shape != 0) {
        vec3 hp = vec3(p, 1.0);
        const float tol = 3.5 / 65534.0;
        float e0 = dot(edge01.xyz, hp);
        if (e0 < -tol || (e0 < 0.0 && (owners & 1) == 0)) return false;
        float e1 = dot(vec3(edge01.w, edge12.x, edge12.y), hp);
        if (e1 < -tol || (e1 < 0.0 && (owners & 2) == 0)) return false;
        float e2 = dot(vec3(edge12.z, edge12.w, edge23.x), hp);
        if (e2 < -tol || (e2 < 0.0 && (owners & 4) == 0)) return false;
        if (shape == 2) {
            float e3 = dot(edge23.yzw, hp);
            if (e3 < -tol || (e3 < 0.0 && (owners & 8) == 0)) return false;
        }
    }

    uv = vec2(
        uvA.x*p.x + uvA.y*p.y + uvA.z,
        uvA.w*p.x + uvB.x*p.y + uvB.y
    );
    nextV = uvB.z;
    return true;
}
