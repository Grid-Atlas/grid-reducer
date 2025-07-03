# ⚡ Getting Started with `grid-reducer`

[![Build](https://github.com/Grid-Atlas/grid-reducer/actions/workflows/ci.yml/badge.svg)](https://github.com/Grid-Atlas/grid-reducer/actions/workflows/ci.yml)
![Python](https://img.shields.io/pypi/pyversions/grid-reducer)
![License](https://img.shields.io/github/license/Grid-Atlas/grid-reducer)
![Coverage](https://img.shields.io/codecov/c/github/Grid-Atlas/grid-reducer)

[View Full Documentation.](https://grid-atlas.github.io/grid-reducer).

Welcome! Follow the steps below to get `grid-reducer` up and running locally.  
We recommend using a Python virtual environment for a clean install 🔒🐍.

## 🧪 Step 1: Set Up a Python Environment

To avoid dependency conflicts, create and activate a virtual environment.

You can use any tool of your choice — here are a few popular options:

<details> <summary><strong>🟢 Option A: Using <code>venv</code> (Standard Library)</strong></summary>

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

</details> <details> <summary><strong>🔵 Option B: Using <code>conda</code></strong></summary>

```bash
conda create -n grid-reducer-env python=3.10
conda activate grid-reducer-env
```

</details>

## 🚀 Step 2: Install the Project Locally

Install the project in editable mode so changes to the code reflect immediately:

```bash
pip install grid_reducer
```

✅ This will also install all required dependencies.

## 🛠 Example CLI Usage

Once installed, you can use command line interface. Run `grid --help` to see all the available command options.

Here is a minimal example to reduce OpenDSS model.

```bash
grid reduce -f Master.dss
```

## Example Python Usage

You can also reduce the feeder model through python scripts.

Here is a minimal example to reduce OpenDSS feeder model using Python Script.

```python
from pathlib import Path

from grid_reducer.reducer import OpenDSSModelReducer

file_path = "master.dss"
reducer = OpenDSSModelReducer(master_dss_file=file_path)
reduced_ckt = reducer.reduce(transform_coordinate=True)

out_folder = Path("outputs")
out_folder.mkdir(parents=True, exist_ok=True)
original_circuit_file = out_folder / "original_ckt.dss"
reduced_circuit_file = out_folder / "reduced_ckt.dss"
reducer.export_original_ckt(original_circuit_file)
reducer.export(reduced_ckt, reduced_circuit_file)
```

## 📌 Notes

* This is the recommended way to use the project during development.
* In the future, the project may support installation via:

```bash
pip install grid-reducer
```

Stay tuned for updates! 📬

Need help? Feel free to open an issue or reach out to the maintainers. 💬

## Attribution and Disclaimer

This software was created under a project sponsored by the U.S. Department of Energy’s Office of Electricity, an agency of the United States Government. Neither the United States Government nor the United States Department of Energy, nor Battelle, nor any of their employees, nor any jurisdiction or organization that has cooperated in the development of these materials, makes any warranty, express or implied, or assumes any legal liability or responsibility for the accuracy, completeness, or usefulness or any information, apparatus, product, software, or process disclosed, or represents that its use would not infringe privately owned rights.

Reference herein to any specific commercial product, process, or service by trade name, trademark, manufacturer, or otherwise does not necessarily constitute or imply its endorsement, recommendation, or favoring by the United States Government or any agency thereof, or Battelle Memorial Institute. The views and opinions of authors expressed herein do not necessarily state or reflect those of the United States Government or any agency thereof.

PACIFIC NORTHWEST NATIONAL LABORATORY

operated by BATTELLE

for the UNITED STATES DEPARTMENT OF ENERGY

under Contract DE-AC05-76RL01830
