from __future__ import annotations

"""Utilities to interact with the Docker & GCP workflow that is currently described in the
Makefile shipped with this repository.

The :class:`ExtensionDeploymentManager` class exposes each Makefile target as a python method so
that the same actions can be invoked directly from python scripts, notebooks or simple REPL
sessions without shelling out to `make`.

The manager works at the service collection level, deploying all services in a ServicesBuilder
as a single containerized application.

Example
-------
>>> from edsl.extensions.authoring.authoring import ServicesBuilder
>>> from edsl.extensions.authoring.docker_manager import ExtensionDeploymentManager
>>> 
>>> # Create a services collection
>>> services = ServicesBuilder(
...     service_collection_name="my_services",
...     creator_ep_username="username"
... )
>>> # ... add services to the builder ...
>>> 
>>> # Create deployment manager for the entire collection
>>> mgr = ExtensionDeploymentManager.from_services_builder(
...     services_builder=services,
...     project_id="extensions-testing-462609",
...     region="us-central1",
... )
>>> mgr.build()
>>> mgr.run()
"""

import os
import shlex
import subprocess
import re
from pathlib import Path
from typing import Sequence, Optional

from .authoring import ServicesBuilder


class ExtensionDeploymentManager:
    """Python interface for the targets defined in *Makefile*.

    Parameters
    ----------
    image_name:
        Docker image tag to build / run.
    container_name:
        Name that will be assigned to the running Docker container.
    port:
        Host and container port to expose the API under.
    project_id:
        Google Cloud project id.
    region:
        GCP region for the Cloud Run service.
    service_name:
        Deployed Cloud Run service name.
    service_collection_name:
        Name of the service collection being deployed.
    """

    def __init__(
        self,
        image_name: str,
        container_name: str,
        port: int,
        project_id: str,
        region: str,
        service_name: str,
        service_collection_name: str,
    ) -> None:
        self.image_name = image_name
        self.container_name = container_name
        self.port = int(port)
        self.project_id = project_id
        self.region = region
        self.service_name = service_name
        self.service_collection_name = service_collection_name
        self.workdir = Path(os.getcwd()).resolve()

    @classmethod
    def from_services_builder(
        cls,
        services_builder: ServicesBuilder,
        project_id: str,
        region: str,
        port: int = 8080,
    ) -> ExtensionDeploymentManager:
        """Create an ExtensionDeploymentManager instance from a ServicesBuilder.

        Parameters
        ----------
        services_builder:
            The ServicesBuilder instance containing the service collection.
        project_id:
            Google Cloud project id.
        region:
            GCP region for the Cloud Run service.
        port:
            Host and container port to expose the API under. Defaults to 8080.
        """
        # Get collection name from the services builder
        service_collection_name = (
            services_builder._default_service_collection_name or "default_collection"
        )

        # Clean collection name to be valid for Docker and Cloud Run
        clean_collection_name = re.sub(
            r"[^a-zA-Z0-9_.-]", "-", service_collection_name.lower()
        )

        # Use collection name for image and service naming
        image_name = clean_collection_name
        container_name = f"{image_name}-container"
        service_name = clean_collection_name

        return cls(
            image_name=image_name,
            container_name=container_name,
            port=port,
            project_id=project_id,
            region=region,
            service_name=service_name,
            service_collection_name=service_collection_name,
        )

    # ---------------------------------------------------------------------
    # Public API – mirrors Make targets
    # ---------------------------------------------------------------------

    def build(self) -> None:
        """Build the Docker image."""
        self._run(
            f"docker build --no-cache -t {self.image_name} {shlex.quote(str(self.workdir))}"
        )

    def run(self) -> None:
        """Run the container in detached mode on *self.port*.

        Idempotent – will stop & remove a previously running container with the
        same *container_name* before creating a new one.
        """
        self.stop(ignore_errors=True)
        self._run(
            "docker run -d --name {cn} -p {p}:{p} {img}".format(
                cn=self.container_name, p=self.port, img=self.image_name
            )
        )
        print(f"API running at http://localhost:{self.port}")

    def stop(self, *, ignore_errors: bool = False) -> None:
        """Stop & remove the running container (if any)."""
        self._run(f"docker stop {self.container_name}", check=not ignore_errors)
        self._run(f"docker rm {self.container_name}", check=not ignore_errors)

    def clean(self) -> None:
        """Stop container and remove image."""
        self.stop(ignore_errors=True)
        self._run(f"docker rmi {self.image_name}", check=False)

    def logs(self) -> None:
        """Tail logs of the running container."""
        self._run(f"docker logs -f {self.container_name}")

    def shell(self) -> None:
        """Open an interactive shell inside the running container."""
        self._run(f"docker exec -it {self.container_name} /bin/bash")

    def restart(self) -> None:
        """Restart the container (stop → run)."""
        self.stop(ignore_errors=True)
        self.run()

    def dev(self) -> None:
        """Run the container with source mounted for hot-reloading."""
        self.stop(ignore_errors=True)
        self._run(
            "docker run --rm --name {cn} -p {p}:{p} -v {src}:/app {img}".format(
                cn=self.container_name,
                p=self.port,
                src=shlex.quote(str(self.workdir)),
                img=self.image_name,
            )
        )

    def run_temp(self) -> None:
        """Run container without persistent name (auto-removes on stop)."""
        self._run(f"docker run --rm -d -p {self.port}:{self.port} {self.image_name}")
        print(f"API running at http://localhost:{self.port} (temporary container)")

    # ---- Google Cloud helpers ------------------------------------------------

    def gcp_build(self) -> None:
        """Build & push image to Google Container Registry using *gcloud*.*"""
        self._run(
            "gcloud builds submit --tag gcr.io/{proj}/{svc}:$(git rev-parse --short HEAD) --project {proj}".format(
                proj=self.project_id, svc=self.service_name
            ),
            shell=True,
        )

    def gcp_deploy(self) -> None:
        """Deploy the current image tag to Cloud Run."""
        cmd = (
            "gcloud run deploy {svc} --image gcr.io/{proj}/{svc}:$(git rev-parse --short HEAD) "
            "--platform managed --region {region} --allow-unauthenticated --memory 2Gi "
            "--cpu 2 --timeout 3600 --concurrency 1000 --project {proj}"
        ).format(svc=self.service_name, proj=self.project_id, region=self.region)
        self._run(cmd, shell=True)

    def gcp_logs(self, *, limit: int = 50) -> None:
        """Show Cloud Run logs for the currently deployed revision(s)."""
        query = (
            "resource.type=cloud_run_revision AND resource.labels.service_name={svc} "
            "AND resource.labels.revision_name~'{svc}-'"
        ).format(svc=self.service_name)
        self._run(
            'gcloud logging read "{q}" --limit {limit} --format "table(timestamp,textPayload)" --project {proj} --freshness=1d'.format(
                q=query, limit=limit, proj=self.project_id
            ),
            shell=True,
        )

    def gcp_logs_current(self, *, limit: int = 50) -> None:
        """View logs from the *latest* ready revision only."""
        cmd_get_revision = (
            'gcloud run services describe {svc} --region={region} --project={proj} --format="value(status.latestReadyRevisionName)"'
        ).format(svc=self.service_name, region=self.region, proj=self.project_id)
        # Capture result
        revision = (
            subprocess.check_output(cmd_get_revision, shell=True, text=True).strip()
            or ""
        )
        if not revision:
            raise RuntimeError("Could not determine latest ready revision via gcloud.")
        print(f"Getting logs for current revision: {revision}")
        self._run(
            'gcloud logging read "resource.type=cloud_run_revision AND resource.labels.revision_name={rev}" --limit {limit} --format "table(timestamp,textPayload)" --project {proj} --freshness=1d'.format(
                rev=revision, limit=limit, proj=self.project_id
            ),
            shell=True,
        )

    def gcp_endpoint(self) -> None:
        """Print the public endpoint URL of the Cloud Run service."""
        self._run(
            'gcloud run services describe {svc} --region={region} --project={proj} --format="value(status.url)"'.format(
                svc=self.service_name, region=self.region, proj=self.project_id
            ),
            shell=True,
        )

    # ------------------------------------------------------------------ utils

    def _run(
        self,
        command: str | Sequence[str],
        *,
        check: bool = True,
        shell: bool = False,
    ) -> None:
        """Wrapper around :pyfunc:`subprocess.run` that streams output live."""
        print(f"$ {command}")
        subprocess.run(
            command if shell else shlex.split(command), check=check, shell=shell
        )

    # ------------------------------------------------------------------ dunder

    def __repr__(self) -> str:  # pragma: no cover – repr only used for debugging.
        params = (
            f"image_name={self.image_name!r}, container_name={self.container_name!r}, "
            f"port={self.port!r}, project_id={self.project_id!r}, region={self.region!r}, "
            f"service_name={self.service_name!r}, workdir={str(self.workdir)!r}, "
            f"service_collection_name={self.service_collection_name!r}"
        )
        return f"{self.__class__.__name__}({params})"


if __name__ == "__main__":
    # Example usage with ServicesBuilder
    from .authoring import ServicesBuilder

    # Create a sample services builder
    services = ServicesBuilder(
        service_collection_name="example_collection", creator_ep_username="test_user"
    )

    # Create deployment manager from services builder
    mgr = ExtensionDeploymentManager.from_services_builder(
        services_builder=services,
        project_id="extensions-testing-462609",
        region="us-central1",
    )
    print(f"Created deployment manager for collection: {mgr.service_collection_name}")
    print(f"Image name: {mgr.image_name}")
    print(f"Service name: {mgr.service_name}")

    # Example commands (commented out to avoid actual deployment)
    # mgr.build()
    # mgr.run()
