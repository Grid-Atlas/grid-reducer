import copy
import networkx as nx
import time

from grid_reducer.altdss.altdss_models import Circuit
from grid_reducer.network import get_graph_from_circuit


def transform_bus_coordinates(circuit: Circuit) -> Circuit:
    """Function to transform the coordinates so it's not traceable."""

    graph = get_graph_from_circuit(circuit)
    start = time.time()
    print("Transforming coordinates...")
    pos = nx.kamada_kawai_layout(graph)
    print(f"Time: {time.time() - start}")
    new_buses = []
    for bus in circuit.Bus:
        new_bus = copy.deepcopy(bus)
        new_bus.X = pos[bus.Name][0]
        new_bus.Y = pos[bus.Name][1]
        new_buses.append(new_bus)
    new_circuit = copy.deepcopy(circuit)
    new_circuit.Bus = new_buses
    return new_circuit
