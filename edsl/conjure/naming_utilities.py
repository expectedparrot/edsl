import re
import keyword

# Ensure nltk stopwords are downloaded
try:
    from nltk.corpus import stopwords
    try:
        stopwords.words('english')
    except LookupError:
        nltk.download('stopwords')
except ImportError:
    print("nltk is not installed. Please install it using 'pip install nltk' to use these features.")


def sanitize_string(input_string):
    # Define the list of stopwords
    stop_words = set(stopwords.words('english'))
    
    # Replace special characters with spaces and split into words
    words = re.sub(r'\W+', ' ', input_string).split()
    
    # Remove stopwords
    important_words = [word for word in words if word.lower() not in stop_words]
    
    # Join words with underscores
    sanitized_string = '_'.join(important_words)
    
    # Ensure the length is less than 25 characters
    if len(sanitized_string) > 25:
        sanitized_string = sanitized_string[:25].rstrip('_')
    
    # Remove leading and trailing underscores
    sanitized_string = sanitized_string.strip('_')
    
    # Check if the string is a Python keyword
    if keyword.iskeyword(sanitized_string):
        sanitized_string += '_'
    
    return sanitized_string.lower()

# Example usage
#input_string = "This is a sample variable-name@123 for testing"
#sanitized_string = sanitize_string(input_string)
#print(sanitized_string)  # Output might be: sample_variable_name_123
