"""
Docker Manager для керування Zero-контейнерами для клієнтів.

Цей модуль дозволяє динамічно створювати, запускати та зупиняти окремі
Docker-контейнери Zero для кожного клієнта.
"""
import logging
from typing import Optional, Dict, Any, cast
import docker
from docker.models.containers import Container
from docker.errors import DockerException, NotFound, APIError, ImageNotFound
from django.conf import settings

logger = logging.getLogger(__name__)


class ZeroDockerManager:
    """Manages per-client Zero Docker containers."""

    def __init__(self):
        try:
            self.client = docker.from_env()
        except DockerException as e:
            logger.error(f"Failed to connect to Docker daemon: {e}")
            raise

    def start_zero_container(
        self,
        container_name: str,
        env: Dict[str, str],
        host_port: Optional[int] = None,
        image: str = "",
        repo_url: str = "https://github.com/Mail-0/Zero",
        repo_branch: str = "staging",
        network: str = "backend_default"
    ) -> Dict[str, Any]:
        """
        Start a Zero container for a client.

        Args:
            container_name: Unique container name
            env: Environment variables dict
            host_port: Host port to map (if None, auto-assign)
            image: Prebuilt image tag (if empty, build from repo)
            repo_url: Git repository URL
            repo_branch: Git branch to use
            network: Docker network to attach to

        Returns:
            Dict with 'container_id', 'host_port', 'status'
        """
        try:
            # Check if container already exists
            existing = self._get_container(container_name)
            if existing:
                if existing.status == 'running':
                    logger.info(f"Container {container_name} is already running")
                    return self._extract_container_info(existing)
                else:
                    logger.info(f"Removing stopped container {container_name}")
                    existing.remove(force=True)

            # Determine image to use
            if not image:
                image = self._build_or_pull_zero_image(repo_url, repo_branch)
            else:
                # Check if image exists locally first
                try:
                    self.client.images.get(image)
                    logger.info(f"Using local image: {image}")
                except ImageNotFound:
                    # Pull prebuilt image if not found locally
                    logger.info(f"Pulling prebuilt Zero image: {image}")
                    self.client.images.pull(image)

            # Prepare port mapping
            ports = {}
            if host_port:
                ports['3000/tcp'] = host_port
            else:
                # Let Docker auto-assign a port
                ports['3000/tcp'] = None

            # Run container
            logger.info(f"Starting Zero container: {container_name}")
            # Type ignore needed due to docker-py's strict type stubs not matching runtime behavior
            container = self.client.containers.run(  # type: ignore
                image=image,
                name=container_name,
                environment=env,
                ports=ports,
                network=network,
                detach=True,
                restart_policy={"Name": "unless-stopped"},  # type: ignore[arg-type]
                labels={
                    "managed_by": "concierge",
                    "service": "zero",
                }
            )

            result = self._extract_container_info(container)
            logger.info(f"Zero container {container_name} started successfully: {result}")
            return result

        except APIError as e:
            logger.error(f"Docker API error starting {container_name}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error starting {container_name}: {e}")
            raise

    def stop_zero_container(self, container_name: str, remove: bool = False) -> Dict[str, str]:
        """
        Stop a Zero container.

        Args:
            container_name: Container name to stop
            remove: If True, remove the container after stopping

        Returns:
            Dict with 'status' and 'message'
        """
        try:
            container = self._get_container(container_name)
            if not container:
                return {"status": "not_found", "message": f"Container {container_name} not found"}

            if container.status == 'running':
                logger.info(f"Stopping container {container_name}")
                container.stop(timeout=10)

            if remove:
                logger.info(f"Removing container {container_name}")
                container.remove()

            return {"status": "stopped", "message": f"Container {container_name} stopped successfully"}

        except NotFound:
            return {"status": "not_found", "message": f"Container {container_name} not found"}
        except APIError as e:
            logger.error(f"Docker API error stopping {container_name}: {e}")
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error stopping {container_name}: {e}")
            return {"status": "error", "message": str(e)}

    def get_container_status(self, container_name: str) -> Dict[str, Any]:
        """
        Get the status of a Zero container.

        Returns:
            Dict with 'exists', 'status', 'health', etc.
        """
        try:
            container = self._get_container(container_name)
            if not container:
                return {"exists": False, "status": "not_found"}

            container.reload()
            return {
                "exists": True,
                "status": container.status,
                "id": container.id,
                "ports": container.ports,
                "health": self._get_health_status(container),
            }

        except Exception as e:
            logger.error(f"Error checking status for {container_name}: {e}")
            return {"exists": False, "status": "error", "error": str(e)}

    def restart_zero_container(self, container_name: str) -> Dict[str, str]:
        """Restart a Zero container."""
        try:
            container = self._get_container(container_name)
            if not container:
                return {"status": "not_found", "message": f"Container {container_name} not found"}

            logger.info(f"Restarting container {container_name}")
            container.restart(timeout=10)
            return {"status": "restarted", "message": f"Container {container_name} restarted successfully"}

        except Exception as e:
            logger.error(f"Error restarting {container_name}: {e}")
            return {"status": "error", "message": str(e)}

    def _get_container(self, name: str) -> Optional[Container]:
        """Get container by name, return None if not found."""
        try:
            return self.client.containers.get(name)
        except NotFound:
            return None

    def _extract_container_info(self, container: Container) -> Dict[str, Any]:
        """Extract useful info from a container object."""
        container.reload()
        
        # Extract host port
        host_port = None
        if container.ports and '3000/tcp' in container.ports:
            bindings = container.ports['3000/tcp']
            if bindings and len(bindings) > 0:
                host_port = int(bindings[0]['HostPort'])

        return {
            "container_id": container.id,
            "container_name": container.name,
            "status": container.status,
            "host_port": host_port,
        }

    def _get_health_status(self, container: Container) -> str:
        """Extract health status from container."""
        try:
            health = container.attrs.get('State', {}).get('Health', {})
            return health.get('Status', 'unknown')
        except Exception:
            return 'unknown'

    def _build_or_pull_zero_image(self, repo_url: str, branch: str) -> str:
        """
        Build or pull Zero image. For now, we use a simple approach:
        - Try to pull 'mail0/zero:staging' or similar if available
        - Otherwise, return a placeholder for manual build

        In production, you might want to:
        1. Clone the repo
        2. Build the image with docker.build()
        3. Tag it appropriately

        For simplicity, we'll assume a prebuilt image exists or admin provides it.
        """
        default_image = "ghcr.io/mail-0/zero:staging"
        try:
            logger.info(f"Attempting to pull default Zero image: {default_image}")
            self.client.images.pull(default_image)
            return default_image
        except Exception as e:
            logger.warning(f"Could not pull {default_image}: {e}")
            logger.info("Falling back to manual image specification required")
            # In a real scenario, you'd build from source here
            # For now, raise an error requiring admin to specify image
            raise ValueError(
                "No prebuilt Zero image available. Please specify an 'image' in ClientZeroConfig."
            )

