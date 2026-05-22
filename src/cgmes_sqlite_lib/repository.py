from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Dict, List, Optional

from cgmes_sqlite_lib.parser import CgmesData, CgmesParser


class CgmesSqliteRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._ensure_parent_folder()
        self._ensure_schema()

    def has_igm(self, igm_name: str) -> bool:
        query = "SELECT 1 FROM cgmes_ingestion WHERE igm_name = ? LIMIT 1"
        with self._connect() as conn:
            row = conn.execute(query, (igm_name,)).fetchone()
        return row is not None

    def save_dataset(self, igm_name: str, data: CgmesData) -> None:
        now_utc = datetime.now(timezone.utc).isoformat()
        connectivity_rows = self._consolidate_rows_by_id(data.objects["ConnectivityNode"])
        terminal_rows = self._consolidate_rows_by_id(data.objects["Terminal"])

        with self._connect() as conn:
            self._delete_igm_rows(conn, igm_name)

            conn.execute(
                "INSERT INTO cgmes_ingestion (igm_name, source_folder, parsed_at_utc) VALUES (?, ?, ?)",
                (igm_name, str(data.source_folder), now_utc),
            )

            self._insert_substations(conn, igm_name, data.objects["Substation"])
            self._insert_voltage_levels(conn, igm_name, data.objects["VoltageLevel"])
            self._insert_bays(conn, igm_name, data.objects["Bay"])
            self._insert_busbar_sections(conn, igm_name, data.objects["BusbarSection"])
            self._insert_power_transformers(conn, igm_name, data.objects["PowerTransformer"])
            self._insert_power_transformer_ends(conn, igm_name, data.objects["PowerTransformerEnd"])
            self._insert_ac_line_segments(conn, igm_name, data.objects["ACLineSegment"])
            self._insert_breakers(conn, igm_name, data.objects["Breaker"])
            self._insert_ratio_tap_changers(conn, igm_name, data.objects["RatioTapChanger"])
            self._insert_phase_tap_changers_asymmetrical(conn, igm_name, data.objects["PhaseTapChangerAsymmetrical"])
            self._insert_phase_tap_changers_symmetrical(conn, igm_name, data.objects["PhaseTapChangerSymmetrical"])
            self._insert_synchronous_machines(conn, igm_name, data.objects["SynchronousMachine"])
            self._insert_generating_units(conn, igm_name, data.objects["GeneratingUnit"])
            self._insert_conform_loads(conn, igm_name, data.objects["ConformLoad"])
            self._insert_non_conform_loads(conn, igm_name, data.objects["NonConformLoad"])
            self._insert_linear_shunt_compensators(conn, igm_name, data.objects["LinearShuntCompensator"])
            self._insert_static_var_compensators(conn, igm_name, data.objects["StaticVarCompensator"])
            self._insert_series_compensators(conn, igm_name, data.objects["SeriesCompensator"])
            self._insert_equivalent_injections(conn, igm_name, data.objects["EquivalentInjection"])
            self._insert_lines(conn, igm_name, data.objects["Line"])
            self._insert_base_voltages(conn, igm_name, data.objects["BaseVoltage"])
            self._insert_geographical_regions(conn, igm_name, data.objects["GeographicalRegion"])
            self._insert_sub_geographical_regions(conn, igm_name, data.objects["SubGeographicalRegion"])
            self._insert_conducting_equipment_map(conn, igm_name, data)
            self._insert_connectivity_nodes(conn, igm_name, connectivity_rows)
            self._insert_terminals(conn, igm_name, terminal_rows)

            conn.commit()

    def load_dataset(self, igm_name: str) -> CgmesData:
        source_folder = self._load_source_folder(igm_name)
        objects = self._load_objects(igm_name)

        return CgmesData(
            source_folder=source_folder,
            profiles={"EQ": [], "TP": []},
            objects=objects,
        )

    # -------------------------------------------------------------------------
    # Per-table writes
    # -------------------------------------------------------------------------

    def _delete_igm_rows(self, conn: sqlite3.Connection, igm_name: str) -> None:
        for table in (
            "terminal", "connectivity_node", "conducting_equipment_map",
            "series_compensator", "equivalent_injection",
            "linear_shunt_compensator", "static_var_compensator",
            "conform_load", "non_conform_load",
            "synchronous_machine", "generating_unit",
            "phase_tap_changer_asymmetrical", "phase_tap_changer_symmetrical",
            "ratio_tap_changer", "breaker",
            "power_transformer_end", "ac_line_segment",
            "power_transformer", "busbar_section", "bay",
            "voltage_level", "substation", "line",
            "sub_geographical_region", "geographical_region", "base_voltage",
            "cgmes_ingestion",
        ):
            conn.execute(f"DELETE FROM {table} WHERE igm_name = ?", (igm_name,))

    def _insert_substations(self, conn, igm_name, rows):
        q = "INSERT INTO substation (id, igm_name, mrid, name, region_id, source_file) VALUES (?,?,?,?,?,?)"
        for r in rows:
            conn.execute(q, (self._require_id(r, "Substation"), igm_name, r.get("mRID"), r.get("name"), r.get("region_id"), r.get("source_file")))

    def _insert_voltage_levels(self, conn, igm_name, rows):
        q = "INSERT INTO voltage_level (id, igm_name, mrid, name, base_voltage_id, substation_id, source_file) VALUES (?,?,?,?,?,?,?)"
        for r in rows:
            conn.execute(q, (self._require_id(r, "VoltageLevel"), igm_name, r.get("mRID"), r.get("name"), r.get("base_voltage_id"), r.get("substation_id"), r.get("source_file")))

    def _insert_bays(self, conn, igm_name, rows):
        q = "INSERT INTO bay (id, igm_name, mrid, name, voltage_level_id, source_file) VALUES (?,?,?,?,?,?)"
        for r in rows:
            conn.execute(q, (self._require_id(r, "Bay"), igm_name, r.get("mRID"), r.get("name"), r.get("voltage_level_id"), r.get("source_file")))

    def _insert_busbar_sections(self, conn, igm_name, rows):
        q = "INSERT INTO busbar_section (id, igm_name, mrid, name, equipment_container_id, source_file) VALUES (?,?,?,?,?,?)"
        for r in rows:
            conn.execute(q, (self._require_id(r, "BusbarSection"), igm_name, r.get("mRID"), r.get("name"), r.get("equipment_container_id"), r.get("source_file")))

    def _insert_power_transformers(self, conn, igm_name, rows):
        q = "INSERT INTO power_transformer (id, igm_name, mrid, name, equipment_container_id, source_file) VALUES (?,?,?,?,?,?)"
        for r in rows:
            conn.execute(q, (self._require_id(r, "PowerTransformer"), igm_name, r.get("mRID"), r.get("name"), r.get("equipment_container_id"), r.get("source_file")))

    def _insert_power_transformer_ends(self, conn, igm_name, rows):
        q = ("INSERT INTO power_transformer_end "
             "(id, igm_name, mrid, name, transformer_id, terminal_id, base_voltage_id, end_number, "
             "rated_u, rated_s, r, x, b, g, connection_kind, source_file) "
             "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)")
        for r in rows:
            conn.execute(q, (
                self._require_id(r, "PowerTransformerEnd"), igm_name,
                r.get("mRID"), r.get("name"), r.get("transformer_id"), r.get("terminal_id"),
                r.get("base_voltage_id"), r.get("end_number"), r.get("rated_u"), r.get("rated_s"),
                r.get("r"), r.get("x"), r.get("b"), r.get("g"), r.get("connection_kind"), r.get("source_file"),
            ))

    def _insert_ac_line_segments(self, conn, igm_name, rows):
        q = "INSERT INTO ac_line_segment (id, igm_name, mrid, name, base_voltage_id, equipment_container_id, source_file) VALUES (?,?,?,?,?,?,?)"
        for r in rows:
            conn.execute(q, (self._require_id(r, "ACLineSegment"), igm_name, r.get("mRID"), r.get("name"), r.get("base_voltage_id"), r.get("equipment_container_id"), r.get("source_file")))

    def _insert_breakers(self, conn, igm_name, rows):
        q = "INSERT INTO breaker (id, igm_name, mrid, name, equipment_container_id, normal_open, retained, source_file) VALUES (?,?,?,?,?,?,?,?)"
        for r in rows:
            conn.execute(q, (self._require_id(r, "Breaker"), igm_name, r.get("mRID"), r.get("name"), r.get("equipment_container_id"), r.get("normal_open"), r.get("retained"), r.get("source_file")))

    def _insert_ratio_tap_changers(self, conn, igm_name, rows):
        q = ("INSERT INTO ratio_tap_changer "
             "(id, igm_name, mrid, name, transformer_end_id, step_voltage_increment, "
             "high_step, low_step, neutral_step, neutral_u, normal_step, ltc_flag, source_file) "
             "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)")
        for r in rows:
            conn.execute(q, (
                self._require_id(r, "RatioTapChanger"), igm_name,
                r.get("mRID"), r.get("name"), r.get("transformer_end_id"), r.get("step_voltage_increment"),
                r.get("high_step"), r.get("low_step"), r.get("neutral_step"), r.get("neutral_u"),
                r.get("normal_step"), r.get("ltc_flag"), r.get("source_file"),
            ))

    def _insert_phase_tap_changers_asymmetrical(self, conn, igm_name, rows):
        q = ("INSERT INTO phase_tap_changer_asymmetrical "
             "(id, igm_name, mrid, name, transformer_end_id, winding_connection_angle, "
             "voltage_step_increment, x_max, x_min, high_step, low_step, "
             "neutral_step, neutral_u, normal_step, ltc_flag, source_file) "
             "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)")
        for r in rows:
            conn.execute(q, (
                self._require_id(r, "PhaseTapChangerAsymmetrical"), igm_name,
                r.get("mRID"), r.get("name"), r.get("transformer_end_id"), r.get("winding_connection_angle"),
                r.get("voltage_step_increment"), r.get("x_max"), r.get("x_min"),
                r.get("high_step"), r.get("low_step"), r.get("neutral_step"), r.get("neutral_u"),
                r.get("normal_step"), r.get("ltc_flag"), r.get("source_file"),
            ))

    def _insert_phase_tap_changers_symmetrical(self, conn, igm_name, rows):
        q = ("INSERT INTO phase_tap_changer_symmetrical "
             "(id, igm_name, mrid, name, transformer_end_id, voltage_step_increment, "
             "x_max, x_min, high_step, low_step, neutral_step, neutral_u, normal_step, ltc_flag, source_file) "
             "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)")
        for r in rows:
            conn.execute(q, (
                self._require_id(r, "PhaseTapChangerSymmetrical"), igm_name,
                r.get("mRID"), r.get("name"), r.get("transformer_end_id"),
                r.get("voltage_step_increment"), r.get("x_max"), r.get("x_min"),
                r.get("high_step"), r.get("low_step"), r.get("neutral_step"), r.get("neutral_u"),
                r.get("normal_step"), r.get("ltc_flag"), r.get("source_file"),
            ))

    def _insert_synchronous_machines(self, conn, igm_name, rows):
        q = ("INSERT INTO synchronous_machine "
             "(id, igm_name, mrid, name, equipment_container_id, generating_unit_id, "
             "rated_s, rated_u, rated_power_factor, max_q, min_q, q_percent, machine_type, source_file) "
             "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)")
        for r in rows:
            conn.execute(q, (
                self._require_id(r, "SynchronousMachine"), igm_name,
                r.get("mRID"), r.get("name"), r.get("equipment_container_id"), r.get("generating_unit_id"),
                r.get("rated_s"), r.get("rated_u"), r.get("rated_power_factor"),
                r.get("max_q"), r.get("min_q"), r.get("q_percent"), r.get("machine_type"), r.get("source_file"),
            ))

    def _insert_generating_units(self, conn, igm_name, rows):
        q = "INSERT INTO generating_unit (id, igm_name, mrid, name, equipment_container_id, max_operating_p, min_operating_p, source_file) VALUES (?,?,?,?,?,?,?,?)"
        for r in rows:
            conn.execute(q, (self._require_id(r, "GeneratingUnit"), igm_name, r.get("mRID"), r.get("name"), r.get("equipment_container_id"), r.get("max_operating_p"), r.get("min_operating_p"), r.get("source_file")))

    def _insert_conform_loads(self, conn, igm_name, rows):
        q = "INSERT INTO conform_load (id, igm_name, mrid, name, equipment_container_id, load_group_id, source_file) VALUES (?,?,?,?,?,?,?)"
        for r in rows:
            conn.execute(q, (self._require_id(r, "ConformLoad"), igm_name, r.get("mRID"), r.get("name"), r.get("equipment_container_id"), r.get("load_group_id"), r.get("source_file")))

    def _insert_non_conform_loads(self, conn, igm_name, rows):
        q = "INSERT INTO non_conform_load (id, igm_name, mrid, name, equipment_container_id, load_group_id, source_file) VALUES (?,?,?,?,?,?,?)"
        for r in rows:
            conn.execute(q, (self._require_id(r, "NonConformLoad"), igm_name, r.get("mRID"), r.get("name"), r.get("equipment_container_id"), r.get("load_group_id"), r.get("source_file")))

    def _insert_linear_shunt_compensators(self, conn, igm_name, rows):
        q = ("INSERT INTO linear_shunt_compensator "
             "(id, igm_name, mrid, name, equipment_container_id, b_per_section, g_per_section, "
             "nom_u, maximum_sections, normal_sections, grounded, source_file) "
             "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)")
        for r in rows:
            conn.execute(q, (
                self._require_id(r, "LinearShuntCompensator"), igm_name,
                r.get("mRID"), r.get("name"), r.get("equipment_container_id"),
                r.get("b_per_section"), r.get("g_per_section"), r.get("nom_u"),
                r.get("maximum_sections"), r.get("normal_sections"), r.get("grounded"), r.get("source_file"),
            ))

    def _insert_static_var_compensators(self, conn, igm_name, rows):
        q = "INSERT INTO static_var_compensator (id, igm_name, mrid, name, equipment_container_id, capacitive_rating, inductive_rating, slope, source_file) VALUES (?,?,?,?,?,?,?,?,?)"
        for r in rows:
            conn.execute(q, (self._require_id(r, "StaticVarCompensator"), igm_name, r.get("mRID"), r.get("name"), r.get("equipment_container_id"), r.get("capacitive_rating"), r.get("inductive_rating"), r.get("slope"), r.get("source_file")))

    def _insert_series_compensators(self, conn, igm_name, rows):
        q = "INSERT INTO series_compensator (id, igm_name, mrid, name, equipment_container_id, base_voltage_id, r, x, source_file) VALUES (?,?,?,?,?,?,?,?,?)"
        for r in rows:
            conn.execute(q, (self._require_id(r, "SeriesCompensator"), igm_name, r.get("mRID"), r.get("name"), r.get("equipment_container_id"), r.get("base_voltage_id"), r.get("r"), r.get("x"), r.get("source_file")))

    def _insert_equivalent_injections(self, conn, igm_name, rows):
        q = "INSERT INTO equivalent_injection (id, igm_name, mrid, name, equipment_container_id, base_voltage_id, regulation_capability, source_file) VALUES (?,?,?,?,?,?,?,?)"
        for r in rows:
            conn.execute(q, (self._require_id(r, "EquivalentInjection"), igm_name, r.get("mRID"), r.get("name"), r.get("equipment_container_id"), r.get("base_voltage_id"), r.get("regulation_capability"), r.get("source_file")))

    def _insert_lines(self, conn, igm_name, rows):
        q = "INSERT INTO line (id, igm_name, mrid, name, region_id, source_file) VALUES (?,?,?,?,?,?)"
        for r in rows:
            conn.execute(q, (self._require_id(r, "Line"), igm_name, r.get("mRID"), r.get("name"), r.get("region_id"), r.get("source_file")))

    def _insert_base_voltages(self, conn, igm_name, rows):
        q = "INSERT INTO base_voltage (id, igm_name, mrid, name, nominal_voltage, source_file) VALUES (?,?,?,?,?,?)"
        for r in rows:
            conn.execute(q, (self._require_id(r, "BaseVoltage"), igm_name, r.get("mRID"), r.get("name"), r.get("nominal_voltage"), r.get("source_file")))

    def _insert_geographical_regions(self, conn, igm_name, rows):
        q = "INSERT INTO geographical_region (id, igm_name, mrid, name, source_file) VALUES (?,?,?,?,?)"
        for r in rows:
            conn.execute(q, (self._require_id(r, "GeographicalRegion"), igm_name, r.get("mRID"), r.get("name"), r.get("source_file")))

    def _insert_sub_geographical_regions(self, conn, igm_name, rows):
        q = "INSERT INTO sub_geographical_region (id, igm_name, mrid, name, region_id, source_file) VALUES (?,?,?,?,?,?)"
        for r in rows:
            conn.execute(q, (self._require_id(r, "SubGeographicalRegion"), igm_name, r.get("mRID"), r.get("name"), r.get("region_id"), r.get("source_file")))

    def _insert_conducting_equipment_map(self, conn, igm_name, data):
        q = "INSERT INTO conducting_equipment_map (id, igm_name, equipment_type) VALUES (?, ?, ?)"
        seen: Dict[str, str] = {}
        conducting_classes = [
            "BusbarSection", "PowerTransformer", "ACLineSegment",
            "Breaker", "SynchronousMachine", "ConformLoad", "NonConformLoad",
            "LinearShuntCompensator", "StaticVarCompensator",
            "SeriesCompensator", "EquivalentInjection",
        ]
        for class_name in conducting_classes:
            for row in data.objects[class_name]:
                row_id = self._require_id(row, class_name)
                if row_id in seen:
                    continue
                seen[row_id] = class_name
                conn.execute(q, (row_id, igm_name, class_name))

    def _insert_connectivity_nodes(self, conn, igm_name, rows):
        q = ("INSERT INTO connectivity_node "
             "(id, igm_name, mrid, name, container_id, topological_node_id, source_file) "
             "VALUES (?,?,?,?,?,?,?)")
        for r in rows:
            conn.execute(q, (self._require_id(r, "ConnectivityNode"), igm_name, r.get("mRID"), r.get("name"), r.get("container_id"), r.get("topological_node_id"), r.get("source_file")))

    def _insert_terminals(self, conn, igm_name, rows):
        q = ("INSERT INTO terminal "
             "(id, igm_name, mrid, name, conducting_equipment_id, connectivity_node_id, "
             "topological_node_id, sequence_number, source_file) "
             "VALUES (?,?,?,?,?,?,?,?,?)")
        for r in rows:
            conn.execute(q, (
                self._require_id(r, "Terminal"), igm_name,
                r.get("mRID"), r.get("name"), r.get("conducting_equipment_id"),
                r.get("connectivity_node_id"), r.get("topological_node_id"),
                r.get("sequence_number"), r.get("source_file"),
            ))

    # -------------------------------------------------------------------------
    # EQ + TP consolidation
    # -------------------------------------------------------------------------

    def _consolidate_rows_by_id(self, rows):
        consolidated: Dict[str, Dict[str, Optional[str]]] = {}
        for row in rows:
            row_id = self._require_id(row, "Object")
            if row_id not in consolidated:
                consolidated[row_id] = dict(row)
                continue
            existing = consolidated[row_id]
            for key, value in row.items():
                if key in ("profile", "source_file"):
                    continue
                existing_value = existing.get(key)
                if existing_value in (None, "") and value not in (None, ""):
                    existing[key] = value
                    continue
                if (existing_value not in (None, "") and value not in (None, "") and existing_value != value):
                    raise ValueError(f"Consolidation conflict for id={row_id}, field={key}: {existing_value} vs {value}")
        return list(consolidated.values())

    # -------------------------------------------------------------------------
    # Per-table reads
    # -------------------------------------------------------------------------

    def _require_id(self, row, class_name):
        row_id = row.get("id")
        if row_id is None or not row_id.strip():
            raise ValueError(f"{class_name} without id cannot be persisted")
        return row_id

    def _load_source_folder(self, igm_name):
        with self._connect() as conn:
            row = conn.execute("SELECT source_folder FROM cgmes_ingestion WHERE igm_name = ?", (igm_name,)).fetchone()
        if row is None:
            raise FileNotFoundError(f"IGM not found in sqlite: {igm_name}")
        return Path(row[0])

    def _load_objects(self, igm_name):
        objects = {class_name: [] for class_name in CgmesParser.ALL_CLASSES}
        with self._connect() as conn:
            objects["Substation"] = self._load_table(conn, igm_name, "substation", ["id", "mRID:mrid", "name", "region_id", "source_file"])
            objects["VoltageLevel"] = self._load_table(conn, igm_name, "voltage_level", ["id", "mRID:mrid", "name", "base_voltage_id", "substation_id", "source_file"])
            objects["Bay"] = self._load_table(conn, igm_name, "bay", ["id", "mRID:mrid", "name", "voltage_level_id", "source_file"])
            objects["BusbarSection"] = self._load_table(conn, igm_name, "busbar_section", ["id", "mRID:mrid", "name", "equipment_container_id", "source_file"])
            objects["PowerTransformer"] = self._load_table(conn, igm_name, "power_transformer", ["id", "mRID:mrid", "name", "equipment_container_id", "source_file"])
            objects["PowerTransformerEnd"] = self._load_table(conn, igm_name, "power_transformer_end", ["id", "mRID:mrid", "name", "transformer_id", "terminal_id", "base_voltage_id", "end_number", "rated_u", "rated_s", "r", "x", "b", "g", "connection_kind", "source_file"])
            objects["ACLineSegment"] = self._load_table(conn, igm_name, "ac_line_segment", ["id", "mRID:mrid", "name", "base_voltage_id", "equipment_container_id", "source_file"])
            objects["Breaker"] = self._load_table(conn, igm_name, "breaker", ["id", "mRID:mrid", "name", "equipment_container_id", "normal_open", "retained", "source_file"])
            objects["RatioTapChanger"] = self._load_table(conn, igm_name, "ratio_tap_changer", ["id", "mRID:mrid", "name", "transformer_end_id", "step_voltage_increment", "high_step", "low_step", "neutral_step", "neutral_u", "normal_step", "ltc_flag", "source_file"])
            objects["PhaseTapChangerAsymmetrical"] = self._load_table(conn, igm_name, "phase_tap_changer_asymmetrical", ["id", "mRID:mrid", "name", "transformer_end_id", "winding_connection_angle", "voltage_step_increment", "x_max", "x_min", "high_step", "low_step", "neutral_step", "neutral_u", "normal_step", "ltc_flag", "source_file"])
            objects["PhaseTapChangerSymmetrical"] = self._load_table(conn, igm_name, "phase_tap_changer_symmetrical", ["id", "mRID:mrid", "name", "transformer_end_id", "voltage_step_increment", "x_max", "x_min", "high_step", "low_step", "neutral_step", "neutral_u", "normal_step", "ltc_flag", "source_file"])
            objects["SynchronousMachine"] = self._load_table(conn, igm_name, "synchronous_machine", ["id", "mRID:mrid", "name", "equipment_container_id", "generating_unit_id", "rated_s", "rated_u", "rated_power_factor", "max_q", "min_q", "q_percent", "machine_type", "source_file"])
            objects["GeneratingUnit"] = self._load_table(conn, igm_name, "generating_unit", ["id", "mRID:mrid", "name", "equipment_container_id", "max_operating_p", "min_operating_p", "source_file"])
            objects["ConformLoad"] = self._load_table(conn, igm_name, "conform_load", ["id", "mRID:mrid", "name", "equipment_container_id", "load_group_id", "source_file"])
            objects["NonConformLoad"] = self._load_table(conn, igm_name, "non_conform_load", ["id", "mRID:mrid", "name", "equipment_container_id", "load_group_id", "source_file"])
            objects["LinearShuntCompensator"] = self._load_table(conn, igm_name, "linear_shunt_compensator", ["id", "mRID:mrid", "name", "equipment_container_id", "b_per_section", "g_per_section", "nom_u", "maximum_sections", "normal_sections", "grounded", "source_file"])
            objects["StaticVarCompensator"] = self._load_table(conn, igm_name, "static_var_compensator", ["id", "mRID:mrid", "name", "equipment_container_id", "capacitive_rating", "inductive_rating", "slope", "source_file"])
            objects["SeriesCompensator"] = self._load_table(conn, igm_name, "series_compensator", ["id", "mRID:mrid", "name", "equipment_container_id", "base_voltage_id", "r", "x", "source_file"])
            objects["EquivalentInjection"] = self._load_table(conn, igm_name, "equivalent_injection", ["id", "mRID:mrid", "name", "equipment_container_id", "base_voltage_id", "regulation_capability", "source_file"])
            objects["Line"] = self._load_table(conn, igm_name, "line", ["id", "mRID:mrid", "name", "region_id", "source_file"])
            objects["BaseVoltage"] = self._load_table(conn, igm_name, "base_voltage", ["id", "mRID:mrid", "name", "nominal_voltage", "source_file"])
            objects["GeographicalRegion"] = self._load_table(conn, igm_name, "geographical_region", ["id", "mRID:mrid", "name", "source_file"])
            objects["SubGeographicalRegion"] = self._load_table(conn, igm_name, "sub_geographical_region", ["id", "mRID:mrid", "name", "region_id", "source_file"])
            objects["ConnectivityNode"] = self._load_table(conn, igm_name, "connectivity_node", ["id", "mRID:mrid", "name", "container_id", "topological_node_id", "source_file"])
            objects["Terminal"] = self._load_table(conn, igm_name, "terminal", ["id", "mRID:mrid", "name", "conducting_equipment_id", "connectivity_node_id", "topological_node_id", "sequence_number", "source_file"])
        return objects

    def _load_table(self, conn, igm_name, table_name, fields):
        # fields entries: "col_name" or "dict_key:col_name"
        col_map = []
        for f in fields:
            if ":" in f:
                dict_key, col = f.split(":", 1)
            else:
                dict_key, col = f, f
            col_map.append((dict_key, col))

        cols = ", ".join(c for _, c in col_map)
        rows = conn.execute(
            f"SELECT {cols} FROM {table_name} WHERE igm_name = ? ORDER BY id",
            (igm_name,),
        ).fetchall()
        return [{dict_key: row[i] for i, (dict_key, _) in enumerate(col_map)} for row in rows]

    # -------------------------------------------------------------------------
    # Schema and connection
    # -------------------------------------------------------------------------

    def _ensure_parent_folder(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _ensure_schema(self):
        ddl_statements = [
            """CREATE TABLE IF NOT EXISTS cgmes_ingestion (
                igm_name TEXT PRIMARY KEY,
                source_folder TEXT NOT NULL,
                parsed_at_utc TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS substation (
                id TEXT PRIMARY KEY, igm_name TEXT NOT NULL,
                mrid TEXT, name TEXT, region_id TEXT, source_file TEXT,
                FOREIGN KEY (igm_name) REFERENCES cgmes_ingestion (igm_name) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS voltage_level (
                id TEXT PRIMARY KEY, igm_name TEXT NOT NULL,
                mrid TEXT, name TEXT, base_voltage_id TEXT, substation_id TEXT, source_file TEXT,
                FOREIGN KEY (igm_name) REFERENCES cgmes_ingestion (igm_name) ON DELETE CASCADE,
                FOREIGN KEY (substation_id) REFERENCES substation (id)
            )""",
            """CREATE TABLE IF NOT EXISTS bay (
                id TEXT PRIMARY KEY, igm_name TEXT NOT NULL,
                mrid TEXT, name TEXT, voltage_level_id TEXT, source_file TEXT,
                FOREIGN KEY (igm_name) REFERENCES cgmes_ingestion (igm_name) ON DELETE CASCADE,
                FOREIGN KEY (voltage_level_id) REFERENCES voltage_level (id)
            )""",
            """CREATE TABLE IF NOT EXISTS busbar_section (
                id TEXT PRIMARY KEY, igm_name TEXT NOT NULL,
                mrid TEXT, name TEXT, equipment_container_id TEXT, source_file TEXT,
                FOREIGN KEY (igm_name) REFERENCES cgmes_ingestion (igm_name) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS power_transformer (
                id TEXT PRIMARY KEY, igm_name TEXT NOT NULL,
                mrid TEXT, name TEXT, equipment_container_id TEXT, source_file TEXT,
                FOREIGN KEY (igm_name) REFERENCES cgmes_ingestion (igm_name) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS power_transformer_end (
                id TEXT PRIMARY KEY, igm_name TEXT NOT NULL,
                mrid TEXT, name TEXT, transformer_id TEXT, terminal_id TEXT,
                base_voltage_id TEXT, end_number TEXT,
                rated_u TEXT, rated_s TEXT, r TEXT, x TEXT, b TEXT, g TEXT,
                connection_kind TEXT, source_file TEXT,
                FOREIGN KEY (igm_name) REFERENCES cgmes_ingestion (igm_name) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS ac_line_segment (
                id TEXT PRIMARY KEY, igm_name TEXT NOT NULL,
                mrid TEXT, name TEXT, base_voltage_id TEXT, equipment_container_id TEXT, source_file TEXT,
                FOREIGN KEY (igm_name) REFERENCES cgmes_ingestion (igm_name) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS breaker (
                id TEXT PRIMARY KEY, igm_name TEXT NOT NULL,
                mrid TEXT, name TEXT, equipment_container_id TEXT,
                normal_open TEXT, retained TEXT, source_file TEXT,
                FOREIGN KEY (igm_name) REFERENCES cgmes_ingestion (igm_name) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS ratio_tap_changer (
                id TEXT PRIMARY KEY, igm_name TEXT NOT NULL,
                mrid TEXT, name TEXT, transformer_end_id TEXT, step_voltage_increment TEXT,
                high_step TEXT, low_step TEXT, neutral_step TEXT, neutral_u TEXT,
                normal_step TEXT, ltc_flag TEXT, source_file TEXT,
                FOREIGN KEY (igm_name) REFERENCES cgmes_ingestion (igm_name) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS phase_tap_changer_asymmetrical (
                id TEXT PRIMARY KEY, igm_name TEXT NOT NULL,
                mrid TEXT, name TEXT, transformer_end_id TEXT, winding_connection_angle TEXT,
                voltage_step_increment TEXT, x_max TEXT, x_min TEXT,
                high_step TEXT, low_step TEXT, neutral_step TEXT, neutral_u TEXT,
                normal_step TEXT, ltc_flag TEXT, source_file TEXT,
                FOREIGN KEY (igm_name) REFERENCES cgmes_ingestion (igm_name) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS phase_tap_changer_symmetrical (
                id TEXT PRIMARY KEY, igm_name TEXT NOT NULL,
                mrid TEXT, name TEXT, transformer_end_id TEXT,
                voltage_step_increment TEXT, x_max TEXT, x_min TEXT,
                high_step TEXT, low_step TEXT, neutral_step TEXT, neutral_u TEXT,
                normal_step TEXT, ltc_flag TEXT, source_file TEXT,
                FOREIGN KEY (igm_name) REFERENCES cgmes_ingestion (igm_name) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS synchronous_machine (
                id TEXT PRIMARY KEY, igm_name TEXT NOT NULL,
                mrid TEXT, name TEXT, equipment_container_id TEXT, generating_unit_id TEXT,
                rated_s TEXT, rated_u TEXT, rated_power_factor TEXT,
                max_q TEXT, min_q TEXT, q_percent TEXT, machine_type TEXT, source_file TEXT,
                FOREIGN KEY (igm_name) REFERENCES cgmes_ingestion (igm_name) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS generating_unit (
                id TEXT PRIMARY KEY, igm_name TEXT NOT NULL,
                mrid TEXT, name TEXT, equipment_container_id TEXT,
                max_operating_p TEXT, min_operating_p TEXT, source_file TEXT,
                FOREIGN KEY (igm_name) REFERENCES cgmes_ingestion (igm_name) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS conform_load (
                id TEXT PRIMARY KEY, igm_name TEXT NOT NULL,
                mrid TEXT, name TEXT, equipment_container_id TEXT, load_group_id TEXT, source_file TEXT,
                FOREIGN KEY (igm_name) REFERENCES cgmes_ingestion (igm_name) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS non_conform_load (
                id TEXT PRIMARY KEY, igm_name TEXT NOT NULL,
                mrid TEXT, name TEXT, equipment_container_id TEXT, load_group_id TEXT, source_file TEXT,
                FOREIGN KEY (igm_name) REFERENCES cgmes_ingestion (igm_name) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS linear_shunt_compensator (
                id TEXT PRIMARY KEY, igm_name TEXT NOT NULL,
                mrid TEXT, name TEXT, equipment_container_id TEXT,
                b_per_section TEXT, g_per_section TEXT, nom_u TEXT,
                maximum_sections TEXT, normal_sections TEXT, grounded TEXT, source_file TEXT,
                FOREIGN KEY (igm_name) REFERENCES cgmes_ingestion (igm_name) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS static_var_compensator (
                id TEXT PRIMARY KEY, igm_name TEXT NOT NULL,
                mrid TEXT, name TEXT, equipment_container_id TEXT,
                capacitive_rating TEXT, inductive_rating TEXT, slope TEXT, source_file TEXT,
                FOREIGN KEY (igm_name) REFERENCES cgmes_ingestion (igm_name) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS series_compensator (
                id TEXT PRIMARY KEY, igm_name TEXT NOT NULL,
                mrid TEXT, name TEXT, equipment_container_id TEXT,
                base_voltage_id TEXT, r TEXT, x TEXT, source_file TEXT,
                FOREIGN KEY (igm_name) REFERENCES cgmes_ingestion (igm_name) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS equivalent_injection (
                id TEXT PRIMARY KEY, igm_name TEXT NOT NULL,
                mrid TEXT, name TEXT, equipment_container_id TEXT,
                base_voltage_id TEXT, regulation_capability TEXT, source_file TEXT,
                FOREIGN KEY (igm_name) REFERENCES cgmes_ingestion (igm_name) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS line (
                id TEXT PRIMARY KEY, igm_name TEXT NOT NULL,
                mrid TEXT, name TEXT, region_id TEXT, source_file TEXT,
                FOREIGN KEY (igm_name) REFERENCES cgmes_ingestion (igm_name) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS base_voltage (
                id TEXT PRIMARY KEY, igm_name TEXT NOT NULL,
                mrid TEXT, name TEXT, nominal_voltage TEXT, source_file TEXT,
                FOREIGN KEY (igm_name) REFERENCES cgmes_ingestion (igm_name) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS geographical_region (
                id TEXT PRIMARY KEY, igm_name TEXT NOT NULL,
                mrid TEXT, name TEXT, source_file TEXT,
                FOREIGN KEY (igm_name) REFERENCES cgmes_ingestion (igm_name) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS sub_geographical_region (
                id TEXT PRIMARY KEY, igm_name TEXT NOT NULL,
                mrid TEXT, name TEXT, region_id TEXT, source_file TEXT,
                FOREIGN KEY (igm_name) REFERENCES cgmes_ingestion (igm_name) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS conducting_equipment_map (
                id TEXT PRIMARY KEY, igm_name TEXT NOT NULL, equipment_type TEXT NOT NULL,
                FOREIGN KEY (igm_name) REFERENCES cgmes_ingestion (igm_name) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS connectivity_node (
                id TEXT PRIMARY KEY, igm_name TEXT NOT NULL,
                mrid TEXT, name TEXT, container_id TEXT, topological_node_id TEXT, source_file TEXT,
                FOREIGN KEY (igm_name) REFERENCES cgmes_ingestion (igm_name) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS terminal (
                id TEXT PRIMARY KEY, igm_name TEXT NOT NULL,
                mrid TEXT, name TEXT, conducting_equipment_id TEXT,
                connectivity_node_id TEXT, topological_node_id TEXT,
                sequence_number TEXT, source_file TEXT,
                FOREIGN KEY (igm_name) REFERENCES cgmes_ingestion (igm_name) ON DELETE CASCADE
            )""",
        ]
        index_statements = [
            "CREATE INDEX IF NOT EXISTS idx_substation_igm ON substation (igm_name)",
            "CREATE INDEX IF NOT EXISTS idx_voltage_level_igm ON voltage_level (igm_name)",
            "CREATE INDEX IF NOT EXISTS idx_voltage_level_substation ON voltage_level (substation_id)",
            "CREATE INDEX IF NOT EXISTS idx_bay_igm ON bay (igm_name)",
            "CREATE INDEX IF NOT EXISTS idx_bay_voltage_level ON bay (voltage_level_id)",
            "CREATE INDEX IF NOT EXISTS idx_busbar_section_igm ON busbar_section (igm_name)",
            "CREATE INDEX IF NOT EXISTS idx_power_transformer_igm ON power_transformer (igm_name)",
            "CREATE INDEX IF NOT EXISTS idx_power_transformer_end_igm ON power_transformer_end (igm_name)",
            "CREATE INDEX IF NOT EXISTS idx_power_transformer_end_transformer ON power_transformer_end (transformer_id)",
            "CREATE INDEX IF NOT EXISTS idx_ac_line_segment_igm ON ac_line_segment (igm_name)",
            "CREATE INDEX IF NOT EXISTS idx_breaker_igm ON breaker (igm_name)",
            "CREATE INDEX IF NOT EXISTS idx_ratio_tap_changer_igm ON ratio_tap_changer (igm_name)",
            "CREATE INDEX IF NOT EXISTS idx_phase_tap_asym_igm ON phase_tap_changer_asymmetrical (igm_name)",
            "CREATE INDEX IF NOT EXISTS idx_phase_tap_sym_igm ON phase_tap_changer_symmetrical (igm_name)",
            "CREATE INDEX IF NOT EXISTS idx_synchronous_machine_igm ON synchronous_machine (igm_name)",
            "CREATE INDEX IF NOT EXISTS idx_generating_unit_igm ON generating_unit (igm_name)",
            "CREATE INDEX IF NOT EXISTS idx_conform_load_igm ON conform_load (igm_name)",
            "CREATE INDEX IF NOT EXISTS idx_non_conform_load_igm ON non_conform_load (igm_name)",
            "CREATE INDEX IF NOT EXISTS idx_linear_shunt_compensator_igm ON linear_shunt_compensator (igm_name)",
            "CREATE INDEX IF NOT EXISTS idx_static_var_compensator_igm ON static_var_compensator (igm_name)",
            "CREATE INDEX IF NOT EXISTS idx_series_compensator_igm ON series_compensator (igm_name)",
            "CREATE INDEX IF NOT EXISTS idx_equivalent_injection_igm ON equivalent_injection (igm_name)",
            "CREATE INDEX IF NOT EXISTS idx_line_igm ON line (igm_name)",
            "CREATE INDEX IF NOT EXISTS idx_base_voltage_igm ON base_voltage (igm_name)",
            "CREATE INDEX IF NOT EXISTS idx_geographical_region_igm ON geographical_region (igm_name)",
            "CREATE INDEX IF NOT EXISTS idx_sub_geographical_region_igm ON sub_geographical_region (igm_name)",
            "CREATE INDEX IF NOT EXISTS idx_conducting_equipment_map_igm ON conducting_equipment_map (igm_name)",
            "CREATE INDEX IF NOT EXISTS idx_connectivity_node_igm ON connectivity_node (igm_name)",
            "CREATE INDEX IF NOT EXISTS idx_terminal_igm ON terminal (igm_name)",
            "CREATE INDEX IF NOT EXISTS idx_terminal_connectivity_node ON terminal (connectivity_node_id)",
            "CREATE INDEX IF NOT EXISTS idx_terminal_conducting_equipment ON terminal (conducting_equipment_id)",
        ]
        with self._connect() as conn:
            self._migrate_connectivity_node_primary_key(conn)
            for stmt in ddl_statements + index_statements:
                conn.execute(stmt)
            conn.commit()

    def _migrate_connectivity_node_primary_key(self, conn: sqlite3.Connection) -> None:
        """Migrate connectivity_node to composite PK (igm_name, id) while preserving data."""
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'connectivity_node'"
        ).fetchone()
        if table_exists is None:
            return

        table_info = conn.execute("PRAGMA table_info('connectivity_node')").fetchall()
        pk_by_column = {row[1]: row[5] for row in table_info}
        id_pk = pk_by_column.get("id", 0)
        igm_pk = pk_by_column.get("igm_name", 0)

        # Old schema: simple id PK. New schema: composite PK (igm_name, id).
        if not (id_pk == 2 and igm_pk == 1):
            if not (id_pk == 1 and igm_pk == 0):
                raise RuntimeError(
                    "Unexpected schema in connectivity_node; automatic migration was not applied."
                )

            conn.execute("ALTER TABLE connectivity_node RENAME TO connectivity_node_legacy")
            conn.execute(
                """CREATE TABLE connectivity_node (
                    id TEXT NOT NULL,
                    igm_name TEXT NOT NULL,
                    mrid TEXT,
                    name TEXT,
                    container_id TEXT,
                    topological_node_id TEXT,
                    source_file TEXT,
                    PRIMARY KEY (igm_name, id),
                    FOREIGN KEY (igm_name) REFERENCES cgmes_ingestion (igm_name) ON DELETE CASCADE
                )"""
            )
            conn.execute(
                """INSERT INTO connectivity_node
                    (id, igm_name, mrid, name, container_id, topological_node_id, source_file)
                    SELECT id, igm_name, mrid, name, container_id, topological_node_id, source_file
                    FROM connectivity_node_legacy"""
            )
            conn.execute("DROP TABLE connectivity_node_legacy")

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
