"""Authentication commands for the EDSL CLI."""

from __future__ import annotations

import sys
import webbrowser

import click

from edsl.cli_shared import EXIT_AUTH, EXIT_REMOTE, error, output


CREDITS_URL = "https://www.expectedparrot.com/home/credits"


def register(app: click.Group, auth: click.Group) -> None:
    # ---------------------------------------------------------------------------
    # ep auth
    # ---------------------------------------------------------------------------

    @auth.command("login")
    @click.option("--api_key", default=None, help="Provide API key directly.")
    def auth_login(api_key):
        """Store an API key for Expected Parrot / Coop access."""
        from edsl.coop.ep_key_handling import ExpectedParrotKeyHandler

        handler = ExpectedParrotKeyHandler()

        if api_key:
            handler.store_ep_api_key(api_key)
            output({"message": "API key stored successfully"})
        else:
            # Browser-based flow
            import secrets
            from edsl.config import CONFIG

            edsl_auth_token = secrets.token_urlsafe(16)
            login_url = f"{CONFIG.EXPECTED_PARROT_URL}/login?edsl_auth_token={edsl_auth_token}"
            output({
                "action": "awaiting_login",
                "login_url": login_url,
            })

            # Poll for key
            try:
                from edsl.coop import Coop
                import webbrowser
                webbrowser.open(login_url)
                coop_client = Coop()
                api_key_result = coop_client._poll_for_api_key(edsl_auth_token)
                if api_key_result:
                    handler.store_ep_api_key(api_key_result)
                    output({"message": "API key stored successfully"})
                else:
                    error("AUTH_TIMEOUT", "Timed out waiting for login.",
                           suggestion="Try again or use --api_key to provide a key directly.",
                           exit_code=EXIT_AUTH)
            except Exception as e:
                error("AUTH_ERROR", str(e),
                       suggestion="Try again or use --api_key to provide a key directly.",
                       exit_code=EXIT_AUTH)


    @auth.command("status")
    def auth_status():
        """Check authentication status."""
        import os

        env_key = os.environ.get("EXPECTED_PARROT_API_KEY", "")
        has_key = bool(env_key)

        data = {
            "authenticated": has_key,
            "api_key_source": "environment" if has_key else "none",
        }

        # Try to get username if authenticated
        if has_key:
            try:
                from edsl.coop import Coop
                # Suppress any stdout from Coop internals
                import io
                old_stdout = sys.stdout
                sys.stdout = io.StringIO()
                try:
                    coop_client = Coop()
                    profile = coop_client.get_profile()
                finally:
                    sys.stdout = old_stdout
                if hasattr(profile, 'get'):
                    data["username"] = profile.get("username", None)
                elif hasattr(profile, 'username'):
                    data["username"] = profile.username
            except Exception:
                data["username"] = None

        output(data)


    @auth.command("balance")
    def auth_balance():
        """Get the authenticated Expected Parrot credit balance."""
        output(_get_expected_parrot_balance())


    @app.group("balance", invoke_without_command=True)
    @click.pass_context
    def balance(ctx):
        """Get the authenticated Expected Parrot credit balance.

        \b
        Examples:
          ep balance
          ep balance alert
          ep balance alert --threshold 25
          ep balance alert --off
        """
        if ctx.invoked_subcommand is None:
            output(_get_expected_parrot_balance())

    @balance.command("alert")
    @click.option(
        "--on/--off",
        "enabled",
        default=None,
        help="Turn the low-balance email on or off.",
    )
    @click.option(
        "--threshold",
        "threshold_usd",
        type=float,
        default=None,
        help="Email when the balance drops below this many US dollars (1 to 10,000).",
    )
    def balance_alert(enabled, threshold_usd):
        """Show or change the low-balance email.

        With no options, shows the current setting.

        \b
        Examples:
          ep balance alert
          ep balance alert --threshold 25
          ep balance alert --on --threshold 50
          ep balance alert --off
        """
        if enabled is None and threshold_usd is None:
            output(
                _call_expected_parrot(
                    lambda coop: coop.get_low_balance_alert(), "BALANCE_ALERT_ERROR"
                )
            )
        else:
            output(
                _call_expected_parrot(
                    lambda coop: coop.update_low_balance_alert(
                        enabled=enabled, threshold_usd=threshold_usd
                    ),
                    "BALANCE_ALERT_ERROR",
                )
            )

    @app.command("credits")
    @click.option("--browser/--no-browser", default=True, help="Open the credits page in a browser.")
    def credits(browser):
        """Open the Expected Parrot credits page.

        \b
        Examples:
          ep credits
          ep credits --no-browser
        """
        opened = False
        if browser:
            try:
                opened = bool(webbrowser.open(CREDITS_URL))
            except Exception as e:
                error(
                    "BROWSER_ERROR",
                    f"Failed to open browser: {e}",
                    suggestion=f"Open this URL manually: {CREDITS_URL}",
                    exit_code=EXIT_REMOTE,
                )
        output({"credits_url": CREDITS_URL, "opened": opened})


    def _get_expected_parrot_balance() -> dict:
        """Return Expected Parrot balance data using the configured API key."""
        balance_info = _call_expected_parrot(
            lambda coop: coop.get_balance(), "BALANCE_ERROR"
        )
        if hasattr(balance_info, "items"):
            return dict(balance_info)
        return {"balance": balance_info}


    def _call_expected_parrot(call, error_code: str):
        """Return ``call(coop)`` for a Coop using the configured API key."""
        from edsl.coop.ep_key_handling import ExpectedParrotKeyHandler

        api_key = ExpectedParrotKeyHandler().get_ep_api_key()
        if not api_key:
            error(
                "AUTH_REQUIRED",
                "No Expected Parrot API key is configured.",
                suggestion="Run 'ep auth login --api_key <key>' or set EXPECTED_PARROT_API_KEY.",
                exit_code=EXIT_AUTH,
            )

        try:
            from edsl.coop import Coop

            import io

            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                return call(Coop(api_key=api_key))
            finally:
                sys.stdout = old_stdout
        except SystemExit:
            raise
        except Exception as e:
            error(
                error_code,
                str(e),
                suggestion="Check your Expected Parrot API key and network connection.",
                exit_code=EXIT_REMOTE,
            )
