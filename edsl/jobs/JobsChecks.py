import os
from edsl.exceptions import MissingAPIKeyError


class JobsChecks:
    def __init__(self, jobs):
        """ """
        self.jobs = jobs

    def check_api_keys(self) -> None:
        from edsl import Model

        for model in self.jobs.models + [Model()]:
            if not model.has_valid_api_key():
                raise MissingAPIKeyError(
                    model_name=str(model.model),
                    inference_service=model._inference_service_,
                )

    def get_missing_api_keys(self) -> set:
        """
        Returns a list of the api keys that a user needs to run this job, but does not currently have in their .env file.
        """
        missing_api_keys = set()

        from edsl import Model
        from edsl.enums import service_to_api_keyname

        for model in self.jobs.models + [Model()]:
            if not model.has_valid_api_key():
                key_name = service_to_api_keyname.get(
                    model._inference_service_, "NOT FOUND"
                )
                missing_api_keys.add(key_name)

        return missing_api_keys

    def user_has_ep_api_key(self) -> bool:
        """
        Returns True if the user has an EXPECTED_PARROT_API_KEY in their env.

        Otherwise, returns False.
        """

        coop_api_key = os.getenv("EXPECTED_PARROT_API_KEY")

        if coop_api_key is not None:
            return True
        else:
            return False

    def user_has_all_model_keys(self):
        """
        Returns True if the user has all model keys required to run their job.

        Otherwise, returns False.
        """

        try:
            self.check_api_keys()
            return True
        except MissingAPIKeyError:
            return False
        except Exception:
            raise

    def needs_external_llms(self) -> bool:
        """
        Returns True if the job needs external LLMs to run.

        Otherwise, returns False.
        """
        # These cases are necessary to skip the API key check during doctests

        # Accounts for Results.example()
        all_agents_answer_questions_directly = len(self.jobs.agents) > 0 and all(
            [hasattr(a, "answer_question_directly") for a in self.jobs.agents]
        )

        # Accounts for InterviewExceptionEntry.example()
        only_model_is_test = set([m.model for m in self.jobs.models]) == set(["test"])

        # Accounts for Survey.__call__
        all_questions_are_functional = set(
            [q.question_type for q in self.jobs.survey.questions]
        ) == set(["functional"])

        if (
            all_agents_answer_questions_directly
            or only_model_is_test
            or all_questions_are_functional
        ):
            return False
        else:
            return True

    def needs_key_process(self):
        return (
            not self.user_has_all_model_keys()
            and not self.user_has_ep_api_key()
            and self.needs_external_llms()
        )

    def key_process(self):
        import secrets
        from dotenv import load_dotenv
        from edsl import CONFIG
        from edsl.coop.coop import Coop
        from edsl.utilities.utilities import write_api_key_to_env

        missing_api_keys = self.get_missing_api_keys()

        edsl_auth_token = secrets.token_urlsafe(16)

        print("You're missing some of the API keys needed to run this job:")
        for api_key in missing_api_keys:
            print(f"     🔑 {api_key}")
        print(
            "\nYou can either add the missing keys to your .env file, or use remote inference."
        )
        print("Remote inference allows you to run jobs on our server.")
        print("\n🚀 To use remote inference, sign up at the following link:")

        coop = Coop()
        coop._display_login_url(edsl_auth_token=edsl_auth_token)

        print(
            "\nOnce you log in, we will automatically retrieve your Expected Parrot API key and continue your job remotely."
        )

        api_key = coop._poll_for_api_key(edsl_auth_token)

        if api_key is None:
            print("\nTimed out waiting for login. Please try again.")
            return

        write_api_key_to_env(api_key)
        print("✨ API key retrieved and written to .env file.\n")

        # Retrieve API key so we can continue running the job
        load_dotenv()


if __name__ == "__main__":
    import doctest

    doctest.testmod()
