import re
import keyword


def sanitize_string(input_string):
    # Ensure nltk stopwords are downloaded
    try:
        from nltk.corpus import stopwords
    except ImportError or ModuleNotFoundError:
        print(
            "nltk is not installed. Please install it using 'pip install nltk' to use these features."
        )
        raise

    try:
        stop_words = set(stopwords.words("english"))
    except LookupError:
        nltk.download("stopwords")
        stop_words = set(stopwords.words("english"))
        # raise LookupError("Stopwords not found. Please download them using nltk.download('stopwords')")

    # Define the list of stopwords

    # Replace special characters with spaces and split into words
    words = re.sub(r"\W+", " ", input_string).split()

    # Remove stopwords
    important_words = [word for word in words if word.lower() not in stop_words]

    # Join words with underscores
    sanitized_string = "_".join(important_words)

    # Ensure the length is less than 25 characters
    if len(sanitized_string) > 25:
        sanitized_string = sanitized_string[:25].rstrip("_")

    # Remove leading and trailing underscores
    sanitized_string = sanitized_string.strip("_")

    # Check if the string is a Python keyword
    if keyword.iskeyword(sanitized_string):
        sanitized_string += "_"

    return sanitized_string.lower()


# Example usage
# input_string = "This is a sample variable-name@123 for testing"
# sanitized_string = sanitize_string(input_string)
# print(sanitized_string)  # Output might be: sample_variable_name_123
