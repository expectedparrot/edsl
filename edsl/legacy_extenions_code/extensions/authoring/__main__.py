"""Run ``python -m edsl.extensions`` to validate and manage extension repositories.

This CLI tool provides commands to work with EDSL extension service implementations:

    validate    Validate an extension repository structure
    local-run   Run an extension service locally without Docker
    run         Run an extension service locally with Docker
    gcp-build   Build a Docker image and push to Google Container Registry
    gcp-deploy  Deploy an extension to Google Cloud Run

You can run ``python -m edsl.extensions --help`` to see all available commands.
"""

from __future__ import annotations

import sys
import json
import subprocess
from pathlib import Path
import tarfile
import tempfile
import click
import importlib.util
from typing import Union, Optional
from .dockerfile_creator import generate_dockerfile
from .docker_manager import ExtensionDeploymentManager
from .authoring import ServicesBuilder  # type: ignore


REQUIRED_FILES = [
    "app.py",
    "requirements.txt",
]

REQUIRED_DIRS = [
    "deps",
]


def validate_extension_repo(target_path: Path) -> list[str]:
    """Return a list of missing required paths (files or directories)."""

    missing: list[str] = []

    for fname in REQUIRED_FILES:
        if not (target_path / fname).is_file():
            missing.append(fname)

    for dname in REQUIRED_DIRS:
        if not (target_path / dname).is_dir():
            missing.append(f"{dname}/")

    return missing


def load_services_builder(path: Union[str, Path] = ".") -> ServicesBuilder:
    """Load a ServicesBuilder from app.py in the given directory.

    Parameters
    ----------
    path
        Directory containing ``app.py``. Defaults to the current working directory.

    Returns
    -------
    ServicesBuilder
        The services builder instance from the app.py file.

    Raises
    ------
    FileNotFoundError
        If app.py cannot be found.
    AttributeError
        If app.py doesn't contain a 'services' variable.
    """
    p = Path(path).expanduser().resolve()

    if p.is_dir():
        app_file = p / "app.py"
    else:
        app_file = p

    if not app_file.is_file():
        raise FileNotFoundError(f"app.py not found at: {app_file}")

    print(f"🔍 DEBUG: Loading app.py from: {app_file}")
    print(f"🔍 DEBUG: File exists: {app_file.exists()}")
    print(f"🔍 DEBUG: File size: {app_file.stat().st_size} bytes")

    # Load the app.py module dynamically
    spec = importlib.util.spec_from_file_location("app", app_file)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module from {app_file}")

    app_module = importlib.util.module_from_spec(spec)

    # Add the directory to sys.path temporarily so imports work
    original_path = sys.path[:]
    sys.path.insert(0, str(app_file.parent))

    try:
        print(f"🔍 DEBUG: Attempting to execute module from {app_file}")

        # First, let's try to compile the file to check for syntax errors
        try:
            with open(app_file, "r", encoding="utf-8") as f:
                source_code = f.read()
            compile(source_code, str(app_file), "exec")
            print("🔍 DEBUG: File compiles successfully")
        except (SyntaxError, IndentationError) as compile_err:
            print(f"❌ COMPILE ERROR in {app_file}:")
            print(f"   Error: {compile_err}")
            print(f"   Line: {getattr(compile_err, 'lineno', 'unknown')}")
            print(f"   Text: {getattr(compile_err, 'text', 'unknown')}")
            raise compile_err

        spec.loader.exec_module(app_module)
        print("🔍 DEBUG: Successfully executed module")
    except IndentationError as e:
        print(f"❌ INDENTATION ERROR in {app_file}:")
        print(f"   Error: {e}")
        print(f"   Line: {getattr(e, 'lineno', 'unknown')}")
        print(f"   Text: {getattr(e, 'text', 'unknown')}")
        print(f"   Position: {getattr(e, 'offset', 'unknown')}")

        # Try to show the problematic lines
        try:
            with open(app_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            if hasattr(e, "lineno") and e.lineno:
                lineno = e.lineno
                print(f"\n📝 Context around line {lineno}:")
                start = max(0, lineno - 3)
                end = min(len(lines), lineno + 3)

                for i in range(start, end):
                    line_num = i + 1
                    line_content = lines[i].rstrip()
                    marker = " --> " if line_num == lineno else "     "
                    print(f"{marker}{line_num:3d}: {line_content}")

                    # Show whitespace for the problematic line
                    if line_num == lineno:
                        visible_whitespace = line_content.replace("\t", "→   ").replace(
                            " ", "·"
                        )
                        print(f"     Whitespace: {visible_whitespace}")
        except Exception as file_err:
            print(f"   Could not read file for context: {file_err}")

        raise IndentationError(f"IndentationError in {app_file}: {e}") from e
    except ImportError as e:
        print(f"❌ IMPORT ERROR when loading {app_file}:")
        print(f"   Error: {e}")
        print(
            "   This usually means one of your imports is missing or has syntax errors"
        )
        print(f"   Check your imports in {app_file}")

        # Try to identify which import is failing
        try:
            with open(app_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            print(f"\n📝 Imports in {app_file}:")
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith(
                    ("import ", "from ")
                ) and not stripped.startswith("#"):
                    print(f"   {i:3d}: {stripped}")
        except Exception as file_err:
            print(f"   Could not read file for analysis: {file_err}")

        raise ImportError(f"ImportError when loading {app_file}: {e}") from e
    except SyntaxError as e:
        print(f"❌ SYNTAX ERROR in {app_file}:")
        print(f"   Error: {e}")
        print(f"   Line: {getattr(e, 'lineno', 'unknown')}")
        print(f"   Text: {getattr(e, 'text', 'unknown')}")
        print(f"   Position: {getattr(e, 'offset', 'unknown')}")

        # Try to show the problematic lines
        try:
            with open(app_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            if hasattr(e, "lineno") and e.lineno:
                lineno = e.lineno
                print(f"\n📝 Context around line {lineno}:")
                start = max(0, lineno - 3)
                end = min(len(lines), lineno + 3)

                for i in range(start, end):
                    line_num = i + 1
                    line_content = lines[i].rstrip()
                    marker = " --> " if line_num == lineno else "     "
                    print(f"{marker}{line_num:3d}: {line_content}")
        except Exception as file_err:
            print(f"   Could not read file for context: {file_err}")

        raise SyntaxError(f"SyntaxError in {app_file}: {e}") from e
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR loading {app_file}:")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Error: {e}")
        raise RuntimeError(f"Failed to load {app_file}: {e}") from e
    finally:
        sys.path[:] = original_path

    # Extract the services builder
    if not hasattr(app_module, "services"):
        print(f"🔍 DEBUG: Available attributes in app module: {dir(app_module)}")
        raise AttributeError(
            "app.py does not contain a 'services' variable of type ServicesBuilder"
        )

    services = app_module.services
    if not isinstance(services, ServicesBuilder):
        print(f"🔍 DEBUG: 'services' variable type: {type(services)}")
        raise TypeError(
            f"'services' variable in app.py is not a ServicesBuilder instance, got {type(services)}"
        )

    print(
        f"🔍 DEBUG: Successfully loaded ServicesBuilder with {len(services)} services"
    )
    return services


@click.group()
def cli():
    """EDSL Extensions management CLI tool.

    This tool helps validate and manage EDSL extension repositories.
    """
    pass


@cli.command()
@click.argument(
    "path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=".",
)
def validate(path: Path):
    """Validate an extension repository structure.

    PATH is the directory to validate (defaults to current directory).
    """
    target = path.expanduser().resolve()

    if not target.exists() or not target.is_dir():
        click.echo(
            click.style("❌  Path does not exist or is not a directory: ", fg="red")
            + str(target)
        )
        sys.exit(2)

    missing_paths = validate_extension_repo(target)

    if missing_paths:
        click.echo(
            click.style("❌  Extension repository is missing required paths:", fg="red")
        )
        for p in missing_paths:
            click.echo(f"   - {p}")
        sys.exit(1)

    click.echo(
        click.style("✅  Extension repository structure looks good.", fg="green")
    )

    # ------------------------------------------------------------------
    #  Load and parse config.py to ensure it is valid
    # ------------------------------------------------------------------

    # try:
    #     _sd = load_service_definition(target)
    #     click.echo(click.style("📝  Loaded service definition: ", fg='green') +
    #               f"name='{_sd.name}', endpoint='{_sd.endpoint}'")
    # except Exception as exc:
    #     click.echo(click.style("❌  Failed to parse config.py: ", fg='red') + str(exc))
    #     sys.exit(3)

    # ------------------------------------------------------------------
    #  Package required components into a temporary .tar.gz archive
    # ------------------------------------------------------------------

    archive_path = create_archive(target)
    click.echo(click.style("📦  Created archive: ", fg="green") + str(archive_path))

    # ------------------------------------------------------------------
    #  Create or update requirements.txt with necessary dependencies
    # ------------------------------------------------------------------

    requirements_path = target / "requirements.txt"
    required_packages = [
        "fastapi>=0.100.0",
        "uvicorn>=0.22.0",
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
        "requests>=2.25.0",
    ]

    # If requirements.txt exists, read existing requirements
    existing_requirements = []
    if requirements_path.exists():
        existing_requirements = requirements_path.read_text().splitlines()
        # Filter out empty lines and comments
        existing_requirements = [
            r for r in existing_requirements if r.strip() and not r.startswith("#")
        ]

    # Add new required packages if they're not already present (checking package names without versions)
    existing_package_names = {
        r.split("==")[0].split(">=")[0].split("<=")[0].strip()
        for r in existing_requirements
    }
    new_requirements = existing_requirements.copy()

    for req in required_packages:
        package_name = req.split(">=")[0].strip()
        if package_name not in existing_package_names:
            new_requirements.append(req)

    # Write the updated requirements
    requirements_path.write_text("\n".join(sorted(new_requirements)) + "\n")
    click.echo(
        click.style("📝  Updated ", fg="green")
        + str(requirements_path)
        + " with FastAPI dependencies"
    )

    # ------------------------------------------------------------------
    #  Generate and write Dockerfile with special handling for requirements
    # ------------------------------------------------------------------

    # Create a custom run command that transforms editable installs
    docker_install_cmd = [
        "pip install --no-cache-dir --upgrade pip",
        # Convert any -e ./deps/* to regular installs
        "sed -i 's/-e \\.\\///' requirements.txt",
        # Force git to not use cache and get fresh clone
        "pip install --no-cache-dir --force-reinstall -r requirements.txt",
    ]

    dockerfile_content = generate_dockerfile(
        python_version="3.11",  # Latest stable Python version
        port=8080,  # Standard port for Cloud Run
        requirements_path="requirements.txt",
        workdir="/app",
        entrypoint="app.py",
        run_command=["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"],
        additional_packages=[
            "build-essential",
            "git",
        ],  # Common build dependencies + git for pip requirements
        pip_install_commands=docker_install_cmd,  # Custom pip install sequence
    )

    dockerfile_path = target / "Dockerfile"
    dockerfile_path.write_text(dockerfile_content, encoding="utf-8")
    click.echo(
        click.style("🐳  Created Dockerfile: ", fg="green") + str(dockerfile_path)
    )


@cli.command()
@click.argument(
    "path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=".",
)
@click.option("--port", type=int, default=8080, help="Port to run the service on")
@click.option(
    "--install-deps", is_flag=True, help="Install dependencies before running"
)
def local_run(path: Path, port: int, install_deps: bool):
    """Run an extension service collection locally without Docker.

    PATH is the directory containing the extension (defaults to current directory).
    """
    target = path.expanduser().resolve()

    try:
        services_builder = load_services_builder(target)

        if install_deps:
            click.echo(click.style("\n📦  Installing dependencies...", fg="yellow"))
            subprocess.run(
                ["pip", "install", "-r", str(target / "requirements.txt")], check=True
            )

        # Add the extension directory to Python path so app.py can find its imports
        sys.path.insert(0, str(target))

        click.echo(
            click.style("\n🚀  Starting local service collection...", fg="green")
        )

        # Update the service collection with the local base URL
        base_url = f"http://localhost:{port}"
        collection_name = (
            services_builder._default_service_collection_name or "default_collection"
        )

        click.echo(f"\n📝  Service Collection: {collection_name}")
        click.echo(f"     Base URL: {base_url}")
        click.echo(f"     Number of services: {len(services_builder)}")

        # Set base URL for all services and push to gateway
        services_builder.set_base_url(base_url, push_to_gateway=True)

        click.echo(
            click.style("\n✨  Starting service collection at ", fg="green") + base_url
        )
        click.echo("   Press Ctrl+C to stop")

        # Run uvicorn
        try:
            subprocess.run(
                [
                    "uvicorn",
                    "app:app",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    str(port),
                    "--reload",  # Enable auto-reload for development
                ],
                cwd=target,
                check=True,
            )
        except KeyboardInterrupt:
            click.echo(click.style("\n\n🛑  Stopping service...", fg="yellow"))
            click.echo("Service stopped.")

    except subprocess.CalledProcessError as e:
        click.echo(click.style(f"\n❌  Command failed: {e}", fg="red"))
        sys.exit(4)
    except Exception as e:
        click.echo(click.style(f"\n❌  Failed to run service: {e}", fg="red"))
        sys.exit(4)


@cli.command()
@click.argument(
    "path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=".",
)
@click.option("--port", type=int, default=8080, help="Port to run the service on")
def run(path: Path, port: int):
    """Run an extension service collection locally with Docker.

    PATH is the directory containing the extension (defaults to current directory).
    """
    target = path.expanduser().resolve()

    try:
        services_builder = load_services_builder(target)
        mgr = ExtensionDeploymentManager.from_services_builder(
            services_builder=services_builder,
            project_id="local-dev",  # Placeholder for local development
            region="local",
            port=port,
        )

        click.echo(click.style("\n🔨  Building Docker image...", fg="yellow"))
        mgr.build()

        click.echo(
            click.style("\n🚀  Starting local service collection...", fg="green")
        )
        mgr.run()

        # Update the service collection with the local base URL
        base_url = f"http://localhost:{mgr.port}"
        collection_name = (
            services_builder._default_service_collection_name or "default_collection"
        )

        click.echo(f"\n📝  Service Collection: {collection_name}")
        click.echo(f"     Base URL: {base_url}")
        click.echo(f"     Number of services: {len(services_builder)}")

        # Set base URL for all services and push to gateway
        services_builder.set_base_url(base_url, push_to_gateway=True)

        click.echo(
            click.style("\n✨  Service collection is running locally at ", fg="green")
            + base_url
        )
        click.echo("   Following logs... (Press Ctrl+C to stop)")

        # Follow the logs
        try:
            mgr.logs()
        except KeyboardInterrupt:
            click.echo(click.style("\n\n🛑  Stopping service...", fg="yellow"))
            mgr.stop()
            click.echo("Service stopped.")

    except Exception as e:
        click.echo(click.style(f"\n❌  Failed to build/run service: {e}", fg="red"))
        sys.exit(4)


def create_archive(source_dir: Path) -> Path:
    """Package mandatory extension components into a temp gzip-compressed tar.

    Only the required files and the `deps/` directory are included.  The
    resulting archive lives in the system temp directory and is safe to send
    to a remote server (e.g., with `curl --upload-file`).
    """

    tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz")
    tmpfile.close()  # We only need the filename – tarfile will reopen it.

    with tarfile.open(tmpfile.name, mode="w:gz") as tar:
        # Add required files.
        for fname in REQUIRED_FILES:
            full_path = source_dir / fname
            tar.add(full_path, arcname=fname)

        # Add required directories recursively.
        for dname in REQUIRED_DIRS:
            full_path = source_dir / dname
            tar.add(full_path, arcname=dname)

    return Path(tmpfile.name)


# ------------------------------------------------------------------
# Convenience helper: load_service_definition
# ------------------------------------------------------------------
# Although this module is primarily intended for `python -m edsl.extensions` CLI
# validation, it is also import-able.  Users often want a one-liner that returns
# the ServiceDefinition object defined by *config.py* in a given directory.  The
# function below offers that.


def load_service_definition(
    path: Union[str, Path] = "."
) -> ServicesBuilder:  # noqa: D401
    """Return a :class:`ServicesBuilder` loaded from *app.py*.

    DEPRECATED: Use load_services_builder directly instead.

    Parameters
    ----------
    path
        Directory containing ``app.py`` **or** the path to the
        app file itself. Defaults to the current working directory.

    Raises
    ------
    FileNotFoundError
        If *app.py* (or the supplied file path) cannot be found.
    ValueError
        If the app file cannot be parsed or is missing required services variable.

    Examples
    --------
    >>> # Assuming you are in an extension repo directory
    >>> services = load_service_definition()
    >>> print(len(services))
    2
    """
    import warnings

    warnings.warn(
        "load_service_definition is deprecated. Use load_services_builder instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    return load_services_builder(path)


def get_gcp_project() -> str:
    """Get the current GCP project ID."""
    try:
        result = subprocess.run(
            ["gcloud", "config", "get-value", "project"],
            capture_output=True,
            text=True,
            check=True,
        )
        project_id = result.stdout.strip()
        if not project_id:
            click.echo(
                click.style("❌ No GCP project configured. Please run:", fg="red")
            )
            click.echo("  gcloud config set project PROJECT_ID")
            sys.exit(1)
        return project_id
    except subprocess.CalledProcessError as e:
        click.echo(
            click.style("❌ Failed to get GCP project ID. Are you logged in?", fg="red")
        )
        click.echo(f"Error: {e}")
        sys.exit(1)


def ensure_gcloud_auth():
    """Ensure user is authenticated with gcloud."""
    try:
        subprocess.run(
            ["gcloud", "auth", "print-identity-token"], capture_output=True, check=True
        )
    except subprocess.CalledProcessError:
        click.echo(
            click.style("❌ Not authenticated with gcloud. Please run:", fg="red")
        )
        click.echo("  gcloud auth login")
        sys.exit(1)


@cli.command()
@click.argument(
    "path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=".",
)
@click.option(
    "--project-id", help="Google Cloud project ID (default: current gcloud project)"
)
@click.option("--region", default="us-central1", help="Google Cloud region")
@click.option(
    "--registry", default="gcr.io", help="Container registry (gcr.io or pkg.dev)"
)
def gcp_build(path: Path, project_id: Optional[str], region: str, registry: str):
    """Build and push a Docker image to Google Container Registry.

    PATH is the directory containing the extension (defaults to current directory).
    """
    ensure_gcloud_auth()

    target = path.expanduser().resolve()

    # Get and validate project ID
    if project_id:
        click.echo(f"Using provided project ID: {project_id}")
    else:
        project_id = get_gcp_project()
        click.echo(f"Using current gcloud project: {project_id}")

    if not project_id:
        click.echo(
            click.style(
                "❌ No project ID available. Please provide --project-id or set a default project:",
                fg="red",
            )
        )
        click.echo("  gcloud config set project PROJECT_ID")
        sys.exit(1)

    try:
        services_builder = load_services_builder(target)

        # Create unique image name based on service collection name
        collection_name = (
            services_builder._default_service_collection_name or "default_collection"
        )
        sanitized_name = sanitize_service_name(collection_name)
        image_name = f"{registry}/{project_id}/{sanitized_name}"

        # Validate image name format
        if "//" in image_name:
            click.echo(
                click.style("❌ Invalid image name generated. Components:", fg="red")
            )
            click.echo(f"  Registry: {registry}")
            click.echo(f"  Project ID: {project_id}")
            click.echo(f"  Collection Name: {sanitized_name}")
            sys.exit(1)

        click.echo(
            click.style(
                "\n🔨  Building Docker image for service collection...", fg="yellow"
            )
        )
        click.echo(f"Collection: {collection_name}")
        click.echo(f"Services: {len(services_builder)}")
        click.echo(f"Image: {image_name}")
        click.echo("Platform: linux/amd64 (required for Cloud Run)")

        # Build the image with platform specification
        build_result = subprocess.run(
            [
                "docker",
                "build",
                "--platform",
                "linux/amd64",  # Specify platform for Cloud Run compatibility
                "-t",
                image_name,
                str(target),
            ],
            capture_output=True,
            text=True,
        )

        if build_result.returncode != 0:
            click.echo(click.style("\n❌  Docker build failed:", fg="red"))
            click.echo(build_result.stderr)
            sys.exit(1)

        click.echo(
            click.style("\n🚀  Pushing to Google Container Registry...", fg="yellow")
        )

        # Configure Docker to use gcloud credentials
        subprocess.run(
            ["gcloud", "auth", "configure-docker", registry, "--quiet"], check=True
        )

        # Push the image
        push_result = subprocess.run(
            ["docker", "push", image_name], capture_output=True, text=True
        )

        if push_result.returncode != 0:
            click.echo(click.style("\n❌  Failed to push image:", fg="red"))
            click.echo(push_result.stderr)
            sys.exit(1)

        click.echo(
            click.style("\n✅  Successfully built and pushed image:", fg="green")
        )
        click.echo(f"    {image_name}")

        # Save the image info for deployment
        config_file = target / ".gcp-config.json"
        config = {
            "image": image_name,
            "project_id": project_id,
            "region": region,
            "service_collection_name": collection_name,
            "sanitized_service_name": sanitized_name,
        }
        config_file.write_text(json.dumps(config, indent=2))

    except subprocess.CalledProcessError as e:
        click.echo(click.style("\n❌  Command failed:", fg="red"))
        click.echo(f"    Command: {' '.join(e.cmd)}")
        if e.stderr:
            click.echo(
                f"    Error: {e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr}"
            )
        sys.exit(1)
    except Exception as e:
        click.echo(click.style("\n❌  Unexpected error:", fg="red"))
        click.echo(f"    {str(e)}")
        sys.exit(1)


def sanitize_service_name(name: str) -> str:
    """Sanitize a service name to be Cloud Run compatible.

    Cloud Run requirements:
    - Only lowercase alphanumeric characters and dashes
    - Cannot begin or end with a dash
    - Maximum length of 63 characters
    """
    # Convert to lowercase and replace invalid chars with dashes
    sanitized = "".join(c if c.isalnum() else "-" for c in name.lower())

    # Remove consecutive dashes
    while "--" in sanitized:
        sanitized = sanitized.replace("--", "-")

    # Remove leading and trailing dashes
    sanitized = sanitized.strip("-")

    # Ensure length limit
    if len(sanitized) > 63:
        sanitized = sanitized[:63].rstrip("-")

    return sanitized


@cli.command()
@click.argument(
    "path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=".",
)
@click.option(
    "--project-id", help="Google Cloud project ID (default: from build config)"
)
@click.option("--region", help="Google Cloud region (default: from build config)")
@click.option("--memory", default="512Mi", help="Memory limit (e.g. 512Mi, 1Gi)")
@click.option("--cpu", default="1", help="CPU limit (e.g. 1, 2)")
@click.option("--min-instances", default=0, help="Minimum number of instances")
@click.option("--max-instances", default=10, help="Maximum number of instances")
@click.option("--port", default=8080, help="Port the service listens on")
def gcp_deploy(
    path: Path,
    project_id: Optional[str],
    region: Optional[str],
    memory: str,
    cpu: str,
    min_instances: int,
    max_instances: int,
    port: int,
):
    """Deploy an extension service collection to Google Cloud Run.

    PATH is the directory containing the extension (defaults to current directory).
    """
    ensure_gcloud_auth()

    target = path.expanduser().resolve()
    config_file = target / ".gcp-config.json"

    if not config_file.exists():
        click.echo(
            click.style("❌ No build config found. Run gcp-build first.", fg="red")
        )
        sys.exit(1)

    try:
        config = json.loads(config_file.read_text())
        project_id = project_id or config["project_id"]
        region = region or config["region"]
        service_name = config["sanitized_service_name"]
        collection_name = config["service_collection_name"]
        image = config["image"]

        click.echo(
            click.style(
                "\n🚀  Deploying service collection to Google Cloud Run...", fg="yellow"
            )
        )
        click.echo(f"Collection: {collection_name}")
        click.echo(f"Service name: {service_name}")
        click.echo(f"Image: {image}")
        click.echo(f"Region: {region}")

        # Deploy to Cloud Run
        deploy_cmd = [
            "gcloud",
            "run",
            "deploy",
            service_name,
            "--image",
            image,
            "--project",
            project_id,
            "--region",
            region,
            "--platform",
            "managed",
            "--memory",
            memory,
            "--cpu",
            cpu,
            "--min-instances",
            str(min_instances),
            "--max-instances",
            str(max_instances),
            "--port",
            str(port),
            "--allow-unauthenticated",  # Remove if authentication is needed
            "--format",
            "json",
        ]

        result = subprocess.run(deploy_cmd, capture_output=True, text=True)

        if result.returncode != 0:
            click.echo(click.style("\n❌  Deployment failed:", fg="red"))
            if result.stderr:
                click.echo(f"    {result.stderr}")
            else:
                click.echo(f"    Command failed with exit code {result.returncode}")
            sys.exit(1)

        try:
            deploy_info = json.loads(result.stdout)
        except json.JSONDecodeError:
            click.echo(
                click.style(
                    "\n⚠️  Warning: Could not parse deployment response", fg="yellow"
                )
            )
            click.echo(
                "Deployment might have succeeded, but service URL is unavailable"
            )
            sys.exit(0)

        # Update the service collection with the Cloud Run URL
        services_builder = load_services_builder(target)
        cloud_run_url = deploy_info.get("status", {}).get("url")

        if cloud_run_url:
            click.echo(
                click.style("\n✅  Successfully deployed to Cloud Run:", fg="green")
            )
            click.echo(f"    URL: {cloud_run_url}")
            click.echo(f"    Collection: {collection_name}")
            click.echo(f"    Services: {len(services_builder)}")

            click.echo(
                click.style(
                    "\n🔄  Updating service collection endpoints...", fg="yellow"
                )
            )
            services_builder.set_base_url(cloud_run_url, push_to_gateway=True)
            click.echo(
                click.style("✅  Service collection registration updated", fg="green")
            )
        else:
            click.echo(
                click.style(
                    "\n⚠️  Deployment succeeded but couldn't get service URL",
                    fg="yellow",
                )
            )
            click.echo("Please check the Cloud Run console for the service URL")

    except subprocess.CalledProcessError as e:
        click.echo(click.style("\n❌  Command failed:", fg="red"))
        click.echo(f"    Command: {' '.join(e.cmd)}")
        if e.stderr:
            click.echo(
                f"    Error: {e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr}"
            )
        sys.exit(1)
    except Exception as e:
        click.echo(click.style("\n❌  Unexpected error:", fg="red"))
        click.echo(f"    {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    cli()
