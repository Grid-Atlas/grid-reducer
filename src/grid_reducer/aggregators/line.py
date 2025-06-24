from typing import TypeVar, Type

from pint import Quantity
from pydantic import BaseModel

from grid_reducer.altdss.altdss_models import Bus, Line_Common, LengthUnit
from grid_reducer.similarity.line import LineSimilarity
from grid_reducer.utils import generate_short_name

T = TypeVar("T")


def _find_start_end_buses_set_based(lines: list[Line_Common]) -> tuple[Bus, Bus]:
    assert len(lines) >= 2
    bus_counts = {}

    for line in lines:
        for bus in (line.Bus1, line.Bus2):
            bus_counts[bus.root] = bus_counts.get(bus.root, 0) + 1

    # Start bus: from first line, whichever bus appears only once
    first_line_buses = [lines[0].Bus1, lines[0].Bus2]
    last_line_buses = [lines[-1].Bus1, lines[-1].Bus2]

    start_bus = next(bus for bus in first_line_buses if bus_counts[bus.root] == 1)
    end_bus = next(bus for bus in last_line_buses if bus_counts[bus.root] == 1)

    return start_bus, end_bus


def aggregate_lines(lines: list[T]) -> T:
    assert len(lines) >= 2
    line_class: Type[BaseModel] = type(lines[0])
    common_fields = line_class.model_fields.keys() - LineSimilarity.ignore_fields

    common_values_dict = {}
    for field in common_fields:
        common_values_dict[field] = getattr(lines[0], field)

    new_line_name = generate_short_name()
    bus1, bus2 = _find_start_end_buses_set_based(lines)
    data = {
        "Name": new_line_name,
        "Bus1": bus1,
        "Bus2": bus2,
    }
    if "Length" in line_class.model_fields:
        data["Length"] = (
            sum([Quantity(line.Length, line.Units.value) for line in lines]).to("m").magnitude
        )
        data["Units"] = LengthUnit.m

    return line_class(
        **data,
        **common_values_dict,
    )
