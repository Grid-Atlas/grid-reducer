## 📥 Downloading a SMARTDS Sample Model

To help you get started with testing the `grid-reducer`, you may need a sample OpenDSS model.  
We recommend using publicly available datasets like **[SMART-DS](https://data.openei.org/submissions/2981)** from NREL.

To simplify this, we’ve provided a small utility function to easily download a SMARTDS feeder model from the OEDI S3 bucket.

### 🛠 Example

```python
from grid_reducer.smartds import download_s3_folder

download_s3_folder(
    "oedi-data-lake", 
    "SMART-DS/v1.0/2018/SFO/P12U/scenarios/base_timeseries/opendss/p12uhs0_1247/p12uhs0_1247--p12udt1266/", 
    "../../../dump"
)
```

📂 This will download the feeder model to your local ../../../dump directory.

## 💡 Why Use This?

* Provides a ready-to-use OpenDSS model for testing the reducer.
* Helps you get started without needing access to proprietary feeder data.
* Pulls directly from NREL’s OEDI S3 public dataset.
