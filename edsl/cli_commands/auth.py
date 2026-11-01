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


    @auth.command("setup-git")
    @click.option("--hostname", default=None, help="Git host URL (default: Expected Parrot's git host).")
    @click.option("--unset", is_flag=True, default=False, help="Remove the credential helper instead.")
    def auth_setup_git(hostname, unset):
        """Let plain git use your Expected Parrot key for the git host, like 'gh auth setup-git'.

        Sets credential.<host>.helper in your global git config to
        'ep auth git-credential', after an empty entry that drops any helper
        set before it for that host.
        """
        import shlex
        import subprocess

        try:
            host = _git_credential_host(hostname or _coop_git_host())
            key = f"credential.{host}.helper"
            if unset:
                subprocess.run(["git", "config", "--global", "--unset-all", key], check=False)
                output({"host": host, "helper": None})
                return
            helper = f"!{shlex.quote(_ep_executable())} auth git-credential --hostname {host}"
            subprocess.run(["git", "config", "--global", "--replace-all", key, ""], check=True)
            subprocess.run(["git", "config", "--global", "--add", key, helper], check=True)
            output({"host": host, "helper": helper})
        except SystemExit:
            raise
        except Exception as e:
            error("SETUP_GIT_ERROR", str(e), suggestion="Check that git is installed.", exit_code=EXIT_REMOTE)


    @auth.command("git-credential", hidden=True)
    @click.argument("operation")
    @click.option("--hostname", default=None)
    def auth_git_credential(operation, hostname):
        """git credential helper: answers 'get' for the git host only."""
        if operation != "get" or not hostname:
            return
        host = _git_credential_host(hostname)
        request = dict(
            line.split("=", 1) for line in sys.stdin.read().splitlines() if "=" in line
        )
        if f"{request.get('protocol')}://{request.get('host')}" != host:
            return
        from edsl.coop import Coop

        coop_client = Coop()
        if not coop_client.api_key:
            return
        try:
            username = coop_client.get_profile().get("username")
        except Exception:
            username = None
        # The git host requires a Basic username to be the key owner's; without
        # a username on the account, the key goes alone.
        if username:
            sys.stdout.write(f"username={username}\npassword={coop_client.api_key}\n")
        else:
            sys.stdout.write(f"username={coop_client.api_key}\npassword=\n")


    @auth.command("balance")
    def auth_balance():
        """Get the authenticated Expected Parrot credit balance."""
        output(_get_expected_parrot_balance())


    @app.command("balance")
    def balance():
        """Get the authenticated Expected Parrot credit balance."""
        output(_get_expected_parrot_balance())

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


    def _git_credential_host(url: str) -> str:
        """``scheme://host[:port]`` of a git host URL or bare host name."""
        from urllib.parse import urlparse

        parsed = urlparse(url if "://" in url else f"https://{url}")
        return f"{parsed.scheme}://{parsed.netloc.rsplit('@', 1)[-1]}"


    def _coop_git_host() -> str:
        """Expected Parrot's git host, as Coop reports it."""
        from edsl.coop import Coop

        coop_client = Coop()
        response = coop_client._send_server_request(uri="api/v0/git-repos", method="GET")
        coop_client._resolve_server_response(response)
        return response.json()["server_url"]


    def _ep_executable() -> str:
        """This ep, by absolute path, so git finds it without the venv on PATH."""
        import shutil
        from pathlib import Path

        running = Path(sys.argv[0])
        if running.name in ("ep", "edsl") and running.exists():
            return str(running.resolve())
        return shutil.which("ep") or "ep"


    def _get_expected_parrot_balance() -> dict:
        """Return Expected Parrot balance data using the configured API key."""
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
