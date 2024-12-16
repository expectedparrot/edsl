from pathlib import Path
import os
import platformdirs


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

    def ask_to_store(self, api_key) -> bool:
        """Ask the user if they want to store the Expected Parrot key. If they say "yes", store it."""
        if self.ok_to_ask_to_store():
            can_we_store = input(
                "Would you like to store your Expected Parrot key for future use? (y/n): "
            )
            if can_we_store.lower() == "y":
                Path(self.config_dir).mkdir(parents=True, exist_ok=True)
                self.store_ep_api_key(api_key)
                print("Stored Expected Parrot API key at ", self.config_dir)
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
        if self._ep_key_file_exists():
            with open(Path(self.config_dir).joinpath(self.ep_key_file_name), "r") as f:
                api_key = f.read().strip()
                print("Using stored Expected Parrot API key at ", f.name)
                return api_key

        api_key = os.getenv("EXPECTED_PARROT_API_KEY")
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
        print("Stored Expected Parrot API key at ", key_path)
