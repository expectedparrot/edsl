# This module is not currently used by any part of the codebase.
# Keeping it commented out for potential future use.

# import requests


# class CloudStorageManager:
#     def __init__(self, secret_token=None):
#         self.api_url = "https://bucket-server-tte53lsfxq-uc.a.run.app"
#         self.secret_token = secret_token

#     def get_signed_url(self, file_name, operation="upload"):
#         """Get a signed URL for uploading or downloading a file."""

#         if operation == "upload":
#             if self.secret_token == None:
#                 raise "Set secret_token for upload permissions"
#             headers = {
#                 "Authorization": self.secret_token,
#                 "Content-Type": "application/json",
#             }
#         else:
#             headers = {
#                 "Content-Type": "application/json",
#             }
#         data = {"file_name": file_name}
#         endpoint = f"{self.api_url}/generate-{operation}-signed-url"
#         response = requests.post(endpoint, json=data, headers=headers)

#         if response.status_code == 200:
#             return response.json().get("signed_url")
#         else:
#             raise Exception(
#                 f"Failed to get signed URL: {response.status_code} {response.text}"
#             )

#     def upload_file(self, file_path, upload_file_name):
#         """Upload a file to the signed URL."""
#         signed_url = self.get_signed_url(upload_file_name, operation="upload")

#         with open(file_path, "rb") as file:
#             upload_response = requests.put(
#                 signed_url,
#                 data=file,
#                 headers={"Content-Type": "application/octet-stream"},
#             )

#             if upload_response.status_code == 200:
#                 print("File uploaded successfully")
#             else:
#                 raise Exception(
#                     f"Failed to upload file: {upload_response.status_code} {upload_response.text}"
#                 )

#     def download_file(self, file_name, save_name):
#         """Download a file from the signed URL."""

#         signed_url = self.get_signed_url(file_name, operation="download")
#         download_response = requests.get(signed_url, stream=True)

#         if download_response.status_code == 200:
#             with open(save_name, "wb") as file:
#                 for chunk in download_response.iter_content(chunk_size=8192):
#                     file.write(chunk)
#             print("File downloaded successfully")
#         else:
#             raise Exception(
#                 f"Failed to download file: {download_response.status_code} {download_response.text}"
#             )

#     def delete_file(self, file_name):
#         """Delete a file from the cloud storage."""
#         headers = {
#             "Authorization": self.secret_token,
#             "Content-Type": "application/json",
#         }
#         data = {"file_name": file_name}
#         endpoint = f"{self.api_url}/delete-file"
#         response = requests.delete(endpoint, params=data, headers=headers)

#         if response.status_code == 200:
#             print("File deleted successfully")
#         else:
#             raise Exception(
#                 f"Failed to delete file: {response.status_code} {response.text}"
#             )

#     def list_files(self):
#         url = self.api_url + "/list_files"
#         headers = {
#             "Authorization": self.secret_token,
#             "Content-Type": "application/json",
#         }
#         res = requests.get(url, headers=headers)
#         data = res.json()
#         for x in data["data"]:
#             x["url"] = self.api_url + "/file/" + x["shaKey"]

#         return data
