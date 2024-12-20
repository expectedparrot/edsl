class RemoteCacheSync:
    def __init__(
        self, coop, cache, output_func, remote_cache=True, remote_cache_description=""
    ):
        self.coop = coop
        self.cache = cache
        self._output = output_func
        self.remote_cache = remote_cache
        self.old_entry_keys = []
        self.new_cache_entries = []
        self.remote_cache_description = remote_cache_description

    def __enter__(self):
        if self.remote_cache:
            self._sync_from_remote()
            self.old_entry_keys = list(self.cache.keys())
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.remote_cache:
            self._sync_to_remote()
        return False  # Propagate exceptions

    def _sync_from_remote(self):
        cache_difference = self.coop.remote_cache_get_diff(self.cache.keys())
        client_missing_cacheentries = cache_difference.get(
            "client_missing_cacheentries", []
        )
        missing_entry_count = len(client_missing_cacheentries)

        if missing_entry_count > 0:
            self._output(
                f"Updating local cache with {missing_entry_count:,} new "
                f"{'entry' if missing_entry_count == 1 else 'entries'} from remote..."
            )
            self.cache.add_from_dict(
                {entry.key: entry for entry in client_missing_cacheentries}
            )
            self._output("Local cache updated!")
        else:
            self._output("No new entries to add to local cache.")

    def _sync_to_remote(self):
        cache_difference = self.coop.remote_cache_get_diff(self.cache.keys())
        server_missing_cacheentry_keys = cache_difference.get(
            "server_missing_cacheentry_keys", []
        )
        server_missing_cacheentries = [
            entry
            for key in server_missing_cacheentry_keys
            if (entry := self.cache.data.get(key)) is not None
        ]

        new_cache_entries = [
            entry
            for entry in self.cache.values()
            if entry.key not in self.old_entry_keys
        ]
        server_missing_cacheentries.extend(new_cache_entries)
        new_entry_count = len(server_missing_cacheentries)

        if new_entry_count > 0:
            self._output(
                f"Updating remote cache with {new_entry_count:,} new "
                f"{'entry' if new_entry_count == 1 else 'entries'}..."
            )
            self.coop.remote_cache_create_many(
                server_missing_cacheentries,
                visibility="private",
                description=self.remote_cache_description,
            )
            self._output("Remote cache updated!")
        else:
            self._output("No new entries to add to remote cache.")

        self._output(
            f"There are {len(self.cache.keys()):,} entries in the local cache."
        )
