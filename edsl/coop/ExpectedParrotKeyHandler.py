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
    asked_to_store_file_name = "asked_to_store.txt"
    ep_key_file_name = "ep_api_key.txt"
    application_name = "edsl"

    @property
    def config_dir(self):
        return platformdirs.user_config_dir(self.application_name)

    def _ep_key_file_exists(self) -> bool:
        """Check if the Expected Parrot key file exists."""
        return Path(self.config_dir).joinpath(self.ep_key_file_name).exists()

    def ok_to_ask_to_store(self):
        """Check if it's okay to ask the user to store the key."""
        from edsl.config import CONFIG

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

    def get_ep_api_key(self):
        # check if the key is stored in the config_dir
        api_key = None
        api_key_from_cache = None
        api_key_from_os = None

        if self._ep_key_file_exists():
            with open(Path(self.config_dir).joinpath(self.ep_key_file_name), "r") as f:
                api_key_from_cache = f.read().strip()

        api_key_from_os = os.getenv("EXPECTED_PARROT_API_KEY")

        if api_key_from_os and api_key_from_cache:
            if api_key_from_os != api_key_from_cache:
                import warnings

                warnings.warn(
                    "WARNING: The Expected Parrot API key from the environment variable "
                    "differs from the one stored in the config directory. Using the one "
                    "from the environment variable."
                )
            api_key = api_key_from_os

        if api_key_from_os and not api_key_from_cache:
            api_key = api_key_from_os

        if not api_key_from_os and api_key_from_cache:
            api_key = api_key_from_cache

        if api_key is not None:
            _ = self.ask_to_store(api_key)
        return api_key

    def delete_ep_api_key(self):
        key_path = Path(self.config_dir) / self.ep_key_file_name
        if key_path.exists():
            os.remove(key_path)
            print("Deleted Expected Parrot API key at ", key_path)

    def store_ep_api_key(self, api_key):
        # Create the directory if it doesn't exist
        os.makedirs(self.config_dir, exist_ok=True)

        # Create the path for the key file
        key_path = Path(self.config_dir) / self.ep_key_file_name

        # Save the key
        with open(key_path, "w") as f:
            f.write(api_key)
        # print("Stored Expected Parrot API key at ", key_path)
