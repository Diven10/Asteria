# TIC/CTL catalog ingestion

Phase 1A treats the STScI TIC/CTL distribution as a **source catalog**. It
does not treat CTL membership as a planet label.

The reader supports plain `.csv` and compressed `.csv.gz` files and streams
rows so a multi-GB TIC file does not have to be loaded into RAM.

For the current STScI distribution, the Exoplanet CTL v08.01 is available as
a ~497 MB CSV. STScI also publishes a 9.5 GB xCTL file cross-matched with TIC
v8.1, while TIC is distributed in declination-binned CSV.GZ files.

Keep downloaded catalogs under `data/raw/` and out of Git.
