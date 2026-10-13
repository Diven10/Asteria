from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.contracts.models import Cadence, LightCurve, Mission
from app.ingestion.base import IngestionError


@dataclass(frozen=True, slots=True)
class TessIngestionConfig:
    """Configuration for TESS light-curve ingestion."""

    flux_column: str = "pdcsap_flux"
    quality_bitmask: str | int = "default"
    author: str | None = "SPOC"


def _load_lightkurve() -> Any:
    """Import Lightkurve lazily so the application remains importable without it."""
    try:
        import lightkurve as lk
    except ImportError as exc:
        raise IngestionError(
            "Lightkurve is required for TESS ingestion. "
            'Install with `pip install -e ".[dev]"`.'
        ) from exc
    return lk


def _as_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(numeric):
        return None
    return int(numeric)


def _as_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if np.isfinite(numeric) else None


def _infer_cadence(time_values: Any) -> Cadence:
    """Infer the coarse cadence class from median time spacing in days."""
    time = np.asarray(time_values, dtype=float)
    finite = time[np.isfinite(time)]
    if finite.size < 2:
        return Cadence.UNKNOWN

    differences = np.diff(finite)
    differences = differences[np.isfinite(differences) & (differences > 0)]
    if differences.size == 0:
        return Cadence.UNKNOWN

    median_days = float(np.median(differences))
    return Cadence.SHORT if median_days <= (5.0 / 1440.0) else Cadence.LONG


def _extract_target_id(light_curve: Any) -> str:
    candidates = [
        getattr(light_curve, "targetid", None),
        getattr(light_curve, "label", None),
    ]
    meta = getattr(light_curve, "meta", {}) or {}
    candidates.extend([meta.get("TARGETID"), meta.get("TICID"), meta.get("OBJECT")])

    for candidate in candidates:
        if candidate is not None and str(candidate).strip():
            return str(candidate).strip()

    raise IngestionError("TESS light curve does not contain a usable target identifier.")


def _extract_sector(light_curve: Any) -> int | None:
    sector = getattr(light_curve, "sector", None)
    if sector is None:
        sector = (getattr(light_curve, "meta", {}) or {}).get("SECTOR")
    return _as_optional_int(sector)


def _extract_time_unit(light_curve: Any) -> str:
    time = getattr(light_curve, "time", None)
    time_format = getattr(time, "format", None)
    if time_format is None:
        time_format = getattr(light_curve, "time_format", None)
    return str(time_format) if time_format else "unknown"


def _extract_flux_unit(light_curve: Any) -> str:
    flux = getattr(light_curve, "flux", None)
    unit = getattr(flux, "unit", None)
    if unit is None:
        unit = getattr(light_curve, "flux_unit", None)
    return str(unit) if unit else "unknown"


def _build_metadata(
    light_curve: Any,
    *,
    source: str,
    config: TessIngestionConfig,
    search_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta = getattr(light_curve, "meta", {}) or {}
    result: dict[str, Any] = {
        "source": source,
        "flux_column": config.flux_column,
        "quality_bitmask": config.quality_bitmask,
    }

    for key in (
        "AUTHOR", "TARGETID", "TICID", "SECTOR", "CAMERA", "CCD",
        "RA_OBJ", "DEC_OBJ", "TELESCOP", "MISSION", "FLUX_ORIGIN",
    ):
        value = meta.get(key)
        if value is not None:
            result[key.lower()] = (
                value if isinstance(value, (int, float, bool)) else str(value)
            )

    for attr, key in (("camera", "camera"), ("ccd", "ccd"), ("ra", "ra"), ("dec", "dec")):
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
    config: TessIngestionConfig,
    search_metadata: dict[str, Any] | None = None,
) -> LightCurve:
    time_obj = getattr(light_curve, "time")
    flux_obj = getattr(light_curve, "flux")
    time_values = np.asarray(getattr(time_obj, "value", time_obj), dtype=float)
    flux_values = np.asarray(getattr(flux_obj, "value", flux_obj), dtype=float)

    if time_values.ndim != 1 or flux_values.ndim != 1:
        raise IngestionError("TESS time and flux arrays must be one-dimensional.")
    if len(time_values) != len(flux_values):
        raise IngestionError("TESS time and flux arrays must have equal lengths.")
    flux_error = getattr(light_curve, "flux_err", None)
    flux_error_values = None
    if flux_error is not None:
        flux_error_values = np.asarray(getattr(flux_error, "value", flux_error), dtype=float)
        if flux_error_values.shape != flux_values.shape:
            raise IngestionError("TESS flux_err must have the same shape as flux.")

    # Filter out NaNs and Infs common in raw NASA TESS data products
    valid = np.isfinite(time_values) & np.isfinite(flux_values)
    time_values = time_values[valid]
    flux_values = flux_values[valid]
    if flux_error_values is not None:
        flux_error_values = flux_error_values[valid]
        if not np.all(np.isfinite(flux_error_values)):
            flux_error_values = np.nan_to_num(flux_error_values, nan=0.0, posinf=0.0, neginf=0.0)

    if len(time_values) < 2:
        raise IngestionError("TESS light curve must contain at least two valid finite samples.")

    mission_value = str(getattr(light_curve, "mission", "TESS")).upper()
    if mission_value != "TESS":
        raise IngestionError(
            f"TESS adapter received a non-TESS light curve: {mission_value!r}."
        )

    return LightCurve(
        target_id=_extract_target_id(light_curve),
        mission=Mission.TESS,
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


class TessIngestor:
    """Adapter for local TESS light curves and unambiguous MAST searches."""

    def __init__(self, config: TessIngestionConfig | None = None) -> None:
        self.config = config or TessIngestionConfig()

    def ingest_file(self, source: str | Path) -> LightCurve:
        source_string = str(source)
        if not source_string.strip():
            raise ValueError("TESS source cannot be empty.")

        path = Path(source_string)
        if not self._is_remote(source_string) and not path.is_file():
            raise FileNotFoundError(f"TESS light-curve file not found: {path}")

        lk = _load_lightkurve()
        native = None
        try:
            native = lk.read(
                source_string,
                flux_column=self.config.flux_column,
                quality_bitmask=self.config.quality_bitmask,
            )
            if hasattr(native, "to_lightcurve"):
                try:
                    native = native.to_lightcurve(aperture_mask="pipeline")
                except Exception:
                    native = native.to_lightcurve()
        except Exception:
            try:
                from lightkurve.lightcurve import TessLightCurve
                native = TessLightCurve.read(
                    source_string,
                    format="tess",
                    flux_column=self.config.flux_column,
                    quality_bitmask=self.config.quality_bitmask,
                )
            except Exception:
                try:
                    tpf = lk.read(source_string)
                    if hasattr(tpf, "to_lightcurve"):
                        native = tpf.to_lightcurve()
                except Exception:
                    pass

        if native is not None and hasattr(native, "time") and hasattr(native, "flux"):
            return _to_contract(native, source=source_string, config=self.config)

        # Direct Astropy FITS Fallback for custom, simulated, or temp FITS files
        try:
            from astropy.io import fits
            with fits.open(source_string) as hdul:
                table_hdu = None
                for hdu in hdul:
                    if (hasattr(hdu, "columns") and hdu.columns is not None) or (
                        hasattr(hdu, "data") and hdu.data is not None and hasattr(hdu.data, "names")
                    ):
                        table_hdu = hdu
                        break
                
                if table_hdu is None:
                    # Check if this is an image HDU with 3D cube (time, y, x)
                    for hdu in hdul:
                        if hasattr(hdu, "data") and hdu.data is not None and isinstance(hdu.data, np.ndarray):
                            if hdu.data.ndim == 3 and hdu.data.shape[0] > 10:
                                flux_series = np.nanmean(hdu.data, axis=(1, 2))
                                time_series = np.arange(len(flux_series), dtype=float) * (2.0 / 1440.0)
                                hdr = hdul[0].header
                                target_id = str(hdr.get("TICID") or hdr.get("OBJECT") or hdr.get("TARGETID") or Path(source_string).stem)
                                return LightCurve(
                                    target_id=target_id,
                                    mission=Mission.TESS,
                                    sector=int(hdr.get("SECTOR", 1)) if str(hdr.get("SECTOR", 1)).isdigit() else 1,
                                    cadence=Cadence.SHORT,
                                    time=time_series.tolist(),
                                    flux=flux_series.tolist(),
                                    flux_error=None,
                                    time_unit="btjd",
                                    flux_unit="electrons/s",
                                    metadata={"source": source_string, "flux_column": "CUBE_APER_MEAN"}
                                )
                    
                    # 2D Image or unrecognized FITS
                    raise IngestionError(
                        "Uploaded FITS contains 2D Astronomical Image data rather than timeseries light curve data. "
                        "Exoplanet transit detection requires observation flux over time (a '_lc.fits' light curve file). "
                        "Please download the Light Curve ('_lc.fits') file from NASA, or use our 1-click sample file on this page."
                    )
                
                col_names = []
                if hasattr(table_hdu, "columns") and table_hdu.columns is not None:
                    col_names = table_hdu.columns.names
                elif hasattr(table_hdu.data, "names"):
                    col_names = list(table_hdu.data.names)
                    
                cols = {name.upper(): name for name in col_names}
                time_col = cols.get("TIME") or cols.get("BJD") or cols.get("BTJD") or cols.get("HJD") or cols.get("CADENCENO")
                flux_col = (
                    cols.get(self.config.flux_column.upper())
                    or cols.get("PDCSAP_FLUX")
                    or cols.get("SAP_FLUX")
                    or cols.get("FLUX")
                    or cols.get("CORR_FLUX")
                    or cols.get("CAL_FLUX")
                    or cols.get("RAW_FLUX")
                )
                err_col = (
                    cols.get(f"{self.config.flux_column.upper()}_ERR")
                    or cols.get("PDCSAP_FLUX_ERR")
                    or cols.get("SAP_FLUX_ERR")
                    or cols.get("FLUX_ERR")
                    or cols.get("ERR")
                )
                
                if not time_col or not flux_col:
                    raise IngestionError(f"FITS file table must contain TIME and FLUX columns. Found: {list(cols.keys())}")
                
                time_arr = np.asarray(table_hdu.data[time_col], dtype=float)
                flux_arr = np.asarray(table_hdu.data[flux_col], dtype=float)
                
                # If flux is multi-dimensional (e.g. Target Pixel File image stamps), average spatial pixels
                if flux_arr.ndim > 1:
                    flux_arr = np.nanmean(flux_arr, axis=tuple(range(1, flux_arr.ndim)))
                    
                err_arr = None
                if err_col:
                    err_arr = np.asarray(table_hdu.data[err_col], dtype=float)
                    if err_arr.ndim > 1:
                        err_arr = np.nanmean(err_arr, axis=tuple(range(1, err_arr.ndim)))
                
                hdr = hdul[0].header
                target_id = str(hdr.get("TICID") or hdr.get("OBJECT") or hdr.get("TARGETID") or Path(source_string).stem)
                sector = hdr.get("SECTOR", 1)
                
                return LightCurve(
                    target_id=target_id,
                    mission=Mission.TESS,
                    sector=int(sector) if str(sector).isdigit() else 1,
                    cadence=_infer_cadence(time_arr),
                    time=time_arr.tolist(),
                    flux=flux_arr.tolist(),
                    flux_error=err_arr.tolist() if err_arr is not None else None,
                    time_unit="btjd",
                    flux_unit="electrons/s",
                    metadata={"source": source_string, "flux_column": flux_col}
                )
        except IngestionError:
            raise
        except Exception as exc:
            raise IngestionError(f"Failed to read TESS light curve from {source_string!r}: {exc}") from exc

    def search_and_download(
        self,
        target: str | int,
        *,
        sector: int | None = None,
        exptime: str | float | int | None = None,
        download_dir: str | Path | None = None,
    ) -> LightCurve:
        if sector is not None and sector < 1:
            raise ValueError("TESS sector must be a positive integer.")

        lk = _load_lightkurve()
        kwargs: dict[str, Any] = {"mission": "TESS", "author": self.config.author}
        if sector is not None:
            kwargs["sector"] = sector
        if exptime is not None:
            kwargs["exptime"] = exptime

        try:
            results = lk.search_lightcurve(target, **kwargs)
        except Exception as exc:
            raise IngestionError(
                f"TESS archive search failed for target {target!r}: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

        count = len(results)
        if count == 0:
            raise IngestionError(f"No TESS light-curve products found for target {target!r}.")
        if count > 1:
            raise IngestionError(
                f"TESS archive search returned {count} products for target {target!r}. "
                "Specify sector/exptime/author more narrowly."
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
                f"Failed to download TESS product for target {target!r}: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

        archive_metadata: dict[str, Any] = {}
        for attribute, key in (("author", "author"), ("sector", "sector")):
            values = getattr(results, attribute, None)
            if values is not None:
                try:
                    value = values[0]
                    value = value.item() if hasattr(value, "item") else value
                    archive_metadata[key] = (
                        _as_optional_int(value) if key == "sector" else str(value)
                    )
                except (IndexError, TypeError, ValueError):
                    pass

        exptime_values = getattr(results, "exptime", None)
        if exptime_values is not None:
            try:
                archive_metadata["exptime_seconds"] = float(exptime_values[0].value)
            except (AttributeError, TypeError, ValueError, IndexError):
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
