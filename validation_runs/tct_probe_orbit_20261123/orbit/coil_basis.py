"""Evaluate the public MAFOT DIII-D I- and C-coil filament basis."""
import numpy as np

REVISION = "7fee4ba4269a614db44b7fdd7d10356f43647b34"
GEOMETRY_SOURCES = [
    f"https://github.com/ORNL-Fusion/MAFOT/blob/{REVISION}/src/libtrip3d/{p}"
    for p in ("d3icoils.f","icoilsd3.i","d3ccoils.f","ccoilsd3.i")
]
# Active geometry values, SI apart from the toroidal angles.
I_CENTERS = (-32.7,-87.3,-152.7,-207.3,-272.7,-327.3)
C_CENTERS = (-79.,-139.,-199.,-259.,-319.,-19.)
LABELS = [f"{row}_{abs(deg):g}" for row,centers in (
    ("I_upper",I_CENTERS),("I_lower",I_CENTERS),("C",C_CENTERS)
) for deg in centers]


def xyz(r,p,z):
    return np.column_stack((r*np.cos(p),r*np.sin(p),np.broadcast_to(z,np.shape(p))))


def loop(phi,span,bottom,top,divisions,upper_first=False):
    mid,width=np.deg2rad([phi,span])
    angles=np.linspace(mid-width/2,mid+width/2,divisions+1)
    low,high=xyz(bottom[0],angles,bottom[1]),xyz(top[0],angles,top[1])
    return (np.concatenate((high,low[::-1])) if upper_first else
            np.concatenate((low,high[::-1])))


def centerlines(divisions):
    profiles=(
        (I_CENTERS,51.72,(2.394,.504),(2.184,1.012),1,False),
        (I_CENTERS,51.72,(2.184,-1.012),(2.394,-.504),1,False),
        (C_CENTERS,58.0,(3.23,-.8),(3.23,.8),4,True),
    )
    return [(loop(p,w,b,t,divisions,uf),turns)
            for angles,w,b,t,turns,uf in profiles for p in angles]


def finite_wires(points, vertices, turns=1):
    # Closed polygon. Each segment is integrated analytically.
    end=np.roll(vertices,-1,axis=0)
    out=np.empty_like(points,dtype=float)
    for begin in range(0,len(points),768):
        chunk=points[begin:begin+768,None]
        a,b=chunk-vertices,chunk-end
        la,lb=np.linalg.norm(a,axis=-1),np.linalg.norm(b,axis=-1)
        denominator=la*lb+np.einsum("...k,...k->...",a,b)
        if np.min(denominator)<=0:
            raise ArithmeticError("Requested field point lies on the filament")
        out[begin:begin+len(chunk)]=turns*1e-7*np.sum(
            np.cross(a,b)*((1/la+1/lb)/denominator)[...,None],axis=1
        )
    return out


def basis(points_rpz,divisions):
    r,p,z=points_rpz.T
    points=xyz(r,p,z)
    co,si=np.cos(p),np.sin(p)
    values=[]
    for vertices,turns in centerlines(divisions):
        x,y,z=finite_wires(points,vertices,turns).T
        values.append(np.stack((co*x+si*y,-si*x+co*y,z),axis=-1))
    return np.stack(values,axis=1)


def verify():
    angles=np.arange(512)*2*np.pi/512
    radius=.72
    test=np.array([[0.,0.,z] for z in (-.3,0.,.52)])
    expected=2*np.pi*1e-7*radius**2/(radius**2+test[:,2]**2)**1.5
    observed=finite_wires(test,xyz(radius,angles,0))
    np.testing.assert_allclose(observed[:,2],expected,rtol=4e-5,atol=1e-13)
    assert np.max(abs(observed[:,:2]))<1e-14
    return float(np.max(abs(observed[:,2]/expected-1)))
