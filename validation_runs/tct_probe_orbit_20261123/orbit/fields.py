"""Interpolate the public coil model in a small outboard orbit corridor."""

from pathlib import Path

import numpy as np
from scipy.optimize import brentq

from coil_basis import basis
from equilibrium import read_geqdsk


ROOT = Path(__file__).resolve().parent
RADIUS = 2.20
HALF_WIDTH = 0.025
TWO_PI = 2 * np.pi


class FieldMap:
    def __init__(self, angles=144, transverse=15, segments=48):
        self.metadata, _, _, self.flux, self.field, self.field_gradient = read_geqdsk(
            ROOT / "reference/g158103.03796"
        )
        self.height = brentq(lambda z: self.ambient(RADIUS, z)[1][2], -0.04, 0.01)
        self.balance_speed = np.sqrt(-RADIUS * self.ambient(RADIUS, self.height)[1][0])
        rs = RADIUS + np.linspace(-0.037, 0.037, transverse)
        zs = self.height + np.linspace(-0.037, 0.037, transverse)
        ps = TWO_PI * np.arange(angles) / angles
        self.start = np.array([rs[0], 0, zs[0]])
        self.step = np.array([rs[1] - rs[0], ps[1], zs[1] - zs[0]])
        self.angles = angles
        pos = np.stack(np.meshgrid(rs, ps, zs, indexing="ij"), axis=-1)
        fields = basis(pos.reshape(-1, 3), segments).reshape(*pos.shape[:3], 18, 3)
        dr = np.gradient(fields, self.step[0], axis=0, edge_order=2)
        dz = np.gradient(fields, self.step[2], axis=2, edge_order=2)
        orders = np.fft.fftfreq(angles, d=1 / angles)[None, :, None, None, None]
        dphi = np.fft.ifft(1j * orders * np.fft.fft(fields, axis=1), axis=1).real
        self.coil_map = np.stack((fields, dr, dphi / rs[:, None, None, None, None], dz), axis=3)
        self.corners = np.array([[r, p, z] for r in (0, 1) for p in (0, 1) for z in (0, 1)])

    def ambient(self, radius, height):
        field = self.field(radius, height)
        deriv = self.field_gradient(radius, height)
        return field, deriv @ field / np.linalg.norm(field)

    def local(self, position):
        frac = (position - self.start) / self.step
        frac[1] %= self.angles
        base = np.floor(frac).astype(int)
        offsets = frac - base
        ijk = base + self.corners
        ijk[:, 1] %= self.angles
        weights = np.prod(np.where(self.corners, offsets, 1 - offsets), axis=1)
        coils = np.einsum("n,nkij->kij", weights, self.coil_map[tuple(ijk.T)])
        radius, _, height = position
        return self.field(radius, height), self.field_gradient(radius, height), coils

    @staticmethod
    def force(local, currents):
        """Full gradient of |B| given currents and local cylindrical components."""
        field, deriv, coils = local
        perturbation = coils.transpose(0, 2, 1) @ currents
        total = field + perturbation[0]
        return (deriv + perturbation[1:]) @ (total / np.linalg.norm(total))

    @staticmethod
    def linear_response(local):
        field, deriv, coils = local
        strength = np.linalg.norm(field)
        unit = field / strength
        base = deriv @ unit
        du = (deriv - base[:, None] * unit) / strength
        return base, coils[1:] @ unit + du @ coils[0].T

    def check(self):
        rng = np.random.default_rng(158103)
        extent = np.array([HALF_WIDTH, np.pi, HALF_WIDTH])
        center = np.array([RADIUS, np.pi, self.height])
        points = center + rng.uniform(-1, 1, (48, 3)) * extent
        currents = rng.uniform(-5000, 5000, 18)
        h = 0.0005
        exact = [basis(points, 96)]
        for axis in range(3):
            delta = np.zeros_like(points)
            delta[:, axis] = h / points[:, 0] if axis == 1 else h
            exact.append((basis(points + delta, 96) - basis(points - delta, 96)) / (2 * h))
        errors = []
        for p, wires in zip(points, np.stack(exact, axis=1)):
            local = self.local(p)
            direct = self.force((*local[:2], wires), currents)
            errors.append(self.force(local, currents) - direct)
        error = np.max(np.abs(errors), axis=0)
        np.testing.assert_array_less(error, [2e-4, 2e-4, 2e-4])
        return error.tolist()
