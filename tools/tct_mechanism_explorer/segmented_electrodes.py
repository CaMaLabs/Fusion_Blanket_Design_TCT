#!/usr/bin/env python3
"""Reduced segmented-electrode actuator model for TCT.

This is a control/reduced-physics layer, not a claim that native M3D-C1 currently
solves electrode sheath/boundary physics. It produces spatially overlapping
E_r(r,z,t), ExB velocity/shear, actuator dynamics and conservative transport
coupling terms suitable for falsification studies and later BOUT++/M3D-C1 handoff.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Iterable
import math

@dataclass
class ElectrodeZone:
    r0: float
    z0: float
    sigma_r: float
    sigma_z: float
    polarity: float = 1.0
    v_limit: float = 1.0
    i_limit: float = 1.0
    slew_v_per_t: float = 10.0
    tau_response: float = 0.02
    latency: float = 0.0
    capacitance: float = 1.0
    plasma_resistance: float = 10.0
    radial_coupling: float = 1.0
    command: Callable[[float], float] | None = None
    _v: float = field(default=0.0, init=False, repr=False)
    _last_t: float | None = field(default=None, init=False, repr=False)

    def reset(self) -> None:
        self._v = 0.0
        self._last_t = None

    def step(self, t: float) -> tuple[float, float, float]:
        dt = 0.0 if self._last_t is None else max(0.0, t-self._last_t)
        self._last_t = t
        delayed_t = t-self.latency
        target = 0.0 if delayed_t < 0 or self.command is None else self.polarity*float(self.command(delayed_t))
        target = max(-self.v_limit, min(self.v_limit, target))
        if dt > 0:
            alpha = 1.0-math.exp(-dt/max(self.tau_response,1e-12))
            desired = self._v + alpha*(target-self._v)
            max_dv = self.slew_v_per_t*dt
            desired = max(self._v-max_dv, min(self._v+max_dv, desired))
            # parallel RC loading: commanded source must support displacement + plasma current
            i_plasma = desired/max(self.plasma_resistance,1e-12)
            i_cap = self.capacitance*(desired-self._v)/dt
            i_total = i_plasma+i_cap
            if abs(i_total) > self.i_limit:
                scale = self.i_limit/abs(i_total)
                desired = self._v+(desired-self._v)*scale
                i_plasma = desired/max(self.plasma_resistance,1e-12)
                i_cap = self.capacitance*(desired-self._v)/dt
                i_total = i_plasma+i_cap
            self._v = desired
        else:
            i_total = self._v/max(self.plasma_resistance,1e-12)
        power = self._v*i_total
        return self._v, i_total, power

    def field_weight(self, r: float, z: float) -> float:
        sr=max(self.sigma_r,1e-12); sz=max(self.sigma_z,1e-12)
        return math.exp(-0.5*((r-self.r0)/sr)**2-0.5*((z-self.z0)/sz)**2)

@dataclass
class SegmentedElectrodeArray:
    zones: list[ElectrodeZone]
    electrode_gap_scale: float = 1.0

    def reset(self) -> None:
        for zone in self.zones: zone.reset()

    def snapshot(self, t: float, r_grid: Iterable[float], z_grid: Iterable[float], b_toroidal: float) -> dict:
        states=[zone.step(t) for zone in self.zones]
        r=list(r_grid); z=list(z_grid)
        er=[]; vexb=[]
        b2=max(b_toroidal*b_toroidal,1e-18)
        for zz in z:
            er_row=[]; v_row=[]
            for rr in r:
                e=sum(zone.radial_coupling*v*zone.field_weight(rr,zz)/max(self.electrode_gap_scale,1e-12)
                      for zone,(v,_,_) in zip(self.zones,states))
                er_row.append(e)
                # For radial E and dominant toroidal B, magnitude |E x B|/B^2 = |E|/|B|;
                # retain sign for shear orientation.
                v_row.append(e*b_toroidal/b2)
            er.append(er_row); vexb.append(v_row)
        shear=[]
        for row in vexb:
            s=[]
            for i,val in enumerate(row):
                if len(r)<2: s.append(0.0)
                elif i==0: s.append((row[1]-row[0])/(r[1]-r[0]))
                elif i==len(r)-1: s.append((row[-1]-row[-2])/(r[-1]-r[-2]))
                else: s.append((row[i+1]-row[i-1])/(r[i+1]-r[i-1]))
            shear.append(s)
        return {
            'time':t,'E_r':er,'v_ExB':vexb,'dvExB_dr':shear,
            'zone_voltage':[x[0] for x in states],
            'zone_current':[x[1] for x in states],
            'zone_power':[x[2] for x in states],
            'actuator_power':sum(abs(x[2]) for x in states),
            'peak_abs_Er':max((abs(x) for row in er for x in row),default=0.0),
            'peak_abs_shear':max((abs(x) for row in shear for x in row),default=0.0),
        }

def shear_transport_multiplier(shear: float, gamma_instability: float, floor: float=0.25) -> float:
    """Conservative decorrelation closure: transport suppression only when shear competes with growth.

    This is explicitly a reduced closure for ranking/falsification. It is not a replacement
    for nonlinear MHD validation.
    """
    g=max(abs(gamma_instability),1e-12)
    return max(floor, 1.0/(1.0+(abs(shear)/g)**2))

def species_guiding_center_drift(E_r: float, B: float, charge_c: float, mass_kg: float,
                                 energy_j: float=0.0, gradB_over_B: float=0.0) -> dict:
    """Reduced species diagnostic. ExB is charge/mass independent; grad-B term is species dependent."""
    b=max(abs(B),1e-12)
    vexb=E_r/B
    mu_energy=max(energy_j,0.0)
    v_gradb=(mu_energy/(max(abs(charge_c),1e-30)*b))*gradB_over_B if charge_c else 0.0
    return {'v_ExB':vexb,'v_gradB_proxy':v_gradb,'mass_kg':mass_kg,'charge_C':charge_c,
            'species_separation_claim_supported':False}
