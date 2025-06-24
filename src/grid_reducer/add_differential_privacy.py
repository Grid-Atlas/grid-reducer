import copy
import numpy as np
from grid_reducer.altdss.altdss_models import Circuit
from typing import List

def apply_gaussian_dp_noise(value: float, std_dev: float) -> float:
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

def get_dp_circuit(circuit: Circuit, positions: List,  noise_level: str) -> Circuit:
    """
    Add differential privacy to the circuit by perturbing bus coordinates.

    Args:
        circuit (Circuit): The original circuit object.
        std_dev (float): Standard deviation of the Gaussian noise.

    Returns:
        Circuit: New circuit object with perturbed bus coordinates.
    """


    match noise_level:
        case "low":
            noise_scale = 0.01
        case "medium":
            noise_scale = 0.05
        case "high":
            noise_scale = 0.1
        case _:
            noise_scale = 0.01  # default case is the low case
    print(f"Noise level:{noise_level}; Noise scale: {noise_scale}")
    new_buses= []
    for bus in circuit.Bus:
        new_bus = copy.deepcopy(bus)
        new_bus.X = apply_gaussian_dp_noise(positions[bus.Name][0], noise_scale)
        new_bus.Y = apply_gaussian_dp_noise(positions[bus.Name][1], noise_scale)
        new_buses.append(new_bus)
    new_circuit = copy.deepcopy(circuit)
    new_circuit.Bus = new_buses
    return new_circuit 
