from pathlib import Path
import re

import networkx as nx
import pytest

from grid_reducer.utils import get_ckt_from_opendss_model, write_to_opendss_file
from grid_reducer.network import get_graph_from_circuit
from grid_reducer.aggregate_secondary import aggregate_secondary_assets
from grid_reducer.opendss import OpenDSS
from grid_reducer.reducer import OpenDSSModelReducer

root_folder = Path(__file__).parent / "data"
additional_data_folder = Path(__file__).parent / "../data"
test_folders = [root_folder, additional_data_folder]
files = []
for folder in test_folders:
    if folder.exists():
        pattern = re.compile(r".*master.*\.dss$", re.IGNORECASE)
        files += [f for f in folder.rglob("*.dss") if pattern.search(f.name)]


@pytest.mark.parametrize("file", files)
def test_networkx_graph_creation(file):
    circuit = get_ckt_from_opendss_model(file)
    graph = get_graph_from_circuit(circuit)
    assert isinstance(graph, nx.Graph)


@pytest.mark.parametrize("file", files)
def test_secondary_aggregation(file, tmp_path):
    circuit = get_ckt_from_opendss_model(file)
    new_circuit = aggregate_secondary_assets(circuit)
    original_circuit_file = tmp_path / "original_ckt.dss"
    reduced_circuit_file = tmp_path / "reduced_ckt.dss"
    write_to_opendss_file(circuit, original_circuit_file)
    write_to_opendss_file(new_circuit, reduced_circuit_file)
    compare_powerflow_results(original_circuit_file, reduced_circuit_file)


def compare_powerflow_results(original_circuit_file, reduced_circuit_file):
    original_ckt_power = OpenDSS(original_circuit_file).get_circuit_power()
    reduced_ckt_power = OpenDSS(reduced_circuit_file).get_circuit_power()
    assert abs((original_ckt_power.real - reduced_ckt_power.real) / original_ckt_power.real) < 0.1


@pytest.mark.parametrize("file", files)
def test_primary_aggregation(file, tmp_path):
    reducer = OpenDSSModelReducer(master_dss_file=file)
    reduced_ckt = reducer.reduce(transform_coordinate=False)
    original_circuit_file = tmp_path / "original_ckt.dss"
    reduced_circuit_file = tmp_path / "reduced_ckt.dss"
    reducer.export_original_ckt(original_circuit_file)
    reducer.export(reduced_ckt, reduced_circuit_file)
    compare_powerflow_results(original_circuit_file, reduced_circuit_file)
