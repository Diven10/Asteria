"""Shared ASTERIA pipeline contracts.

These models are the stable boundary between Dev's ML pipeline and Prem's
validation/ranking/API modules. Keep them domain-oriented and dependency-light.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Annotated, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]
Probability = Annotated[float, Field(ge=0.0, le=1.0)]
PositiveFloat = Annotated[float, Field(gt=0.0, allow_inf_nan=False)]
NonNegativeFloat = Annotated[float, Field(ge=0.0, allow_inf_nan=False)]


class Mission(str, Enum):
    """Mission/source supported by the common ingestion contract."""

    TESS = "TESS"
    KEPLER = "KEPLER"
    PLATO_SYNTHETIC = "PLATO_SYNTHETIC"
    OTHER = "OTHER"


class Cadence(str, Enum):
    """Nominal cadence family; exact cadence can remain in metadata."""

    SHORT = "SHORT"
    LONG = "LONG"
    UNKNOWN = "UNKNOWN"


class PredictionLabel(str, Enum):
    PLANET_CANDIDATE = "planet_candidate"
    NON_PLANET = "non_planet"


class ContractBase(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class LightCurve(ContractBase):
    """Common light-curve representation shared by ingestion and all consumers.

    Raw ingestion may contain NaN/Inf values because real FITS products can be
    incomplete. Preprocessing is responsible for cleaning them before BLS.
    """

    schema_version: str = "1.0"
    light_curve_id: UUID = Field(default_factory=uuid4)
    target_id: str = Field(min_length=1, description="Mission/catalog target identifier")
    mission: Mission
    sector: int | None = Field(default=None, ge=0)
    cadence: Cadence = Cadence.UNKNOWN
    time: list[FiniteFloat]
    flux: list[float]
    flux_error: list[FiniteFloat] | None = None
    time_unit: str = "BTJD"
    flux_unit: str = "normalized"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_series_lengths(self) -> "LightCurve":
        if len(self.time) != len(self.flux):
            raise ValueError("time and flux must have identical lengths")
        if self.flux_error is not None and len(self.flux_error) != len(self.flux):
            raise ValueError("flux_error must have the same length as flux")
        if len(self.time) < 2:
            raise ValueError("light curve must contain at least two samples")
        return self


class DetectionCandidate(ContractBase):
    """Output of transit detection/feature extraction before ML classification."""

    schema_version: str = "1.0"
    candidate_id: UUID = Field(default_factory=uuid4)
    light_curve_id: UUID
    target_id: str = Field(min_length=1)
    mission: Mission

    # BLS-derived transit parameters.
    period_days: PositiveFloat
    epoch_btjd: FiniteFloat
    duration_hours: PositiveFloat
    depth: NonNegativeFloat
    bls_power: NonNegativeFloat

    # Screening/feature values available before classification.
    snr: NonNegativeFloat | None = None
    transit_count: int = Field(default=0, ge=0)
    odd_even_depth_difference: NonNegativeFloat | None = None
    secondary_eclipse_depth: NonNegativeFloat | None = None
    secondary_eclipse_power: NonNegativeFloat | None = None
    half_period_depth: NonNegativeFloat | None = None

    # Optional astrophysical context; catalog lookup may populate these later.
    stellar_radius_solar: PositiveFloat | None = None
    stellar_mass_solar: PositiveFloat | None = None
    stellar_teff_k: PositiveFloat | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _sync_secondary_depth_and_power(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if data.get("secondary_eclipse_depth") is not None and data.get("secondary_eclipse_power") is None:
                data["secondary_eclipse_power"] = data["secondary_eclipse_depth"]
            elif data.get("secondary_eclipse_power") is not None and data.get("secondary_eclipse_depth") is None:
                data["secondary_eclipse_depth"] = data["secondary_eclipse_power"]
        return data

    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)
        if name == "secondary_eclipse_power" and hasattr(self, "__dict__"):
            if self.__dict__.get("secondary_eclipse_depth") != value:
                super().__setattr__("secondary_eclipse_depth", value)
        elif name == "secondary_eclipse_depth" and hasattr(self, "__dict__"):
            if self.__dict__.get("secondary_eclipse_power") != value:
                super().__setattr__("secondary_eclipse_power", value)




class ClassifiedCandidate(ContractBase):
    """ML handoff from Dev to Prem.

    Prem can consume this object without knowing the classifier internals.
    The feature mapping is retained for SHAP and auditability, while the model
    identity/version makes predictions reproducible.
    """

    schema_version: str = "1.0"
    candidate: DetectionCandidate
    prediction: PredictionLabel
    planet_probability: Probability
    model_name: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    feature_schema_version: str = Field(min_length=1)
    features: dict[str, float | None] = Field(default_factory=dict)
    predicted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)
