# import os
# import pytest


# @pytest.fixture(scope="session", autouse=True)
# def clean_environment_variables():
#     os.environ.pop("OPENAI_API_KEY", None)
#     os.environ.pop("GOOGLE_API_KEY", None)
#     os.environ.pop("DEEP_INFRA_API_KEY", None)
#     yield
