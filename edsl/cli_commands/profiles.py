"""Expected Parrot environment profile commands for the EDSL CLI."""

from __future__ import annotations

import os
import re
from pathlib import Path

import click
from dotenv import dotenv_values

from edsl.cli_shared import EXIT_NOT_FOUND, EXIT_USAGE, error, output


START_MARKER = "# >>> EDSL_PROFILE"
END_MARKER = "# <<< EDSL_PROFILE"
ACTIVE_PROFILE_KEY = "EDSL_ACTIVE_PROFILE"
SENSITIVE_MARKERS = ("API_KEY", "AUTH_TOKEN", "SECRET", "PASSWORD", "TOKEN")
PROFILE_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def register(app: click.Group, profiles_group: click.Group) -> None:
    @app.command("check")
    @click.option("--profile", "profile_name", help="Check a named local profile without activating it.")
    @click.option("--profiles-dir", default=".edsl/profiles", show_default=True)
    @click.option("--env-file", default=".env", show_default=True)
    @click.option("--timeout", default=10.0, show_default=True, type=float)
    def check(profile_name: str | None, profiles_dir: str, env_file: str, timeout: float):
        """Check Expected Parrot URL and API key connectivity."""
        _check_connectivity(
            profile_name=profile_name,
            profiles_dir=profiles_dir,
            env_file=env_file,
            timeout=timeout,
        )

    @profiles_group.command("list")
    @click.option("--profiles-dir", default=".edsl/profiles", show_default=True)
    @click.option("--env-file", default=".env", show_default=True)
    def list_profiles(profiles_dir: str, env_file: str):
        """List available Expected Parrot profiles."""
        profile_dir = Path(profiles_dir)
        active = _active_profile(Path(env_file))
        profiles = []
        if profile_dir.exists():
            for path in sorted(profile_dir.glob("*.env")):
                name = path.stem
                profiles.append(
                    {
                        "name": name,
                        "active": name == active,
                        "path": str(path),
                        "config": _redact_config(_read_profile(path)),
                    }
                )

        output(
            {
                "active_profile": active,
                "profiles_dir": str(profile_dir),
                "profile_count": len(profiles),
                "profiles": profiles,
            }
        )

    @profiles_group.command("current")
    @click.option("--env-file", default=".env", show_default=True)
    def current_profile(env_file: str):
        """Show the active profile and current Expected Parrot file settings."""
        env_path = Path(env_file)
        values = _read_env_file(env_path)
        config = {
            key: value
            for key, value in values.items()
            if _is_profile_config_key(key) or key == ACTIVE_PROFILE_KEY
        }
        output(
            {
                "active_profile": values.get(ACTIVE_PROFILE_KEY),
                "env_file": str(env_path),
                "env_file_exists": env_path.exists(),
                "config": _redact_config(config),
            }
        )

    @profiles_group.command("show")
    @click.argument("name")
    @click.option("--profiles-dir", default=".edsl/profiles", show_default=True)
    def show_profile(name: str, profiles_dir: str):
        """Show a profile with secrets redacted."""
        _validate_profile_name(name)
        path = _profile_path(Path(profiles_dir), name)
        if not path.exists():
            error(
                "PROFILE_NOT_FOUND",
                f"Profile not found: {name}",
                suggestion="Run 'edsl profiles list' to see available profiles.",
                exit_code=EXIT_NOT_FOUND,
            )
        output(
            {
                "name": name,
                "path": str(path),
                "config": _redact_config(_read_profile(path)),
            }
        )

    def profile_value_options(func):
        func = click.option(
            "--set",
            "settings",
            multiple=True,
            help="Additional EXPECTED_PARROT_* setting as KEY=VALUE. Can be repeated or comma-separated.",
        )(func)
        func = click.option(
            "--api-key-env",
            help="Read EXPECTED_PARROT_API_KEY from this environment variable.",
        )(func)
        func = click.option("--api-key", help="EXPECTED_PARROT_API_KEY value.")(func)
        func = click.option(
            "--url-env",
            help="Read EXPECTED_PARROT_URL from this environment variable.",
        )(func)
        func = click.option("--url", help="EXPECTED_PARROT_URL value.")(func)
        return func

    @profiles_group.command("create")
    @click.argument("name")
    @click.option("--profiles-dir", default=".edsl/profiles", show_default=True)
    @click.option("--env-file", default=".env", show_default=True)
    @click.option(
        "--from-current",
        is_flag=True,
        help="Seed values from the current environment and .env.",
    )
    @profile_value_options
    @click.option("--overwrite", is_flag=True, help="Replace an existing profile.")
    @click.argument("extra_settings", nargs=-1)
    def create_profile(
        name: str,
        profiles_dir: str,
        env_file: str,
        from_current: bool,
        url: str | None,
        url_env: str | None,
        api_key: str | None,
        api_key_env: str | None,
        settings: tuple[str, ...],
        overwrite: bool,
        extra_settings: tuple[str, ...],
    ):
        """Create an Expected Parrot profile."""
        _validate_profile_name(name)
        path = _profile_path(Path(profiles_dir), name)
        if path.exists() and not overwrite:
            error(
                "PROFILE_EXISTS",
                f"Profile already exists: {name}",
                suggestion="Use --overwrite to replace it.",
                exit_code=EXIT_USAGE,
            )

        config: dict[str, str] = {}
        if from_current:
            config.update(_current_profile_values(Path(env_file)))
        config.update(
            _profile_updates(
                url=url,
                url_env=url_env,
                api_key=api_key,
                api_key_env=api_key_env,
                settings=settings + extra_settings,
            )
        )

        config = {key: value for key, value in config.items() if _has_value(value)}
        if not config:
            error(
                "EMPTY_PROFILE",
                "No profile values were provided.",
                suggestion=(
                    "Use --from-current, --url, --url-env, --api-key-env, "
                    "or --set EXPECTED_PARROT_NAME=value."
                ),
                exit_code=EXIT_USAGE,
            )

        _write_profile(path, config)
        _ensure_profiles_gitignore(path.parent)
        output({"name": name, "path": str(path), "config": _redact_config(config)})

    @profiles_group.command("update")
    @click.argument("name")
    @click.option("--profiles-dir", default=".edsl/profiles", show_default=True)
    @profile_value_options
    @click.argument("extra_settings", nargs=-1)
    def update_profile(
        name: str,
        profiles_dir: str,
        url: str | None,
        url_env: str | None,
        api_key: str | None,
        api_key_env: str | None,
        settings: tuple[str, ...],
        extra_settings: tuple[str, ...],
    ):
        """Update an existing Expected Parrot profile."""
        _validate_profile_name(name)
        path = _profile_path(Path(profiles_dir), name)
        if not path.exists():
            error(
                "PROFILE_NOT_FOUND",
                f"Profile not found: {name}",
                suggestion="Run 'edsl profiles list' to see available profiles.",
                exit_code=EXIT_NOT_FOUND,
            )

        updates = _profile_updates(
            url=url,
            url_env=url_env,
            api_key=api_key,
            api_key_env=api_key_env,
            settings=settings + extra_settings,
        )
        if not updates:
            error(
                "EMPTY_PROFILE_UPDATE",
                "No profile values were provided.",
                suggestion="Use --url, --url-env, --api-key, --api-key-env, or --set KEY=VALUE.",
                exit_code=EXIT_USAGE,
            )

        config = _read_profile(path)
        config.update(updates)
        _write_profile(path, config)
        output({"name": name, "path": str(path), "config": _redact_config(config)})

    @profiles_group.command("set")
    @click.argument("name")
    @click.option("--profiles-dir", default=".edsl/profiles", show_default=True)
    @click.option("--env-file", default=".env", show_default=True)
    @click.option("--dry-run", is_flag=True, help="Show the managed block without writing .env.")
    def set_profile(name: str, profiles_dir: str, env_file: str, dry_run: bool):
        """Activate a profile by updating the managed block in .env."""
        _validate_profile_name(name)
        path = _profile_path(Path(profiles_dir), name)
        if not path.exists():
            error(
                "PROFILE_NOT_FOUND",
                f"Profile not found: {name}",
                suggestion="Run 'edsl profiles list' to see available profiles.",
                exit_code=EXIT_NOT_FOUND,
            )

        config = _read_profile(path)
        block = _profile_block(name, config)
        env_path = Path(env_file)
        if not dry_run:
            _replace_managed_block(env_path, block)
        warnings = []
        if not _has_value(config.get("EXPECTED_PARROT_API_KEY")):
            warnings.append(
                "Profile has no EXPECTED_PARROT_API_KEY. "
                "Run 'edsl profiles update "
                f"{name} --api-key <key>' before using authenticated services."
            )

        output(
            {
                "active_profile": name,
                "profile_path": str(path),
                "env_file": str(env_path),
                "dry_run": dry_run,
                "config": _redact_config(config),
                "managed_block": (
                    _profile_block(name, _redact_config(config)) if dry_run else None
                ),
            },
            warnings=warnings,
        )

    @profiles_group.command("check")
    @click.argument("name", required=False)
    @click.option("--profiles-dir", default=".edsl/profiles", show_default=True)
    @click.option("--env-file", default=".env", show_default=True)
    @click.option("--timeout", default=10.0, show_default=True, type=float)
    def check_profile(
        name: str | None,
        profiles_dir: str,
        env_file: str,
        timeout: float,
    ):
        """Check Expected Parrot URL and API key connectivity."""
        _check_connectivity(
            profile_name=name,
            profiles_dir=profiles_dir,
            env_file=env_file,
            timeout=timeout,
        )


def _validate_profile_name(name: str) -> None:
    if not PROFILE_NAME_RE.match(name):
        error(
            "INVALID_PROFILE_NAME",
            f"Invalid profile name: {name}",
            suggestion="Use only letters, numbers, underscores, and hyphens.",
            exit_code=EXIT_USAGE,
        )


def _check_connectivity(
    profile_name: str | None,
    profiles_dir: str,
    env_file: str,
    timeout: float,
) -> None:
    config, source = _check_config(profile_name, Path(profiles_dir), Path(env_file))
    url = config.get("EXPECTED_PARROT_URL") or "https://www.expectedparrot.com"
    api_key = config.get("EXPECTED_PARROT_API_KEY")

    from edsl.coop import Coop

    coop = Coop(api_key=api_key, url=url)
    checks = {
        "url_configured": bool(url),
        "api_url_resolved": bool(coop.api_url),
        "api_key_configured": _has_value(api_key),
        "reachable": False,
        "authenticated": False,
    }
    data = {
        "source": source,
        "profile": profile_name,
        "url": coop.url,
        "api_url": coop.api_url,
        "config": _redact_config(config),
        "checks": checks,
    }

    if not _has_value(api_key):
        error(
            "CHECK_AUTH_REQUIRED",
            "No EXPECTED_PARROT_API_KEY is configured for this profile.",
            suggestion="Run 'edsl profiles update <name> --api-key <key>' or update .env.",
            details=[data],
            exit_code=EXIT_USAGE,
        )

    from edsl.coop.exceptions import CoopServerResponseError
    import requests

    try:
        response = coop._send_server_request(
            uri="api/v0/users/profile",
            method="GET",
            timeout=timeout,
        )
        checks["reachable"] = True
        coop._resolve_server_response(response, check_api_key=False)
        profile = response.json()
        checks["authenticated"] = True
        data["user"] = _profile_identity(profile)
        output(data)
    except requests.Timeout:
        data["checks"] = checks
        error(
            "CHECK_TIMEOUT",
            f"Timed out connecting to {coop.api_url}.",
            suggestion="Check EXPECTED_PARROT_URL and network connectivity.",
            details=[data],
            exit_code=EXIT_USAGE,
        )
    except requests.ConnectionError:
        data["checks"] = checks
        error(
            "CHECK_CONNECTION_ERROR",
            f"Could not connect to {coop.api_url}.",
            suggestion="Check EXPECTED_PARROT_URL and network connectivity.",
            details=[data],
            exit_code=EXIT_USAGE,
        )
    except CoopServerResponseError as exc:
        data["checks"] = checks
        error(
            "CHECK_AUTH_ERROR",
            _short_exception_message(exc),
            suggestion="Check EXPECTED_PARROT_API_KEY for this profile.",
            details=[data],
            exit_code=EXIT_USAGE,
        )


def _check_config(
    profile_name: str | None,
    profiles_dir: Path,
    env_path: Path,
) -> tuple[dict[str, str], str]:
    if profile_name:
        _validate_profile_name(profile_name)
        path = _profile_path(profiles_dir, profile_name)
        if not path.exists():
            error(
                "PROFILE_NOT_FOUND",
                f"Profile not found: {profile_name}",
                suggestion="Run 'edsl profiles list' to see available profiles.",
                exit_code=EXIT_NOT_FOUND,
            )
        return _read_profile(path), str(path)
    env_values = _read_env_file(env_path)
    if env_values.get(ACTIVE_PROFILE_KEY) or any(
        _is_profile_config_key(key) for key in env_values
    ):
        return {
            key: value
            for key, value in env_values.items()
            if _is_profile_config_key(key) and _has_value(value)
        }, str(env_path)
    return _current_profile_values(env_path), str(env_path)


def _short_exception_message(exc: Exception) -> str:
    message = str(exc).strip()
    return message.splitlines()[0] if message else exc.__class__.__name__


def _profile_identity(profile: object) -> dict[str, object]:
    if hasattr(profile, "items"):
        return {
            key: value
            for key, value in profile.items()
            if key in ("username", "email", "id", "uuid")
        }
    return {}


def _profile_path(profiles_dir: Path, name: str) -> Path:
    return profiles_dir / f"{name}.env"


def _active_profile(env_path: Path) -> str | None:
    return _read_env_file(env_path).get(ACTIVE_PROFILE_KEY)


def _read_env_file(path: Path) -> dict[str, str | None]:
    if not path.exists():
        return {}
    return dict(dotenv_values(path))


def _read_profile(path: Path) -> dict[str, str]:
    values = _read_env_file(path)
    return {
        key: value
        for key, value in values.items()
        if _is_profile_config_key(key) and _has_value(value)
    }


def _current_profile_values(env_path: Path) -> dict[str, str]:
    values = dict(os.environ)
    values.update(_read_env_file(env_path))
    return {
        key: value
        for key, value in values.items()
        if _is_profile_config_key(key) and _has_value(value)
    }


def _profile_updates(
    url: str | None,
    url_env: str | None,
    api_key: str | None,
    api_key_env: str | None,
    settings: tuple[str, ...],
) -> dict[str, str]:
    updates = {}
    if url_env:
        updates["EXPECTED_PARROT_URL"] = _read_required_env(url_env)
    if api_key_env:
        updates["EXPECTED_PARROT_API_KEY"] = _read_required_env(api_key_env)
    if url:
        updates["EXPECTED_PARROT_URL"] = url
    if api_key:
        updates["EXPECTED_PARROT_API_KEY"] = api_key
    updates.update(_parse_settings(settings))
    return {key: value for key, value in updates.items() if _has_value(value)}


def _parse_settings(settings: tuple[str, ...]) -> dict[str, str]:
    parsed = {}
    for setting in _split_settings(settings):
        if "=" not in setting:
            error(
                "INVALID_PROFILE_SETTING",
                f"Invalid profile setting: {setting}",
                suggestion="Use KEY=VALUE syntax.",
                exit_code=EXIT_USAGE,
            )
        key, value = setting.split("=", 1)
        if not _is_profile_config_key(key):
            error(
                "INVALID_PROFILE_SETTING",
                f"Invalid profile setting key: {key}",
                suggestion="Profile settings must use EXPECTED_PARROT_* keys.",
                exit_code=EXIT_USAGE,
            )
        parsed[key] = value
    return parsed


def _split_settings(settings: tuple[str, ...]) -> list[str]:
    split = []
    for setting in settings:
        for part in setting.split(","):
            part = part.strip().strip(",")
            if part:
                split.append(part)
    return split


def _is_profile_config_key(key: str) -> bool:
    return key.startswith("EXPECTED_PARROT_")


def _has_value(value: object) -> bool:
    return value not in (None, "", "None")


def _read_required_env(name: str) -> str:
    value = os.environ.get(name)
    if not _has_value(value):
        error(
            "ENV_VAR_NOT_FOUND",
            f"Environment variable is not set: {name}",
            suggestion="Export the variable or pass the value directly.",
            exit_code=EXIT_USAGE,
        )
    return value


def _write_profile(path: Path, config: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(
        f"{key}={_quote_env_value(value)}\n"
        for key, value in sorted(config.items())
    )
    path.write_text(content, encoding="utf-8")
    _chmod_private(path)


def _profile_block(name: str, config: dict[str, str]) -> str:
    lines = [START_MARKER, f"{ACTIVE_PROFILE_KEY}={_quote_env_value(name)}"]
    for key, value in sorted(config.items()):
        lines.append(f"{key}={_quote_env_value(value)}")
    lines.append(END_MARKER)
    return "\n".join(lines)


def _replace_managed_block(env_path: Path, block: str) -> None:
    old_text = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    new_text = _replace_block_text(old_text, block)
    env_path.write_text(new_text, encoding="utf-8")
    _chmod_private(env_path)


def _replace_block_text(text: str, block: str) -> str:
    lines = text.splitlines()
    start = _find_line(lines, START_MARKER)
    end = _find_line(lines, END_MARKER)

    if start is not None and end is not None and start <= end:
        replacement = block.splitlines()
        lines = lines[:start] + replacement + lines[end + 1 :]
        return "\n".join(lines).rstrip() + "\n"

    if text.strip():
        return text.rstrip() + "\n\n" + block + "\n"
    return block + "\n"


def _find_line(lines: list[str], marker: str) -> int | None:
    for idx, line in enumerate(lines):
        if line.strip() == marker:
            return idx
    return None


def _quote_env_value(value: str) -> str:
    if "\n" in value or "\r" in value:
        error(
            "INVALID_PROFILE_VALUE",
            "Profile values cannot contain newlines.",
            exit_code=EXIT_USAGE,
        )
    if re.match(r"^[A-Za-z0-9_./:@%+=,-]+$", value):
        return value
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _redact_config(config: dict[str, str | None]) -> dict[str, str | None]:
    redacted = {}
    for key, value in config.items():
        if any(marker in key.upper() for marker in SENSITIVE_MARKERS):
            redacted[key] = "***" if _has_value(value) else value
        else:
            redacted[key] = value
    return redacted


def _ensure_profiles_gitignore(profile_dir: Path) -> None:
    edsl_dir = profile_dir.parent
    if edsl_dir.name != ".edsl":
        return
    gitignore = edsl_dir / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    if "profiles/" not in existing.splitlines():
        gitignore.parent.mkdir(parents=True, exist_ok=True)
        content = (existing.rstrip() + "\n" if existing else "") + "profiles/\n"
        gitignore.write_text(content, encoding="utf-8")


def _chmod_private(path: Path) -> None:
    try:
        path.chmod(0o600)
    except OSError:
        pass
