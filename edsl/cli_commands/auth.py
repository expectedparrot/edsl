"""Authentication commands for the EDSL CLI."""

from __future__ import annotations

import sys

import click

from edsl.cli_shared import EXIT_AUTH, EXIT_REMOTE, error, output


def register(app: click.Group, auth: click.Group) -> None:
    # ---------------------------------------------------------------------------
    # edsl auth
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


    @app.command("balance")
    def balance():
        """Get the authenticated Expected Parrot credit balance."""
        output(_get_expected_parrot_balance())


    def _get_expected_parrot_balance() -> dict:
        """Return Expected Parrot balance data using the configured API key."""
        from edsl.coop.ep_key_handling import ExpectedParrotKeyHandler

        api_key = ExpectedParrotKeyHandler().get_ep_api_key()
        if not api_key:
            error(
                "AUTH_REQUIRED",
                "No Expected Parrot API key is configured.",
                suggestion="Run 'edsl auth login --api_key <key>' or set EXPECTED_PARROT_API_KEY.",
                exit_code=EXIT_AUTH,
            )

        try:
            from edsl.coop import Coop

            import io

            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                balance_info = Coop(api_key=api_key).get_balance()
            finally:
                sys.stdout = old_stdout
        except SystemExit:
            raise
        except Exception as e:
            error(
                "BALANCE_ERROR",
                str(e),
                suggestion="Check your Expected Parrot API key and network connection.",
                exit_code=EXIT_REMOTE,
            )

        if hasattr(balance_info, "items"):
            return dict(balance_info)
        return {"balance": balance_info}
