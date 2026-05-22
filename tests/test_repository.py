from pathlib import Path

import pytest

from cgmes_sqlite_lib import CgmesParser, CgmesSqliteRepository


def _examples_root() -> Path:
    return Path(__file__).resolve().parents[1] / "examples" / "xml"


def test_repository_roundtrip_for_common_and_one_igm(tmp_path: Path) -> None:
    parser = CgmesParser()
    repo = CgmesSqliteRepository(tmp_path / "cgmes.db")

    common_file = _examples_root() / "CommonAndBoundaryData" / "Grid_CommonData_CGM-CD.xml"
    igm_folder = _examples_root() / "IGM_Belgovia"

    common_data = parser.parse_common_data_file(common_file)
    igm_data = parser.parse_igm(igm_folder)

    repo.save_dataset("_CommonData", common_data)
    repo.save_dataset("IGM_Belgovia", igm_data)

    assert repo.has_igm("_CommonData")
    assert repo.has_igm("IGM_Belgovia")

    loaded = repo.load_dataset("IGM_Belgovia")

    assert len(loaded.objects["Substation"]) == 2
    assert len(loaded.objects["ConnectivityNode"]) == 35
    assert len(loaded.objects["Terminal"]) == 96


def test_repository_load_missing_igm_raises(tmp_path: Path) -> None:
    repo = CgmesSqliteRepository(tmp_path / "empty.db")

    with pytest.raises(FileNotFoundError, match="IGM not found in sqlite"):
        repo.load_dataset("IGM_UNKNOWN")
