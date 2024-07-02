import re
import keyword


def sanitize_string(input_string, max_length=25):
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
    if len(sanitized_string) > max_length:
        # sanitized_string = sanitized_string[:25].rstrip("_")
        # split off the last word and remove it
        words = sanitized_string[:max_length].split("_")
        if len(words) == 1:
            sanitized_string = words[0]
        else:
            sanitized_string = "_".join(words[:-1])

    # Remove leading and trailing underscores
    sanitized_string = sanitized_string.strip("_")

    # Check if the string is a Python keyword
    if keyword.iskeyword(sanitized_string):
        sanitized_string += "_modified"

    return sanitized_string.lower()


# Example usage
# input_string = "This is a sample variable-name@123 for testing"
# sanitized_string = sanitize_string(input_string)
# print(sanitized_string)  # Output might be: sample_variable_name_123

if __name__ == "__main__":
    candidate_names = [
        "How are you doing this morning, Dave? What is your favorite kind of coffee?",
        "class",
        "def",
        "here_is_some_text",
    ]
    for name in candidate_names:
        print(f"Original: {name}")
        print(f"Sanitized: {sanitize_string(name)}")
        print()
