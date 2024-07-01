from edsl.utilities.gcp_bucket.cloud_storage import CloudStorageManager

manager = CloudStorageManager()

# Download Process
file_name = "GSS2022.dta"  # Name for the downloaded file
save_name = "test.dta"

manager.download_file(file_name, save_name)
