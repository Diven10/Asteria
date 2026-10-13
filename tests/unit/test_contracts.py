from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.contracts.models import (
    ClassifiedCandidate,
    DetectionCandidate,
    LightCurve,
    Mission,
    PredictionLabel,
)


def make_light_curve() -> LightCurve:
    return LightCurve(
        target_id="TIC-123",
        mission=Mission.TESS,
        time=[1.0, 1.1, 1.2],
        flux=[1.0, 0.99, 1.0],
    )


def make_candidate(light_curve: LightCurve) -> DetectionCandidate:
    return DetectionCandidate(
        light_curve_id=light_curve.light_curve_id,
        target_id=light_curve.target_id,
        mission=light_curve.mission,
        period_days=3.5,
        epoch_btjd=1.1,
        duration_hours=2.0,
        depth=0.01,
        bls_power=0.8,
        snr=10.0,
    )


def test_light_curve_requires_equal_series_lengths() -> None:
    with pytest.raises(ValidationError):
        LightCurve(
            target_id="TIC-123",
            mission=Mission.TESS,
            time=[1.0, 2.0],
            flux=[1.0],
        )


def test_detection_candidate_links_to_light_curve() -> None:
    light_curve = make_light_curve()
    candidate = make_candidate(light_curve)

    assert candidate.light_curve_id == light_curve.light_curve_id
    assert candidate.target_id == light_curve.target_id


def test_classified_candidate_accepts_probability_between_zero_and_one() -> None:
    light_curve = make_light_curve()
    candidate = make_candidate(light_curve)

    result = ClassifiedCandidate(
        candidate=candidate,
        prediction=PredictionLabel.PLANET_CANDIDATE,
        planet_probability=0.91,
        model_name="asteria-xgboost",
        model_version="0.1.0",
        feature_schema_version="1.0",
        features={"period_days": 3.5, "snr": 10.0},
    )

    assert result.planet_probability == 0.91


def test_classified_candidate_rejects_invalid_probability() -> None:
    light_curve = make_light_curve()
    candidate = make_candidate(light_curve)

    with pytest.raises(ValidationError):
        ClassifiedCandidate(
            candidate=candidate,
            prediction=PredictionLabel.PLANET_CANDIDATE,
            planet_probability=1.5,
            model_name="asteria-xgboost",
            model_version="0.1.0",
            feature_schema_version="1.0",
        )
