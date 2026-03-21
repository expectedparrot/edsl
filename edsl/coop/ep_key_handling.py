import os


class ExpectedParrotKeyHandler:
    """
    Manages Expected Parrot API keys for user authentication.

    Keys are read exclusively from the EXPECTED_PARROT_API_KEY environment
    variable (typically set via a .env file).  The legacy platform-specific
    config directory (managed by platformdirs) is no longer consulted.
    """

    def get_ep_api_key(self) -> str:
        """
        Retrieve the Expected Parrot API key from the environment.

        Returns:
            str: The Expected Parrot API key, or None if not found.
        """
        return os.getenv("EXPECTED_PARROT_API_KEY")

    def store_ep_api_key(self, api_key: str) -> None:
        """
        Store the Expected Parrot API key in the .env file and set it
        in the current process environment.

        Parameters:
            api_key (str): The API key to store.
        """
        from ..utilities.utilities import write_api_key_to_env

        write_api_key_to_env(api_key)
        os.environ["EXPECTED_PARROT_API_KEY"] = api_key

    def delete_ep_api_key(self) -> None:
        """Remove the API key from the current process environment."""
        os.environ.pop("EXPECTED_PARROT_API_KEY", None)
