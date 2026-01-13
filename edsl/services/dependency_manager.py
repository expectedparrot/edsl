"""
DependencyManager: Handles checking and prompted installation of service dependencies.

When a service requires packages that aren't installed, prompts the user to install
them rather than silently installing or failing with cryptic errors.

Environment Variables:
    EDSL_AUTO_INSTALL_DEPS: If set to "1", "true", or "yes", automatically install
                           missing dependencies without prompting.
    EDSL_INSTALL_DEPS: If set to "0", "false", or "no", never install dependencies
                       (useful for CI/production).

Example:
    >>> from edsl.services.dependency_manager import DependencyManager
    >>> 
    >>> # Check if deps are available, prompt if not
    >>> DependencyManager.ensure_available("firecrawl")
    # If firecrawl-py not installed:
    # "The 'firecrawl' service requires: firecrawl-py
    #  Install now? [y/N]: "
    
    >>> # Auto-install without prompting
    >>> import os
    >>> os.environ["EDSL_AUTO_INSTALL_DEPS"] = "1"
    >>> DependencyManager.ensure_available("firecrawl")  # Installs automatically
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from typing import Dict, List, Optional, Set


def _get_install_mode() -> str:
    """Get the installation mode from environment.

    Returns:
        "auto": Auto-install without prompting
        "never": Never install (raise error)
        "prompt": Prompt user (default)
    """
    auto = os.environ.get("EDSL_AUTO_INSTALL_DEPS", "").lower()
    if auto in ("1", "true", "yes"):
        return "auto"

    never = os.environ.get("EDSL_INSTALL_DEPS", "").lower()
    if never in ("0", "false", "no"):
        return "never"

    return "prompt"


# Cache of packages we've confirmed are installed (avoid repeated checks)
_installed_cache: Set[str] = set()


def _package_to_import_name(package: str) -> str:
    """Convert pip package name to Python import name.

    Examples:
        firecrawl-py -> firecrawl
        google-genai -> google.genai (but we check 'google')
        scikit-learn -> sklearn
    """
    # Special cases
    special_mappings = {
        "firecrawl-py": "firecrawl",
        "scikit-learn": "sklearn",
        "google-genai": "google.genai",
        "azure-ai-inference": "azure.ai.inference",
        "python-docx": "docx",
        "python-pptx": "pptx",
        "pypdf2": "PyPDF2",
        "exa-py": "exa_py",
        "fal-client": "fal_client",
        "youtube-transcript-api": "youtube_transcript_api",
        "wikipedia-api": "wikipediaapi",
        "sentence-transformers": "sentence_transformers",
        "vl-convert-python": "vl_convert",
    }

    # Strip version specifiers
    pkg_name = package.split(">=")[0].split("==")[0].split("<")[0].split("[")[0].strip()

    if pkg_name in special_mappings:
        return special_mappings[pkg_name]

    # Default: replace hyphens with underscores
    return pkg_name.replace("-", "_")


def _is_package_installed(package: str) -> bool:
    """Check if a package is installed."""
    import_name = _package_to_import_name(package)

    # Check cache first
    if import_name in _installed_cache:
        return True

    # For dotted imports (e.g., google.genai), check the root
    root_module = import_name.split(".")[0]

    if importlib.util.find_spec(root_module) is not None:
        _installed_cache.add(import_name)
        return True

    return False


def _prompt_user(service_name: str, missing_packages: List[str]) -> bool:
    """Prompt user to install missing packages.

    Returns True if user approves installation.
    """
    packages_str = " ".join(missing_packages)

    print(f"\n╭─ Missing Dependencies ─────────────────────────────────────╮")
    print(f"│ The '{service_name}' service requires packages that aren't installed:")
    print(f"│")
    for pkg in missing_packages:
        print(f"│   • {pkg}")
    print(f"│")
    print(f"│ Install command: pip install {packages_str}")
    print(f"╰────────────────────────────────────────────────────────────╯")

    try:
        response = input(f"\nInstall now? [y/N]: ").strip().lower()
        return response in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        print()  # Newline after interrupt
        return False


def _install_packages(packages: List[str], quiet: bool = False) -> bool:
    """Install packages using uv (fast) or pip (fallback).

    Returns True if installation succeeded.
    """
    if not packages:
        return True

    # Try uv first (10-100x faster than pip)
    try:
        cmd = [sys.executable, "-m", "uv", "pip", "install"]
        if quiet:
            cmd.append("--quiet")
        cmd.extend(packages)

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            # Clear cache for installed packages
            for pkg in packages:
                import_name = _package_to_import_name(pkg)
                _installed_cache.discard(import_name)
            return True
    except FileNotFoundError:
        pass  # uv not available

    # Fallback to pip
    cmd = [sys.executable, "-m", "pip", "install"]
    if quiet:
        cmd.append("--quiet")
    cmd.extend(packages)

    print(f"Installing: {' '.join(packages)}...")
    result = subprocess.run(cmd, capture_output=not quiet, text=True)

    if result.returncode == 0:
        for pkg in packages:
            import_name = _package_to_import_name(pkg)
            _installed_cache.discard(import_name)
        print("✓ Installation complete")
        return True

    print(f"✗ Installation failed")
    if result.stderr:
        print(result.stderr)
    return False


class DependencyManager:
    """
    Manages service dependencies with user-prompted installation.

    Usage:
        # In service accessor, before dispatch:
        DependencyManager.ensure_available("firecrawl")

        # Check without prompting:
        if DependencyManager.check_available("firecrawl"):
            ...
    """

    # Service -> list of required packages
    # This will be populated from ServiceRegistry metadata
    _service_dependencies: Dict[str, List[str]] = {}

    @classmethod
    def register_dependencies(cls, service_name: str, packages: List[str]) -> None:
        """Register dependencies for a service.

        Called automatically when services are registered with dependencies.
        """
        cls._service_dependencies[service_name] = packages

    @classmethod
    def get_dependencies(cls, service_name: str) -> List[str]:
        """Get the list of dependencies for a service."""
        return cls._service_dependencies.get(service_name, [])

    @classmethod
    def get_missing(cls, service_name: str) -> List[str]:
        """Get list of missing packages for a service."""
        deps = cls.get_dependencies(service_name)
        return [pkg for pkg in deps if not _is_package_installed(pkg)]

    @classmethod
    def check_available(cls, service_name: str) -> bool:
        """Check if all dependencies for a service are installed.

        Does not prompt or install - just checks.
        """
        return len(cls.get_missing(service_name)) == 0

    @classmethod
    def ensure_available(
        cls,
        service_name: str,
        *,
        auto_install: Optional[bool] = None,
        quiet: bool = False,
    ) -> None:
        """Ensure all dependencies for a service are available.

        If dependencies are missing:
        - If auto_install=True or EDSL_AUTO_INSTALL_DEPS=1: Install without prompting
        - If EDSL_INSTALL_DEPS=0: Raise error immediately (no install)
        - Otherwise: Prompt user to approve installation

        Args:
            service_name: Name of the service
            auto_install: If True, install without prompting. If None, check env vars.
            quiet: If True, suppress installation output

        Raises:
            ImportError: If dependencies are missing and user declines installation
        """
        missing = cls.get_missing(service_name)

        if not missing:
            return  # All deps available

        # Determine install mode
        mode = _get_install_mode()

        # Override with explicit parameter if provided
        if auto_install is True:
            mode = "auto"
        elif auto_install is False:
            mode = "prompt"

        # Handle never mode
        if mode == "never":
            packages_str = " ".join(missing)
            raise ImportError(
                f"The '{service_name}' service requires: {', '.join(missing)}\n"
                f"Install with: pip install {packages_str}\n"
                f"(Auto-install disabled via EDSL_INSTALL_DEPS=0)"
            )

        # Check if we should auto-install or prompt
        if mode == "auto":
            approved = True
            if not quiet:
                print(
                    f"📦 Auto-installing dependencies for '{service_name}': {', '.join(missing)}"
                )
        else:
            approved = _prompt_user(service_name, missing)

        if approved:
            success = _install_packages(missing, quiet=quiet)
            if not success:
                raise ImportError(
                    f"Failed to install dependencies for '{service_name}': {missing}\n"
                    f"Try manually: pip install {' '.join(missing)}"
                )
        else:
            # User declined - raise helpful error
            packages_str = " ".join(missing)
            raise ImportError(
                f"The '{service_name}' service requires: {', '.join(missing)}\n"
                f"Install with: pip install {packages_str}"
            )

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the installed package cache.

        Useful for testing or after manual package installation.
        """
        global _installed_cache
        _installed_cache.clear()


# Convenience function for use in service accessors
def ensure_dependencies(service_name: str, **kwargs) -> None:
    """Ensure dependencies are available for a service.

    Shorthand for DependencyManager.ensure_available().
    """
    DependencyManager.ensure_available(service_name, **kwargs)
