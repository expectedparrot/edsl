@echo off
:: commands.bat

if "%1" == "test" goto test
if "%1" == "clean-test" goto clean-test
goto end

::###############
::##@Utils ⭐ 
::############### 

:clean-test
:: Clean test files
if exist dist rmdir /s /q dist
if exist htmlcov rmdir /s /q htmlcov
if exist prof rmdir /s /q prof
if exist tests\temp_outputs rmdir /s /q tests\temp_outputs
if exist tests\edsl_cache_test.db del /q tests\edsl_cache_test.db
if exist tests\interview.log del /q tests\interview.log
for %%f in (*.html) do (
    if exist "%%f" del /q "%%f"
)
for %%f in (*.jsonl) do (
    if exist "%%f" del /q "%%f"
)
goto end

::###############
::##@Testing 🐛
::###############

:test
:: Run regular tests (no Coop tests) 
call :clean-test
pytest -xv tests --nocoop
goto end

:end
