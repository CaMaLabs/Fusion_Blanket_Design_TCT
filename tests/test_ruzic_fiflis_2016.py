import math

from liquid_lithium_stability.ruzic_fiflis_2016 import (
    RuzicInputs,
    evaluate,
    max_stable_width_mm,
    normalized_plasma_impulse,
    plateau_rayleigh_curvature_index,
)


def test_eq23_x_one_is_25_mm():
    assert math.isclose(max_stable_width_mm(1.0), 25.0, rel_tol=0.0, abs_tol=1e-12)


def test_paper_boundary_22_stable_26_unstable_at_reference_rt_impulse():
    stable = evaluate(RuzicInputs(120.0, 0.22, 0.0, 22.0, 90.0, True))
    unstable = evaluate(RuzicInputs(120.0, 0.22, 0.0, 26.0, 90.0, True))
    assert stable.stable_by_eq23 is True
    assert unstable.stable_by_eq23 is False


def test_parallel_current_removes_rt_jxb_term():
    x, j_perp, rt, kh = normalized_plasma_impulse(120.0, 0.22, 10.0, 20.0, 0.0)
    assert math.isclose(j_perp, 0.0, abs_tol=1e-12)
    assert math.isclose(rt, 0.0, abs_tol=1e-12)
    assert math.isclose(x, kh, abs_tol=1e-12)


def test_unwetted_case_is_not_passed_by_eq23_gate():
    result = evaluate(RuzicInputs(120.0, 0.22, 0.0, 10.0, 90.0, False))
    assert result.stable_by_eq23 is False
    assert "UNWETTED" in result.wetting_label


def test_plateau_rayleigh_index_sign():
    assert plateau_rayleigh_curvature_index(10.0, 1.0) > 0.0
    assert plateau_rayleigh_curvature_index(1.0, 10.0) < 0.0
