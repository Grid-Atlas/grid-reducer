import copy
import time
import numpy as np

import networkx as nx

from grid_reducer.altdss.altdss_models import Circuit
from grid_reducer.network import get_graph_from_circuit
from grid_reducer.utils import extract_bus_name


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

def add_gaussian_noise(value, std_dev):
    """
    Add Gaussian noise to a value, based on the given standard deviation.

    Args:
        value (float): Original value to perturb.
        std_dev (float): Standard deviation of the Gaussian noise.

    Returns:
        float: Perturbed value with Gaussian noise applied.
    """
    noise = np.random.normal(0, std_dev)  # Generate Gaussian noise centered at 0
    return value + noise

def transform_bus_coordinates_original(circuit: Circuit) -> Circuit:
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


def transform_bus_coordinates(circuit: Circuit) -> Circuit:
    """Function to transform the coordinates so it's not traceable."""

    noise_scale = 0.01
    std_dev = noise_scale
    graph = get_graph_from_circuit(circuit)
    start = time.time()
    print("Transforming coordinates...")
    pos = nx.kamada_kawai_layout(graph)
    print(pos)
    print(circuit.Bus[0])
    
    print(f"Time: {time.time() - start}")
    new_buses, new_buses2 = [], []
    for bus in circuit.Bus:
        new_bus = copy.deepcopy(bus)
        new_bus2 = copy.deepcopy(bus)
        new_bus.X = pos[bus.Name][0]
        new_bus.Y = pos[bus.Name][1]
        new_bus2.X = pos[bus.Name][0]
        new_bus2.Y = pos[bus.Name][1]
        # Add Gaussian noise to the coordinates
        new_bus.X = add_gaussian_noise(new_bus.X, std_dev)
        new_bus.Y = add_gaussian_noise(new_bus.Y, std_dev)
        new_buses.append(new_bus)
        new_buses2.append(new_bus2)
    new_circuit = copy.deepcopy(circuit)
    new_circuit.Bus = new_buses

    new_circuit2 = copy.deepcopy(circuit)
    new_circuit2.Bus = new_buses2
    return new_circuit, new_circuit2
