"""Unit tests for candidate-level signal matching and ephemeris verification."""

import pytest
from app.ml.signal_matcher import (
    CatalogEphemeris,
    MatchMethod,
    MatchStatus,
    SignalMatcher,
    compute_folded_phase_offset,
)


def test_folded_phase_offset_calculation():
    # Exactly in phase
    assert compute_folded_phase_offset(100.0, 100.0, 5.0) == 0.0
    # Exactly one full period offset
    assert compute_folded_phase_offset(105.0, 100.0, 5.0) == 0.0
    # Exactly half-orbit offset (phase 0.5)
    assert compute_folded_phase_offset(102.5, 100.0, 5.0) == 0.5
    # Small offset: 0.1 days on a 10-day orbit -> 0.01 phase
    assert pytest.approx(compute_folded_phase_offset(100.1, 100.0, 10.0), abs=1e-5) == 0.01
    # Negative time offset: -0.1 days on a 10-day orbit -> 0.01 phase folded
    assert pytest.approx(compute_folded_phase_offset(99.9, 100.0, 10.0), abs=1e-5) == 0.01


def test_signal_matcher_direct_match():
    matcher = SignalMatcher(period_tolerance=0.03, max_phase_offset=0.05)
    catalog = [
        CatalogEphemeris(
            toi_id="101.01",
            tic_id="12345",
            period_days=4.5000,
            epoch_bjd=2458300.2500,  # BTJD = 1300.2500
            duration_hours=2.5,
            disposition="CP",
        )
    ]

    # Detected BLS signal within 0.2% period and tiny epoch difference
    res = matcher.match_candidate(
        detected_period=4.5050,
        detected_epoch_btjd=1300.2530,
        detected_duration_hours=2.4,
        catalog_candidates=catalog,
    )

    assert res.is_matched is True
    assert res.match_status == MatchStatus.DIRECT_MATCH
    assert res.match_method == MatchMethod.FUNDAMENTAL_EPHEMERIS
    assert res.matched_toi_id == "101.01"
    assert res.matched_disposition == "CP"
    assert res.period_relative_error < 0.002
    assert res.epoch_phase_offset < 0.002
    assert res.exclusion_reason is None


def test_signal_matcher_half_period_harmonic():
    matcher = SignalMatcher(period_tolerance=0.03, max_phase_offset=0.05)
    catalog = [
        CatalogEphemeris(
            toi_id="202.01",
            tic_id="67890",
            period_days=8.0000,
            epoch_bjd=2458400.1000,  # BTJD = 1400.1000
            duration_hours=3.0,
            disposition="FP",
        )
    ]

    # BLS folded at half the period (P = 4.002 d ~ P_cat / 2)
    res = matcher.match_candidate(
        detected_period=4.0020,
        detected_epoch_btjd=1400.1020,
        detected_duration_hours=3.0,
        catalog_candidates=catalog,
    )

    assert res.is_matched is True
    assert res.match_status == MatchStatus.HARMONIC_HALF_MATCH
    assert res.match_method == MatchMethod.HALF_PERIOD_HARMONIC
    assert res.matched_toi_id == "202.01"
    assert res.matched_disposition == "FP"


def test_signal_matcher_double_period_harmonic():
    matcher = SignalMatcher(period_tolerance=0.03, max_phase_offset=0.05)
    catalog = [
        CatalogEphemeris(
            toi_id="303.01",
            tic_id="11122",
            period_days=3.0000,
            epoch_bjd=2458500.5000,  # BTJD = 1500.5000
            duration_hours=2.0,
            disposition="KP",
        )
    ]

    # BLS folded at double period (P = 6.005 d ~ 2 * P_cat)
    res = matcher.match_candidate(
        detected_period=6.0050,
        detected_epoch_btjd=1500.5020,
        detected_duration_hours=2.0,
        catalog_candidates=catalog,
    )

    assert res.is_matched is True
    assert res.match_status == MatchStatus.HARMONIC_DOUBLE_MATCH
    assert res.match_method == MatchMethod.DOUBLE_PERIOD_HARMONIC
    assert res.matched_toi_id == "303.01"


def test_signal_matcher_unmatched_period():
    matcher = SignalMatcher(period_tolerance=0.03, max_phase_offset=0.05)
    catalog = [
        CatalogEphemeris(
            toi_id="404.01",
            tic_id="33344",
            period_days=10.0000,
            epoch_bjd=2458600.0000,
            duration_hours=4.0,
            disposition="CP",
        )
    ]

    # Detected signal has period 7.2 days (completely unrelated)
    res = matcher.match_candidate(
        detected_period=7.2000,
        detected_epoch_btjd=1600.0000,
        detected_duration_hours=3.0,
        catalog_candidates=catalog,
    )

    assert res.is_matched is False
    assert res.match_status == MatchStatus.UNMATCHED_PERIOD
    assert "does not match closest catalog candidate" in res.exclusion_reason


def test_signal_matcher_unmatched_epoch_phase_mismatch():
    matcher = SignalMatcher(period_tolerance=0.03, max_phase_offset=0.04)
    catalog = [
        CatalogEphemeris(
            toi_id="505.01",
            tic_id="55566",
            period_days=5.0000,
            epoch_bjd=2458700.0000,  # BTJD = 1700.0000
            duration_hours=2.0,  # duration = 0.083 d, phase width = 0.0167
            disposition="CP",
        )
    ]

    # Period matches (5.001 d ~ 5.0 d), but epoch is 1701.25 d (phase offset = 0.25, a quarter of an orbit away!)
    res = matcher.match_candidate(
        detected_period=5.0010,
        detected_epoch_btjd=1701.2500,
        detected_duration_hours=2.0,
        catalog_candidates=catalog,
    )

    assert res.is_matched is False
    assert res.match_status == MatchStatus.UNMATCHED_EPOCH
    assert "phase offset" in res.exclusion_reason


def test_signal_matcher_multi_candidate_disambiguation():
    # Multi-candidate host star: Candidate .01 has P=3.5 d, Candidate .02 has P=9.2 d
    matcher = SignalMatcher(period_tolerance=0.03, max_phase_offset=0.05)
    catalog = [
        CatalogEphemeris(
            toi_id="606.01",
            tic_id="77788",
            period_days=3.5000,
            epoch_bjd=2458800.1000,  # BTJD = 1800.1000
            duration_hours=2.0,
            disposition="CP",
        ),
        CatalogEphemeris(
            toi_id="606.02",
            tic_id="77788",
            period_days=9.2000,
            epoch_bjd=2458802.3000,  # BTJD = 1802.3000
            duration_hours=3.5,
            disposition="FP",
        ),
    ]

    # BLS detected signal at P = 9.205 d
    res = matcher.match_candidate(
        detected_period=9.2050,
        detected_epoch_btjd=1802.3020,
        detected_duration_hours=3.4,
        catalog_candidates=catalog,
    )

    assert res.is_matched is True
    assert res.matched_toi_id == "606.02"  # Matches candidate .02!
    assert res.matched_disposition == "FP"
    assert res.match_status == MatchStatus.DIRECT_MATCH
