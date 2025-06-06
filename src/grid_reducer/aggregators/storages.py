from abc import ABC, abstractmethod
import math

from grid_reducer.altdss.altdss_models import (
    Storage_kWRatedkvar,
    Storage_kWRatedPF,
    Storage_Common,
    BusConnection,
)
from grid_reducer.utils import (
    generate_short_name,
    get_number_of_phases_from_bus,
    get_extra_param_values,
    sum_or_none,
    group_objects_excluding_fields,
)
from grid_reducer.aggregators.registry import register_aggregator


class StorageAggregationStrategy(ABC):
    @abstractmethod
    def compute(self, pvs: list) -> float:
        pass


class PFAggregation(StorageAggregationStrategy):
    def compute(self, storages: list[Storage_kWRatedPF]):
        total_kw = sum(storage.kWRated for storage in storages)
        total_kvar = sum(
            math.sqrt((storage.kWRated / abs(storage.PF)) ** 2 - storage.kWRated**2)
            * (-1 if storage.PF < 0 else 1)
            for storage in storages
        )
        total_kva = math.sqrt(total_kw**2 + total_kvar**2)
        total_pf = total_kw / total_kva if total_kva else 0.0
        total_pf *= -1 if total_kvar < 0 else 1
        return total_pf


class KvarAggregation(StorageAggregationStrategy):
    def compute(self, storages: list[Storage_kWRatedkvar]):
        return sum_or_none([storage.kvar for storage in storages])


def _aggregate_storages(
    storages: list[Storage_Common],
    bus1: str,
    kv: float,
    storage_cls: Storage_Common,
    field: str,
    fields: set,
    strategy: StorageAggregationStrategy,
) -> list[Storage_Common]:
    value_mapper = group_objects_excluding_fields(storages, fields)
    new_storages = []
    for _, storage_list in value_mapper.items():
        new_storage_name = generate_short_name()
        num_phase = get_number_of_phases_from_bus(bus1)
        base_kv = kv if num_phase == 1 else round(kv * math.sqrt(3), 3)
        agg_val = strategy.compute(storage_list)

        new_storages.append(
            storage_cls(
                Name=new_storage_name,
                Bus1=BusConnection(root=bus1),
                Phases=num_phase,
                kVA=sum_or_none([storage.kVA for storage in storage_list]),
                kWRated=sum_or_none([storage.kWRated for storage in storage_list]),
                kV=base_kv,
                **{field: agg_val},
                **get_extra_param_values(storage_cls, storage_list, fields),
            )
        )
    return new_storages


@register_aggregator(Storage_kWRatedPF)
def aggregate_storage_pf(
    storages: list[Storage_kWRatedPF], bus1: str, kv: float
) -> list[Storage_kWRatedPF]:
    return _aggregate_storages(
        storages,
        bus1,
        kv,
        storage_cls=Storage_kWRatedPF,
        field="PF",
        fields={"Name", "Bus1", "Phases", "kV", "PF", "kVA", "kWRated"},
        strategy=PFAggregation(),
    )


@register_aggregator(Storage_kWRatedkvar)
def aggregate_storage_kvar(
    storages: list[Storage_kWRatedkvar], bus1: str, kv: float
) -> list[Storage_kWRatedkvar]:
    return _aggregate_storages(
        storages,
        bus1,
        kv,
        storage_cls=Storage_kWRatedkvar,
        field="kvar",
        fields={"Name", "Bus1", "Phases", "kV", "kvar", "kVA", "kWRated"},
        strategy=KvarAggregation(),
    )
