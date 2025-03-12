"""Module to store system information."""

# This module is not currently used by any part of the codebase.
# Keeping it commented out for potential future use.

# from dataclasses import dataclass
# import getpass
# import platform
# import pkg_resources


# @dataclass
# class SystemInfo:
#     """Dataclass to store system information."""

#     username: str
#     system_info: str
#     release_info: str
#     package_name: str
#     package_version: str

#     def __init__(self, package_name: str):
#         """Initialize the dataclass with system."""
#         self.username = getpass.getuser()
#         self.system_info = platform.system()
#         self.release_info = platform.release()
#         self.package_name = package_name
#         try:
#             self.package_version = pkg_resources.get_distribution(package_name).version
#         except pkg_resources.DistributionNotFound:
#             self.package_version = "Not installed"
