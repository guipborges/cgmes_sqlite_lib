from pathlib import Path

from cgmes_sqlite_lib import CgmesParser, CgmesSqliteRepository


def main() -> None:
    root = Path(__file__).resolve().parent
    xml_root = root / "xml"
    db_path = root / "example.db"

    parser = CgmesParser()
    repo = CgmesSqliteRepository(db_path)

    common_file = xml_root / "CommonAndBoundaryData" / "Grid_CommonData_CGM-CD.xml"
    common = parser.parse_common_data_file(common_file)
    repo.save_dataset("_CommonData", common)

    belgovia_folder = xml_root / "IGM_Belgovia"
    data = parser.parse_igm(belgovia_folder)
    repo.save_dataset("IGM_Belgovia", data)

    loaded = repo.load_dataset("IGM_Belgovia")
    print("Loaded IGM:", loaded.source_folder)
    print("Substations:", len(loaded.objects["Substation"]))
    print("Terminals:", len(loaded.objects["Terminal"]))


if __name__ == "__main__":
    main()
