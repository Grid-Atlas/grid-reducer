import networkx as nx
import matplotlib.pyplot as plt

from grid_reducer.altdss.altdss_models import SwtControlState

from grid_reducer.altdss.altdss_models import Circuit
from grid_reducer.utils import get_circuit_bus_name


def dfs_tree_with_attrs(graph: nx.Graph, source):
    if len(list(nx.simple_cycles(graph))) > 0:
        raise Exception("Loop not supported yet.")

    if not nx.is_connected(graph):
        for component in nx.connected_components(graph):
            if source.split(".")[0] in component:
                print(
                    f"Warning: Removed {len(graph.nodes) - len(component)} nodes not connected to source."
                )
                graph = graph.subgraph(component).copy()
                break
        else:
            raise ValueError(f"Source node '{source}' not found in any connected component.")

    dfs_tree: nx.DiGraph = nx.dfs_tree(graph, source)
    for node in dfs_tree.nodes():
        if node in graph.nodes:
            dfs_tree.nodes[node].update(graph.nodes[node])

    for u, v in dfs_tree.edges():
        if graph.has_edge(u, v):
            dfs_tree.edges[u, v].update(graph.edges[u, v])

    return dfs_tree


def get_normally_open_switches(circuit_obj: Circuit) -> list[str]:
    normally_open_switches = []
    if circuit_obj.SwtControl is None:
        return normally_open_switches
    for switch in circuit_obj.SwtControl.root.root:
        if switch.SwitchedObj and switch.Normal == SwtControlState.open:
            normally_open_switches.append(switch.SwitchedObj.replace("Line.", ""))
    return normally_open_switches


def get_graph_from_circuit(circuit_obj: Circuit, directed: bool = False) -> nx.Graph:
    bus_voltage_mapper = {}
    no_switches = get_normally_open_switches(circuit_obj)
    graph = nx.Graph()
    for bus in circuit_obj.Bus:
        graph.add_node(
            bus.Name,
            pos=(bus.X, bus.Y),
            kv=bus.kVLN,
        )
        bus_voltage_mapper[bus.Name] = bus.kVLN
    for line in circuit_obj.Line.root.root:
        bus1 = line.root.Bus1.root.split(".")[0]
        bus2 = line.root.Bus2.root.split(".")[0]
        if line.root.Name in no_switches:
            continue
        graph.add_edge(
            bus1,
            bus2,
            kv=bus_voltage_mapper[bus1],
            phases=line.root.Phases,
            ampacity=line.root.NormAmps,
            edge=line.root,
            name=line.root.Name,
        )
    for transformer in circuit_obj.Transformer.root.root:
        buses = set([el.root.split(".")[0] for el in transformer.root.Bus])
        if len(buses) == 2:
            bus_voltages = [bus_voltage_mapper[bus] for bus in buses]
            edge_components = [transformer.root]
            if graph.has_edge(*buses):
                edge_data = graph.get_edge_data(*buses)
                edge_components += edge_data.get("edge", [])

            phases_set = {t.Phases for t in edge_components}
            kva_list = [min(t.kVA) for t in edge_components]
            name_list = [t.Name for t in edge_components]
            if len(phases_set) == 1:
                graph.add_edge(
                    *buses,
                    high_kv=max(bus_voltages),
                    low_kv=min(bus_voltages),
                    phases=phases_set.pop(),
                    kva=kva_list,
                    edge=edge_components,
                    name=",".join(name_list),
                )
            else:
                msg = f"""Inconsistent transformer parameters on edge ({bus1}, {bus2}),
                skipping. {phases_set=}, {name_list=}"""
                raise Exception(msg)
        else:
            raise Exception("Transformer with more than 2 buses not supported.")

    return (
        graph
        if not directed
        else dfs_tree_with_attrs(graph, source=get_circuit_bus_name(circuit_obj))
    )


def plot_graph(
    graph: nx.Graph,
    show_node_labels: bool = False,
    show_edge_labels: bool = False,
    nodes_of_interest=None,
    node_size=50,
):
    pos = nx.get_node_attributes(graph, "pos")
    if nodes_of_interest is None:
        nodes_of_interest = []

    # Assign color: red for nodes of interest, blue otherwise
    node_colors = ["red" if node in nodes_of_interest else "blue" for node in graph.nodes]

    nx.draw(graph, pos, with_labels=show_node_labels, node_color=node_colors, node_size=node_size)
    if show_edge_labels:
        edge_labels = nx.get_edge_attributes(graph, "name")
        nx.draw_networkx_edge_labels(graph, pos, edge_labels=edge_labels, font_size=6)
    plt.show()
