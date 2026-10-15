import numpy as np
import pytest
from uuid import uuid4

from app.contracts.models import LightCurve, Mission, Cadence, DetectionCandidate, ClassifiedCandidate, PredictionLabel
from app.detection.bls import BLSDetector
from app.validation.rules import validate_candidate, ValidationConfig


def generate_light_curve_fixture(
    period: float = 4.0,
    duration: float = 0.15,
    epoch: float = 1.0,
    primary_depth: float = 0.01,
    secondary_depth: float = 0.0,
    n_days: float = 20.0,
    n_points: int = 4000,
) -> LightCurve:
    """Generates a controlled photometric time-series fixture for testing transit statistics."""
    time = np.linspace(0, n_days, n_points)
    flux = np.ones_like(time)

    # Primary transit at phase 0.0 (t = epoch + k*period)
    phase_pri = (time - epoch + 0.5 * period) % period - 0.5 * period
    flux[np.abs(phase_pri) < 0.5 * duration] -= primary_depth

    # Secondary eclipse at phase 0.5 (t = epoch + (k + 0.5)*period)
    if secondary_depth > 0:
        phase_sec = (time - (epoch + 0.5 * period) + 0.5 * period) % period - 0.5 * period
        flux[np.abs(phase_sec) < 0.5 * duration] -= secondary_depth

    return LightCurve(
        target_id="TIC_TEST_SEC",
        mission=Mission.TESS,
        cadence=Cadence.SHORT,
        time=time.tolist(),
        flux=flux.tolist(),
        flux_error=(np.ones_like(time) * 0.0001).tolist(),
        time_unit="days",
        flux_unit="normalized",
    )


def test_transit_with_no_meaningful_secondary_event():
    """Verify that a light curve with a primary transit and flat phase 0.5 produces ~0 secondary eclipse depth and passes validation."""
    lc = generate_light_curve_fixture(primary_depth=0.01, secondary_depth=0.0)

    detector = BLSDetector(min_period=2.0, max_period=6.0)
    candidates = detector.detect(lc)
    assert len(candidates) > 0
    best = candidates[0]

    # Verify detected period is close to 4.0
    assert abs(best.period_days - 4.0) < 0.05
    assert best.depth > 0.008

    # Secondary eclipse depth at phase 0.5 must be 0.0 (no dip)
    assert best.secondary_eclipse_depth is not None
    assert best.secondary_eclipse_depth < 0.0005  # Negligible or 0.0

    # Classify and validate
    classified = ClassifiedCandidate.model_construct(
        candidate=best,
        prediction=PredictionLabel.PLANET_CANDIDATE,
        planet_probability=0.95,
        model_name="test",
        model_version="1.0",
        feature_schema_version="1.1",
        features={},
    )
    val = validate_candidate(classified)

    # Must pass secondary eclipse check
    sec_rule = next(r for r in val.rules if r.rule_name == "secondary_eclipse")
    assert sec_rule.passed is True
    assert "within threshold" in sec_rule.reason


def test_transit_with_secondary_event_at_half_orbital_phase():
    """Verify that a significant event at phase 0.5 (e.g. 40% of primary depth) is detected and fails validation as an eclipsing binary."""
    lc = generate_light_curve_fixture(primary_depth=0.01, secondary_depth=0.004)

    # Search window around the 4.0-day fundamental period
    detector = BLSDetector(min_period=3.0, max_period=5.0)
    candidates = detector.detect(lc)

    assert len(candidates) > 0
    best = candidates[0]

    assert abs(best.period_days - 4.0) < 0.05

    # Secondary eclipse depth at phase 0.5 must reflect the 0.004 dip
    assert best.secondary_eclipse_depth is not None
    assert abs(best.secondary_eclipse_depth - 0.004) < 0.001

    # Ratio of secondary depth to primary depth must be ~ 0.40 (> 0.10 threshold)
    ratio = best.secondary_eclipse_depth / best.depth
    assert ratio > 0.30

    classified = ClassifiedCandidate.model_construct(
        candidate=best,
        prediction=PredictionLabel.PLANET_CANDIDATE,
        planet_probability=0.90,
        model_name="test",
        model_version="1.0",
        feature_schema_version="1.1",
        features={},
    )
    val = validate_candidate(classified)

    # Must FAIL secondary eclipse check
    sec_rule = next(r for r in val.rules if r.rule_name == "secondary_eclipse")
    assert sec_rule.passed is False
    assert "Secondary eclipse depth ratio" in sec_rule.reason
    assert not val.is_valid_astrophysically


def test_missing_and_insufficient_data():
    """Verify missing secondary eclipse data is flagged as inconclusive without crashing."""
    # 1. Missing secondary eclipse depth
    cand = DetectionCandidate(
        light_curve_id=uuid4(),
        target_id="TIC_MISSING",
        mission=Mission.TESS,
        period_days=3.0,
        epoch_btjd=1.0,
        duration_hours=1.5,
        depth=0.01,
        bls_power=50.0,
        secondary_eclipse_depth=None,
        secondary_eclipse_power=None,
    )
    classified = ClassifiedCandidate.model_construct(
        candidate=cand,
        prediction=PredictionLabel.PLANET_CANDIDATE,
        planet_probability=0.85,
        model_name="test",
        model_version="1.0",
        feature_schema_version="1.1",
        features={},
    )
    val = validate_candidate(classified)
    sec_rule = next(r for r in val.rules if r.rule_name == "secondary_eclipse")
    assert sec_rule.is_missing_data is True
    assert val.validation_status == "INCONCLUSIVE"
    assert val.is_inconclusive is True

    # 2. Insufficient points in light curve (< 10 samples)
    short_lc = LightCurve(
        target_id="TIC_SHORT",
        mission=Mission.TESS,
        cadence=Cadence.SHORT,
        time=[1.0, 2.0, 3.0],
        flux=[1.0, 1.0, 1.0],
        time_unit="days",
        flux_unit="normalized",
    )
    detector = BLSDetector(min_period=1.0, max_period=5.0)
    assert detector.detect(short_lc) == []


def test_half_period_signal_not_mislabeled_as_secondary_eclipse():
    """Verify that a single-period transit signal (where depth_half is non-zero because folding at P/2 averages primary with flat baseline)
    is NOT mislabeled as having a secondary eclipse.
    """
    lc = generate_light_curve_fixture(primary_depth=0.010, secondary_depth=0.0)

    detector = BLSDetector(min_period=2.0, max_period=6.0)
    candidates = detector.detect(lc)
    assert len(candidates) > 0
    best = candidates[0]

    # Verify that half_period_depth (from depth_half at P/2) is ~ 0.005
    assert best.half_period_depth is not None
    assert abs(best.half_period_depth - 0.005) < 0.001

    # BUT secondary_eclipse_depth (from depth_phased at phase 0.5) must be 0.0!
    assert best.secondary_eclipse_depth == 0.0

    # Ensure validation evaluates secondary_eclipse_depth (0.0), NOT half_period_depth (0.005)
    classified = ClassifiedCandidate.model_construct(
        candidate=best,
        prediction=PredictionLabel.PLANET_CANDIDATE,
        planet_probability=0.92,
        model_name="test",
        model_version="1.0",
        feature_schema_version="1.1",
        features={},
    )
    val = validate_candidate(classified)
    sec_rule = next(r for r in val.rules if r.rule_name == "secondary_eclipse")
    assert sec_rule.passed is True
    assert "within threshold" in sec_rule.reason


def test_alternating_depth_detected_by_odd_even_not_mislabeled_as_secondary_eclipse():
    """Verify that when an alternating-depth binary is detected at half the orbital period (P=2.0 instead of P=4.0),
    the odd-even depth difference correctly catches the alternating depths, and secondary eclipse is not erroneously triggered.
    """
    lc = generate_light_curve_fixture(primary_depth=0.010, secondary_depth=0.004)

    # Let detector search from period 1.0; it will find the 2.0-day period (half the true orbit)
    detector = BLSDetector(min_period=1.0, max_period=3.0)
    candidates = detector.detect(lc)
    assert len(candidates) > 0
    best = candidates[0]

    # Period is ~ 2.0 days
    assert abs(best.period_days - 2.0) < 0.05

    # Odd-even depth difference is ~ 0.0057 (> 10% of 0.0066 depth)
    assert best.odd_even_depth_difference is not None
    assert best.odd_even_depth_difference > 0.003

    # At this folded 2.0-day period, phase 0.5 has no event, so secondary_eclipse_depth is effectively 0.0
    assert best.secondary_eclipse_depth < 1e-6


    classified = ClassifiedCandidate.model_construct(
        candidate=best,
        prediction=PredictionLabel.PLANET_CANDIDATE,
        planet_probability=0.90,
        model_name="test",
        model_version="1.0",
        feature_schema_version="1.1",
        features={},
    )
    val = validate_candidate(classified)

    # Odd-even rule must fail
    odd_even_rule = next(r for r in val.rules if r.rule_name == "odd_even")
    assert odd_even_rule.passed is False
    assert "Difference ratio" in odd_even_rule.reason

    # Secondary eclipse rule should pass at this 2.0-day period (it's caught by odd-even!)
    sec_rule = next(r for r in val.rules if r.rule_name == "secondary_eclipse")
    assert sec_rule.passed is True

