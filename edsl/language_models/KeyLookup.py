import os
from collections import UserDict

from edsl.enums import service_to_api_keyname
from edsl.exceptions import MissingAPIKeyError


class KeyLookup(UserDict):
    @classmethod
    def from_os_environ(cls):
        """Create an instance of KeyLookupAPI with keys from os.environ"""
        return cls({key: value for key, value in os.environ.items()})

    def get_api_token(self, service: str, remote: bool = False):
        key_name = service_to_api_keyname.get(service, "NOT FOUND")

        if service == "bedrock":
            api_token = [self.get(key_name[0]), self.get(key_name[1])]
            missing_token = any(token is None for token in api_token)
        else:
            api_token = self.get(key_name)
            missing_token = api_token is None

        if missing_token and service != "test" and not remote:
            raise MissingAPIKeyError(
                f"""The key for service: `{service}` is not set.
                    Need a key with name {key_name} in your .env file."""
            )

        return api_token
