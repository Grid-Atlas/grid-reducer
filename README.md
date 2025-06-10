# Grid Reducer

A private repository for performing network reduction in distribution system power flow model. Read more abour the appraoch [here](./docs/approach.md).

## Getting Started 

Activate the python environment and follow these commands to install this codebase locally.

If you do not have environment set-up please follow guide on how to create python environments.
As there are so many ways one can create python environment. We are leaving it upto the user how they would like to
manage their local environment. 

```bash
git clone https://tanuki.pnnl.gov/gridatlas/grid-reducer.git
cd grid-reducer
pip install -e.
```

## Running test locally.

```bash
cd grid-reducer
pytest .
```

## Using CLI

```bash
grid --help
```

## Reducing the OpenDSS model

Following options are available when reducing the grid model.

```cli
Usage: grid reduce [OPTIONS]

Options:
  -f, --opendss-file TEXT         Path to master opendss file for which data
                                  is to be extracted.
  -rs, --remove-secondary BOOLEAN
                                  Boolean falg indicating whether to reduce
                                  secondary or not.
  -ap, --aggregate-primary BOOLEAN
                                  Boolean falg indicating whether to aggregate
                                  primary ckt or not.
  -tc, --transform-coordinate BOOLEAN
                                  Boolean falg indicating whether to transform
                                  coordinates or not.
  -eo, --export-original BOOLEAN  Boolean flag indicating whether to export
                                  original circuit or not.
  -ro, --reduced-ckt-output-file TEXT
                                  Path to output dss file for reduced circuit.
  -oo, --original-ckt-output-file TEXT
                                  Path to output dss file for original
                                  circuit.
  --help                          Show this message and exit.
```

Here is an example usage.

```bash
grid reduce -f Master.dss
```

## Downloading SMARTDS model

```python
from grid_reducer.smartds import download_s3_folder
download_s3_folder(
        "oedi-data-lake", 
        "SMART-DS/v1.0/2018/SFO/P12U/scenarios/base_timeseries/opendss/p12uhs0_1247/p12uhs0_1247--p12udt1266/", 
        "../../../dump"
    )
```

## Creating Networkx From OpenDSS Model

```python 
from grid_reducer.network import get_networkx_graph_from_opendss_model
graph = get_networkx_graph_from_opendss_model("tests/smartds/Master.dss")
```

## Plotting the network

For simple graphs with no geo-graphic coordinates use this.

```python
from grid_reducer.network import plot_networkx
plot_networkx(graph)
```

However, if you want to plot graph with map layer we suggest using geo-pandas.
Please follow this [examples/explore_grapph.ipynb](./examples/explore_graph.ipynb) to learn more. 

## Attribution and Disclaimer

This software was created under a project sponsored by the U.S. Department of Energy’s Office of Electricity, an agency of the United States Government. Neither the United States Government nor the United States Department of Energy, nor Battelle, nor any of their employees, nor any jurisdiction or organization that has cooperated in the development of these materials, makes any warranty, express or implied, or assumes any legal liability or responsibility for the accuracy, completeness, or usefulness or any information, apparatus, product, software, or process disclosed, or represents that its use would not infringe privately owned rights.

Reference herein to any specific commercial product, process, or service by trade name, trademark, manufacturer, or otherwise does not necessarily constitute or imply its endorsement, recommendation, or favoring by the United States Government or any agency thereof, or Battelle Memorial Institute. The views and opinions of authors expressed herein do not necessarily state or reflect those of the United States Government or any agency thereof.

PACIFIC NORTHWEST NATIONAL LABORATORY 

operated by BATTELLE 

for the UNITED STATES DEPARTMENT OF ENERGY 

under Contract DE-AC05-76RL01830