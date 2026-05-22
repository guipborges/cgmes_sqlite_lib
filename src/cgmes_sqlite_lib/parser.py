from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional
import xml.etree.ElementTree as ET


RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
CIM_NS = "http://iec.ch/TC57/CIM100#"


def _strip_hash(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return value[1:] if value.startswith("#") else value


def _rdf_identifier(element: ET.Element) -> Optional[str]:
    return element.attrib.get(f"{{{RDF_NS}}}ID") or _strip_hash(
        element.attrib.get(f"{{{RDF_NS}}}about")
    )


def _child_text(element: ET.Element, child_tag: str) -> Optional[str]:
    child = element.find(f"{{{CIM_NS}}}{child_tag}")
    if child is None:
        return None
    if child.text is None:
        return None
    value = child.text.strip()
    return value if value else None


def _child_resource(element: ET.Element, child_tag: str) -> Optional[str]:
    child = element.find(f"{{{CIM_NS}}}{child_tag}")
    if child is None:
        return None
    return _strip_hash(child.attrib.get(f"{{{RDF_NS}}}resource"))


def _iter_cim_elements(file_path: Path, cim_class: str) -> Iterable[ET.Element]:
    tag = f"{{{CIM_NS}}}{cim_class}"
    context = ET.iterparse(file_path, events=("end",))
    for _, elem in context:
        if elem.tag == tag:
            yield elem
            elem.clear()


@dataclass
class CgmesData:
    source_folder: Path
    profiles: Dict[str, List[Path]]
    objects: Dict[str, List[Dict[str, Optional[str]]]]

    def to_dataframes(self) -> Dict[str, "pd.DataFrame"]:
        import pandas as pd

        return {
            class_name: pd.DataFrame(rows)
            for class_name, rows in self.objects.items()
        }


class CgmesParser:
    """Stage 1 CGMES parser for EQ and TP profiles."""

    TARGET_CLASSES = (
        "Substation",
        "VoltageLevel",
        "Bay",
        "BusbarSection",
        "PowerTransformer",
        "PowerTransformerEnd",
        "ACLineSegment",
        "ConnectivityNode",
        "Terminal",
        "Breaker",
        "RatioTapChanger",
        "PhaseTapChangerAsymmetrical",
        "PhaseTapChangerSymmetrical",
        "SynchronousMachine",
        "GeneratingUnit",
        "ConformLoad",
        "NonConformLoad",
        "LinearShuntCompensator",
        "StaticVarCompensator",
        "SeriesCompensator",
        "EquivalentInjection",
        "Line",
    )

    COMMON_DATA_CLASSES = (
        "BaseVoltage",
        "GeographicalRegion",
        "SubGeographicalRegion",
    )

    ALL_CLASSES = TARGET_CLASSES + COMMON_DATA_CLASSES

    def parse_igm(self, igm_folder: str | Path) -> CgmesData:
        folder = Path(igm_folder)
        if not folder.exists() or not folder.is_dir():
            raise FileNotFoundError(f"IGM folder not found: {folder}")

        profile_files = {
            "EQ": sorted(folder.glob("*_EQ_*.xml")),
            "TP": sorted(folder.glob("*_TP_*.xml")),
        }

        if not profile_files["EQ"]:
            raise FileNotFoundError(f"EQ file not found in: {folder}")
        if not profile_files["TP"]:
            raise FileNotFoundError(f"TP file not found in: {folder}")

        objects: Dict[str, List[Dict[str, Optional[str]]]] = {
            class_name: [] for class_name in self.ALL_CLASSES
        }

        for eq_file in profile_files["EQ"]:
            self._parse_eq_file(eq_file, objects)

        for tp_file in profile_files["TP"]:
            self._parse_tp_file(tp_file, objects)

        return CgmesData(source_folder=folder, profiles=profile_files, objects=objects)

    def parse_grid_instances(self, grid_folder: str | Path) -> Dict[str, CgmesData]:
        grid = Path(grid_folder)
        if not grid.exists() or not grid.is_dir():
            raise FileNotFoundError(f"Grid folder not found: {grid}")

        results: Dict[str, CgmesData] = {}
        for igm_dir in sorted(grid.glob("IGM_*")):
            if igm_dir.is_dir():
                results[igm_dir.name] = self.parse_igm(igm_dir)
        return results

    def _parse_eq_file(
        self,
        eq_file: Path,
        objects: Dict[str, List[Dict[str, Optional[str]]]],
    ) -> None:
        objects["Substation"].extend(self._parse_substations(eq_file, "EQ"))
        objects["VoltageLevel"].extend(self._parse_voltage_levels(eq_file, "EQ"))
        objects["Bay"].extend(self._parse_bays(eq_file, "EQ"))
        objects["BusbarSection"].extend(self._parse_busbar_sections(eq_file, "EQ"))
        objects["PowerTransformer"].extend(
            self._parse_power_transformers(eq_file, "EQ")
        )
        objects["ACLineSegment"].extend(self._parse_ac_line_segments(eq_file, "EQ"))
        objects["ConnectivityNode"].extend(
            self._parse_connectivity_nodes_eq(eq_file, "EQ")
        )
        objects["Terminal"].extend(self._parse_terminals_eq(eq_file, "EQ"))
        objects["PowerTransformerEnd"].extend(self._parse_power_transformer_ends(eq_file))
        objects["Breaker"].extend(self._parse_breakers(eq_file))
        objects["RatioTapChanger"].extend(self._parse_ratio_tap_changers(eq_file))
        objects["PhaseTapChangerAsymmetrical"].extend(self._parse_phase_tap_changers_asymmetrical(eq_file))
        objects["PhaseTapChangerSymmetrical"].extend(self._parse_phase_tap_changers_symmetrical(eq_file))
        objects["SynchronousMachine"].extend(self._parse_synchronous_machines(eq_file))
        objects["GeneratingUnit"].extend(self._parse_generating_units(eq_file))
        objects["ConformLoad"].extend(self._parse_conform_loads(eq_file))
        objects["NonConformLoad"].extend(self._parse_non_conform_loads(eq_file))
        objects["LinearShuntCompensator"].extend(self._parse_linear_shunt_compensators(eq_file))
        objects["StaticVarCompensator"].extend(self._parse_static_var_compensators(eq_file))
        objects["SeriesCompensator"].extend(self._parse_series_compensators(eq_file))
        objects["EquivalentInjection"].extend(self._parse_equivalent_injections(eq_file))
        objects["Line"].extend(self._parse_lines(eq_file))

    def _parse_tp_file(
        self,
        tp_file: Path,
        objects: Dict[str, List[Dict[str, Optional[str]]]],
    ) -> None:
        objects["ConnectivityNode"].extend(
            self._parse_connectivity_nodes_tp(tp_file, "TP")
        )
        objects["Terminal"].extend(self._parse_terminals_tp(tp_file, "TP"))

    def _parse_substations(
        self, file_path: Path, profile: str
    ) -> List[Dict[str, Optional[str]]]:
        rows: List[Dict[str, Optional[str]]] = []
        for element in _iter_cim_elements(file_path, "Substation"):
            rows.append(
                {
                    "id": _rdf_identifier(element),
                    "mRID": _child_text(element, "IdentifiedObject.mRID"),
                    "name": _child_text(element, "IdentifiedObject.name"),
                    "region_id": _child_resource(element, "Substation.Region"),
                    "profile": profile,
                    "source_file": file_path.name,
                }
            )
        return rows

    def _parse_voltage_levels(
        self, file_path: Path, profile: str
    ) -> List[Dict[str, Optional[str]]]:
        rows: List[Dict[str, Optional[str]]] = []
        for element in _iter_cim_elements(file_path, "VoltageLevel"):
            rows.append(
                {
                    "id": _rdf_identifier(element),
                    "mRID": _child_text(element, "IdentifiedObject.mRID"),
                    "name": _child_text(element, "IdentifiedObject.name"),
                    "base_voltage_id": _child_resource(
                        element, "VoltageLevel.BaseVoltage"
                    ),
                    "substation_id": _child_resource(
                        element, "VoltageLevel.Substation"
                    ),
                    "profile": profile,
                    "source_file": file_path.name,
                }
            )
        return rows

    def _parse_bays(self, file_path: Path, profile: str) -> List[Dict[str, Optional[str]]]:
        rows: List[Dict[str, Optional[str]]] = []
        for element in _iter_cim_elements(file_path, "Bay"):
            rows.append(
                {
                    "id": _rdf_identifier(element),
                    "mRID": _child_text(element, "IdentifiedObject.mRID"),
                    "name": _child_text(element, "IdentifiedObject.name"),
                    "voltage_level_id": _child_resource(element, "Bay.VoltageLevel"),
                    "profile": profile,
                    "source_file": file_path.name,
                }
            )
        return rows

    def _parse_busbar_sections(
        self, file_path: Path, profile: str
    ) -> List[Dict[str, Optional[str]]]:
        rows: List[Dict[str, Optional[str]]] = []
        for element in _iter_cim_elements(file_path, "BusbarSection"):
            rows.append(
                {
                    "id": _rdf_identifier(element),
                    "mRID": _child_text(element, "IdentifiedObject.mRID"),
                    "name": _child_text(element, "IdentifiedObject.name"),
                    "equipment_container_id": _child_resource(
                        element, "Equipment.EquipmentContainer"
                    ),
                    "profile": profile,
                    "source_file": file_path.name,
                }
            )
        return rows

    def _parse_power_transformers(
        self, file_path: Path, profile: str
    ) -> List[Dict[str, Optional[str]]]:
        rows: List[Dict[str, Optional[str]]] = []
        for element in _iter_cim_elements(file_path, "PowerTransformer"):
            rows.append(
                {
                    "id": _rdf_identifier(element),
                    "mRID": _child_text(element, "IdentifiedObject.mRID"),
                    "name": _child_text(element, "IdentifiedObject.name"),
                    "equipment_container_id": _child_resource(
                        element, "Equipment.EquipmentContainer"
                    ),
                    "profile": profile,
                    "source_file": file_path.name,
                }
            )
        return rows

    def _parse_ac_line_segments(
        self, file_path: Path, profile: str
    ) -> List[Dict[str, Optional[str]]]:
        rows: List[Dict[str, Optional[str]]] = []
        for element in _iter_cim_elements(file_path, "ACLineSegment"):
            rows.append(
                {
                    "id": _rdf_identifier(element),
                    "mRID": _child_text(element, "IdentifiedObject.mRID"),
                    "name": _child_text(element, "IdentifiedObject.name"),
                    "base_voltage_id": _child_resource(
                        element, "ConductingEquipment.BaseVoltage"
                    ),
                    "equipment_container_id": _child_resource(
                        element, "Equipment.EquipmentContainer"
                    ),
                    "profile": profile,
                    "source_file": file_path.name,
                }
            )
        return rows

    def _parse_connectivity_nodes_eq(
        self, file_path: Path, profile: str
    ) -> List[Dict[str, Optional[str]]]:
        rows: List[Dict[str, Optional[str]]] = []
        for element in _iter_cim_elements(file_path, "ConnectivityNode"):
            rows.append(
                {
                    "id": _rdf_identifier(element),
                    "mRID": _child_text(element, "IdentifiedObject.mRID"),
                    "name": _child_text(element, "IdentifiedObject.name"),
                    "container_id": _child_resource(
                        element, "ConnectivityNode.ConnectivityNodeContainer"
                    ),
                    "topological_node_id": None,
                    "profile": profile,
                    "source_file": file_path.name,
                }
            )
        return rows

    def _parse_connectivity_nodes_tp(
        self, file_path: Path, profile: str
    ) -> List[Dict[str, Optional[str]]]:
        rows: List[Dict[str, Optional[str]]] = []
        for element in _iter_cim_elements(file_path, "ConnectivityNode"):
            rows.append(
                {
                    "id": _rdf_identifier(element),
                    "mRID": None,
                    "name": None,
                    "container_id": None,
                    "topological_node_id": _child_resource(
                        element, "ConnectivityNode.TopologicalNode"
                    ),
                    "profile": profile,
                    "source_file": file_path.name,
                }
            )
        return rows

    def _parse_terminals_eq(
        self, file_path: Path, profile: str
    ) -> List[Dict[str, Optional[str]]]:
        rows: List[Dict[str, Optional[str]]] = []
        for element in _iter_cim_elements(file_path, "Terminal"):
            rows.append(
                {
                    "id": _rdf_identifier(element),
                    "mRID": _child_text(element, "IdentifiedObject.mRID"),
                    "name": _child_text(element, "IdentifiedObject.name"),
                    "conducting_equipment_id": _child_resource(
                        element, "Terminal.ConductingEquipment"
                    ),
                    "connectivity_node_id": _child_resource(
                        element, "Terminal.ConnectivityNode"
                    ),
                    "topological_node_id": None,
                    "sequence_number": _child_text(
                        element, "ACDCTerminal.sequenceNumber"
                    ),
                    "profile": profile,
                    "source_file": file_path.name,
                }
            )
        return rows

    def _parse_terminals_tp(
        self, file_path: Path, profile: str
    ) -> List[Dict[str, Optional[str]]]:
        rows: List[Dict[str, Optional[str]]] = []
        for element in _iter_cim_elements(file_path, "Terminal"):
            rows.append(
                {
                    "id": _rdf_identifier(element),
                    "mRID": None,
                    "name": None,
                    "conducting_equipment_id": None,
                    "connectivity_node_id": None,
                    "topological_node_id": _child_resource(
                        element, "Terminal.TopologicalNode"
                    ),
                    "sequence_number": None,
                    "profile": profile,
                    "source_file": file_path.name,
                }
            )
        return rows

    def _parse_power_transformer_ends(
        self, file_path: Path
    ) -> List[Dict[str, Optional[str]]]:
        rows: List[Dict[str, Optional[str]]] = []
        for element in _iter_cim_elements(file_path, "PowerTransformerEnd"):
            rows.append(
                {
                    "id": _rdf_identifier(element),
                    "mRID": _child_text(element, "IdentifiedObject.mRID"),
                    "name": _child_text(element, "IdentifiedObject.name"),
                    "transformer_id": _child_resource(element, "PowerTransformerEnd.PowerTransformer"),
                    "terminal_id": _child_resource(element, "TransformerEnd.Terminal"),
                    "base_voltage_id": _child_resource(element, "TransformerEnd.BaseVoltage"),
                    "end_number": _child_text(element, "TransformerEnd.endNumber"),
                    "rated_u": _child_text(element, "PowerTransformerEnd.ratedU"),
                    "rated_s": _child_text(element, "PowerTransformerEnd.ratedS"),
                    "r": _child_text(element, "PowerTransformerEnd.r"),
                    "x": _child_text(element, "PowerTransformerEnd.x"),
                    "b": _child_text(element, "PowerTransformerEnd.b"),
                    "g": _child_text(element, "PowerTransformerEnd.g"),
                    "connection_kind": _child_resource(element, "PowerTransformerEnd.connectionKind"),
                    "source_file": file_path.name,
                }
            )
        return rows

    def _parse_breakers(
        self, file_path: Path
    ) -> List[Dict[str, Optional[str]]]:
        rows: List[Dict[str, Optional[str]]] = []
        for element in _iter_cim_elements(file_path, "Breaker"):
            rows.append(
                {
                    "id": _rdf_identifier(element),
                    "mRID": _child_text(element, "IdentifiedObject.mRID"),
                    "name": _child_text(element, "IdentifiedObject.name"),
                    "equipment_container_id": _child_resource(element, "Equipment.EquipmentContainer"),
                    "normal_open": _child_text(element, "Switch.normalOpen"),
                    "retained": _child_text(element, "Switch.retained"),
                    "source_file": file_path.name,
                }
            )
        return rows

    def _parse_ratio_tap_changers(
        self, file_path: Path
    ) -> List[Dict[str, Optional[str]]]:
        rows: List[Dict[str, Optional[str]]] = []
        for element in _iter_cim_elements(file_path, "RatioTapChanger"):
            rows.append(
                {
                    "id": _rdf_identifier(element),
                    "mRID": _child_text(element, "IdentifiedObject.mRID"),
                    "name": _child_text(element, "IdentifiedObject.name"),
                    "transformer_end_id": _child_resource(element, "RatioTapChanger.TransformerEnd"),
                    "step_voltage_increment": _child_text(element, "RatioTapChanger.stepVoltageIncrement"),
                    "high_step": _child_text(element, "TapChanger.highStep"),
                    "low_step": _child_text(element, "TapChanger.lowStep"),
                    "neutral_step": _child_text(element, "TapChanger.neutralStep"),
                    "neutral_u": _child_text(element, "TapChanger.neutralU"),
                    "normal_step": _child_text(element, "TapChanger.normalStep"),
                    "ltc_flag": _child_text(element, "TapChanger.ltcFlag"),
                    "source_file": file_path.name,
                }
            )
        return rows

    def _parse_phase_tap_changers_asymmetrical(
        self, file_path: Path
    ) -> List[Dict[str, Optional[str]]]:
        rows: List[Dict[str, Optional[str]]] = []
        for element in _iter_cim_elements(file_path, "PhaseTapChangerAsymmetrical"):
            rows.append(
                {
                    "id": _rdf_identifier(element),
                    "mRID": _child_text(element, "IdentifiedObject.mRID"),
                    "name": _child_text(element, "IdentifiedObject.name"),
                    "transformer_end_id": _child_resource(element, "PhaseTapChanger.TransformerEnd"),
                    "winding_connection_angle": _child_text(element, "PhaseTapChangerAsymmetrical.windingConnectionAngle"),
                    "voltage_step_increment": _child_text(element, "PhaseTapChangerNonLinear.voltageStepIncrement"),
                    "x_max": _child_text(element, "PhaseTapChangerNonLinear.xMax"),
                    "x_min": _child_text(element, "PhaseTapChangerNonLinear.xMin"),
                    "high_step": _child_text(element, "TapChanger.highStep"),
                    "low_step": _child_text(element, "TapChanger.lowStep"),
                    "neutral_step": _child_text(element, "TapChanger.neutralStep"),
                    "neutral_u": _child_text(element, "TapChanger.neutralU"),
                    "normal_step": _child_text(element, "TapChanger.normalStep"),
                    "ltc_flag": _child_text(element, "TapChanger.ltcFlag"),
                    "source_file": file_path.name,
                }
            )
        return rows

    def _parse_phase_tap_changers_symmetrical(
        self, file_path: Path
    ) -> List[Dict[str, Optional[str]]]:
        rows: List[Dict[str, Optional[str]]] = []
        for element in _iter_cim_elements(file_path, "PhaseTapChangerSymmetrical"):
            rows.append(
                {
                    "id": _rdf_identifier(element),
                    "mRID": _child_text(element, "IdentifiedObject.mRID"),
                    "name": _child_text(element, "IdentifiedObject.name"),
                    "transformer_end_id": _child_resource(element, "PhaseTapChanger.TransformerEnd"),
                    "voltage_step_increment": _child_text(element, "PhaseTapChangerNonLinear.voltageStepIncrement"),
                    "x_max": _child_text(element, "PhaseTapChangerNonLinear.xMax"),
                    "x_min": _child_text(element, "PhaseTapChangerNonLinear.xMin"),
                    "high_step": _child_text(element, "TapChanger.highStep"),
                    "low_step": _child_text(element, "TapChanger.lowStep"),
                    "neutral_step": _child_text(element, "TapChanger.neutralStep"),
                    "neutral_u": _child_text(element, "TapChanger.neutralU"),
                    "normal_step": _child_text(element, "TapChanger.normalStep"),
                    "ltc_flag": _child_text(element, "TapChanger.ltcFlag"),
                    "source_file": file_path.name,
                }
            )
        return rows

    def _parse_synchronous_machines(
        self, file_path: Path
    ) -> List[Dict[str, Optional[str]]]:
        rows: List[Dict[str, Optional[str]]] = []
        for element in _iter_cim_elements(file_path, "SynchronousMachine"):
            rows.append(
                {
                    "id": _rdf_identifier(element),
                    "mRID": _child_text(element, "IdentifiedObject.mRID"),
                    "name": _child_text(element, "IdentifiedObject.name"),
                    "equipment_container_id": _child_resource(element, "Equipment.EquipmentContainer"),
                    "generating_unit_id": _child_resource(element, "RotatingMachine.GeneratingUnit"),
                    "rated_s": _child_text(element, "RotatingMachine.ratedS"),
                    "rated_u": _child_text(element, "RotatingMachine.ratedU"),
                    "rated_power_factor": _child_text(element, "RotatingMachine.ratedPowerFactor"),
                    "max_q": _child_text(element, "SynchronousMachine.maxQ"),
                    "min_q": _child_text(element, "SynchronousMachine.minQ"),
                    "q_percent": _child_text(element, "SynchronousMachine.qPercent"),
                    "machine_type": _child_resource(element, "SynchronousMachine.type"),
                    "source_file": file_path.name,
                }
            )
        return rows

    def _parse_generating_units(
        self, file_path: Path
    ) -> List[Dict[str, Optional[str]]]:
        rows: List[Dict[str, Optional[str]]] = []
        for element in _iter_cim_elements(file_path, "GeneratingUnit"):
            rows.append(
                {
                    "id": _rdf_identifier(element),
                    "mRID": _child_text(element, "IdentifiedObject.mRID"),
                    "name": _child_text(element, "IdentifiedObject.name"),
                    "equipment_container_id": _child_resource(element, "Equipment.EquipmentContainer"),
                    "max_operating_p": _child_text(element, "GeneratingUnit.maxOperatingP"),
                    "min_operating_p": _child_text(element, "GeneratingUnit.minOperatingP"),
                    "source_file": file_path.name,
                }
            )
        return rows

    def _parse_conform_loads(
        self, file_path: Path
    ) -> List[Dict[str, Optional[str]]]:
        rows: List[Dict[str, Optional[str]]] = []
        for element in _iter_cim_elements(file_path, "ConformLoad"):
            rows.append(
                {
                    "id": _rdf_identifier(element),
                    "mRID": _child_text(element, "IdentifiedObject.mRID"),
                    "name": _child_text(element, "IdentifiedObject.name"),
                    "equipment_container_id": _child_resource(element, "Equipment.EquipmentContainer"),
                    "load_group_id": _child_resource(element, "ConformLoad.LoadGroup"),
                    "source_file": file_path.name,
                }
            )
        return rows

    def _parse_non_conform_loads(
        self, file_path: Path
    ) -> List[Dict[str, Optional[str]]]:
        rows: List[Dict[str, Optional[str]]] = []
        for element in _iter_cim_elements(file_path, "NonConformLoad"):
            rows.append(
                {
                    "id": _rdf_identifier(element),
                    "mRID": _child_text(element, "IdentifiedObject.mRID"),
                    "name": _child_text(element, "IdentifiedObject.name"),
                    "equipment_container_id": _child_resource(element, "Equipment.EquipmentContainer"),
                    "load_group_id": _child_resource(element, "NonConformLoad.LoadGroup"),
                    "source_file": file_path.name,
                }
            )
        return rows

    def _parse_linear_shunt_compensators(
        self, file_path: Path
    ) -> List[Dict[str, Optional[str]]]:
        rows: List[Dict[str, Optional[str]]] = []
        for element in _iter_cim_elements(file_path, "LinearShuntCompensator"):
            rows.append(
                {
                    "id": _rdf_identifier(element),
                    "mRID": _child_text(element, "IdentifiedObject.mRID"),
                    "name": _child_text(element, "IdentifiedObject.name"),
                    "equipment_container_id": _child_resource(element, "Equipment.EquipmentContainer"),
                    "b_per_section": _child_text(element, "LinearShuntCompensator.bPerSection"),
                    "g_per_section": _child_text(element, "LinearShuntCompensator.gPerSection"),
                    "nom_u": _child_text(element, "ShuntCompensator.nomU"),
                    "maximum_sections": _child_text(element, "ShuntCompensator.maximumSections"),
                    "normal_sections": _child_text(element, "ShuntCompensator.normalSections"),
                    "grounded": _child_text(element, "ShuntCompensator.grounded"),
                    "source_file": file_path.name,
                }
            )
        return rows

    def _parse_static_var_compensators(
        self, file_path: Path
    ) -> List[Dict[str, Optional[str]]]:
        rows: List[Dict[str, Optional[str]]] = []
        for element in _iter_cim_elements(file_path, "StaticVarCompensator"):
            rows.append(
                {
                    "id": _rdf_identifier(element),
                    "mRID": _child_text(element, "IdentifiedObject.mRID"),
                    "name": _child_text(element, "IdentifiedObject.name"),
                    "equipment_container_id": _child_resource(element, "Equipment.EquipmentContainer"),
                    "capacitive_rating": _child_text(element, "StaticVarCompensator.capacitiveRating"),
                    "inductive_rating": _child_text(element, "StaticVarCompensator.inductiveRating"),
                    "slope": _child_text(element, "StaticVarCompensator.slope"),
                    "source_file": file_path.name,
                }
            )
        return rows

    def _parse_series_compensators(
        self, file_path: Path
    ) -> List[Dict[str, Optional[str]]]:
        rows: List[Dict[str, Optional[str]]] = []
        for element in _iter_cim_elements(file_path, "SeriesCompensator"):
            rows.append(
                {
                    "id": _rdf_identifier(element),
                    "mRID": _child_text(element, "IdentifiedObject.mRID"),
                    "name": _child_text(element, "IdentifiedObject.name"),
                    "equipment_container_id": _child_resource(element, "Equipment.EquipmentContainer"),
                    "base_voltage_id": _child_resource(element, "ConductingEquipment.BaseVoltage"),
                    "r": _child_text(element, "SeriesCompensator.r"),
                    "x": _child_text(element, "SeriesCompensator.x"),
                    "source_file": file_path.name,
                }
            )
        return rows

    def _parse_equivalent_injections(
        self, file_path: Path
    ) -> List[Dict[str, Optional[str]]]:
        rows: List[Dict[str, Optional[str]]] = []
        for element in _iter_cim_elements(file_path, "EquivalentInjection"):
            rows.append(
                {
                    "id": _rdf_identifier(element),
                    "mRID": _child_text(element, "IdentifiedObject.mRID"),
                    "name": _child_text(element, "IdentifiedObject.name"),
                    "equipment_container_id": _child_resource(element, "Equipment.EquipmentContainer"),
                    "base_voltage_id": _child_resource(element, "ConductingEquipment.BaseVoltage"),
                    "regulation_capability": _child_text(element, "EquivalentInjection.regulationCapability"),
                    "source_file": file_path.name,
                }
            )
        return rows

    def _parse_lines(
        self, file_path: Path
    ) -> List[Dict[str, Optional[str]]]:
        rows: List[Dict[str, Optional[str]]] = []
        for element in _iter_cim_elements(file_path, "Line"):
            rows.append(
                {
                    "id": _rdf_identifier(element),
                    "mRID": _child_text(element, "IdentifiedObject.mRID"),
                    "name": _child_text(element, "IdentifiedObject.name"),
                    "region_id": _child_resource(element, "Line.Region"),
                    "source_file": file_path.name,
                }
            )
        return rows

    def parse_common_data_file(self, common_data_file: str | Path) -> CgmesData:
        file_path = Path(common_data_file)
        if not file_path.exists():
            raise FileNotFoundError(f"CommonData file not found: {file_path}")

        objects: Dict[str, List[Dict[str, Optional[str]]]] = {
            class_name: [] for class_name in self.ALL_CLASSES
        }

        objects["BaseVoltage"] = self._parse_base_voltages(file_path)
        objects["GeographicalRegion"] = self._parse_geographical_regions(file_path)
        objects["SubGeographicalRegion"] = self._parse_sub_geographical_regions(file_path)

        return CgmesData(
            source_folder=file_path.parent,
            profiles={"CD": [file_path]},
            objects=objects,
        )

    def _parse_base_voltages(
        self, file_path: Path
    ) -> List[Dict[str, Optional[str]]]:
        rows: List[Dict[str, Optional[str]]] = []
        for element in _iter_cim_elements(file_path, "BaseVoltage"):
            rows.append(
                {
                    "id": _rdf_identifier(element),
                    "mRID": _child_text(element, "IdentifiedObject.mRID"),
                    "name": _child_text(element, "IdentifiedObject.name"),
                    "nominal_voltage": _child_text(element, "BaseVoltage.nominalVoltage"),
                    "source_file": file_path.name,
                }
            )
        return rows

    def _parse_geographical_regions(
        self, file_path: Path
    ) -> List[Dict[str, Optional[str]]]:
        rows: List[Dict[str, Optional[str]]] = []
        for element in _iter_cim_elements(file_path, "GeographicalRegion"):
            rows.append(
                {
                    "id": _rdf_identifier(element),
                    "mRID": _child_text(element, "IdentifiedObject.mRID"),
                    "name": _child_text(element, "IdentifiedObject.name"),
                    "source_file": file_path.name,
                }
            )
        return rows

    def _parse_sub_geographical_regions(
        self, file_path: Path
    ) -> List[Dict[str, Optional[str]]]:
        rows: List[Dict[str, Optional[str]]] = []
        for element in _iter_cim_elements(file_path, "SubGeographicalRegion"):
            rows.append(
                {
                    "id": _rdf_identifier(element),
                    "mRID": _child_text(element, "IdentifiedObject.mRID"),
                    "name": _child_text(element, "IdentifiedObject.name"),
                    "region_id": _child_resource(element, "SubGeographicalRegion.Region"),
                    "source_file": file_path.name,
                }
            )
        return rows
