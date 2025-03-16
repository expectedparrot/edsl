import sys

from .. import logger

class BaseException(Exception):
    """Base exception class for all EDSL exceptions.
    
    This class extends the standard Python Exception class to provide more helpful error messages
    by including links to relevant documentation and example notebooks when available.
    
    Attributes:
        relevant_doc: URL to documentation explaining this type of exception
        relevant_notebook: Optional URL to a notebook with usage examples
    """
    relevant_doc = "https://docs.expectedparrot.com/"
    suppress_traceback = True

    def __init__(self, message:str, *, show_docs:bool=True, log_level:str="error"):
        """Initialize a new BaseException with formatted error message.
        
        Args:
            message: The primary error message
            show_docs: If True, append documentation links to the error message
            log_level: The logging level to use ("debug", "info", "warning", "error", "critical")
        """
        # Format main error message
        formatted_message = [message.strip()]

        # Add documentation links if requested
        if show_docs:
            if hasattr(self, "relevant_doc"):
                formatted_message.append(
                    f"\nFor more information, see: {self.relevant_doc}"
                )
            if hasattr(self, "relevant_notebook"):
                formatted_message.append(
                    f"\nFor a usage example, see: {self.relevant_notebook}"
                )

        # Join with double newlines for clear separation
        final_message = "\n\n".join(formatted_message)
        super().__init__(final_message)
        
        # Log the exception
        if log_level == "debug":
            logger.debug(f"{self.__class__.__name__}: {message}")
        elif log_level == "info":
            logger.info(f"{self.__class__.__name__}: {message}")
        elif log_level == "warning":
            logger.warning(f"{self.__class__.__name__}: {message}")
        elif log_level == "error":
            logger.error(f"{self.__class__.__name__}: {message}")
        elif log_level == "critical":
            logger.critical(f"{self.__class__.__name__}: {message}")

        self._setup_exception_handling()

    @classmethod
    def _setup_exception_handling(cls):
        """Set up custom exception handling to suppress tracebacks for this class."""
        # Only set up the handler if it hasn't been set yet
        if getattr(sys, 'custom_excepthook_installed', False):
            return
            
        # Store the original excepthook
        original_excepthook = sys.excepthook
        
        # Define the custom excepthook
        def custom_excepthook(exc_type, exc_value, exc_traceback):
            # Check if this is one of our exceptions and we want to suppress the traceback
            if issubclass(exc_type, BaseException) and BaseException.suppress_traceback:
                try:
                    display(HTML(f"<div style='color: red'>❌ EDSL ERROR: {exc_type.__name__}: {exc_value.html_message}</div>"))
                except:
                    print(f"❌ EDSL ERROR: {exc_type.__name__}: {exc_value}", file=sys.stderr)
                return  # Suppress traceback
            # Otherwise, use the default handler
            return original_excepthook(exc_type, exc_value, exc_traceback)
        
        # Install the custom excepthook
        sys.excepthook = custom_excepthook
        sys.custom_excepthook_installed = True

        # Add IPython exception handling if available
        try:
            ip = get_ipython()
            def custom_showtraceback(*args, **kwargs):
                exc_type, exc_value, _ = sys.exc_info()
                if issubclass(exc_type, BaseException) and BaseException.suppress_traceback:
                    print(f"❌ EDSL ERROR: {exc_type.__name__}: {exc_value}", file=sys.stderr)
                    return
                return ip.showtraceback(*args, **kwargs)
            ip.showtraceback = custom_showtraceback
        except NameError:
            pass  # Not in IPython environment