from typing import Any

import networkx as nx

from grid_reducer.altdss.altdss_models import Circuit
from grid_reducer.utils import (
    get_circuit_bus_name,
    extract_bus_name,
    get_normally_open_switches,
    get_open_lines,
)


def get_source_connected_component(graph: nx.Graph, source: str) -> nx.Graph:
    """Get the connected component of the graph that contains the source node."""
    if not nx.is_connected(graph):
        for component in nx.connected_components(graph):
            if source.split(".")[0] in component:
                print(
                    f"Warning: Removed {len(graph.nodes) - len(component)} nodes not connected to source."
                )
                return graph.subgraph(component).copy()
        raise ValueError(f"Source node '{source}' not found in any connected component.")
    return graph.copy()


def dfs_tree_with_attrs(graph: nx.Graph, source):
    graph = get_source_connected_component(graph, source)
    dfs_tree: nx.DiGraph = nx.dfs_tree(graph, source)
    for node in dfs_tree.nodes():
        if node in graph.nodes:
            dfs_tree.nodes[node].update(graph.nodes[node])

    for u, v in dfs_tree.edges():
        if graph.has_edge(u, v):
            dfs_tree.edges[u, v].update(graph.edges[u, v])

    return dfs_tree


def create_bus_voltage_mapper(circuit_obj: Circuit) -> dict[str, float]:
    """Create a mapping of bus names to their voltages."""
    bus_voltage_mapper = {}
    for bus in circuit_obj.Bus:
        bus_voltage_mapper[bus.Name] = bus.kVLN
    return bus_voltage_mapper


def add_bus_nodes(graph: nx.Graph, circuit_obj):
    """Add bus nodes to the graph with their properties."""
    for bus in circuit_obj.Bus:
        graph.add_node(
            bus.Name,
            pos=(bus.X, bus.Y),
            kv=bus.kVLN,
        )


def get_component_buses(component: Any) -> tuple[str, str]:
    """Extract bus names from a component."""
    bus1 = extract_bus_name(component.root.Bus1)
    bus2 = extract_bus_name(component.root.Bus2) if component.root.Bus2 is not None else None
    return bus1, bus2


def add_component_edge(
    graph: nx.Graph,
    bus1: str,
    bus2: str,
    component: Any,
    component_type: str,
    bus_voltage_mapper: dict[str, float],
):
    """Add or update an edge for a component between two buses."""
    edge_components = [component.root]
    if graph.has_edge(bus1, bus2):
        edge_data = graph.get_edge_data(bus1, bus2)
        edge_components += edge_data.get("edge", [])
        graph[bus1][bus2].update(
            {"edge": edge_components, "name": ",".join([t.Name for t in edge_components])}
        )
    else:
        graph.add_edge(
            bus1,
            bus2,
            kv=bus_voltage_mapper[bus1],
            edge=edge_components,
            component_type=component_type,
            name=",".join([t.Name for t in edge_components]),
        )


def add_line_and_reactor_components(
    graph: nx.Graph,
    circuit_obj: Circuit,
    no_switches: list[str],
    bus_voltage_mapper: dict[str, float],
):
    """Add line and reactor components as edges to the graph."""
    components_dict = {
        "Line": circuit_obj.Line,
        "Reactor": circuit_obj.Reactor,
    }

    for component_type, components in components_dict.items():
        if not components:
            continue
        for component in components.root.root:
            name = component.root.Name
            if name in no_switches:
                continue

            bus1, bus2 = get_component_buses(component)
            if not bus2:
                continue
            add_component_edge(graph, bus1, bus2, component, component_type, bus_voltage_mapper)


def validate_transformer_edge_components(edge_components: list, buses: list[str]):
    """Validate transformer edge components have consistent parameters."""
    phases_set = {t.Phases for t in edge_components}
    name_list = [t.Name for t in edge_components]

    if len(phases_set) != 1:
        bus1, bus2 = tuple(buses)
        msg = f"""Inconsistent transformer parameters on edge ({bus1}, {bus2}),
        skipping. {phases_set=}, {name_list=}"""
        raise Exception(msg)

    return name_list


def add_transformer_edge(
    graph: nx.Graph, buses: list[str], transformer: Any, bus_voltage_mapper: dict[str, float]
):
    """Add a transformer edge between two buses."""
    bus_voltages = [bus_voltage_mapper[bus] for bus in buses]
    edge_components = [transformer.root]

    if graph.has_edge(*buses):
        edge_data = graph.get_edge_data(*buses)
        edge_components += edge_data.get("edge", [])

    name_list = validate_transformer_edge_components(edge_components, buses)
    kva_list = [min(t.kVA) if t.kVA else None for t in edge_components]

    graph.add_edge(
        *buses,
        high_kv=max(bus_voltages),
        low_kv=min(bus_voltages),
        kva=kva_list,
        edge=edge_components,
        component_type="Transformer",
        name=",".join(name_list),
    )


def add_transformer_components(
    graph: nx.Graph, circuit_obj: Circuit, bus_voltage_mapper: dict[str, float]
):
    """Add transformer components as edges to the graph."""
    if circuit_obj.Transformer is None:
        return
    for transformer in circuit_obj.Transformer.root.root:
        buses = set([el.root.split(".")[0] for el in transformer.root.Bus])
        if len(buses) == 2:
            add_transformer_edge(graph, buses, transformer, bus_voltage_mapper)
        else:
            raise Exception("Transformer with more than 2 buses not supported.")


def get_graph_from_circuit(circuit_obj: Circuit, directed: bool = False) -> nx.Graph:
    bus_voltage_mapper = create_bus_voltage_mapper(circuit_obj)
    no_switches = get_normally_open_switches(circuit_obj) + get_open_lines(circuit_obj)
    graph = nx.Graph()
    add_bus_nodes(graph, circuit_obj)
    add_line_and_reactor_components(graph, circuit_obj, no_switches, bus_voltage_mapper)
    add_transformer_components(graph, circuit_obj, bus_voltage_mapper)
    return (
        graph
        if not directed
        else dfs_tree_with_attrs(graph, source=get_circuit_bus_name(circuit_obj))
    )
