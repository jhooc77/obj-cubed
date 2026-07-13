#!/usr/bin/env python3
import math, random

def matmul(A,B):
    return [[sum(A[i][k]*B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
def Rx(x): return [[1,0,0],[0,math.cos(x),-math.sin(x)],[0,math.sin(x),math.cos(x)]]
def Ry(y): return [[math.cos(y),0,math.sin(y)],[0,1,0],[-math.sin(y),0,math.cos(y)]]
def Rz(z): return [[math.cos(z),-math.sin(z),0],[math.sin(z),math.cos(z),0],[0,0,1]]
def cols(M): return [[M[i][j] for i in range(3)] for j in range(3)]
def euler_from_cols(c0,c1,c2):
    r00,r10,r20=c0; r01,r11,r21=c1; _,r12,r22=c2
    y=math.asin(max(-1,min(1,-r20))); cy=math.cos(y)
    if abs(cy)>1e-6:
        x=math.atan2(r21,r22); z=math.atan2(r10,r00)
    else:
        x=math.atan2(-r12,r11); z=0
    return x,y,z

def err(A,B): return max(abs(A[i][j]-B[i][j]) for i in range(3) for j in range(3))
worst=0
for _ in range(20000):
    x=random.uniform(-math.pi,math.pi)
    y=random.uniform(-math.pi/2,math.pi/2)
    z=random.uniform(-math.pi,math.pi)
    M=matmul(matmul(Rz(z),Ry(y)),Rx(x))
    xx,yy,zz=euler_from_cols(*cols(M))
    M2=matmul(matmul(Rz(zz),Ry(yy)),Rx(xx))
    worst=max(worst,err(M,M2))
assert worst < 1e-5, worst

# Barycentric UV reconstruction over a rectangle carrier.
def cross2(a,b): return a[0]*b[1]-a[1]*b[0]
def bary(p,a,b,c):
    den=cross2((b[0]-a[0],b[1]-a[1]),(c[0]-a[0],c[1]-a[1]))
    w0=cross2((b[0]-p[0],b[1]-p[1]),(c[0]-p[0],c[1]-p[1]))/den
    w1=cross2((c[0]-p[0],c[1]-p[1]),(a[0]-p[0],a[1]-p[1]))/den
    return w0,w1,1-w0-w1
P=[(0.1,0.2),(0.9,0.1),(0.8,0.85),(0.2,0.75)]
UV=[(0.0,0.0),(1.0,0.0),(1.0,1.0),(0.0,1.0)]
for tri in ((0,1,2),(0,2,3)):
    for _ in range(1000):
        r1,r2=random.random(),random.random()
        if r1+r2>1: r1,r2=1-r1,1-r2
        w=(1-r1-r2,r1,r2)
        p=(sum(P[tri[i]][0]*w[i] for i in range(3)),sum(P[tri[i]][1]*w[i] for i in range(3)))
        got=bary(p,*[P[i] for i in tri])
        assert max(abs(got[i]-w[i]) for i in range(3))<1e-9
print(f'OK: Euler round-trip worst error={worst:.3e}; barycentric reconstruction passed')
