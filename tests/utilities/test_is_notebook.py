import sys
import types

from edsl.utilities.is_notebook import is_notebook


class _FakeStdout:
    def __init__(self, is_tty: bool):
        self._is_tty = is_tty

    def isatty(self) -> bool:
        return self._is_tty


def _install_fake_ipython(monkeypatch, shell_name: str):
    shell = type(shell_name, (), {})()
    fake_ipython = types.ModuleType("IPython")
    fake_ipython.get_ipython = lambda: shell
    monkeypatch.setitem(sys.modules, "IPython", fake_ipython)


def test_zmq_shell_with_tty_is_not_notebook(monkeypatch):
    _install_fake_ipython(monkeypatch, "ZMQInteractiveShell")
    monkeypatch.setattr(sys, "stdout", _FakeStdout(True))
    assert is_notebook() is False


def test_zmq_shell_without_tty_is_notebook(monkeypatch):
    _install_fake_ipython(monkeypatch, "ZMQInteractiveShell")
    monkeypatch.setattr(sys, "stdout", _FakeStdout(False))
    assert is_notebook() is True


def test_terminal_ipython_is_not_notebook(monkeypatch):
    _install_fake_ipython(monkeypatch, "TerminalInteractiveShell")
    monkeypatch.setattr(sys, "stdout", _FakeStdout(True))
    assert is_notebook() is False
