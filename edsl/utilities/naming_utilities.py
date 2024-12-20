import re
import keyword

stop_words = {
    "into",
    "mustn't",
    "there",
    "you'll",
    "don",
    "have",
    "at",
    "if",
    "on",
    "some",
    "with",
    "in",
    "can",
    "mightn",
    "off",
    "few",
    "not",
    "d",
    "hadn",
    "shan't",
    "t",
    "re",
    "where",
    "s",
    "won't",
    "mustn",
    "wasn't",
    "didn't",
    "has",
    "same",
    "too",
    "will",
    "you've",
    "all",
    "haven't",
    "isn't",
    "over",
    "of",
    "about",
    "its",
    "being",
    "it",
    "her",
    "should",
    "himself",
    "wasn",
    "out",
    "theirs",
    "aren",
    "that",
    "our",
    "shouldn't",
    "you'd",
    "such",
    "above",
    "my",
    "the",
    "any",
    "been",
    "as",
    "very",
    "herself",
    "o",
    "weren",
    "until",
    "their",
    "shouldn",
    "up",
    "wouldn",
    "couldn't",
    "hasn't",
    "no",
    "than",
    "hadn't",
    "had",
    "you",
    "here",
    "yourself",
    "yourselves",
    "during",
    "ain",
    "once",
    "aren't",
    "what",
    "so",
    "hers",
    "that'll",
    "other",
    "ours",
    "yours",
    "nor",
    "him",
    "doesn",
    "doesn't",
    "he",
    "them",
    "for",
    "ll",
    "isn",
    "this",
    "or",
    "who",
    "only",
    "itself",
    "they",
    "between",
    "against",
    "under",
    "me",
    "now",
    "mightn't",
    "those",
    "needn't",
    "these",
    "when",
    "before",
    "his",
    "she's",
    "having",
    "be",
    "don't",
    "haven",
    "won",
    "while",
    "both",
    "didn",
    "by",
    "ourselves",
    "m",
    "your",
    "then",
    "myself",
    "we",
    "it's",
    "should've",
    "through",
    "why",
    "from",
    "and",
    "hasn",
    "more",
    "how",
    "ve",
    "most",
    "because",
    "did",
    "y",
    "i",
    "an",
    "but",
    "whom",
    "below",
    "further",
    "am",
    "which",
    "just",
    "ma",
    "you're",
    "couldn",
    "do",
    "shan",
    "own",
    "again",
    "are",
    "weren't",
    "down",
    "is",
    "were",
    "each",
    "needn",
    "themselves",
    "she",
    "after",
    "does",
    "wouldn't",
    "to",
    "a",
    "was",
    "doing",
}


def sanitize_string(input_string, max_length=35):
    """Return a sanitized version of the input string that can be used as a variable name.

    >>> candidate_names = ["How are you doing this morning, Dave? What is your favorite kind of coffee?", "class", "def", "here_is_some_text"]
    >>> [sanitize_string(name) for name in candidate_names]
    ['morning_dave_favorite_kind_coffee', 'class_modified', 'def_modified', 'here_is_some_text']
    """

    # Ensure nltk stopwords are downloaded
    # try:
    #     from nltk.corpus import stopwords
    # except ImportError or ModuleNotFoundError:
    #     print(
    #         "nltk is not installed. Please install it using 'pip install nltk' to use these features."
    #     )
    #     raise

    # try:
    #     stop_words = set(stopwords.words("english"))
    # except LookupError:
    #     nltk.download("stopwords")
    #     stop_words = set(stopwords.words("english"))
    #     # raise LookupError("Stopwords not found. Please download them using nltk.download('stopwords')")

    # # Define the list of stopwords

    # Replace special characters with spaces and split into words
    words = re.sub(r"\W+", " ", input_string).split()

    # Remove stopwords
    important_words = [word for word in words if word.lower() not in stop_words]

    # Join words with underscores
    sanitized_string = "_".join(important_words)

    # Ensure the length is less than 25 characters
    if len(sanitized_string) > max_length:
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

    result = sanitized_string.lower()
    return result


# Example usage
# input_string = "This is a sample variable-name@123 for testing"
# sanitized_string = sanitize_string(input_string)
# print(sanitized_string)  # Output might be: sample_variable_name_123

# if __name__ == "__main__":
#     candidate_names = [
#         "How are you doing this morning, Dave? What is your favorite kind of coffee?",
#         "class",
#         "def",
#         "here_is_some_text",
#     ]
#     for name in candidate_names:
#         print(f"Original: {name}")
#         print(f"Sanitized: {sanitize_string(name)}")
#         print()

if __name__ == "__main__":
    # from edsl.conjure.InputData import InputDataABC
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
