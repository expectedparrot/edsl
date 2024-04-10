# Changelog

## Unreleased

## [0.1.0] - 2023-12-20
### Added
- Base feature

## [0.1.1] - 2023-12-24
### Added
- Changelog file

### Fixed
- Image display and description text in README.md

### Removed
- Unused files

## [0.1.4] - 2024-01-22
### Added
- Support for several large language models
- Async survey running
- Asking for API keys before they are used

### Fixed
- Bugs in survey running
- Bugs in several question types 

### Removed
- Unused files
- Unused package dependencies

## [0.1.5] - 2024-01-23

### Fixed
- Improvements in async survey running

## [0.1.6] - 2024-01-24

### Fixed
- Improvements in async survey running

## [0.1.7] - 2024-01-25

### Fixed
- Improvements in async survey running
- Added logging

## [0.1.8] - 2024-01-26

### Fixed
- Better handling of async failures
- Fixed bug in survey logic

## [0.1.9] - 2024-01-27

### Added
- Report functionalities are now part of the main package.

### Fixed
- Fixed a bug in the Results.print() function

### Removed
- The package no longer supports a report extras option.
- Fixed a bug in EndofSurvey

## [0.1.11] - 2024-02-01

### Added
- 

### Fixed
- Question options can now be 1 character long or more (down from 2 characters)
- Fixed a bug where prompts displayed were incorrect (prompts sent were correct)

### Removed
- 

## [0.1.12] - 2024-02-12

### Added
- Results now provides a `.sql()` method that can be used to explore data in a SQL-like manner.
- Results now provides a `.ggplot()` method that can be used to create ggplot2 visualizations.
- Agent now admits an optional `name` argument that can be used to identify the Agent.

### Fixed
- Fixed various issues with visualizations. They should now work better.

### Removed

## [0.1.13] - 2024-03-01

### Added
- The `answer` component of the `Results` object is printed in a nicer format.

### Fixed
- `trait_name` descriptor was not working; it is now fixed.
- `QuestionList` is now working properly again

### Removed

## [0.1.14] - 2024-03-06

### Added
- The raw model response is now available in the `Results` object, accessed via "raw_model_response" keyword. 
There is one for each question. The key is the question_name + `_raw_response_model`
- The `.run(progress_bar = True)` returns a much more informative real-time view of job progress.

### Fixed

### Removed

## [0.1.15] - 2024-03-09

### Added

### Fixed
- Various fixes and small improvements

### Removed


## [0.1.16] - 2024-04-10

### Added
- New documentation page: https://docs.expectedparrot.com
- Progress bar: You can now pass `progress_bar=True` to the `run()` method to see a progress bar as your survey is running. Example:

### Changed
- Caching:

### Deprecated

### Removed

### Fixed
- `.run(n = ...)` now works and will run each interview as many times as needed


