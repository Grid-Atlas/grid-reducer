from typing import TypeVar
from typing import Any, Type
import math
from collections import defaultdict
import copy

import networkx as nx
from pydantic import BaseModel

from grid_reducer.altdss.altdss_models import (
    Circuit,
    Load,
    Load_kWkvar,
    BusConnection,
    Transformer_Common,
    Line_Common,
    PVSystem,
    Capacitor,
    Storage,
    Generator,
    Reactor,
    Line,
    Transformer,
    SwtControl,
)
from grid_reducer.network import get_graph_from_circuit, get_normally_open_switches
from grid_reducer.utils import get_bus_connected_assets, generate_short_name

T = TypeVar("T")


def get_number_of_phases_from_bus(bus: str) -> int:
    if "." not in bus:
        return 3
    bus_splits = bus.split(".")[1:]
    if "0" in bus_splits:
        bus_splits.remove("0")
    return len(bus_splits)


def get_extra_param_values(
    class_type: BaseModel, objects: list[BaseModel], params_to_aggregate: set[str]
) -> dict[str, Any]:
    other_params = class_type.model_fields.keys() - params_to_aggregate
    other_params_val_mapper = {}
    for key in other_params:
        first_val = getattr(objects[0], key)
        values = set(
            [
                tuple(getattr(obj, key)) if isinstance(first_val, list) else getattr(obj, key)
                for obj in objects
            ]
        )
        if len(values) > 1:
            raise NotImplementedError(
                f"Aggregating {class_type=} with different {values=} for {key=} is not supported yet."
            )
        other_params_val_mapper[key] = first_val
    return other_params_val_mapper


def aggregate_load_kwkvar(loads: list[Load_kWkvar], bus1: str, kv: float) -> Load_kWkvar:
    new_load_name = generate_short_name("".join([load.Name for load in loads]))
    params_to_aggregate = {"Name", "Bus1", "Phases", "kV", "kW", "kvar"}
    num_phase = get_number_of_phases_from_bus(bus1)
    assert num_phase >= max([load.Phases for load in loads])
    return Load_kWkvar(
        Name=new_load_name,
        Bus1=BusConnection(root=bus1),
        Phases=get_number_of_phases_from_bus(bus1),
        kV=kv if num_phase == 1 else round(kv * math.sqrt(3), 3),
        kW=sum([load.kW for load in loads]),
        kvar=sum([load.kvar for load in loads]),
        **get_extra_param_values(Load_kWkvar, loads, params_to_aggregate),
    )


def aggregate_generic_objects(objects: list[T], bus1: str, kv: float) -> list[Any]:
    agg_objects = []
    class_types = set([type(obj) for obj in objects])
    for class_type in class_types:
        func_name = f"aggregate_{class_type.__name__.lower()}"
        if func_name in globals():
            aggregate_func = globals()[func_name]
            agg_objects.append(
                aggregate_func(
                    [obj for obj in objects if isinstance(obj, class_type)], bus1=bus1, kv=kv
                )
            )
        else:
            raise KeyError(f"Function '{func_name}' not found in globals.")
    return agg_objects


def _update_circuit_in_place(circuit: Circuit, assets: list[Any], asset_type) -> None:
    container_class = type(getattr(circuit, asset_type.__name__))
    asset_list_class = type(getattr(circuit, asset_type.__name__).root)
    setattr(
        circuit,
        asset_type.__name__,
        container_class(
            root=asset_list_class(
                root=[asset_type(root=asset.model_dump(mode="python")) for asset in assets]
                if "root" in asset_type.model_fields
                else assets
            ).model_dump(mode="python")
        ),
    )


def _filter_assets_by_graph_nodes(
    list_of_nodes: list[str], circuit: Circuit, asset_types: list[Type[BaseModel]]
) -> dict[Type[BaseModel], list[BaseModel]]:
    assets_to_keep = defaultdict(list)
    for asset_type in asset_types:
        for node in list_of_nodes:
            container_obj = getattr(circuit, asset_type.__name__)
            if container_obj is None:
                continue
            assets_to_keep[asset_type].extend(get_bus_connected_assets(container_obj, node))
    return assets_to_keep


def aggregate_secondary_assets(circuit: Circuit, threshold_kv_ln: float = 1.0) -> Circuit:
    """
    Aggregates assets connected at voltage levels lower than a given threshold
    to a parent node with a voltage close to the threshold.
    """
    # Convert circuit to a directed graph
    dgraph: nx.DiGraph = get_graph_from_circuit(circuit, directed=True)

    # Filter nodes to keep those above the threshold voltage
    nodes_to_keep = [node for node in dgraph.nodes if dgraph.nodes[node]["kv"] >= threshold_kv_ln]
    agg_graph: nx.DiGraph = dgraph.subgraph(nodes_to_keep)

    # Aggregate assets for each leaf node
    aggregated_assets = defaultdict(list)
    asset_types = [Load, PVSystem, Capacitor, Storage, Generator, Reactor]
    for asset_type in asset_types:
        for node in agg_graph.nodes:
            if agg_graph.out_degree(node) < dgraph.out_degree(node):
                successors_diff = set(dgraph.successors(node)) - set(agg_graph.successors(node))
                successors_descendants = [
                    snode
                    for successor in successors_diff
                    for snode in nx.descendants(dgraph, successor)
                ] + list(successors_diff)
                agg_assets = _aggregate_leaf_assets(
                    node, dgraph, dgraph.subgraph(successors_descendants), asset_type, circuit
                )
                if agg_assets:
                    aggregated_assets[asset_type].extend(agg_assets)

    new_circuit = copy.deepcopy(circuit)
    assets_to_keep = _filter_assets_by_graph_nodes(nodes_to_keep, circuit, asset_types)
    for asset_type in asset_types:
        assets = assets_to_keep.get(asset_type, []) + aggregated_assets.get(asset_type, [])
        if assets:
            _update_circuit_in_place(new_circuit, assets, asset_type)

    assets_to_keep_mapper = {
        Line: [data["edge"] for _, _, data in agg_graph.edges(data=True) if "kva" not in data],
        Transformer: [
            tr for _, _, data in agg_graph.edges(data=True) if "kva" in data for tr in data["edge"]
        ],
    }
    no_switches = get_normally_open_switches(circuit)
    for line in circuit.Line.root.root:
        if line.root.Name in no_switches:
            assets_to_keep_mapper[Line].append(line.root)

    lines_preserved = [line.Name for line in assets_to_keep_mapper[Line]]
    if circuit.SwtControl is not None:
        assets_to_keep_mapper[SwtControl] = [
            swt
            for swt in circuit.SwtControl.root.root
            if swt.SwitchedObj.replace("Line.", "") in lines_preserved
        ]
    for asset_type, assets in assets_to_keep_mapper.items():
        _update_circuit_in_place(new_circuit, assets, asset_type)

    new_circuit.Bus = [bus for bus in new_circuit.Bus if bus.Name in nodes_to_keep]
    return new_circuit


def _aggregate_leaf_assets(
    leaf: str, dgraph: nx.DiGraph, descendant_graph: nx.DiGraph, asset_type: T, circuit: Circuit
) -> list[T] | None:
    """Helper function to aggregate assets for a given leaf node."""

    asset_container = getattr(circuit, asset_type.__name__)
    if not asset_container:
        return

    # Get incoming edges and extract bus information
    in_edges = [data["edge"] for _, _, data in dgraph.in_edges(leaf, data=True)]
    leaf_bus_set = _extract_leaf_buses(leaf, in_edges)

    if len(leaf_bus_set) > 1:
        raise NotImplementedError(f"Multiple phases not supported yet: {leaf_bus_set=}")
    assets = [
        asset
        for node in descendant_graph.nodes
        for asset in get_bus_connected_assets(asset_container, node)
    ]
    return aggregate_generic_objects(assets, bus1=leaf_bus_set.pop(), kv=dgraph.nodes[leaf]["kv"])


def combine_bus_names(bus_names):
    if len(bus_names) == 1:
        return bus_names[0]
    base, phases = zip(*(bus.split(".") for bus in sorted(bus_names)), strict=False)
    if len(set(base)) > 1:
        msg = f"Multiple base buses not supported yet: {base=}"
        raise NotImplementedError(msg)
    return f"{base[0]}." + ".".join(sorted(set(phases)))


COMMON_EDGE_TYPE = Line_Common | Transformer_Common
COMMON_EDGE_GROUP = COMMON_EDGE_TYPE | list[COMMON_EDGE_TYPE]


def _extract_leaf_buses(leaf: str, in_edges: list[COMMON_EDGE_GROUP]) -> set:
    """Extracts the bus connections for a given leaf node."""
    leaf_bus_set = {
        bus
        for edge in in_edges
        for bus in (
            combine_bus_names([el.Bus1.root for el in edge])
            if isinstance(edge, list)
            else edge.Bus1.root,
            combine_bus_names([el.Bus2.root for el in edge])
            if isinstance(edge, list)
            else edge.Bus2.root,
        )
        if leaf == bus.split(".")[0]
    }
    return leaf_bus_set
