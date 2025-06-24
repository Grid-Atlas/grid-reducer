from pathlib import Path

from grid_reducer.utils import get_ckt_from_opendss_model
from grid_reducer.altdss.altdss_models import Circuit
from grid_reducer.aggregate_secondary import aggregate_secondary_assets
from grid_reducer.aggregate_primary import aggregate_primary_conductors
from grid_reducer.utils import write_to_opendss_file
from grid_reducer.transform_coordinate import transform_bus_coordinates
from grid_reducer.add_differential_privacy import get_dp_circuit
from grid_reducer.rename_components import rename_assets


class OpenDSSModelReducer:
    def __init__(self, master_dss_file: Path | str):
        self.master_dss_file = master_dss_file
        self.ckt = get_ckt_from_opendss_model(Path(master_dss_file))

    def reduce(
        self,
        reduce_secondary: bool = True,
        aggregate_primary: bool = True,
        transform_coordinate: bool = True,
        noise_level: str = "low",
    ) -> Circuit:
        reduced_ckt = aggregate_secondary_assets(self.ckt) if reduce_secondary else self.ckt
        final_ckt = aggregate_primary_conductors(reduced_ckt) if aggregate_primary else reduced_ckt
        transformed_ckt = (
            transform_bus_coordinates(final_ckt, noise_level) if transform_coordinate else final_ckt
        )
        private_ckt = get_dp_circuit(transformed_ckt,transform_coordinate, noise_level) if noise_level != "none" else transformed_ckt
        renamed_ckt = rename_assets(private_ckt)
        return renamed_ckt

    def export(self, ckt: Circuit, file_path: Path | str):
        write_to_opendss_file(ckt, file_path)

    def export_original_ckt(self, file_path: Path | str):
        write_to_opendss_file(self.ckt, file_path)
