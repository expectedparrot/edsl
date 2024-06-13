:: ---------
:: Analogues for makefile commands, to help our developers who use Windows
:: ---------
@echo off
:: commands.bat

if "%1" == "install" goto install
if "%1" == "test" goto test
if "%1" == "clean-test" goto clean-test
goto end

::###############
::##@Utils ⭐ 
::############### 

:install
:: Install all project deps and create a venv (local)
call :clean-all
echo Creating a venv from pyproject.toml and installing deps using poetry...
poetry install --with dev
echo All deps installed and venv created.
goto end

:clean
echo Cleaning tempfiles...
if exist .coverage del .coverage
if exist .edsl_cache rmdir /s /q .edsl_cache
if exist .mypy_cache rmdir /s /q .mypy_cache
if exist .temp rmdir /s /q .temp
if exist dist rmdir /s /q dist
if exist htmlcov rmdir /s /q htmlcov
if exist prof rmdir /s /q prof
for /r %%i in (*.db) do if not "%%~dpi"=="%CD%\.venv\" del "%%i"
for /r %%i in (*.db.bak) do if not "%%~dpi"=="%CD%\.venv\" del "%%i"
for /r %%i in (*.log) do if not "%%~dpi"=="%CD%\.venv\" del "%%i"
for /r %%i in (.) do (
    if "%%~nxi" == ".venv" (
        echo Skipping this directory... >NUL
    ) else (
        if "%%~nxi" == ".pytest_cache" (
            rmdir /s /q "%%i"
        )
    )
)
for /r %%i in (.) do (
    if "%%~nxi" == ".venv" (
        echo Skipping this directory... >NUL
    ) else (
        if "%%~nxi" == "__pycache__" (
            rmdir /s /q "%%i"
        )
    )
)
goto end

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

:clean-all
:: Clean everything (including the venv)
if defined VIRTUAL_ENV (
    echo Your virtual environment is active. Please deactivate it.
    exit /b 1
)
echo Cleaning tempfiles...
call :clean
echo Cleaning testfiles...
call :clean-test
echo Cleaning the venv...
if exist .venv (
    rmdir /s /q .venv
)
echo Done!
goto end

::###############
::##@Testing 🐛
::###############

:test
:: Run regular tests (no Coop tests) 
call :clean-test
pytest -xv tests --nocoop --windows
goto end

:end
