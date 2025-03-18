import sys
from IPython.core.interactiveshell import InteractiveShell
from IPython.display import HTML, display

# Example logger import
from .. import logger

class BaseException(Exception):
    """
    Base exception class for all EDSL exceptions.

    This class extends the standard Python Exception class to provide more helpful 
    error messages by including links to relevant documentation and example notebooks 
    when available.
    """

    relevant_doc = "https://docs.expectedparrot.com/"
    relevant_notebook = None  # or set a default if you like
    suppress_traceback = True

    def __init__(self, message: str, *, show_docs: bool = True, 
                 log_level: str = "error", silent: bool = False):
        """
        Initialize a new BaseException with a formatted error message.
        
        Args:
            message (str): The primary error message.
            show_docs (bool): If True, append documentation links to the error message.
            log_level (str): The logging level to use 
                             ("debug", "info", "warning", "error", "critical").
            silent (bool): If True, suppress all output when the exception is caught.
        """
        self.silent = silent
        
        # Format main error message
        formatted_message = [message.strip()]

        # Add documentation links if requested
        if show_docs:
            if self.relevant_doc:
                formatted_message.append(
                    f"\nFor more information, see: {self.relevant_doc}"
                )
            if self.relevant_notebook:
                formatted_message.append(
                    f"\nFor a usage example, see: {self.relevant_notebook}"
                )

        # Join with double newlines for clear separation
        final_message = "\n\n".join(formatted_message)
        super().__init__(final_message)
        
        # Log the exception unless silent is True
        if not self.silent:
            self._log_message(log_level, message)
            
    @staticmethod
    def _log_message(log_level: str, message: str):
        """Helper to log a message at the specified log level."""
        # Adjust as needed for your logger setup
        if log_level == "debug":
            logger.debug(message)
        elif log_level == "info":
            logger.info(message)
        elif log_level == "warning":
            logger.warning(message)
        elif log_level == "error":
            logger.error(message)
        elif log_level == "critical":
            logger.critical(message)

    @classmethod
    def install_exception_hook(cls):
        """
        Install custom exception handling for EDSL exceptions.

        In an IPython/Jupyter environment, this uses `set_custom_exc` to handle
        BaseException (and its subclasses). In a standard Python environment,
        it falls back to overriding `sys.excepthook`.
        """
        if cls._in_ipython():
            cls._install_ipython_hook()
        else:
            cls._install_sys_excepthook()

    @classmethod
    def _install_ipython_hook(cls):
        """Use IPython's recommended approach for a custom exception handler."""

        shell = InteractiveShell.instance()

        # Wrap in a function so we can pass it to set_custom_exc.
        def _ipython_custom_exc(shell, etype, evalue, tb, tb_offset=None):
            if issubclass(etype, BaseException) and cls.suppress_traceback:
                # Show custom message only if not silent
                if not getattr(evalue, 'silent', False):
                    # Try HTML display first; fall back to stderr
                    # try:
                    #     display(
                    #         HTML(
                    #             f"<div style='color: red'>❌ EDSL ERROR: "
                    #             f"{etype.__name__}: {evalue}</div>"
                    #         )
                    #     )
                    # except:
                        print(f"❌ EDSL ERROR: {etype.__name__}: {evalue}", file=sys.stderr)
                # Suppress IPython’s normal traceback
                return
            # Otherwise, fall back to the usual traceback
            return shell.showtraceback((etype, evalue, tb), tb_offset=tb_offset)

        shell.set_custom_exc((BaseException,), _ipython_custom_exc)

    @classmethod
    def _install_sys_excepthook(cls):
        """
        Override the default sys.excepthook in a standard Python environment.
        This is typically NOT recommended for IPython/Jupyter.
        """
        if getattr(sys, 'custom_excepthook_installed', False):
            return  # Already installed

        original_excepthook = sys.excepthook

        def _custom_excepthook(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, BaseException) and cls.suppress_traceback:
                # Show custom message only if not silent
                if not getattr(exc_value, 'silent', False):
                    try:
                        display(
                            HTML(
                                f"<div style='color: red'>❌ EDSL ERROR: "
                                f"{exc_type.__name__}: {exc_value}</div>"
                            )
                        )
                    except:
                        print(f"❌ EDSL ERROR: {exc_type.__name__}: {exc_value}",
                              file=sys.stderr)
                # Suppress traceback
                return
            # Otherwise, use the default handler
            return original_excepthook(exc_type, exc_value, exc_traceback)

        sys.excepthook = _custom_excepthook
        sys.custom_excepthook_installed = True

    @staticmethod
    def _in_ipython() -> bool:
        """Return True if running inside IPython/Jupyter, False otherwise."""
        try:
            get_ipython()  # noqa
            return True
        except NameError:
            return False
