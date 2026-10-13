from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.contracts.models import Cadence, LightCurve, Mission
from app.ingestion.base import IngestionError

# Reuse standard helpers from tess.py
from app.ingestion.tess import (
    _load_lightkurve,
    _as_optional_int,
    _as_optional_float,
    _infer_cadence,
    _extract_time_unit,
    _extract_flux_unit,
)


@dataclass(frozen=True, slots=True)
class KeplerIngestionConfig:
    """Configuration for Kepler/K2 light-curve ingestion."""

    flux_column: str = "pdcsap_flux"
    quality_bitmask: str | int = "default"
    author: str | None = "Kepler"


def _extract_target_id(light_curve: Any) -> str:
    candidates = [
        getattr(light_curve, "targetid", None),
        getattr(light_curve, "label", None),
    ]
    meta = getattr(light_curve, "meta", {}) or {}
    candidates.extend([meta.get("TARGETID"), meta.get("KEPLERID"), meta.get("OBJECT")])

    for candidate in candidates:
        if candidate is not None and str(candidate).strip():
            return str(candidate).strip()

    raise IngestionError("Kepler light curve does not contain a usable target identifier.")


def _extract_sector(light_curve: Any) -> int | None:
    # Kepler has Quarters, K2 has Campaigns. We map them to the generic "sector" field.
    sector = getattr(light_curve, "quarter", None)
    if sector is None:
        sector = getattr(light_curve, "campaign", None)
    if sector is None:
        meta = getattr(light_curve, "meta", {}) or {}
        sector = meta.get("QUARTER", meta.get("CAMPAIGN"))
    return _as_optional_int(sector)


def _build_metadata(
    light_curve: Any,
    *,
    source: str,
    config: KeplerIngestionConfig,
    search_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta = getattr(light_curve, "meta", {}) or {}
    result: dict[str, Any] = {
        "source": source,
        "flux_column": config.flux_column,
        "quality_bitmask": config.quality_bitmask,
    }

    for key in (
        "AUTHOR", "TARGETID", "KEPLERID", "QUARTER", "CAMPAIGN", "CHANNEL", "MODULE", "OUTPUT",
        "RA_OBJ", "DEC_OBJ", "TELESCOP", "MISSION", "FLUX_ORIGIN",
    ):
        value = meta.get(key)
        if value is not None:
            result[key.lower()] = (
                value if isinstance(value, (int, float, bool)) else str(value)
            )

    for attr, key in (("channel", "channel"), ("module", "module"), ("ra", "ra"), ("dec", "dec")):
        value = getattr(light_curve, attr, None)
        if value is not None:
            result[key] = (
                _as_optional_float(value)
                if key in {"ra", "dec"}
                else _as_optional_int(value)
            )

    if search_metadata:
        result["archive"] = search_metadata
    return result


def _to_contract(
    light_curve: Any,
    *,
    source: str,
    config: KeplerIngestionConfig,
    search_metadata: dict[str, Any] | None = None,
) -> LightCurve:
    time_obj = getattr(light_curve, "time")
    flux_obj = getattr(light_curve, "flux")
    time_values = np.asarray(getattr(time_obj, "value", time_obj), dtype=float)
    flux_values = np.asarray(getattr(flux_obj, "value", flux_obj), dtype=float)

    if time_values.ndim != 1 or flux_values.ndim != 1:
        raise IngestionError("Kepler time and flux arrays must be one-dimensional.")
    if len(time_values) != len(flux_values):
        raise IngestionError("Kepler time and flux arrays must have equal lengths.")
    if len(time_values) < 2:
        raise IngestionError("Kepler light curve must contain at least two samples.")

    flux_error = getattr(light_curve, "flux_err", None)
    flux_error_values = None
    if flux_error is not None:
        flux_error_values = np.asarray(getattr(flux_error, "value", flux_error), dtype=float)
        if flux_error_values.shape != flux_values.shape:
            raise IngestionError("Kepler flux_err must have the same shape as flux.")

    mission_value = str(getattr(light_curve, "mission", "KEPLER")).upper()
    if mission_value not in ("KEPLER", "K2"):
        raise IngestionError(
            f"Kepler adapter received a non-Kepler/K2 light curve: {mission_value!r}."
        )

    return LightCurve(
        target_id=_extract_target_id(light_curve),
        mission=Mission.KEPLER,
        sector=_extract_sector(light_curve),
        cadence=_infer_cadence(time_values),
        time=time_values.tolist(),
        flux=flux_values.tolist(),
        flux_error=None if flux_error_values is None else flux_error_values.tolist(),
        time_unit=_extract_time_unit(light_curve),
        flux_unit=_extract_flux_unit(light_curve),
        metadata=_build_metadata(
            light_curve,
            source=source,
            config=config,
            search_metadata=search_metadata,
        ),
    )


class KeplerIngestor:
    """Adapter for local Kepler light curves and unambiguous MAST searches."""

    def __init__(self, config: KeplerIngestionConfig | None = None) -> None:
        self.config = config or KeplerIngestionConfig()

    def ingest_file(self, source: str | Path) -> LightCurve:
        source_string = str(source)
        if not source_string.strip():
            raise ValueError("Kepler source cannot be empty.")

        path = Path(source_string)
        if not self._is_remote(source_string) and not path.is_file():
            raise FileNotFoundError(f"Kepler light-curve file not found: {path}")

        lk = _load_lightkurve()
        try:
            native = lk.read(
                source_string,
                flux_column=self.config.flux_column,
                quality_bitmask=self.config.quality_bitmask,
            )
        except Exception as exc:
            raise IngestionError(
                f"Failed to read Kepler light curve from {source_string!r}: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

        return _to_contract(native, source=source_string, config=self.config)

    def search_and_download(
        self,
        target: str | int,
        *,
        quarter: int | None = None,
        campaign: int | None = None,
        exptime: str | float | int | None = None,
        download_dir: str | Path | None = None,
    ) -> LightCurve:
        lk = _load_lightkurve()
        kwargs: dict[str, Any] = {"mission": ("Kepler", "K2"), "author": self.config.author}
        if quarter is not None:
            kwargs["quarter"] = quarter
        if campaign is not None:
            kwargs["campaign"] = campaign
        if exptime is not None:
            kwargs["exptime"] = exptime

        try:
            results = lk.search_lightcurve(target, **kwargs)
        except Exception as exc:
            raise IngestionError(
                f"Kepler archive search failed for target {target!r}: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

        count = len(results)
        if count == 0:
            raise IngestionError(f"No Kepler light-curve products found for target {target!r}.")
        if count > 1:
            raise IngestionError(
                f"Kepler archive search returned {count} products for target {target!r}. "
                "Specify quarter/campaign/author more narrowly."
            )

        download_kwargs: dict[str, Any] = {
            "quality_bitmask": self.config.quality_bitmask
        }
        if download_dir is not None:
            download_kwargs["download_dir"] = str(download_dir)

        try:
            native = results[0].download(**download_kwargs)
        except Exception as exc:
            raise IngestionError(
                f"Failed to download Kepler product for target {target!r}: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

        archive_metadata: dict[str, Any] = {}
        for attribute, key in (("author", "author"), ("quarter", "quarter"), ("campaign", "campaign")):
            values = getattr(results, attribute, None)
            if values is not None:
                try:
                    value = values[0]
                    value = value.item() if hasattr(value, "item") else value
                    archive_metadata[key] = (
                        _as_optional_int(value) if key in ("quarter", "campaign") else str(value)
                    )
                except (IndexError, TypeError, ValueError):
                    pass

        return _to_contract(
            native,
            source=f"MAST:{target}",
            config=self.config,
            search_metadata=archive_metadata,
        )

    @staticmethod
    def _is_remote(source: str) -> bool:
        return source.lower().startswith(("http://", "https://", "s3://"))
