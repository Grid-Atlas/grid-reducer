import networkx as nx
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import LineString


def check_if_graph_has_coordinates(graph: nx.Graph) -> bool:
    if any(["pos" in data for _, data in graph.nodes(data=True)]):
        return True
    return False


def are_nodes_wgs84(graph: nx.Graph) -> bool:
    """
    Auto-detect WGS 84 coordinates in graph node attributes
    Returns: (has_coordinates, is_wgs84, sample_coords)
    """
    if not check_if_graph_has_coordinates(graph):
        return False

    for _, data in graph.nodes(data=True):
        pos_val = data["pos"]
        if isinstance(pos_val, (tuple, list)) and len(pos_val) == 2:
            x, y = pos_val
            # Check if looks like WGS84 coordinates
            if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                if -180 <= x <= 180 and -90 <= y <= 90:
                    continue
        return False
    return True


def graph_to_geo_dataframe(graph: nx.Graph) -> gpd.GeoDataFrame:
    if not check_if_graph_has_coordinates(graph):
        raise ValueError("Graph does not have coordinates")
    if not are_nodes_wgs84(graph):
        raise ValueError("Graph does not have WGS84 coordinates")
    pos = nx.get_node_attributes(graph, "pos")
    edge_lines = []
    edge_data = []
    for i, edge in enumerate(graph.edges()):
        if edge[0] in pos and edge[1] in pos:
            lon0, lat0 = pos[edge[0]]
            lon1, lat1 = pos[edge[1]]
            line = LineString([(lon0, lat0), (lon1, lat1)])
            edge_lines.append(line)

            # Add edge attributes if they exist
            edge_attrs = graph.get_edge_data(edge[0], edge[1], {})
            edge_attrs = {k: v for k, v in edge_attrs.items() if k != "edge" and v}
            edge_info = {
                "edge_id": i,
                "source": edge[0],
                "target": edge[1],
                "length_km": round(line.length * 111, 2),  # Rough conversion to km
            }
            edge_info.update(edge_attrs)  # Add any existing edge attributes
            edge_data.append(edge_info)
    edge_df = gpd.GeoDataFrame(edge_data, geometry=edge_lines, crs="EPSG:4326")
    return edge_df


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
