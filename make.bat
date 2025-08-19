:: ---------
:: Analogues for makefile commands, to help our developers who use Windows
:: ---------
@echo off
setlocal
:: To run a command, type `make.bat <command-name-here> in your terminal
if "%1" == "bump" goto :bump
if "%1" == "clean-docs" goto :clean-docs
if "%1" == "clean-test" goto :clean-test
if "%1" == "docs" goto :docs
if "%1" == "docs-view" goto :docs-view
if "%1" == "install" goto :install
if "%1" == "publish" goto :publish
if "%1" == "test" goto :test
if "%1" == "test-coop" goto :test-coop
if "%1" == "test-coverage" goto :test-coverage
if "%1" == "test-data" goto :test-data
echo Command not found.
goto :end

::###############
::##@Utils ⭐ 
::############### 

:install
:: Install all project deps and create a venv (local)
call :clean-all
echo Creating a venv from pyproject.toml and installing deps using poetry...
poetry install --with dev
echo All deps installed and venv created.
goto :end

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
goto :end

:clean-docs
:: Clean documentation files
echo Cleaning docs...
if exist .temp\docs rmdir /s /q .temp\docs
goto :end

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
goto :end

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
goto :end

:publish
:: Publish the package to PyPI (requires credentials)
for /f "tokens=1,* delims=:" %%a in ('findstr /n /C:"version =" pyproject.toml') do if not defined version (
    for /f "tokens=3 delims= " %%c in ("%%b") do set "version=%%~c"
)
set version=%version:"=%
echo You are about to publish EDSL version '%version%' to PyPI.
set /p answer=Are you sure you want to continue? (y/n) 
if /i not "%answer%"=="y" (
    echo Publish canceled.
    goto end
)
poetry build
poetry publish
goto :end

::###############
::##@Development 🛠️  
::###############
:bump
:: Bump the version of the package
if "%2" == "" (
    echo Please specify the bump type: dev, patch, minor, or major
    goto :end
)
echo Bumping version...
python scripts\bump_version.py %2
goto :end

:docs
:: Generate documentation
call :clean-docs
if not exist .temp\docs (
    mkdir .temp\docs
)
poetry export -f requirements.txt --with dev --output .temp\docs\requirements.txt
poetry export -f requirements.txt --with dev --output docs\requirements.txt
sphinx-build -b html docs .temp\docs
goto :end

:docs-view
:: View documentation
for /f "tokens=2 delims==" %%I in ('wmic os get Caption /value') do set "OSNAME=%%I"
echo %OSNAME% | findstr /I "Windows" >NUL
if %errorlevel% == 0 (
    echo Supported operating system - docs will open automatically: %OSNAME%
    start .temp\docs\index.html
) else (
    echo Unsupported operating system - docs will not open automatically: %OSNAME%
)
goto :end

::###############
::##@Testing 🐛
::###############

:test
:: Run regular tests (no Coop tests) 
call :clean-test
pytest -xv tests --nocoop --windows
goto :end

:test-coop
:: Run Coop tests (no regular tests, requires Coop local server running)
call :clean-test
pytest -xv tests --coop --windows
goto :end

:test-coverage
:: Run regular tests and get a coverage report
call :clean-test
poetry run coverage run -m pytest -x tests --nocoop --windows --ignore=tests\stress
if %errorlevel% neq 0 (
    echo Tests failed
    exit /b %errorlevel%
)
poetry run coverage html
for /f "tokens=2 delims==" %%I in ('wmic os get Caption /value') do set "OSNAME=%%I"
echo %OSNAME% | findstr /I "Windows" >NUL
if %errorlevel% == 0 (
    echo Supported operating system - coverage report will open automatically: %OSNAME%
    start htmlcov\index.html
) else (
    echo Unsupported operating system - coverage report will not open automatically: %OSNAME%
)
goto :end

:test-data
:: Create serialization test data for the current EDSL version
python scripts/create_serialization_test_data.py
goto :end

:end
endlocal
