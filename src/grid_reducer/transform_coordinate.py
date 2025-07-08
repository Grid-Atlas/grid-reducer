import copy
import time

import networkx as nx

from grid_reducer.altdss.altdss_models import Circuit
from grid_reducer.network import get_graph_from_circuit
from grid_reducer.utils import extract_bus_name


def get_switch_connected_buses(circuit: Circuit) -> set[str]:
    """
    Returns a set of buses that are connected by switches, considering both
    SwtControl objects and Line elements with Switch=True/y/yes.
    """
    if not circuit.Line:
        return []
    buses_to_preserve = set()
    lines_that_are_switch = set()

    if circuit.SwtControl:
        for switch in circuit.SwtControl.root.root:
            if not switch.SwitchedObj:
                continue
            lines_that_are_switch.add(switch.SwitchedObj.replace("Line.", ""))

    for line in circuit.Line.root.root:
        is_switch_line = (
            line.root.Name in lines_that_are_switch
            or line.root.Enabled is False
            or line.root.Switch
        )
        if is_switch_line:
            bus1 = extract_bus_name(getattr(line.root, "Bus1", ""))
            bus2 = extract_bus_name(getattr(line.root, "Bus2", ""))
            buses_to_preserve.update([bus1, bus2])
    return buses_to_preserve


def remove_bus_coordinates(circuit: Circuit, preserve_buses: list[str] | None):
    if preserve_buses is None:
        preserve_buses = []

    new_buses = []
    for bus in circuit.Bus:
        if bus.Name not in preserve_buses:
            new_bus = copy.deepcopy(bus)
            new_bus.X = None
            new_bus.Y = None
            new_buses.append(new_bus)
        else:
            new_buses.append(bus)
    new_circuit = copy.deepcopy(circuit)
    new_circuit.Bus = new_buses
    return new_circuit


def transform_bus_coordinates(circuit: Circuit) -> Circuit:
    """Function to transform the coordinates so it's not traceable."""

    switch_buses = get_switch_connected_buses(circuit)
    new_circuit = remove_bus_coordinates(circuit, switch_buses)
    if switch_buses:
        return new_circuit
    graph = get_graph_from_circuit(new_circuit)
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
