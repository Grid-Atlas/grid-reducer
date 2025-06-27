import copy
import math
import random

import numpy as np

from grid_reducer.altdss.altdss_models import Circuit
from grid_reducer.transform_coordinate import get_switch_connected_buses
from grid_reducer.transform_coordinate import remove_bus_coordinates


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


def apply_planar_laplace_noise(x: float, y: float, epsilon: float) -> tuple[float, float]:
    # Generate random angle and radius
    theta = 2 * math.pi * random.random()
    u1, u2 = random.random(), random.random()
    r = -(1 / epsilon) * math.log(u1 * u2)  # Radial noise from Gamma distribution

    # Apply noise in polar coordinates
    x_noisy = x + r * math.cos(theta)
    y_noisy = y + r * math.sin(theta)
    return x_noisy, y_noisy


def get_dp_circuit(circuit: Circuit, transform_coordinate: bool, noise_level: str) -> Circuit:
    """
    Adds differential privacy to the circuit by perturbing bus coordinates with noise.

    Args:
        circuit (Circuit): The original circuit object whose bus coordinates will be perturbed.
        transform_coordinate (bool): If True, adds Gaussian noise to all bus coordinates.
                                    If False, adds planar Laplace noise only to non-switch-connected bus coordinates.
        noise_level (str): Specifies the strength of the noise: "low", "medium", or "high".

    Returns:
        Circuit: A new circuit object with perturbed bus coordinates.

    """

    new_buses = []
    if transform_coordinate:
        # simply add noise to the bus coordinates
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
        for bus in circuit.Bus:
            new_bus = copy.deepcopy(bus)
            new_bus.X = apply_gaussian_dp_noise(new_bus.X, noise_scale) if new_bus.X else new_bus.X
            new_bus.Y = apply_gaussian_dp_noise(new_bus.Y, noise_scale) if new_bus.Y else new_bus.Y
            new_buses.append(new_bus)
        new_circuit = copy.deepcopy(circuit)
        new_circuit.Bus = new_buses
        return new_circuit
    else:
        # check for switch connected buses and do not perturb their coordinates
        match noise_level:
            case "low":
                epsilon = 5000
            case "medium":
                epsilon = 3500
            case "high":
                epsilon = 2000
            case _:
                epsilon = 5000  # Default to low
        print(f"Noise level:{noise_level}; Epsilon: {epsilon}")
        switch_buses = get_switch_connected_buses(circuit)
        circuit1 = remove_bus_coordinates(circuit, switch_buses)
        for bus in circuit1.Bus:
            new_bus = copy.deepcopy(bus)
            if new_bus.X and new_bus.Y:
                new_bus.X, new_bus.Y = apply_planar_laplace_noise(new_bus.X, new_bus.Y, epsilon)
            new_buses.append(new_bus)
        new_circuit = copy.deepcopy(circuit)
        new_circuit.Bus = new_buses
        return new_circuit
