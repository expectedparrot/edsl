"""Account and diagnostic commands for the EDSL CLI."""

from __future__ import annotations

import click

from edsl.cli_shared import EXIT_REMOTE, error, jsonable, output


def register(app: click.Group) -> None:
    # ---------------------------------------------------------------------------
    # edsl info
    # ---------------------------------------------------------------------------

    @app.command()
    def info():
        """Version, config, and diagnostics."""
        from edsl.__version__ import __version__
        from edsl.config import CONFIG
        from edsl.coop.ep_key_handling import ExpectedParrotKeyHandler

        handler = ExpectedParrotKeyHandler()
        api_key = handler.get_ep_api_key()

        output({
            "version": __version__,
            "config": _redact_config(CONFIG.to_dict()),
            "api_key_configured": bool(api_key),
        })


    def _redact_config(config: dict) -> dict:
        redacted = {}
        sensitive_markers = ("API_KEY", "AUTH_TOKEN", "SECRET", "PASSWORD")
        for key, value in config.items():
            if any(marker in key.upper() for marker in sensitive_markers):
                redacted[key] = "***" if value not in (None, "", "None") else value
            else:
                redacted[key] = value
        return redacted






    @app.command("profile")
    def profile():
        """Get the authenticated Expected Parrot profile."""
        try:
            from edsl.coop import Coop

            output(jsonable(Coop().get_profile()))
        except SystemExit:
            raise
        except Exception as e:
            error(
                "PROFILE_ERROR",
                str(e),
                suggestion="Check your Expected Parrot API key with 'edsl auth status'.",
                exit_code=EXIT_REMOTE,
            )




    @app.command("settings")
    def settings():
        """Get Expected Parrot EDSL settings and rate-limit configuration."""
        try:
            from edsl.coop import Coop

            coop = Coop()
            output(
                {
                    "edsl_settings": jsonable(coop.edsl_settings),
                    "rate_limit_config": jsonable(coop.fetch_rate_limit_config_vars()),
                }
            )
        except SystemExit:
            raise
        except Exception as e:
            error(
                "SETTINGS_ERROR",
                str(e),
                suggestion="Check your Expected Parrot API key and network connection.",
                exit_code=EXIT_REMOTE,
            )




