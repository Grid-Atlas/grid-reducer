from abc import ABC, abstractmethod
import math
from typing import Type

from grid_reducer.altdss.altdss_models import Load_kWkvar, Load_kVAPF, Load_kWPF, BusConnection
from grid_reducer.utils import (
    get_number_of_phases_from_bus,
    get_extra_param_values,
    generate_short_name,
    group_objects_excluding_fields,
)
from grid_reducer.aggregators.registry import register_aggregator


class LoadAggregationStrategy(ABC):
    @abstractmethod
    def compute(self, loads: list) -> tuple[float, float, float, float]:
        """Returns (kW, kvar, kVA, pf)"""
        pass


class KWKVARAggregation(LoadAggregationStrategy):
    def compute(self, loads: list[Load_kWkvar]):
        total_kw = sum(load.kW for load in loads)
        total_kvar = sum(load.kvar for load in loads)
        total_kva = math.sqrt(total_kw**2 + total_kvar**2)
        total_pf = total_kw / total_kva if total_kva else 0.0
        return total_kw, total_kvar, total_kva, total_pf


class KVAPFAggregation(LoadAggregationStrategy):
    def compute(self, loads: list[Load_kVAPF]):
        total_kw = sum(load.kVA * abs(load.PF) for load in loads)
        total_kvar = sum(
            math.sqrt(load.kVA**2 - (load.kVA * abs(load.PF)) ** 2) * (-1 if load.PF < 0 else 1)
            for load in loads
        )
        total_kva = math.sqrt(total_kw**2 + total_kvar**2)
        total_pf = total_kw / total_kva if total_kva else 0.0
        total_pf *= -1 if total_kvar < 0 else 1
        return total_kw, total_kvar, total_kva, total_pf


class KWPFAggregation(LoadAggregationStrategy):
    def compute(self, loads: list[Load_kWPF]):
        total_kw = sum(load.kW for load in loads)
        total_kvar = sum(
            math.sqrt((load.kW / abs(load.PF)) ** 2 - load.kW**2) * (-1 if load.PF < 0 else 1)
            for load in loads
        )
        total_kva = math.sqrt(total_kw**2 + total_kvar**2)
        total_pf = total_kw / total_kva if total_kva else 0.0
        total_pf *= -1 if total_kvar < 0 else 1
        return total_kw, total_kvar, total_kva, total_pf


def _aggregate_loads(
    loads: list,
    bus1: str,
    kv: float,
    load_cls: Type,
    fields: set,
    strategy: LoadAggregationStrategy,
) -> list:
    value_mapper = group_objects_excluding_fields(loads, fields)
    new_loads = []
    for _, load_list in value_mapper.items():
        new_load_name = generate_short_name()
        num_phase = get_number_of_phases_from_bus(bus1)
        base_kv = kv if num_phase == 1 else round(kv * math.sqrt(3), 3)
        total_kw, total_kvar, total_kva, total_pf = strategy.compute(load_list)

        power_args = {
            "kW": round(total_kw, 3),
            "kvar": round(total_kvar, 3),
            "kVA": round(total_kva, 3),
            "PF": round(total_pf, 3),
        }
        new_loads.append(
            load_cls(
                Name=new_load_name,
                Bus1=BusConnection(root=bus1),
                Phases=num_phase,
                kV=base_kv,
                **{k: power_args[k] for k in fields if k in power_args},
                **get_extra_param_values(load_cls, load_list, fields),
            )
        )

    return new_loads


@register_aggregator(Load_kWkvar)
def aggregate_load_kwkvar(loads: list[Load_kWkvar], bus1: str, kv: float) -> list[Load_kWkvar]:
    return _aggregate_loads(
        loads,
        bus1,
        kv,
        load_cls=Load_kWkvar,
        fields={"Name", "Bus1", "Phases", "kV", "kW", "kvar"},
        strategy=KWKVARAggregation(),
    )


@register_aggregator(Load_kVAPF)
def aggregate_load_kvapf(loads: list[Load_kVAPF], bus1: str, kv: float) -> list[Load_kVAPF]:
    return _aggregate_loads(
        loads,
        bus1,
        kv,
        load_cls=Load_kVAPF,
        fields={"Name", "Bus1", "Phases", "kV", "kVA", "PF"},
        strategy=KVAPFAggregation(),
    )


@register_aggregator(Load_kWPF)
def aggregate_load_kwpf(loads: list[Load_kWPF], bus1: str, kv: float) -> list[Load_kWPF]:
    return _aggregate_loads(
        loads,
        bus1,
        kv,
        load_cls=Load_kWPF,
        fields={"Name", "Bus1", "Phases", "kV", "kW", "PF"},
        strategy=KWPFAggregation(),
    )
