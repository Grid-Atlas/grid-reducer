from abc import ABC, abstractmethod
import math

from grid_reducer.altdss.altdss_models import (
    PVSystem_PF,
    PVSystem_kvar,
    PVSystem_Common,
    BusConnection,
)
from grid_reducer.utils import (
    generate_short_name,
    get_number_of_phases_from_bus,
    get_extra_param_values,
    sum_or_none,
    weighted_average_or_none,
    group_objects_excluding_fields,
)
from grid_reducer.aggregators.registry import register_aggregator


class PVAggregationStrategy(ABC):
    @abstractmethod
    def compute(self, pvs: list) -> float:
        pass


class PFAggregation(PVAggregationStrategy):
    def compute(self, pvs: list[PVSystem_PF]):
        if all([pv.PF is None for pv in pvs]):
            return None
        estimated_kws = [(pv.Pmpp or 0) * (pv.Irradiance or 1) for pv in pvs]
        pfs = [pv.PF or 1 for pv in pvs]
        total_kw = sum(estimated_kws)
        total_kvar = sum(
            math.sqrt((kw / abs(pf)) ** 2 - kw**2) * (-1 if pf < 0 else 1)
            for kw, pf in zip(estimated_kws, pfs, strict=True)
        )
        total_kva = math.sqrt(total_kw**2 + total_kvar**2)
        total_pf = total_kw / total_kva if total_kva else 0.0
        total_pf *= -1 if total_kvar < 0 else 1
        return total_pf


class KvarAggregation(PVAggregationStrategy):
    def compute(self, pvs: list[PVSystem_kvar]):
        return sum_or_none([pv.kvar for pv in pvs])


def _aggregate_pvs(
    pvs: list[PVSystem_Common],
    bus1: str,
    kv: float,
    pv_cls: PVSystem_Common,
    field: str,
    fields: set,
    strategy: PVAggregationStrategy,
) -> list[PVSystem_Common]:
    value_mapper = group_objects_excluding_fields(pvs, fields)
    new_pvs = []
    for _, pv_list in value_mapper.items():
        new_pv_name = generate_short_name()
        num_phase = get_number_of_phases_from_bus(bus1)
        base_kv = kv if num_phase == 1 else round(kv * math.sqrt(3), 3)
        agg_val = strategy.compute(pv_list)

        new_pvs.append(
            pv_cls(
                Name=new_pv_name,
                Bus1=BusConnection(root=bus1),
                Phases=num_phase,
                Pmpp=sum_or_none([pv.Pmpp for pv in pvs]),
                kVA=sum_or_none([pv.kVA for pv in pvs]),
                Irradiance=weighted_average_or_none(
                    [pv.Irradiance for pv in pvs], [pv.Pmpp for pv in pvs]
                ),
                kV=base_kv,
                **{field: agg_val},
                **get_extra_param_values(pv_cls, pvs, fields),
            )
        )
    return new_pvs


@register_aggregator(PVSystem_PF)
def aggregate_pv_pf(pvs: list[PVSystem_PF], bus1: str, kv: float) -> list[PVSystem_PF]:
    return _aggregate_pvs(
        pvs,
        bus1,
        kv,
        pv_cls=PVSystem_PF,
        field="PF",
        fields={"Name", "Bus1", "Phases", "kV", "PF", "Pmpp", "Irradiance", "kVA"},
        strategy=PFAggregation(),
    )


@register_aggregator(PVSystem_kvar)
def aggregate_pv_kvar(loads: list[PVSystem_kvar], bus1: str, kv: float) -> list[PVSystem_kvar]:
    return _aggregate_pvs(
        loads,
        bus1,
        kv,
        pv_cls=PVSystem_kvar,
        field="kvar",
        fields={"Name", "Bus1", "Phases", "kV", "kvar", "Pmpp", "Irradiance", "kVA"},
        strategy=KvarAggregation(),
    )
