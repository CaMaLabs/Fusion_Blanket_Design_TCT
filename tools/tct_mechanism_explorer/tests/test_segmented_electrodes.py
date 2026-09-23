import math
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from segmented_electrodes import ElectrodeZone, SegmentedElectrodeArray, shear_transport_multiplier, species_guiding_center_drift

class SegmentedElectrodeTests(unittest.TestCase):
    def test_zero_command_zero_field(self):
        z=ElectrodeZone(1.0,0.0,0.2,0.2,command=lambda t:0.0)
        a=SegmentedElectrodeArray([z],electrode_gap_scale=0.1)
        a.snapshot(0.0,[0.9,1.0,1.1],[0.0],2.0)
        s=a.snapshot(0.01,[0.9,1.0,1.1],[0.0],2.0)
        self.assertAlmostEqual(s['peak_abs_Er'],0.0,places=12)
        self.assertAlmostEqual(s['peak_abs_shear'],0.0,places=12)

    def test_overlapping_zones_superpose(self):
        def zone(v): return ElectrodeZone(1.0,0.0,0.2,0.2,tau_response=1e-6,slew_v_per_t=1e9,command=lambda t:v)
        a=SegmentedElectrodeArray([zone(0.2),zone(0.3)],electrode_gap_scale=0.1)
        a.snapshot(0.0,[1.0],[0.0],2.0)
        s=a.snapshot(0.01,[1.0],[0.0],2.0)
        self.assertAlmostEqual(s['E_r'][0][0],5.0,places=5)

    def test_exb_species_independent(self):
        e=species_guiding_center_drift(10.0,5.0,-1.0,1.0)
        i=species_guiding_center_drift(10.0,5.0,1.0,100.0)
        self.assertEqual(e['v_ExB'],i['v_ExB'])
        self.assertFalse(e['species_separation_claim_supported'])

    def test_shear_suppresses_reduced_transport(self):
        self.assertLess(shear_transport_multiplier(3.0,1.0),shear_transport_multiplier(0.2,1.0))

    def test_latency_and_slew_limit(self):
        z=ElectrodeZone(1.0,0.0,0.2,0.2,latency=0.05,slew_v_per_t=1.0,tau_response=1e-6,command=lambda t:1.0)
        self.assertEqual(z.step(0.0)[0],0.0)
        self.assertEqual(z.step(0.02)[0],0.0)
        v=z.step(0.06)[0]
        self.assertLessEqual(v,0.04+1e-12)

if __name__=='__main__': unittest.main()
