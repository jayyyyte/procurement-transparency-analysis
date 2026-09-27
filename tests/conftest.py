import pytest

from src.config import load_config


@pytest.fixture
def cfg(tmp_path):
    """Real config with every output path redirected to a temp dir."""
    c = load_config()
    return c.with_paths(raw_dir=str(tmp_path / "raw"), interim_dir=str(tmp_path / "interim"),
                        processed_dir=str(tmp_path / "processed"), reports_dir=str(tmp_path / "reports"),
                        figures_dir=str(tmp_path / "reports/figures"), tables_dir=str(tmp_path / "reports/tables"),
                        logs_dir=str(tmp_path / "logs"), checkpoint_db=str(tmp_path / "cp.sqlite"))
