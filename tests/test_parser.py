from pathlib import Path

import pytest

from cgmes_sqlite_lib import CgmesParser


def _examples_root() -> Path:
    return Path(__file__).resolve().parents[1] / "examples" / "xml"


def test_parse_igm_belgovia_counts() -> None:
    parser = CgmesParser()
    igm_folder = _examples_root() / "IGM_Belgovia"

    data = parser.parse_igm(igm_folder)

    assert len(data.profiles["EQ"]) == 1
    assert len(data.profiles["TP"]) == 1
    assert len(data.objects["Substation"]) == 2
    assert len(data.objects["VoltageLevel"]) == 6
    assert len(data.objects["ConnectivityNode"]) == 62
    assert len(data.objects["Terminal"]) == 192


def test_parse_common_data_file() -> None:
    parser = CgmesParser()
    common_file = _examples_root() / "CommonAndBoundaryData" / "Grid_CommonData_CGM-CD.xml"

    data = parser.parse_common_data_file(common_file)

    assert "CD" in data.profiles
    assert len(data.objects["BaseVoltage"]) > 0


def test_parse_igm_missing_folder_raises() -> None:
    parser = CgmesParser()

    with pytest.raises(FileNotFoundError, match="IGM folder not found"):
        parser.parse_igm("missing_igm")
