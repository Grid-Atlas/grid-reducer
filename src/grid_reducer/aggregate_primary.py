import networkx as nx
from typing import TypeVar
import copy

from pint import Quantity

from grid_reducer.altdss.altdss_models import (
    Circuit,
    Line_LineCode,
    Line_LineGeometry,
    Line_SpacingWires,
    Line_Z0Z1C0C1,
    Line_ZMatrixCMatrix,
    Line_Common,
    Bus,
    LengthUnit,
    Line,
)
from grid_reducer.network import get_graph_from_circuit
from grid_reducer.utils import generate_short_name
from grid_reducer.aggregate_secondary import _update_circuit_in_place


LINE_TYPE = (
    Line_LineCode | Line_LineGeometry | Line_SpacingWires | Line_Z0Z1C0C1 | Line_ZMatrixCMatrix
)


def _get_list_of_edges_to_preserve(network: nx.Graph, ckt: Circuit) -> list[tuple[str, str]]:
    """Assumes switches and transformers to be preserved."""
    edges_to_preserve = set()
    capacitor_control_elements = (
        [item.Element.split(".")[1] for item in ckt.CapControl.root.root]
        if ckt.CapControl is not None
        else []
    )
    for u, v, edge_data in network.edges(data=True):
        edge = (u, v)
        if "kva" in edge_data:
            edges_to_preserve.add(edge)
            continue
        edge_component: LINE_TYPE = edge_data["edge"]
        if edge_component.Switch:
            edges_to_preserve.add(edge)
            continue
        if edge_data["edge"].Name in capacitor_control_elements:
            edges_to_preserve.add(edge)
    return edges_to_preserve


def _get_list_of_nodes_to_preserve(circuit: Circuit) -> set[str]:
    """Returns nodes that must be preserved, based on assets and switches."""

    def _should_preserve(item) -> bool:
        item_type = type(item)
        return "Bus1" in item_type.model_fields and (
            "Bus2" not in item_type.model_fields or item.Bus2 is None
        )

    def _extract_items(field_data):
        if not hasattr(field_data, "root") or not hasattr(field_data.root, "root"):
            return []
        return [item.root if hasattr(item, "root") else item for item in field_data.root.root]

    nodes_to_be_preserved = set()

    for field in Circuit.model_fields:
        field_data = getattr(circuit, field)
        if not field_data:
            continue
        for item in _extract_items(field_data):
            if _should_preserve(item):
                nodes_to_be_preserved.add(item.Bus1.root.split(".")[0])

    for line in circuit.Line.root.root:
        if line.root.Switch:
            for bus in [line.root.Bus1, line.root.Bus2]:
                nodes_to_be_preserved.add(bus.root.split(".")[0])

    return nodes_to_be_preserved


def extract_segments_from_linear_tree(dgraph: nx.DiGraph, subset: set[str]) -> list[nx.DiGraph]:
    subset = set(subset)
    nodes = list(nx.topological_sort(dgraph))

    if not nodes:
        return []

    segments = []
    current_path = [nodes[0]]

    for node in nodes[1:]:
        current_path.append(node)
        if node in subset:
            edges = list(zip(current_path, current_path[1:], strict=False))
            if edges:
                segments.append(dgraph.edge_subgraph(edges).copy())
            current_path = [node]  # start new segment from here

    # Add trailing segment if any
    if len(current_path) > 1:
        edges = list(zip(current_path, current_path[1:], strict=False))
        segments.append(dgraph.edge_subgraph(edges).copy())

    return segments


def is_linear_tree(G):
    if not nx.is_directed(G):
        raise ValueError("Graph must be directed")

    if not nx.is_arborescence(G):
        return False  # not a rooted tree

    in_deg = G.in_degree()
    out_deg = G.out_degree()

    counts = {
        (0, 1): 0,  # root
        (1, 1): 0,  # internal nodes
        (1, 0): 0,  # leaf
    }

    for node in G.nodes:
        deg = (in_deg[node], out_deg[node])
        if deg in counts:
            counts[deg] += 1
        else:
            return False  # invalid node degree for a linear tree

    n = G.number_of_nodes()
    return counts[(0, 1)] == 1 and counts[(1, 0)] == 1 and counts[(1, 1)] == n - 2


def get_linear_trees(G):
    if not nx.is_arborescence(G):
        raise ValueError("Graph must be a directed tree (arborescence)")

    root = [n for n, d in G.in_degree() if d == 0][0]
    visited_edges = set()
    linear_subtrees = []

    def walk_from(node):
        for succ in G.successors(node):
            if (node, succ) in visited_edges:
                continue
            path = [node, succ]
            current = succ
            while G.in_degree(current) == 1 and G.out_degree(current) == 1:
                next_node = next(G.successors(current))
                path.append(next_node)
                current = next_node
            edges = list(zip(path, path[1:], strict=False))
            visited_edges.update(edges)
            linear_subtrees.append(G.edge_subgraph(edges).copy())
            walk_from(current)

    walk_from(root)
    return linear_subtrees


def _get_linear_trees_from_graph(
    graph: nx.DiGraph, edges_to_remove: list[tuple[str, str]] | None = None
):
    if not edges_to_remove:
        return get_linear_trees(graph)

    # Copy and remove specified edges
    modified_graph = graph.copy()
    modified_graph.remove_edges_from(edges_to_remove)

    # Find weakly connected components after edge removal
    linear_trees = []
    for component_nodes in nx.weakly_connected_components(modified_graph):
        subgraph = graph.subgraph(component_nodes).copy()
        linear_trees.extend(get_linear_trees(subgraph))

    return linear_trees


def topologically_sorted_edges(graph: nx.DiGraph) -> list[tuple[str, str]]:
    sorted_nodes = list(nx.topological_sort(graph))
    position = {node: i for i, node in enumerate(sorted_nodes)}

    # Sort edges by source node's position in the topological sort
    return sorted(graph.edges(), key=lambda e: position[e[0]])


T = TypeVar("T")


class CheckSimilarity:
    ignore_fields = None
    class_type = None

    def check_if_similar(self, source_edge: T, target_edge: T) -> bool:
        if self.class_type is None:
            raise Exception("Class type is not set.")
        for field in self.class_type.model_fields:
            if self.ignore_fields is not None and field in self.ignore_fields:
                continue
            source_val = getattr(source_edge, field)
            target_val = getattr(target_edge, field)
            if source_val != target_val:
                return False
        return True


class Line_LineCode_Similarity(CheckSimilarity):
    ignore_fields = {"Name", "Bus1", "Bus2", "Length", "Units"}
    class_type = Line_LineCode


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


def aggregate_line_linecode(lines: list[Line_LineCode]) -> Line_LineCode:
    assert len(lines) >= 2
    common_fields = Line_LineCode.model_fields.keys() - Line_LineCode_Similarity.ignore_fields

    common_values_dict = {}
    for field in common_fields:
        common_values_dict[field] = getattr(lines[0], field)

    new_line_name = generate_short_name("".join([line.Name for line in lines]))
    bus1, bus2 = _find_start_end_buses_set_based(lines)
    total_length = sum([Quantity(line.Length, line.Units.value) for line in lines]).to("m")
    return Line_LineCode(
        Name=new_line_name,
        Bus1=bus1,
        Bus2=bus2,
        Length=total_length.magnitude,
        Units=LengthUnit.m,
        **common_values_dict,
    )


def aggregate_primary_conductors(circuit: Circuit) -> Circuit:
    """
    This function intends to aggregate similar primary branches
    and preserves capacitor, transformers and switches.
    """
    dgraph = get_graph_from_circuit(circuit, directed=True)
    edges_to_preserve = _get_list_of_edges_to_preserve(dgraph, circuit)
    nodes_to_preserve = _get_list_of_nodes_to_preserve(circuit)
    linear_trees = _get_linear_trees_from_graph(dgraph, edges_to_preserve)
    linear_trees_with_more_than_one_edge = [tree for tree in linear_trees if len(tree.edges) > 1]
    graph_with_more_than_one_edge: list[nx.DiGraph] = []
    for linear_tree in linear_trees_with_more_than_one_edge:
        preserved_nodes = set(linear_tree.nodes).intersection(nodes_to_preserve)
        if preserved_nodes:
            segments = extract_segments_from_linear_tree(linear_tree, preserved_nodes)
        else:
            segments = [linear_tree]
        graph_with_more_than_one_edge.extend(seg for seg in segments if len(seg.edges) > 1)

    lines_aggregated, lines_to_remove = [], []
    for graph in graph_with_more_than_one_edge:
        assert is_linear_tree(graph)
        sorted_edges = topologically_sorted_edges(graph)
        similar_edges = [graph.get_edge_data(*sorted_edges[0])["edge"]]
        current_edge_type = type(similar_edges[0])
        for edge in sorted_edges[1:]:
            edge_comp = graph.get_edge_data(*edge)["edge"]
            similarity_check_class = globals()[f"{current_edge_type.__name__}_Similarity"]()
            if isinstance(
                edge_comp, current_edge_type
            ) and similarity_check_class.check_if_similar(similar_edges[-1], edge_comp):
                similar_edges.append(edge_comp)
                continue
            if len(similar_edges) > 1:
                aggregate_func = globals()[f"aggregate_{current_edge_type.__name__.lower()}"]
                aggregated_line = aggregate_func(similar_edges)
                lines_aggregated.append(aggregated_line)
                lines_to_remove.extend(similar_edges)
            similar_edges = [edge_comp]
            current_edge_type = type(edge_comp)

        if len(similar_edges) > 1:
            aggregate_func = globals()[f"aggregate_{current_edge_type.__name__.lower()}"]
            aggregated_line = aggregate_func(similar_edges)
            lines_aggregated.append(aggregated_line)
            lines_to_remove.extend(similar_edges)

    all_lines = [line.root for line in circuit.Line.root.root]
    line_names_to_remove = [line.Name for line in lines_to_remove]
    filtered_lines: list[LINE_TYPE] = [
        line for line in all_lines if line.Name not in line_names_to_remove
    ]
    new_circuit = copy.deepcopy(circuit)
    _update_circuit_in_place(new_circuit, filtered_lines + lines_aggregated, Line)
    buses_to_keep = _get_buses_to_keep(new_circuit)
    new_circuit.Bus = [bus for bus in new_circuit.Bus if bus.Name in buses_to_keep]
    print(f"Number of aggregated lines = {len(lines_aggregated)}")
    print(f"Number of removed lines = {len(lines_to_remove)}")
    return new_circuit


def _get_buses_to_keep(circuit: Circuit) -> set:
    buses_to_keep = set()
    lines = [line.root for line in circuit.Line.root.root]
    transformers = [transformer.root for transformer in circuit.Transformer.root.root]
    for line in lines:
        for bus in [line.Bus1, line.Bus2]:
            buses_to_keep.add(bus.root.split(".")[0])
    for transformer in transformers:
        for bus in transformer.Bus:
            buses_to_keep.add(bus.root.split(".")[0])
    return buses_to_keep
