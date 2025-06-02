from pathlib import Path
import json
from typing import Any

import opendssdirect as odd
import xxhash

from grid_reducer.altdss.altdss_models import Circuit


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


def generate_short_name(long_string: str) -> str:
    return xxhash.xxh32(long_string).hexdigest()[:8]
