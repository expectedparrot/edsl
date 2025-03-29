from pathlib import Path
import os
import platformdirs


import sys
import select


def get_input_with_timeout(prompt, timeout=5, default="y"):
    print(prompt, end="", flush=True)
    ready, _, _ = select.select([sys.stdin], [], [], timeout)
    if ready:
        return sys.stdin.readline().strip()
    print(f"\nNo input received within {timeout} seconds. Using default: {default}")
    return default


class ExpectedParrotKeyHandler:
    """
    Manages Expected Parrot API keys for user authentication.
    
    This class handles the storage, retrieval, and management of Expected Parrot API keys.
    It provides functionality to securely store API keys in platform-specific user
    configuration directories and retrieve them when needed. It also handles key
    preference management (e.g., environment variables vs. stored keys).
    
    The key handler follows a priority order when retrieving keys:
    1. Environment variables (EXPECTED_PARROT_API_KEY)
    2. Platform-specific user config directory
    
    Attributes:
        asked_to_store_file_name (str): Filename for tracking if user was asked about storage
        ep_key_file_name (str): Filename for the stored API key
        application_name (str): Application name for the config directory
    """
    asked_to_store_file_name = "asked_to_store.txt"
    ep_key_file_name = "ep_api_key.txt"
    application_name = "edsl"

    @property
    def config_dir(self) -> str:
        """
        Get the platform-specific user configuration directory for the application.
        
        This property uses the platformdirs library to determine the appropriate
        location for storing configuration files based on the user's operating system.
        
        Returns:
            str: Path to the user configuration directory
            
        Notes:
            - On Windows, typically: C:\\Users\\<username>\\AppData\\Local\\edsl
            - On macOS, typically: ~/Library/Application Support/edsl
            - On Linux, typically: ~/.config/edsl
        """
        return platformdirs.user_config_dir(self.application_name)

    def _ep_key_file_exists(self) -> bool:
        """
        Check if the Expected Parrot key file exists in the config directory.
        
        Returns:
            bool: True if the key file exists, False otherwise
            
        Notes:
            - Does not check the validity of the stored key
        """
        return Path(self.config_dir).joinpath(self.ep_key_file_name).exists()

    def ok_to_ask_to_store(self):
        """Check if it's okay to ask the user to store the key."""
        from ..config import CONFIG

        if CONFIG.get("EDSL_RUN_MODE") != "production":
            return False

        return (
            not Path(self.config_dir).joinpath(self.asked_to_store_file_name).exists()
        )

    def reset_asked_to_store(self):
        """Reset the flag that indicates whether the user has been asked to store the key."""
        asked_to_store_path = Path(self.config_dir).joinpath(
            self.asked_to_store_file_name
        )
        if asked_to_store_path.exists():
            os.remove(asked_to_store_path)
            print(
                "Deleted the file that indicates whether the user has been asked to store the key."
            )

    def ask_to_store(self, api_key) -> bool:
        """Ask the user if they want to store the Expected Parrot key. If they say "yes", store it."""
        if self.ok_to_ask_to_store():
            # can_we_store = get_input_with_timeout(
            #     "Would you like to store your Expected Parrot key for future use? (y/n): ",
            #     timeout=5,
            #     default="y",
            # )
            can_we_store = "y"
            if can_we_store.lower() == "y":
                Path(self.config_dir).mkdir(parents=True, exist_ok=True)
                self.store_ep_api_key(api_key)
                # print("Stored Expected Parrot API key at ", self.config_dir)
                return True
            else:
                Path(self.config_dir).mkdir(parents=True, exist_ok=True)
                with open(
                    Path(self.config_dir).joinpath(self.asked_to_store_file_name), "w"
                ) as f:
                    f.write("Yes")
        return False

    def get_ep_api_key(self) -> str:
        """
        Retrieve the Expected Parrot API key from available sources.
        
        This method checks multiple sources for the API key, with the following priority:
        1. Environment variable (EXPECTED_PARROT_API_KEY)
        2. Stored key in the user's config directory
        
        If keys are found in multiple sources and they differ, the environment
        variable takes precedence. A warning is issued in this case.
        
        Returns:
            str: The Expected Parrot API key, or None if not found
            
        Notes:
            - If a key is found, it will attempt to store it persistently if appropriate
            - Warnings are issued if conflicting keys are found in different sources
            - Environment variables always take precedence over stored keys
        """
        # Initialize variables
        api_key = None
        api_key_from_cache = None
        api_key_from_os = None

        # Try to get key from config directory
        if self._ep_key_file_exists():
            with open(Path(self.config_dir).joinpath(self.ep_key_file_name), "r") as f:
                api_key_from_cache = f.read().strip()

        # Try to get key from environment variable
        api_key_from_os = os.getenv("EXPECTED_PARROT_API_KEY")

        # Handle the case where both sources have keys
        if api_key_from_os and api_key_from_cache:
            if api_key_from_os != api_key_from_cache:
                import warnings
                warnings.warn(
                    "WARNING: The Expected Parrot API key from the environment variable "
                    "differs from the one stored in the config directory. Using the one "
                    "from the environment variable."
                )
            api_key = api_key_from_os
        # Handle the case where only OS environment has key
        elif api_key_from_os:
            api_key = api_key_from_os
        # Handle the case where only cached key exists
        elif api_key_from_cache:
            api_key = api_key_from_cache

        # If a key was found, ask to store it persistently
        if api_key is not None:
            _ = self.ask_to_store(api_key)
            
        return api_key

    def delete_ep_api_key(self):
        key_path = Path(self.config_dir) / self.ep_key_file_name
        if key_path.exists():
            os.remove(key_path)
            print("Deleted Expected Parrot API key at ", key_path)

    def store_ep_api_key(self, api_key: str) -> None:
        """
        Store the Expected Parrot API key in the user's config directory.
        
        This method saves the provided API key to a file in the platform-specific
        user configuration directory, creating the directory if it doesn't exist.
        
        Parameters:
            api_key (str): The API key to store
            
        Notes:
            - The key is stored in plain text in the user's config directory
            - The directory is created if it doesn't exist
            - Any existing key file will be overwritten
            - The location of the config directory is platform-specific
        """
        # Create the directory if it doesn't exist
        os.makedirs(self.config_dir, exist_ok=True)

        # Create the path for the key file
        key_path = Path(self.config_dir) / self.ep_key_file_name

        # Save the key
        with open(key_path, "w") as f:
            f.write(api_key)
        # print("Stored Expected Parrot API key at ", key_path)
