import openai
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Get the OpenAI API key from the environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

from openai import Client


def get_embeddings(texts):
    """
    Get embeddings for a list of texts using OpenAI API.

    Args:
        texts (list of str): List of strings to get embeddings for.

    Returns:
        list of list of float: List of embeddings.
    """
    client = Client()
    response = client.embeddings.create(input=texts, model="text-embedding-ada-002")
    embeddings = [item.embedding for item in response.data]
    return embeddings
