import pytest
from edsl import Coop


@pytest.mark.coop
def test_coop_remote_cache():
    coop = Coop(api_key="b")
    coop.api_key = "a"
    response = coop.error_create({"something": "This is an error message"})
    assert response["status"] == "success"
    coop.api_key = None
    response = coop.error_create({"something": "This is an error message"})
    assert response["status"] == "success"
