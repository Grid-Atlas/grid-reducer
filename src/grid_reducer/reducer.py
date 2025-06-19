from pathlib import Path

from grid_reducer.utils import get_ckt_from_opendss_model, print_summary_to_cli
from grid_reducer.altdss.altdss_models import Circuit
from grid_reducer.aggregate_secondary import aggregate_secondary_assets
from grid_reducer.aggregate_primary import aggregate_primary_conductors
from grid_reducer.utils import write_to_opendss_file
from grid_reducer.transform_coordinate import transform_bus_coordinates
from grid_reducer.rename_components import rename_assets


def get_edge_count(ckt: Circuit) -> int:
    return (
        len(ckt.Line.root.root)
        if ckt.Line
        else 0 + len(ckt.Transformer.root.root)
        if ckt.Transformer
        else 0
    )


class OpenDSSModelReducer:
    def __init__(self, master_dss_file: Path | str):
        self.master_dss_file = master_dss_file
        self.ckt = get_ckt_from_opendss_model(Path(master_dss_file))

    def reduce(
        self,
        reduce_secondary: bool = True,
        aggregate_primary: bool = True,
        transform_coordinate: bool = True,
    ) -> Circuit:
        if reduce_secondary:
            reduced_ckt, summary = aggregate_secondary_assets(self.ckt)
            print_summary_to_cli(summary.get_summary())
        else:
            reduced_ckt = self.ckt

        if aggregate_primary:
            final_ckt, summary = aggregate_primary_conductors(reduced_ckt)
            print_summary_to_cli(summary.get_summary())
        else:
            final_ckt = reduced_ckt

        transformed_ckt = (
            transform_bus_coordinates(final_ckt) if transform_coordinate else final_ckt
        )
        renamed_ckt = rename_assets(transformed_ckt)
        print(f"Total Node Reductions: {len(self.ckt.Bus)}  → {len(final_ckt.Bus)}")
        print(f"Total Edge Reductions: {get_edge_count(self.ckt)}  → {get_edge_count(final_ckt)}")
        return renamed_ckt

    def export(self, ckt: Circuit, file_path: Path | str):
        write_to_opendss_file(ckt, file_path)

    def export_original_ckt(self, file_path: Path | str):
        write_to_opendss_file(self.ckt, file_path)
