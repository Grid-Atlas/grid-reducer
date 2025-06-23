import networkx as nx
import copy
from typing import Any
from itertools import chain
from collections import defaultdict

from grid_reducer.altdss.altdss_models import (
    Circuit,
    Line_LineCode,
    Line_LineGeometry,
    Line_SpacingWires,
    Line_Z0Z1C0C1,
    Line_ZMatrixCMatrix,
    Reactor_Common,
    Line,
)
from grid_reducer.network import get_graph_from_circuit
from grid_reducer.aggregate_secondary import _update_circuit_in_place
from grid_reducer.similarity.line import LineSimilarity
from grid_reducer.aggregators.line import aggregate_lines
from grid_reducer.summary import PrimaryAssetSummary, PrimaryAssetSummaryItem


LINE_TYPE = (
    Line_LineCode
    | Line_LineGeometry
    | Line_SpacingWires
    | Line_Z0Z1C0C1
    | Line_ZMatrixCMatrix
    | Reactor_Common
)


def fetch_element_name(element: str) -> str:
    return element.split(".")[1] if "." in element else element


def fetch_element_names(obj_type: Any) -> list[str]:
    """Fetches element names from a given object type."""
    if hasattr(obj_type, "root") and hasattr(obj_type.root, "root"):
        return [fetch_element_name(item.Element) for item in obj_type.root.root]
    return []


def _get_list_of_edges_to_preserve(network: nx.Graph, ckt: Circuit) -> list[tuple[str, str]]:
    """Assumes switches and transformers to be preserved."""
    edges_to_preserve = set()
    element_names = list(
        chain.from_iterable(map(fetch_element_names, [ckt.CapControl, ckt.EnergyMeter]))
    )
    for u, v, edge_data in network.edges(data=True):
        edge = (u, v)
        if edge_data["component_type"] == "Transformer":
            edges_to_preserve.add(edge)
            continue
        edge_components: list[LINE_TYPE] = edge_data["edge"]
        if any(
            edge_component.Switch
            for edge_component in edge_components
            if hasattr(edge_component, "Switch")
        ):
            edges_to_preserve.add(edge)
            continue
        if any(edge_component.Name in element_names for edge_component in edge_components):
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


def extract_segments_from_linear_tree(d_graph: nx.DiGraph, subset: set[str]) -> list[nx.DiGraph]:
    subset = set(subset)
    nodes = list(nx.topological_sort(d_graph))

    if not nodes:
        return []

    segments = []
    current_path = [nodes[0]]

    for node in nodes[1:]:
        current_path.append(node)
        if node in subset:
            edges = list(zip(current_path, current_path[1:], strict=False))
            if edges:
                segments.append(d_graph.edge_subgraph(edges).copy())
            current_path = [node]  # start new segment from here

    # Add trailing segment if any
    if len(current_path) > 1:
        edges = list(zip(current_path, current_path[1:], strict=False))
        segments.append(d_graph.edge_subgraph(edges).copy())

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
        for successor in G.successors(node):
            if (node, successor) in visited_edges:
                continue
            path = [node, successor]
            current = successor
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


def aggregate_primary_conductors(circuit: Circuit) -> Circuit:
    """
    This function intends to aggregate similar primary branches
    and preserves capacitor, transformers and switches.
    """
    summary = PrimaryAssetSummary(name="🔗 Merged Primary Edges", items=[])
    d_graph = get_graph_from_circuit(circuit, directed=True)
    edges_to_preserve = _get_list_of_edges_to_preserve(d_graph, circuit)
    nodes_to_preserve = _get_list_of_nodes_to_preserve(circuit)
    linear_trees = _get_linear_trees_from_graph(d_graph, edges_to_preserve)
    multi_edge_trees = [tree for tree in linear_trees if len(tree.edges) > 1]
    aggregatable_segments: list[nx.DiGraph] = []
    for tree in multi_edge_trees:
        preserved_nodes = set(tree.nodes) & nodes_to_preserve
        segments = (
            extract_segments_from_linear_tree(tree, preserved_nodes) if preserved_nodes else [tree]
        )
        aggregatable_segments.extend(seg for seg in segments if len(seg.edges) > 1)

    lines_aggregated, lines_to_remove = [], []
    similarity_checker = LineSimilarity()
    agg_summary_dict = defaultdict(lambda: defaultdict(int))
    for graph in aggregatable_segments:
        assert is_linear_tree(graph)
        sorted_edges = topologically_sorted_edges(graph)
        similar_edges, current_edge_type = [], None
        for edge in sorted_edges:
            edge_comps = graph.get_edge_data(*edge)["edge"]
            if len(edge_comps) > 1:
                continue
            edge_comp = edge_comps[0]
            if not similar_edges:
                similar_edges = [edge_comp]
                current_edge_type = type(edge_comp)
                continue
            similarity_checker = LineSimilarity()
            if isinstance(edge_comp, current_edge_type) and similarity_checker.check_if_similar(
                similar_edges[-1], edge_comp
            ):
                similar_edges.append(edge_comp)
                continue
            if len(similar_edges) > 1:
                agg_summary_dict[current_edge_type]["aggregated"] += 1
                agg_summary_dict[current_edge_type]["removed"] += len(similar_edges)
                lines_aggregated.append(aggregate_lines(similar_edges))
                lines_to_remove.extend(similar_edges)
            similar_edges = [edge_comp]
            current_edge_type = type(edge_comp)

        if len(similar_edges) > 1:
            agg_summary_dict[current_edge_type]["aggregated"] += 1
            agg_summary_dict[current_edge_type]["removed"] += len(similar_edges)
            lines_aggregated.append(aggregate_lines(similar_edges))
            lines_to_remove.extend(similar_edges)

    for asset_type, counts in agg_summary_dict.items():
        summary.items.append(
            PrimaryAssetSummaryItem(
                asset_type=asset_type, merged=counts["aggregated"], removed=counts["removed"]
            )
        )
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
    return new_circuit, summary


def _get_buses_to_keep(circuit: Circuit) -> set:
    buses_to_keep = set()
    lines = [line.root for line in circuit.Line.root.root]
    transformers = (
        [transformer.root for transformer in circuit.Transformer.root.root]
        if circuit.Transformer
        else []
    )
    for line in lines:
        for bus in [line.Bus1, line.Bus2]:
            buses_to_keep.add(bus.root.split(".")[0])
    for transformer in transformers:
        for bus in transformer.Bus:
            buses_to_keep.add(bus.root.split(".")[0])
    return buses_to_keep
