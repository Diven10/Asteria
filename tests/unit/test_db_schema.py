from app.db.base import Base
from app.db import models  # noqa: F401


def test_phase0_database_tables_exist() -> None:
    expected = {
        "raw_data",
        "processed_light_curves",
        "model_registry",
        "candidate_results",
        "reports",
        "pipeline_logs",
    }

    assert expected.issubset(Base.metadata.tables.keys())
