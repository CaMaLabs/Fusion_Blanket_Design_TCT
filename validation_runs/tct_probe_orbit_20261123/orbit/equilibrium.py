"""Audit aligned-dipole force authority using the archived DIII-D equilibrium."""
import hashlib
import json
import re

import numpy as np
from scipy.interpolate import PchipInterpolator, RectBivariateSpline


def read_geqdsk(path):
    header, raw = path.read_text().split("\n",1)
    nr,nz=map(int,header.split()[-2:])
    token=r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[EeDd][-+]?\d+)?"
    values=np.array([float(v.replace("D","E").replace("d","e"))
                     for v in re.findall(token,raw)])
    dr,dz,r0,r_left,z_mid = values[:5]
    ra,za,psi_axis,psi_boundary,b0=values[5:10]
    r=np.linspace(r_left,r_left+dr,nr)
    z=np.linspace(z_mid-dz/2,z_mid+dz/2,nz)
    fpol=PchipInterpolator(np.linspace(0,1,nr),values[20:20+nr],extrapolate=False)
    psi_start=20+4*nr
    psi=RectBivariateSpline(r,z,values[psi_start:psi_start+nr*nz].reshape(nz,nr).T)
    assert abs(psi.ev(ra,za)-psi_axis)<1e-4

    def normalized_flux(r,z):
        return (psi.ev(r,z)-psi_axis)/(psi_boundary-psi_axis)

    def field(r,z):
        flux=normalized_flux(r,z)
        # Permit small spline deviations at the reconstructed magnetic axis.
        if np.any((flux < -0.002) | (flux > 1)):
            raise ValueError("Force calculation left the confined equilibrium region")
        return np.stack((-psi.ev(r,z,dy=1)/r,
                         fpol(np.clip(flux,0,1))/r,psi.ev(r,z,dx=1)/r),axis=-1)

    def field_gradient(r,z):
        normalized=normalized_flux(r,z)
        f=fpol(normalized)
        df=fpol.derivative()(normalized)/(psi_boundary-psi_axis)
        psi_r=psi.ev(r,z,dx=1)
        psi_z=psi.ev(r,z,dy=1)
        psi_rz=psi.ev(r,z,dx=1,dy=1)
        radial=np.stack((-psi_rz/r+psi_z/r**2,
                         df*psi_r/r-f/r**2,
                         psi.ev(r,z,dx=2)/r-psi_r/r**2),axis=-1)
        vertical=np.stack((-psi.ev(r,z,dy=2)/r,df*psi_z/r,psi_rz/r),axis=-1)
        return np.stack((radial,np.zeros_like(radial),vertical),axis=-2)
    metadata=dict(shot=158103,time_ms=3796,reference_R_m=r0,reference_Bphi_T=b0,
                  magnetic_axis_RZ_m=[ra,za],header=header,
                  file_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    return metadata,r,z,normalized_flux,field,field_gradient
