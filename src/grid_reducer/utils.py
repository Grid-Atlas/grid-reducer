from pathlib import Path
import json
from typing import Any, Type, TypeVar
from collections import defaultdict

import opendssdirect as odd
from uuid import uuid4
from pydantic import BaseModel
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from grid_reducer.altdss.altdss_models import Circuit, BusConnection, SwtControlState


T = TypeVar("T", bound=BaseModel)


def get_dict_from_opendss(master_file: Path) -> dict:
    odd.Text.Command(f'Redirect "{master_file}"')
    odd.Text.Command("Solve")
    circuit_dict = json.loads(odd.Circuit.ToJSON())
    odd.Text.Command("clear")
    return circuit_dict


def get_ckt_from_opendss_model(master_file: Path) -> Circuit:
    circuit_dict = get_dict_from_opendss(master_file)
    return Circuit.model_validate(circuit_dict)


def get_circuit_bus_name(circuit: Circuit) -> str:
    return circuit.Vsource.root.root[0].root.Bus1.root.split(".")[0]


def get_bus_voltage_ln_mapper(circuit: Circuit) -> dict[str, float]:
    bus_voltage_mapper = {}
    for bus in circuit.Bus:
        bus_voltage_mapper[bus.Name] = bus.kVLN
    return bus_voltage_mapper


def get_bus_connected_assets(asset_container: Any, bus_name: str) -> list[Any]:
    return [
        asset.root
        for asset in asset_container.root.root
        if asset.root.Bus1.root.split(".")[0] == bus_name
    ]


def write_to_opendss_file(circuit: Circuit, output_file: Path | str) -> None:
    with open(output_file, "w", encoding="utf-8") as fp:
        circuit.dump_dss(fp)


def read_json_file(file_path: Path) -> dict:
    with open(file_path, "r", encoding="utf-8") as fp:
        contents = json.load(fp)
    return contents


def generate_short_name() -> str:
    return str(uuid4())


def get_number_of_phases_from_bus(bus: str) -> int:
    if "." not in bus:
        return 3
    bus_splits = bus.split(".")[1:]
    if "0" in bus_splits:
        bus_splits.remove("0")
    return len(bus_splits)


def get_tuple_of_values_from_object(obj: BaseModel, params: set[str]) -> tuple[Any, ...]:
    return tuple(
        tuple(value) if isinstance(value, list) else value
        for key in params
        for value in [getattr(obj, key)]
    )


def get_extra_param_values(
    class_type: Type[BaseModel], objects: list[BaseModel], params_to_aggregate: set[str]
) -> dict[str, Any]:
    other_params = class_type.model_fields.keys() - params_to_aggregate
    other_params_val_mapper = {}
    for key in other_params:
        first_val = getattr(objects[0], key)
        values = set(
            [
                tuple(getattr(obj, key)) if isinstance(first_val, list) else getattr(obj, key)
                for obj in objects
            ]
        )
        if len(values) > 1:
            raise NotImplementedError(
                f"Aggregating {class_type=} with different {values=} for {key=} is not supported yet."
            )
        other_params_val_mapper[key] = first_val
    return other_params_val_mapper


def sum_or_none(elements):
    if all(el is None for el in elements):
        return None
    return sum(el for el in elements if el is not None)


def weighted_average_or_none(values, weights):
    # Filter out pairs where either value or weight is None
    filtered = [
        (v, w) for v, w in zip(values, weights, strict=False) if v is not None and w is not None
    ]

    if not filtered:
        return None

    total_weight = sum(w for _, w in filtered)
    if total_weight == 0:
        return None

    weighted_sum = sum(v * w for v, w in filtered)
    return weighted_sum / total_weight


def extract_bus_name(bus_obj: BusConnection) -> str:
    return bus_obj.root.split(".")[0]


def group_objects_excluding_fields(objects: list[T], fields: set) -> dict[str, list[T]]:
    """Group objects by the specified fields."""
    value_mapper = defaultdict(list)
    obj_type = type(objects[0])
    for obj in objects:
        key = get_tuple_of_values_from_object(obj, obj_type.model_fields.keys() - fields)
        value_mapper[repr(key)].append(obj)
    return value_mapper


def get_open_lines(circuit_obj: Circuit) -> list[str]:
    """Get a list of open lines from the circuit object."""
    open_lines = []
    for command in circuit_obj.PostCommands:
        if command.startswith("Open Line."):
            open_lines.append(command.split(".")[1].split(" ")[0])
    return open_lines


def get_normally_open_switches(circuit_obj: Circuit) -> list[str]:
    normally_open_switches = []
    for line in circuit_obj.Line.root.root:
        if line.root.Enabled is False:
            normally_open_switches.append(line.root.Name)
    if circuit_obj.SwtControl is None:
        return normally_open_switches
    for switch in circuit_obj.SwtControl.root.root:
        if switch.SwitchedObj and switch.Normal == SwtControlState.open:
            normally_open_switches.append(switch.SwitchedObj.replace("Line.", ""))
    return normally_open_switches


console = Console()


def print_summary_to_cli(summary: dict):
    text = ""
    for section, details in summary.items():
        text += f"{section}:\n"
        for key, val in details.items():
            text += f"  - {key}: {val}\n"
    markdown = Markdown(text)
    console.print(Panel.fit(markdown, title="🧾 Summary Report", border_style="green"))
