# ASTERIA Phase 1 — Data Sources and Ingestion

## Phase 1A — TIC/CTL ingestion

Responsibility:

- Read locally downloaded STScI TIC/CTL CSV or CSV.GZ files.
- Stream rows instead of loading multi-GB catalogs into memory.
- Normalize the TIC identifier.
- Expose core stellar metadata needed by later host-star characterization.
- Preserve the complete source row in `CatalogRecord.raw`.
- Never interpret CTL membership as a planet label.

The STScI TIC/CTL distribution is the source of catalog metadata. The current
STScI page lists Exoplanet CTL v08.01 ("xCTL") at about 497 MB and an xCTL
cross-matched with TIC v8.1 at about 9.5 GB. TIC is distributed in
declination-binned CSV.GZ files.

## Phase 1B — TESS light-curve ingestion

Responsibility:

- Read TESS FITS products through Lightkurve.
- Convert them into the shared `LightCurve` contract.
- Preserve native time/flux arrays and metadata.
- Support unambiguous MAST search/download.
- Reject ambiguous archive results rather than silently selecting one.

## Explicit boundary

Phase 1 does not:

- detrend
- normalize flux
- sigma clip
- interpolate gaps
- filter noise
- run BLS
- generate labels
- train a model

Those belong to later phases.

## Definition of Done

- Phase 0 tests remain green.
- TIC/CTL plain CSV and CSV.GZ tests pass.
- TESS adapter tests pass.
- Python compilation passes.
- Real STScI catalog and real TESS FITS validation are performed on the
  developer machine before Phase 1 is closed.
