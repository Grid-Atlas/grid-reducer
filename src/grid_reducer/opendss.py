from pathlib import Path
import json

import opendssdirect as odd

from grid_reducer.utils import read_json_file


class OpenDSS:
    def __init__(self, dist_model: Path | dict):
        if dist_model.suffix == ".dss":
            odd.Command(f'Redirect "{str(dist_model)}"')

        elif isinstance(dist_model, dict):
            odd.Circuit.FromJSON(json.dumps(dist_model))

        elif dist_model.suffix == ".json":
            odd.Circuit.FromJSON(json.dumps(read_json_file(dist_model)))

        else:
            msg = f"Unsupported dist_model type: {type(dist_model)}"
            raise NotImplementedError(msg)

        self.solve()

    def solve(self):
        odd.Solution.Solve()

    def get_circuit_power(self) -> complex:
        return complex(*odd.Circuit.TotalPower())
