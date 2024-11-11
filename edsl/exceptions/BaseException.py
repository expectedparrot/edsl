class BaseException(Exception):
    relevant_doc = "https://docs.expectedparrot.com/"

    def __init__(self, message, *, show_docs=True):
        # Format main error message
        formatted_message = [message.strip()]

        # Add documentation links if requested
        if show_docs:
            if hasattr(self, "relevant_doc"):
                formatted_message.append(
                    f"\nFor more information, see:\n{self.relevant_doc}"
                )
            if hasattr(self, "relevant_notebook"):
                formatted_message.append(
                    f"\nFor a usage example, see:\n{self.relevant_notebook}"
                )

        # Join with double newlines for clear separation
        final_message = "\n\n".join(formatted_message)
        super().__init__(final_message)
