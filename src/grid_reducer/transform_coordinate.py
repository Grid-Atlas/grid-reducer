import copy
import time
import numpy as np

import networkx as nx

from grid_reducer.altdss.altdss_models import Circuit
from grid_reducer.network import get_graph_from_circuit
from grid_reducer.utils import extract_bus_name
from grid_reducer.add_differential_privacy import get_dp_circuit


def get_switch_connected_buses(circuit: Circuit) -> list[str]:
    if not circuit.Line:
        return []

    buses_to_preserve = set()
    lines_that_are_switch = []
    if circuit.SwtControl:
        for switch in circuit.SwtControl.root.root:
            if switch.SwitchedObj:
                lines_that_are_switch.append(switch.SwitchedObj.replace("Line.", ""))
    for line in circuit.Line.root.root:
        if line.root.Name in lines_that_are_switch or line.root.Enabled is False:
            bus1 = extract_bus_name(line.root.Bus1)
            bus2 = extract_bus_name(line.root.Bus2)
            buses_to_preserve.update([bus1, bus2])

    return buses_to_preserve


def remove_bus_coordinates(circuit: Circuit, preserve_buses: list[str] | None):
    if preserve_buses is None:
        preserve_buses = []

    new_buses = []
    for bus in circuit.Bus:
        if bus.Name in preserve_buses:
            new_bus = copy.deepcopy(bus)
            new_bus.X = None
            new_bus.Y = None
            new_buses.append(new_bus)
        else:
            new_buses.append(bus)
    new_circuit = copy.deepcopy(circuit)
    new_circuit.Bus = new_buses
    return new_circuit





def transform_bus_coordinates(circuit: Circuit, noise_level:str = "low") -> Circuit:
    """Function to transform the coordinates so it's not traceable."""

    switch_buses = get_switch_connected_buses(circuit)
    new_circuit = remove_bus_coordinates(circuit, switch_buses)
    print(f"Circuit: {circuit}")
    print(f"switch_buses: {switch_buses}")
    print(f"new_circuit: {new_circuit}")
    if switch_buses:
        return new_circuit

    
    graph = get_graph_from_circuit(new_circuit)
    print("Transforming coordinates...")
    start = time.time()
    pos = nx.kamada_kawai_layout(graph)
    #print(pos)
    #print(circuit.Bus[0])
    
    print(f"Time: {time.time() - start}")
    if(noise_level == "none"):
        print("No noise added to the coordinates.")
        new_buses= []
        for bus in circuit.Bus:
            new_bus = copy.deepcopy(bus)
            new_bus.X = pos[bus.Name][0]
            new_bus.Y = pos[bus.Name][1]
            new_buses.append(new_bus)
        new_circuit = copy.deepcopy(circuit)
        new_circuit.Bus = new_buses
        return new_circuit
    else:
        new_circuit = get_dp_circuit(circuit, pos, noise_level)
        return new_circuit
