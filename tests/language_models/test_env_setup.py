import pytest 
import os
from tempfile import TemporaryDirectory
import dotenv

@pytest.fixture
def temp_env():
    # Create a temporary directory
    with TemporaryDirectory() as temp_dir:
        # Create a custom .env file in the temporary directory
        env_path = os.path.join(temp_dir, '.env')
        with open(env_path, 'w') as f:
            f.write("KEY=VALUE\nANOTHER_KEY=ANOTHER_VALUE")

        # Change the current working directory to the temporary directory
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        dotenv.load_dotenv(env_path, override=True)        
        
        yield
        
        # Change back to the original directory after the test
        os.chdir(original_cwd)


def test_application_with_custom_env(temp_env):
    # This test will run as if the .env is located in a new temporary directory
    import os
    value = os.getenv('KEY')
    assert value == 'VALUE'

    #key = os.getenv('OPENAI_API_KEY')
    #assert key == "a_fake_key"

    from edsl import Model
    m = Model()
    assert m.has_valid_api_key()

    original_value = os.environ.pop('OPENAI_API_KEY', None)
    assert not m.has_valid_api_key()
    
