from abc import ABC, abstractmethod
import math

from grid_reducer.altdss.altdss_models import (
    Generator_kWkvar,
    Generator_kWpf,
    Generator_Common,
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


class GeneratorAggregationStrategy(ABC):
    @abstractmethod
    def compute(self, pvs: list) -> float:
        pass


class PFAggregation(GeneratorAggregationStrategy):
    def compute(self, generators: list[Generator_kWpf]):
        total_kw = sum(generator.kW for generator in generators)
        total_kvar = sum(
            math.sqrt((generator.kW / abs(generator.PF)) ** 2 - generator.kW**2)
            * (-1 if generator.PF < 0 else 1)
            for generator in generators
        )
        total_kva = math.sqrt(total_kw**2 + total_kvar**2)
        total_pf = total_kw / total_kva if total_kva else 0.0
        total_pf *= -1 if total_kvar < 0 else 1
        return total_pf


class KvarAggregation(GeneratorAggregationStrategy):
    def compute(self, generators: list[Generator_kWkvar]):
        return sum_or_none([generator.kvar for generator in generators])


def _aggregate_generators(
    generators: list[Generator_Common],
    bus1: str,
    kv: float,
    generator_cls: Generator_Common,
    field: str,
    fields: set,
    strategy: GeneratorAggregationStrategy,
) -> list[Generator_Common]:
    value_mapper = group_objects_excluding_fields(generators, fields)
    new_generators = []
    for _, generator_list in value_mapper.items():
        new_generator_name = generate_short_name()
        num_phase = get_number_of_phases_from_bus(bus1)
        base_kv = kv if num_phase == 1 else round(kv * math.sqrt(3), 3)
        agg_val = strategy.compute(generator_list)

        new_generators.append(
            generator_cls(
                Name=new_generator_name,
                Bus1=BusConnection(root=bus1),
                Phases=num_phase,
                kVA=sum_or_none([generator.kVA for generator in generator_list]),
                kW=sum_or_none([generator.kW for generator in generator_list]),
                kV=base_kv,
                **{field: agg_val},
                **get_extra_param_values(generator_cls, generator_list, fields),
            )
        )
    return new_generators


@register_aggregator(Generator_kWpf)
def aggregate_generator_pf(
    generators: list[Generator_kWpf], bus1: str, kv: float
) -> list[Generator_kWpf]:
    return _aggregate_generators(
        generators,
        bus1,
        kv,
        generator_cls=Generator_kWpf,
        field="PF",
        fields={"Name", "Bus1", "Phases", "kV", "PF", "kVA", "kW"},
        strategy=PFAggregation(),
    )


@register_aggregator(Generator_kWkvar)
def aggregate_storage_kvar(
    generators: list[Generator_kWkvar], bus1: str, kv: float
) -> list[Generator_kWkvar]:
    return _aggregate_generators(
        generators,
        bus1,
        kv,
        generator_cls=Generator_kWkvar,
        field="kvar",
        fields={"Name", "Bus1", "Phases", "kV", "kvar", "kVA", "kW"},
        strategy=KvarAggregation(),
    )
