.. _logging:

Log Management
==============

EDSL provides comprehensive log management capabilities through the **LogManager** class. This powerful tool allows you to filter, analyze, and manage EDSL log files with advanced features for debugging, monitoring, and data analysis.

Quick Start
-----------

.. code-block:: python

   from edsl.logger import LogManager
   
   # Create LogManager instance
   log_manager = LogManager()
   
   # View overview with statistics and available commands
   log_manager

This displays a rich overview of your log file:

.. code-block:: text

   LogManager(
     📁 Log file: /Users/john/.edsl/logs/edsl.log
     📊 Total entries: 9,420
     📅 Date range: 2025-08-15 23:40 to 2025-08-16 09:23
     📈 Levels: INFO:5471, ERROR:3949
     🔍 Top logger: edsl.edsl.coop.coop

     💡 Common commands:
       .get_filtered_entries(level='ERROR', n=50)          # Get recent errors
       .to_scenario_list(level='ERROR', since_hours=24)    # Convert to scenarios
       .analyze_patterns(n=100)                            # Pattern analysis
       .archive()                                          # Archive and clear logs
       .clear()                                            # Clear all log entries
   )

Core Features
-------------

Log Filtering
~~~~~~~~~~~~~

Filter log entries using multiple criteria:

.. code-block:: python

   from edsl.logger import LogManager
   
   log_manager = LogManager()
   
   # Filter by log level
   errors = log_manager.get_filtered_entries(level='ERROR', n=50)
   warnings_and_above = log_manager.get_filtered_entries(min_level='WARNING')
   
   # Time-based filtering
   recent = log_manager.get_filtered_entries(since_hours=24)
   last_week = log_manager.get_filtered_entries(since_hours=168)  # 7 days
   date_range = log_manager.get_filtered_entries(
       start_date='2024-08-15', 
       end_date='2024-08-16'
   )
   
   # Pattern matching
   auth_issues = log_manager.get_filtered_entries(pattern='authentication|login')
   failures = log_manager.get_filtered_entries(pattern='fail.*|error.*', n=100)
   
   # Logger-specific filtering
   coop_logs = log_manager.get_filtered_entries(logger_pattern='coop')
   job_logs = log_manager.get_filtered_entries(logger_pattern='jobs')
   
   # Complex combinations
   recent_job_errors = log_manager.get_filtered_entries(
       level='ERROR',
       since_hours=12,
       logger_pattern='jobs',
       n=25
   )

Scenario Conversion for Analysis
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convert log entries to EDSL scenarios for advanced analysis:

.. code-block:: python

   # Convert logs to scenarios
   error_scenarios = log_manager.to_scenario_list(level='ERROR', n=50)
   
   # Each log entry becomes a scenario with rich metadata
   first_scenario = error_scenarios[0]
   print(f"Error level: {first_scenario['level']}")
   print(f"Timestamp: {first_scenario['timestamp_str']}")
   print(f"Logger: {first_scenario['logger_module']}")
   print(f"Message: {first_scenario['message']}")
   print(f"Is error: {first_scenario['is_error']}")
   print(f"Hour of day: {first_scenario['hour']}")

**Available scenario fields:**
- ``timestamp_str``: Formatted timestamp
- ``logger_name``: Full logger name
- ``logger_module``: Last part of logger name  
- ``level``: Log level (ERROR, INFO, etc.)
- ``level_int``: Numeric level for comparison
- ``message``: Log message content
- ``raw_line``: Original log line
- ``hour``, ``minute``, ``weekday``: Time components
- ``date_str``: Date in YYYY-MM-DD format
- ``is_error``: Boolean for ERROR/CRITICAL levels
- ``is_warning_or_above``: Boolean for WARNING+ levels
- ``has_exception``: Boolean if message contains "exception"
- ``has_failed``: Boolean if message contains "fail"
- ``message_length``: Character count of message
- ``words_count``: Word count of message

Using Log Scenarios with EDSL
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Analyze log entries using EDSL questions:

.. code-block:: python

   from edsl import QuestionFreeText, QuestionMultipleChoice
   
   # Convert error logs to scenarios
   error_scenarios = log_manager.to_scenario_list(level='ERROR', n=25)
   
   # Analyze error causes
   analysis_question = QuestionFreeText(
       question_name="error_analysis",
       question_text="What likely caused this error: {{ message }}?"
   )
   
   # Categorize errors
   category_question = QuestionMultipleChoice(
       question_name="error_category",
       question_text="Categorize this error: {{ message }}",
       question_options=[
           "Authentication/Authorization",
           "Network/Connection",
           "Data/Validation",
           "System/Resource",
           "Configuration",
           "Other"
       ]
   )
   
   # Run analysis
   from edsl import Survey
   survey = Survey([analysis_question, category_question])
   results = survey.by(error_scenarios).run()
   
   # View results
   print(results.select("error_analysis", "error_category").print())

Pattern Analysis
~~~~~~~~~~~~~~~

Extract insights from log patterns:

.. code-block:: python

   # Analyze recent log patterns
   analysis = log_manager.analyze_patterns(n=1000)
   
   # View time patterns
   print(f"Busiest hour: {analysis['time_patterns']['busiest_hour']}")
   print(f"Daily distribution: {analysis['time_patterns']['daily_distribution']}")
   
   # View level distribution
   print(f"Level counts: {analysis['level_patterns']}")
   
   # View top loggers
   print(f"Top loggers: {analysis['logger_patterns']}")
   
   # Error analysis
   if 'error_patterns' in analysis:
       error_info = analysis['error_patterns']
       print(f"Error percentage: {error_info['error_percentage']:.1f}%")
       print(f"Exception count: {error_info['exception_count']}")

Statistics and Reporting
~~~~~~~~~~~~~~~~~~~~~~~

Get comprehensive statistics about your logs:

.. code-block:: python

   # Overall statistics
   stats = log_manager.get_stats()
   print(f"Total entries: {stats['total']:,}")
   print(f"Date range: {stats['date_range']['earliest']} to {stats['date_range']['latest']}")
   print(f"Level distribution: {stats['level_counts']}")
   print(f"Top 5 loggers: {list(stats['top_loggers'].items())[:5]}")
   
   # Statistics for filtered entries
   recent_errors = log_manager.get_filtered_entries(level='ERROR', since_hours=24)
   error_stats = log_manager.get_stats(recent_errors)
   print(f"Recent errors: {error_stats['total']}")

Export and Sharing
~~~~~~~~~~~~~~~~~

Export filtered logs or share via Coop:

.. code-block:: python

   from pathlib import Path
   
   # Export filtered logs to file
   export_path = Path('recent_errors.log')
   count = log_manager.export_filtered_logs(
       export_path,
       level='ERROR',
       since_hours=24
   )
   print(f"Exported {count} entries to {export_path}")
   
   # Share logs via Coop
   from edsl.coop import Coop
   coop = Coop()
   
   # Upload filtered logs as file
   result = coop.send_log(level='ERROR', n=50, alias='recent-errors')
   
   # Upload as scenarios for collaborative analysis
   result = coop.send_log(
       level='ERROR', 
       since_hours=24,
       as_scenario_list=True,
       alias='error-scenarios-for-analysis'
   )

Log Maintenance
--------------

Archive Logs
~~~~~~~~~~~

Create timestamped backups of your logs:

.. code-block:: python

   # Archive with compression and clear original (default)
   archive_path = log_manager.archive()
   
   # Archive only, keep original
   backup_path = log_manager.archive(clear_after_archive=False)
   
   # Custom archive location without compression
   custom_backup = log_manager.archive(
       archive_path=Path('~/my_backups'),
       compress=False,
       clear_after_archive=False
   )

The archive process shows detailed progress:

.. code-block:: text

   📦 About to archive EDSL log file:
      📁 Source: /Users/john/.edsl/logs/edsl.log
      📊 Entries: 9,420 (2025-08-15 to 2025-08-16)
      📦 Archive: /Users/john/.edsl/archives/edsl_log_20250816_092142.log.gz
      🗜️  Compress: Yes
      🧹 Clear after: Yes
      Continue? (type 'yes' to confirm):

Clear Logs
~~~~~~~~~~

Remove all log entries to start fresh:

.. code-block:: python

   # Clear with confirmation prompt (safe)
   success = log_manager.clear()
   
   # Clear immediately for scripts (use with caution)
   success = log_manager.clear(confirm=True)

The clear process includes safety confirmation:

.. code-block:: text

   ⚠️  About to clear EDSL log file:
      📁 File: /Users/john/.edsl/logs/edsl.log
      📊 Entries: 9,420
      ⚠️  This action cannot be undone!
      Continue? (type 'yes' to confirm):

Advanced Usage
-------------

Custom Log Files
~~~~~~~~~~~~~~~

Work with non-default log files:

.. code-block:: python

   from pathlib import Path
   
   # Custom log file location
   custom_log_manager = LogManager(Path('/path/to/custom.log'))
   
   # Check if log file exists
   if custom_log_manager.log_file_path.exists():
       stats = custom_log_manager.get_stats()
       print(f"Custom log has {stats['total']} entries")

Filtering Best Practices
~~~~~~~~~~~~~~~~~~~~~~~~

Combine filters for precise results:

.. code-block:: python

   # Find authentication errors in the last day
   auth_errors = log_manager.get_filtered_entries(
       level='ERROR',
       pattern='auth.*|login.*|token.*',
       since_hours=24,
       case_sensitive=False
   )
   
   # Find slow operations (assuming they log with "slow" keyword)
   slow_operations = log_manager.get_filtered_entries(
       pattern='slow.*|timeout.*|.*ms$',
       since_hours=6,
       n=50
   )
   
   # Debug specific component
   coop_debug = log_manager.get_filtered_entries(
       logger_pattern='coop.*',
       min_level='DEBUG',
       since_minutes=30
   )

Performance Optimization
~~~~~~~~~~~~~~~~~~~~~~~

LogManager automatically caches statistics for better performance:

.. code-block:: python

   # First call computes and caches stats
   log_manager = LogManager()
   print(log_manager)  # Caches statistics
   
   # Subsequent calls use cached data
   stats = log_manager.get_stats()  # Fast - uses cache
   
   # Cache is cleared after maintenance operations
   log_manager.clear(confirm=True)  # Clears cache automatically
   print(log_manager)  # Recomputes statistics

Integration Examples
------------------

Debugging Workflows
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Daily error review
   def daily_error_review():
       log_manager = LogManager()
       
       # Get yesterday's errors
       errors = log_manager.get_filtered_entries(
           level='ERROR',
           since_hours=24
       )
       
       if errors:
           print(f"Found {len(errors)} errors in last 24 hours:")
           for error in errors[-5:]:  # Show last 5
               print(f"  {error.timestamp}: {error.message}")
           
           # Convert to scenarios for analysis
           error_scenarios = log_manager.to_scenario_list(entries=errors)
           
           # Analyze with EDSL
           from edsl import QuestionFreeText
           q = QuestionFreeText(
               question_name="priority",
               question_text="Rate the priority of this error (1-5): {{ message }}"
           )
           priorities = q.by(error_scenarios[:10]).run()  # Analyze top 10
           print(priorities.select("priority").print())

Monitoring Automation
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Automated log monitoring
   def monitor_system_health():
       log_manager = LogManager()
       
       # Check for recent critical issues
       critical = log_manager.get_filtered_entries(
           level='CRITICAL',
           since_minutes=60
       )
       
       if critical:
           # Send alert via Coop
           from edsl.coop import Coop
           coop = Coop()
           alert_result = coop.send_log(
               level='CRITICAL',
               since_minutes=60,
               as_scenario_list=True,
               alias='critical-alerts'
           )
           print(f"Alert sent: {alert_result['url']}")
       
       # Weekly log maintenance
       from datetime import datetime
       if datetime.now().weekday() == 0:  # Monday
           archive_path = log_manager.archive()
           print(f"Weekly archive created: {archive_path}")

Research and Analysis
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Research log patterns for insights
   def analyze_usage_patterns():
       log_manager = LogManager()
       
       # Convert logs to scenarios
       scenarios = log_manager.to_scenario_list(n=1000)
       
       # Research questions about usage
       from edsl import QuestionMultipleChoice, Survey
       
       q1 = QuestionMultipleChoice(
           question_name="time_category",
           question_text="What time category is {{ hour }}:00?",
           question_options=["Night (0-5)", "Morning (6-11)", "Afternoon (12-17)", "Evening (18-23)"]
       )
       
       q2 = QuestionMultipleChoice(
           question_name="operation_type",
           question_text="What type of operation does this suggest: {{ message }}",
           question_options=["API Call", "Data Processing", "User Interface", "System Maintenance", "Other"]
       )
       
       survey = Survey([q1, q2])
       results = survey.by(scenarios).run()
       
       # Analyze patterns
       time_patterns = results.select("time_category").to_list()
       operation_patterns = results.select("operation_type").to_list()
       
       print("Usage patterns analysis complete!")
       return results

Jupyter Notebook Integration
---------------------------

LogManager provides rich HTML displays in Jupyter notebooks:

.. code-block:: python

   # In Jupyter notebook
   from edsl.logger import LogManager
   
   log_manager = LogManager()
   log_manager  # Shows rich HTML table with colored log levels

The HTML display includes:
- Overview with file path, entry count, and date range
- Color-coded log level distribution (red for errors, blue for info)
- Top loggers table with counts
- Interactive command examples with syntax highlighting

API Reference
-------------

LogManager Class
~~~~~~~~~~~~~~~

.. py:class:: LogManager(log_file_path=None)

   Main class for EDSL log management.
   
   :param log_file_path: Optional path to log file. Defaults to ``~/.edsl/logs/edsl.log``
   :type log_file_path: Path, optional

.. py:method:: get_filtered_entries(**kwargs)

   Filter log entries by various criteria.
   
   :param n: Maximum number of entries to return
   :type n: int, optional
   :param level: Specific level(s) to include ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
   :type level: str or List[str], optional
   :param min_level: Minimum level (includes this level and above)
   :type min_level: str, optional
   :param since_hours: Include entries from last N hours
   :type since_hours: float, optional
   :param since_minutes: Include entries from last N minutes
   :type since_minutes: float, optional
   :param start_date: Start date for filtering ('YYYY-MM-DD')
   :type start_date: str or datetime, optional
   :param end_date: End date for filtering ('YYYY-MM-DD')
   :type end_date: str or datetime, optional
   :param pattern: Regex pattern for message content
   :type pattern: str, optional
   :param logger_pattern: Regex pattern for logger names
   :type logger_pattern: str, optional
   :param case_sensitive: Whether pattern matching is case sensitive
   :type case_sensitive: bool, optional
   :param reverse: Return in reverse chronological order
   :type reverse: bool, optional
   :returns: List of filtered log entries
   :rtype: List[LogEntry]

.. py:method:: to_scenario_list(entries=None, **filter_kwargs)

   Convert log entries to EDSL scenarios.
   
   :param entries: Pre-filtered entries to convert
   :type entries: List[LogEntry], optional
   :param filter_kwargs: Arguments for get_filtered_entries()
   :returns: ScenarioList with log data
   :rtype: ScenarioList

.. py:method:: analyze_patterns(**filter_kwargs)

   Analyze log patterns and extract insights.
   
   :param filter_kwargs: Arguments for get_filtered_entries()
   :returns: Dictionary with pattern analysis
   :rtype: Dict[str, Any]

.. py:method:: get_stats(entries=None)

   Get statistics about log entries.
   
   :param entries: Specific entries to analyze
   :type entries: List[LogEntry], optional
   :returns: Statistics dictionary
   :rtype: Dict[str, Any]

.. py:method:: export_filtered_logs(output_path, **filter_kwargs)

   Export filtered log entries to file.
   
   :param output_path: Path for output file
   :type output_path: Path
   :param filter_kwargs: Arguments for get_filtered_entries()
   :returns: Number of entries exported
   :rtype: int

.. py:method:: archive(archive_path=None, clear_after_archive=True, compress=True, confirm=False)

   Archive log file with timestamp.
   
   :param archive_path: Directory for archive (default: ~/.edsl/archives/)
   :type archive_path: Path, optional
   :param clear_after_archive: Clear original after archiving
   :type clear_after_archive: bool
   :param compress: Gzip compress the archive
   :type compress: bool
   :param confirm: Skip confirmation prompt
   :type confirm: bool
   :returns: Path to created archive
   :rtype: Path or None

.. py:method:: clear(confirm=False)

   Clear all log entries.
   
   :param confirm: Skip confirmation prompt
   :type confirm: bool
   :returns: Success status
   :rtype: bool

LogEntry Class
~~~~~~~~~~~~~

.. py:class:: LogEntry

   Represents a parsed log entry.
   
   :param timestamp: When the log entry was created
   :type timestamp: datetime
   :param logger_name: Name of the logger
   :type logger_name: str
   :param level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
   :type level: str
   :param message: Log message content
   :type message: str
   :param raw_line: Original log line
   :type raw_line: str
   :param level_int: Numeric level for comparisons
   :type level_int: int

Best Practices
--------------

Safety Guidelines
~~~~~~~~~~~~~~~

- Always use confirmation prompts for destructive operations (default behavior)
- Archive logs before clearing in production environments
- Use specific filters to avoid processing unnecessary log entries
- Test complex regex patterns with small datasets first

Performance Tips
~~~~~~~~~~~~~~~

- Use ``n`` parameter to limit results when exploring large logs
- Combine multiple filters in single calls rather than chaining
- Cache LogManager instances when doing multiple operations
- Consider archiving very large log files before analysis

Common Patterns
~~~~~~~~~~~~~

**Error Investigation:**
  1. Filter recent errors: ``get_filtered_entries(level='ERROR', since_hours=24)``
  2. Convert to scenarios for analysis: ``to_scenario_list()``
  3. Use EDSL questions to categorize and analyze
  4. Export findings or share via Coop

**Regular Maintenance:**
  1. Weekly archive: ``archive()`` (includes clearing)
  2. Monitor critical issues: ``get_filtered_entries(level='CRITICAL')``
  3. Pattern analysis: ``analyze_patterns()`` for trends

**Debugging Workflows:**
  1. Filter by component: ``logger_pattern='component_name'``
  2. Time-bound investigation: ``since_hours=X`` for specific incidents
  3. Pattern matching: ``pattern='specific_error_text'``
  4. Export for sharing: ``export_filtered_logs()``

Troubleshooting
--------------

Common Issues
~~~~~~~~~~~~

**Log file not found:**
  Check the log file path. EDSL logs are typically at ``~/.edsl/logs/edsl.log``

**No entries returned:**
  - Verify log file has content: ``log_manager.get_stats()``
  - Check filter criteria are not too restrictive
  - Ensure date ranges are correct

**Performance issues with large logs:**
  - Use ``n`` parameter to limit results
  - Consider archiving old entries
  - Filter by time ranges first, then other criteria

**Permission errors:**
  - Ensure read access to log file
  - For archive/clear operations, ensure write access to log directory

Getting Help
~~~~~~~~~~~

- View available commands: ``print(log_manager)``
- Check method documentation: ``help(log_manager.method_name)``
- View log overview: ``log_manager.get_stats()``
- Test filters with small limits: ``get_filtered_entries(n=10, ...)``

The LogManager provides powerful capabilities for understanding, analyzing, and maintaining your EDSL logs. Whether you're debugging issues, monitoring system health, or conducting research on usage patterns, LogManager offers the tools you need for effective log management.