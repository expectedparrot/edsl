from typing import Optional


class CoopFunctionsMixin:
    def better_names(self, existing_names):
        from .. import QuestionList, Scenario

        s = Scenario({"existing_names": existing_names})
        q = QuestionList(
            question_text="""The following column names are already in use: {{ existing_names }} 
                         Please provide new column names.
                         They should be short (one or two words) and unique valid Python idenifiers (i.e., use underscores instead of spaces). 
                         """,
            question_name="better_names",
        )
        results = q.by(s).run(verbose=False)
        return results.select("answer.better_names").first()

    def send_log(
        self,
        n: Optional[int] = 100,
        description: Optional[str] = None,
        alias: Optional[str] = None,
        level: Optional[str] = None,
        min_level: Optional[str] = None,
        since_hours: Optional[float] = None,
        since_minutes: Optional[float] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        pattern: Optional[str] = None,
        logger_pattern: Optional[str] = None,
        as_scenario_list: bool = False,
    ):
        """
        Create a FileStore or ScenarioList of filtered EDSL log entries and push it to coop.

        Args:
            n: Maximum number of log entries to include (default: 100)
            description: Optional description for the uploaded object
            alias: Optional alias for the uploaded object
            level: Specific log level(s) to include ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
            min_level: Minimum log level (includes this level and higher)
            since_hours: Include entries from last N hours
            since_minutes: Include entries from last N minutes
            start_date: Start date for filtering (format: 'YYYY-MM-DD')
            end_date: End date for filtering (format: 'YYYY-MM-DD')
            pattern: Regex pattern to match in log messages
            logger_pattern: Regex pattern to match logger names
            as_scenario_list: If True, convert logs to ScenarioList for EDSL analysis

        Returns:
            The result from pushing the object to coop

        Raises:
            FileNotFoundError: If the log file doesn't exist
            Exception: If there's an error reading the log or uploading to coop

        Examples:
            # Send last 50 error entries as log file
            coop.send_log(n=50, level='ERROR')

            # Send entries as ScenarioList for analysis
            coop.send_log(level='ERROR', n=25, as_scenario_list=True)

            # Send time-filtered entries for pattern analysis
            coop.send_log(since_hours=24, pattern='exception|error', as_scenario_list=True)
        """
        from ..scenarios import FileStore
        from ..logger import LogManager
        import tempfile
        import os

        # Create LogManager instance
        log_manager = LogManager()

        # Get filtered log entries
        try:
            entries = log_manager.get_filtered_entries(
                n=n,
                level=level,
                min_level=min_level,
                since_hours=since_hours,
                since_minutes=since_minutes,
                start_date=start_date,
                end_date=end_date,
                pattern=pattern,
                logger_pattern=logger_pattern,
            )
        except Exception as e:
            raise Exception(f"Error filtering log entries: {e}")

        if not entries:
            raise Exception("No log entries match the specified filters")

        # Generate description if not provided
        filter_desc = []
        if level:
            filter_desc.append(f"level={level}")
        if min_level:
            filter_desc.append(f"min_level={min_level}")
        if since_hours:
            filter_desc.append(f"last {since_hours}h")
        if since_minutes:
            filter_desc.append(f"last {since_minutes}m")
        if start_date or end_date:
            date_range = f"{start_date or 'beginning'} to {end_date or 'now'}"
            filter_desc.append(f"dates: {date_range}")
        if pattern:
            filter_desc.append(f"pattern: {pattern}")
        if logger_pattern:
            filter_desc.append(f"logger: {logger_pattern}")

        filter_str = ", ".join(filter_desc) if filter_desc else "all entries"

        if as_scenario_list:
            # Convert to ScenarioList and push directly
            scenario_list = log_manager.to_scenario_list(entries=entries)

            if description is None:
                description = (
                    f"EDSL log scenarios ({len(scenario_list)} scenarios, {filter_str})"
                )

            # Push the ScenarioList to coop
            result = self.push(scenario_list, description=description, alias=alias)
            return result

        else:
            # Convert entries back to log lines and create FileStore
            log_lines = log_manager.get_entry_lines(entries)

            # Create a temporary file with the filtered log entries
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".log", delete=False, encoding="utf-8"
            ) as temp_file:
                for line in log_lines:
                    temp_file.write(line + "\n")
                temp_file_path = temp_file.name

            try:
                # Create a FileStore object from the temporary file
                file_store = FileStore(temp_file_path)

                if description is None:
                    description = (
                        f"EDSL log entries ({len(log_lines)} entries, {filter_str})"
                    )

                # Push the FileStore to coop
                result = self.push(file_store, description=description, alias=alias)

                return result

            finally:
                # Clean up the temporary file
                try:
                    os.unlink(temp_file_path)
                except Exception:
                    pass  # If cleanup fails, don't raise an error
