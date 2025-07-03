# ⚡ Getting Started with `grid-reducer`

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
