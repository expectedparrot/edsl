from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from typing import Optional, Sequence

__all__ = ["generate_dockerfile"]


def _cmd_list_to_docker_json(cmd: Sequence[str]) -> str:
    """Return a JSON array string (Dockerfile exec form) from *cmd* list."""
    import json

    # Docker expects double-quoted JSON; ensure all values are str
    return json.dumps(list(map(str, cmd)))


def generate_dockerfile(
    *,
    python_version: str = "3.11",
    port: int = 8080,
    requirements_path: str | Path = "requirements.txt",
    workdir: str | Path = "/app",
    entrypoint: str | Path = "app.py",
    run_command: Optional[Sequence[str]] = None,
    additional_packages: Optional[Sequence[str]] = None,
    debian_release: str = "slim-bookworm",
    pip_install_commands: Optional[Sequence[str]] = None,
) -> str:
    """Return a complete Dockerfile as a string.

    Parameters
    ----------
    python_version
        Major.minor version tag for the base image (e.g., "3.11").
    port
        Port that the container will listen on (Google Cloud Run expects the
        service to bind to the value in the ``PORT`` env-var which it sets at
        runtime).  The value is exposed via ``EXPOSE`` and exported via ``ENV
        PORT``.  Defaults to **8080**.
    requirements_path
        Path to *requirements.txt* inside the build context.
    workdir
        Directory inside the image where the application will live – copied as
        ``COPY . <workdir>`` and set by ``WORKDIR``.
    entrypoint
        The main Python module/file.  Only used when *run_command* is *None*.
    run_command
        Optional explicit command to run (exec-form).  Example:
        ``["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "$PORT"]``.
        If *None* (default) the command will be ``["python", "<entrypoint>"]``.
    additional_packages
        A sequence of Debian packages to install via ``apt-get`` (e.g.,
        build-essentials).  If *None* (default) no extra packages are installed.
    debian_release
        The Debian release tag appended to the base image (default:
        "slim-bookworm").  Change to "slim-bullseye" etc. as desired.
    pip_install_commands
        Optional sequence of commands to run for pip installation. If provided,
        these commands will be used instead of the default pip install command.
    """

    base_image = f"python:{python_version}-{debian_release}"
    workdir = Path(workdir)
    entrypoint = Path(entrypoint)
    requirements_path = Path(requirements_path)

    if run_command is None:
        run_command = ["python", str(entrypoint)]

    run_cmd_json = _cmd_list_to_docker_json(run_command)

    # Build the pip install commands
    if pip_install_commands is None:
        pip_install_commands = [
            "pip install --no-cache-dir --upgrade pip",
            f"if [ -f {requirements_path} ]; then pip install --no-cache-dir -r {requirements_path}; fi"
        ]
    pip_install_str = " && \\\n        ".join(pip_install_commands)

    # Build the Dockerfile content
    dockerfile = dedent(
        f"""
        # syntax=docker/dockerfile:1
        FROM {base_image} AS base

        # Prevent Python from writing *.pyc files and buffering stdout/stderr
        ENV PYTHONDONTWRITEBYTECODE=1
        ENV PYTHONUNBUFFERED=1
        ENV PORT={port}

        # Install system packages (optional)
        RUN apt-get update --yes && \
            apt-get install --no-install-recommends --yes {' '.join(additional_packages) if additional_packages else ''} && \
            rm -rf /var/lib/apt/lists/*

        # App layer
        WORKDIR {workdir}
        COPY . {workdir}

        # Install Python dependencies
        RUN {pip_install_str}

        EXPOSE {port}

        # Runtime stage (same as build to keep things simple)
        CMD {run_cmd_json}
        """
    ).strip() + "\n"

    # Clean up potential double spaces introduced when no additional packages
    dockerfile = '\n'.join(line.rstrip() for line in dockerfile.split('\n'))

    return dockerfile 