# ASTERIA — Clean Phase 0 + Phase 1A/1B Replacement

This package combines the verified Phase 0 scaffold with the Phase 1A TIC/CTL and Phase 1B TESS ingestion overlay.

## Install and verify

```bash
cd ~/Desktop/Asteria
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest
```

Expected result after a clean install: **21 passed**.

Real STScI catalog and real TESS FITS validation are still required before Phase 1 is scientifically closed.
