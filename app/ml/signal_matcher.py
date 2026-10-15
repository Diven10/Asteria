"""Candidate-level signal matching for exoplanet transit detections.

Compares detected Box Least Squares (BLS) signals against authoritative ephemerides
from astronomical catalogs (e.g. NASA Exoplanet Archive TOI). Handles period harmonics
(P/2, 2P) and phase/epoch consistency, preventing unverified or misidentified signal
labelling.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, List, Optional


class MatchStatus(str, Enum):
    """Categorical classification of candidate ephemeris matching."""

    DIRECT_MATCH = "DIRECT_MATCH"
    HARMONIC_HALF_MATCH = "HARMONIC_HALF_MATCH"
    HARMONIC_DOUBLE_MATCH = "HARMONIC_DOUBLE_MATCH"
    UNMATCHED_EPOCH = "UNMATCHED_EPOCH"
    UNMATCHED_PERIOD = "UNMATCHED_PERIOD"
    UNMATCHED_NO_DETECTION = "UNMATCHED_NO_DETECTION"
    MULTI_CANDIDATE_AMBIGUOUS = "MULTI_CANDIDATE_AMBIGUOUS"


class MatchMethod(str, Enum):
    """Method utilized to verify signal identity."""

    FUNDAMENTAL_EPHEMERIS = "FUNDAMENTAL_EPHEMERIS"
    HALF_PERIOD_HARMONIC = "HALF_PERIOD_HARMONIC"
    DOUBLE_PERIOD_HARMONIC = "DOUBLE_PERIOD_HARMONIC"
    NONE = "NONE"


@dataclass
class CatalogEphemeris:
    """Authoritative transit ephemeris for a specific planet candidate."""

    toi_id: str
    tic_id: str
    period_days: float
    epoch_bjd: float
    duration_hours: Optional[float] = None
    depth_ppm: Optional[float] = None
    disposition: str = "UNKNOWN"

    @property
    def epoch_btjd(self) -> float:
        """Converts BJD to BTJD if epoch is in standard Julian Date format."""
        if self.epoch_bjd > 2450000.0:
            return self.epoch_bjd - 2457000.0
        return self.epoch_bjd


@dataclass
class SignalMatchResult:
    """Outcome of ephemeris comparison between BLS candidate and catalog."""

    is_matched: bool
    match_status: MatchStatus
    match_method: MatchMethod
    matched_toi_id: Optional[str] = None
    matched_disposition: Optional[str] = None
    detected_period: Optional[float] = None
    catalog_period: Optional[float] = None
    period_relative_error: Optional[float] = None
    detected_epoch_btjd: Optional[float] = None
    catalog_epoch_btjd: Optional[float] = None
    epoch_phase_offset: Optional[float] = None
    exclusion_reason: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_matched": self.is_matched,
            "match_status": self.match_status.value,
            "match_method": self.match_method.value,
            "matched_toi_id": self.matched_toi_id,
            "matched_disposition": self.matched_disposition,
            "detected_period": self.detected_period,
            "catalog_period": self.catalog_period,
            "period_relative_error": self.period_relative_error,
            "detected_epoch_btjd": self.detected_epoch_btjd,
            "catalog_epoch_btjd": self.catalog_epoch_btjd,
            "epoch_phase_offset": self.epoch_phase_offset,
            "exclusion_reason": self.exclusion_reason,
        }


def compute_folded_phase_offset(
    detected_epoch_btjd: float,
    catalog_epoch_btjd: float,
    period_days: float,
) -> float:
    """Computes the absolute folded phase offset on [-0.5, 0.5] between two epochs."""
    if period_days <= 0:
        return 1.0
    phase_diff = (detected_epoch_btjd - catalog_epoch_btjd) % period_days
    norm_phase = phase_diff / period_days
    # Fold to [-0.5, 0.5] interval
    return abs(((norm_phase + 0.5) % 1.0) - 0.5)


class SignalMatcher:
    """Matches detected BLS transit candidates against catalog ephemerides."""

    def __init__(
        self,
        period_tolerance: float = 0.03,  # 3% relative error tolerance
        max_phase_offset: float = 0.05,  # 5% phase offset tolerance
    ):
        self.period_tolerance = period_tolerance
        self.max_phase_offset = max_phase_offset

    def match_candidate(
        self,
        detected_period: float,
        detected_epoch_btjd: float,
        detected_duration_hours: Optional[float],
        catalog_candidates: List[CatalogEphemeris],
    ) -> SignalMatchResult:
        """Compares a detected BLS signal against one or more catalog candidates."""
        if not catalog_candidates:
            return SignalMatchResult(
                is_matched=False,
                match_status=MatchStatus.UNMATCHED_PERIOD,
                match_method=MatchMethod.NONE,
                detected_period=detected_period,
                detected_epoch_btjd=detected_epoch_btjd,
                exclusion_reason="No catalog candidates available for target.",
            )

        matches: List[SignalMatchResult] = []

        for cat in catalog_candidates:
            cat_period = cat.period_days
            cat_epoch = cat.epoch_btjd
            if cat_period is None or cat_period <= 0 or cat_epoch is None:
                continue

            # Calculate adaptive phase tolerance based on transit duration
            duration = cat.duration_hours or detected_duration_hours or 2.0
            phase_width = (duration / 24.0) / cat_period
            adaptive_phase_tol = max(self.max_phase_offset, 1.5 * phase_width)

            # 1. Direct Fundamental Match
            rel_err_fund = abs(detected_period - cat_period) / cat_period
            phase_offset_fund = compute_folded_phase_offset(
                detected_epoch_btjd, cat_epoch, cat_period
            )

            if rel_err_fund <= self.period_tolerance:
                if phase_offset_fund <= adaptive_phase_tol:
                    matches.append(
                        SignalMatchResult(
                            is_matched=True,
                            match_status=MatchStatus.DIRECT_MATCH,
                            match_method=MatchMethod.FUNDAMENTAL_EPHEMERIS,
                            matched_toi_id=cat.toi_id,
                            matched_disposition=cat.disposition,
                            detected_period=detected_period,
                            catalog_period=cat_period,
                            period_relative_error=rel_err_fund,
                            detected_epoch_btjd=detected_epoch_btjd,
                            catalog_epoch_btjd=cat_epoch,
                            epoch_phase_offset=phase_offset_fund,
                        )
                    )
                    continue
                else:
                    # Period matched but phase is off
                    matches.append(
                        SignalMatchResult(
                            is_matched=False,
                            match_status=MatchStatus.UNMATCHED_EPOCH,
                            match_method=MatchMethod.NONE,
                            matched_toi_id=cat.toi_id,
                            matched_disposition=cat.disposition,
                            detected_period=detected_period,
                            catalog_period=cat_period,
                            period_relative_error=rel_err_fund,
                            detected_epoch_btjd=detected_epoch_btjd,
                            catalog_epoch_btjd=cat_epoch,
                            epoch_phase_offset=phase_offset_fund,
                            exclusion_reason=(
                                f"Period matches TOI-{cat.toi_id} ({cat_period:.4f} d), "
                                f"but phase offset {phase_offset_fund:.4f} exceeds tolerance {adaptive_phase_tol:.4f}."
                            ),
                        )
                    )
                    continue

            # 2. Half-Period Harmonic Match (BLS folded at P/2)
            half_cat_period = cat_period / 2.0
            rel_err_half = abs(detected_period - half_cat_period) / half_cat_period
            phase_offset_half = compute_folded_phase_offset(
                detected_epoch_btjd, cat_epoch, half_cat_period
            )

            if rel_err_half <= self.period_tolerance:
                if phase_offset_half <= adaptive_phase_tol:
                    matches.append(
                        SignalMatchResult(
                            is_matched=True,
                            match_status=MatchStatus.HARMONIC_HALF_MATCH,
                            match_method=MatchMethod.HALF_PERIOD_HARMONIC,
                            matched_toi_id=cat.toi_id,
                            matched_disposition=cat.disposition,
                            detected_period=detected_period,
                            catalog_period=cat_period,
                            period_relative_error=rel_err_half,
                            detected_epoch_btjd=detected_epoch_btjd,
                            catalog_epoch_btjd=cat_epoch,
                            epoch_phase_offset=phase_offset_half,
                        )
                    )
                    continue
                else:
                    matches.append(
                        SignalMatchResult(
                            is_matched=False,
                            match_status=MatchStatus.UNMATCHED_EPOCH,
                            match_method=MatchMethod.NONE,
                            matched_toi_id=cat.toi_id,
                            matched_disposition=cat.disposition,
                            detected_period=detected_period,
                            catalog_period=cat_period,
                            period_relative_error=rel_err_half,
                            detected_epoch_btjd=detected_epoch_btjd,
                            catalog_epoch_btjd=cat_epoch,
                            epoch_phase_offset=phase_offset_half,
                            exclusion_reason=(
                                f"Half-period matches TOI-{cat.toi_id} ({half_cat_period:.4f} d), "
                                f"but phase offset {phase_offset_half:.4f} exceeds tolerance {adaptive_phase_tol:.4f}."
                            ),
                        )
                    )
                    continue

            # 3. Double-Period Harmonic Match (BLS folded at 2P)
            double_cat_period = cat_period * 2.0
            rel_err_double = abs(detected_period - double_cat_period) / double_cat_period
            phase_offset_double = compute_folded_phase_offset(
                detected_epoch_btjd, cat_epoch, cat_period
            )

            if rel_err_double <= self.period_tolerance:
                if phase_offset_double <= adaptive_phase_tol:
                    matches.append(
                        SignalMatchResult(
                            is_matched=True,
                            match_status=MatchStatus.HARMONIC_DOUBLE_MATCH,
                            match_method=MatchMethod.DOUBLE_PERIOD_HARMONIC,
                            matched_toi_id=cat.toi_id,
                            matched_disposition=cat.disposition,
                            detected_period=detected_period,
                            catalog_period=cat_period,
                            period_relative_error=rel_err_double,
                            detected_epoch_btjd=detected_epoch_btjd,
                            catalog_epoch_btjd=cat_epoch,
                            epoch_phase_offset=phase_offset_double,
                        )
                    )
                    continue
                else:
                    matches.append(
                        SignalMatchResult(
                            is_matched=False,
                            match_status=MatchStatus.UNMATCHED_EPOCH,
                            match_method=MatchMethod.NONE,
                            matched_toi_id=cat.toi_id,
                            matched_disposition=cat.disposition,
                            detected_period=detected_period,
                            catalog_period=cat_period,
                            period_relative_error=rel_err_double,
                            detected_epoch_btjd=detected_epoch_btjd,
                            catalog_epoch_btjd=cat_epoch,
                            epoch_phase_offset=phase_offset_double,
                            exclusion_reason=(
                                f"Double-period matches TOI-{cat.toi_id} ({double_cat_period:.4f} d), "
                                f"but phase offset {phase_offset_double:.4f} exceeds tolerance {adaptive_phase_tol:.4f}."
                            ),
                        )
                    )
                    continue

        # Evaluate collected matches
        successful_matches = [m for m in matches if m.is_matched]

        if len(successful_matches) == 1:
            return successful_matches[0]

        if len(successful_matches) > 1:
            # Sort by lowest period error and lowest phase offset
            successful_matches.sort(
                key=lambda m: (m.period_relative_error or 1.0) + (m.epoch_phase_offset or 1.0)
            )
            # If the best match is significantly better than second, select it
            best = successful_matches[0]
            second = successful_matches[1]
            if (best.period_relative_error or 0) < 0.5 * (second.period_relative_error or 1.0):
                return best
            return SignalMatchResult(
                is_matched=False,
                match_status=MatchStatus.MULTI_CANDIDATE_AMBIGUOUS,
                match_method=MatchMethod.NONE,
                detected_period=detected_period,
                detected_epoch_btjd=detected_epoch_btjd,
                exclusion_reason=(
                    f"Ambiguous match across multiple catalog candidates: "
                    f"TOI-{best.matched_toi_id} vs TOI-{second.matched_toi_id}."
                ),
            )

        # If any candidate matched period but failed epoch, report that failure
        epoch_mismatches = [m for m in matches if m.match_status == MatchStatus.UNMATCHED_EPOCH]
        if epoch_mismatches:
            return epoch_mismatches[0]

        # No match found
        closest = min(
            catalog_candidates,
            key=lambda c: abs(detected_period - c.period_days) if c.period_days else 999.0,
        )
        return SignalMatchResult(
            is_matched=False,
            match_status=MatchStatus.UNMATCHED_PERIOD,
            match_method=MatchMethod.NONE,
            detected_period=detected_period,
            detected_epoch_btjd=detected_epoch_btjd,
            catalog_period=closest.period_days,
            exclusion_reason=(
                f"Detected period {detected_period:.4f} d does not match closest "
                f"catalog candidate TOI-{closest.toi_id} ({closest.period_days} d) within {self.period_tolerance * 100:.1f}%."
            ),
        )
