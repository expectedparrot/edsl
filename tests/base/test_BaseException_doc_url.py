import pytest
from edsl.base import BaseException
from edsl.surveys.exceptions import SurveyError, SurveyCreationError


def test_base_exception_doc_url():
    """Test that the get_doc_url method works correctly."""
    # Base class with no doc_page should return the base URL
    assert BaseException.get_doc_url() == "https://docs.expectedparrot.com/en/latest/"
    
    # SurveyError with doc_page but no doc_anchor
    assert SurveyError.get_doc_url() == "https://docs.expectedparrot.com/en/latest/surveys.html"
    
    # SurveyCreationError inherits doc_page from SurveyError and adds doc_anchor
    assert SurveyCreationError.get_doc_url() == "https://docs.expectedparrot.com/en/latest/surveys.html#creating-surveys"
    
    # Test that the URL is included in the exception message
    survey_error = SurveyError("Test error")
    assert "https://docs.expectedparrot.com/en/latest/surveys.html" in str(survey_error)
    
    survey_creation_error = SurveyCreationError("Test error")
    assert "https://docs.expectedparrot.com/en/latest/surveys.html#creating-surveys" in str(survey_creation_error)


if __name__ == "__main__":
    test_base_exception_doc_url()
    print("All tests passed!")