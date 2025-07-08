import os

import s3fs
from tqdm import tqdm


def download_s3_folder(bucket_name: str, prefix: str, local_dir: str):
    """
    Download a large folder from a public AWS S3 bucket using fsspec. This will print nothing except a progress bar.

    :param bucket_name: Name of the S3 bucket (e.g., 'my-public-bucket').
    :param prefix: Path of the folder in S3 (e.g., 'my-folder/').
    :param local_dir: Local directory to store downloaded files.
    """
    s3 = s3fs.S3FileSystem(anon=True)  # 'anon=True' means accessing a public bucket
    s3_path = f"{bucket_name}/{prefix}"

    # Use fsspec to list all files in the given S3 folder
    files = s3.glob(f"{s3_path}*")  # Get list of files

    if not files:
        print("No files found in the specified path.")
        return

    os.makedirs(local_dir, exist_ok=True)

    for file in tqdm(files, desc="Downloading files", unit="file"):
        relative_path = file.replace(s3_path, "")
        local_file_path = os.path.join(local_dir, relative_path)
        os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
        s3.get(file, local_file_path)
