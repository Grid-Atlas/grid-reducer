import copy
import math
import random
from dataclasses import dataclass
from typing import Union, Literal

import numpy as np

from grid_reducer.altdss.altdss_models import Circuit


@dataclass
class NoiseSetting:
    type: Literal["geo_coordinate", "non_geo_coordinate"]
    value: Union[int, float]


GEO_COORDINATE_NOISE_SETTINGS = {
    "low": NoiseSetting(type="geo_coordinate", value=5000),
    "medium": NoiseSetting(type="geo_coordinate", value=3500),
    "high": NoiseSetting(type="geo_coordinate", value=2000),
}


NON_GEO_COORDINATE_NOISE_SETTINGS = {
    "low": NoiseSetting(type="non_geo_coordinate", value=0.01),
    "medium": NoiseSetting(type="non_geo_coordinate", value=0.05),
    "high": NoiseSetting(type="non_geo_coordinate", value=0.1),
}


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


def is_geo_coordinate(x: float, y: float) -> bool:
    """
    Determines if coordinates are in standard geo-coordinate ranges,
    excluding transformed layout coordinates (like from kamada_kawai_layout).

    Transformed layouts typically produce coordinates in [0,1] or [-1,1] range.
    """
    # Check if coordinates are within standard geo bounds
    geo_bounds = (-180.0 <= x <= 180.0) and (-90.0 <= y <= 90.0)

    # Exclude transformed layout coordinates (typical range: [-1.5, 1.5])
    is_transformed = (-1.5 <= x <= 1.5) and (-1.5 <= y <= 1.5)

    return geo_bounds and not is_transformed


def get_dp_circuit(circuit: Circuit, noise_level: str) -> Circuit:
    """
    Applies differential privacy to all bus coordinates:
    - Planar Laplace noise for all geo-coordinates (including switch-connected)
    - Gaussian noise for transformed layout coordinates

    Args:
        circuit (Circuit): Original circuit
        noise_level (str): "low", "medium", or "high" noise strength

    Returns:
        Circuit: New circuit with perturbed bus coordinates
    """

    geo_config = GEO_COORDINATE_NOISE_SETTINGS.get(
        noise_level, GEO_COORDINATE_NOISE_SETTINGS["low"]
    )
    non_geo_config = NON_GEO_COORDINATE_NOISE_SETTINGS.get(
        noise_level, NON_GEO_COORDINATE_NOISE_SETTINGS["low"]
    )

    new_buses = []
    geo_count = 0
    non_geo_count = 0

    for bus in circuit.Bus:
        new_bus = copy.deepcopy(bus)

        if new_bus.X is not None and new_bus.Y is not None:
            if is_geo_coordinate(new_bus.X, new_bus.Y):
                new_bus.X, new_bus.Y = apply_planar_laplace_noise(
                    new_bus.X, new_bus.Y, int(geo_config.value)
                )
                geo_count += 1
            else:
                noise_scale = float(non_geo_config.value)
                new_bus.X = apply_gaussian_dp_noise(new_bus.X, noise_scale)
                new_bus.Y = apply_gaussian_dp_noise(new_bus.Y, noise_scale)
                non_geo_count += 1

        new_buses.append(new_bus)

    # print(f"Processed {geo_count} geo-coordinates and {non_geo_count} non-geo coordinates")

    new_circuit = copy.deepcopy(circuit)
    new_circuit.Bus = new_buses
    return new_circuit
