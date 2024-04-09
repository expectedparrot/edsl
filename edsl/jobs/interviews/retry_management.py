from edsl import CONFIG

from tenacity import (
    retry,
    wait_exponential,
    stop_after_attempt,
    retry_if_exception_type,
    before_sleep,
)

EDSL_BACKOFF_START_SEC = float(CONFIG.get("EDSL_BACKOFF_START_SEC"))
EDSL_MAX_BACKOFF_SEC = float(CONFIG.get("EDSL_MAX_BACKOFF_SEC"))
EDSL_MAX_ATTEMPTS = int(CONFIG.get("EDSL_MAX_ATTEMPTS"))


def print_retry(retry_state, print_to_terminal=False):
    "Prints details on tenacity retries."
    attempt_number = retry_state.attempt_number
    exception = retry_state.outcome.exception()
    wait_time = retry_state.next_action.sleep
    # breakpoint()
    if print_to_terminal:
        print(
            f"Attempt {attempt_number} failed with exception: {repr(exception)}; "
            f"now waiting {wait_time:.2f} seconds before retrying."
            f" Parameters: start={EDSL_BACKOFF_START_SEC}, max={EDSL_MAX_BACKOFF_SEC}, max_attempts={EDSL_MAX_ATTEMPTS}."
        )


retry_strategy = retry(
    wait=wait_exponential(
        multiplier=EDSL_BACKOFF_START_SEC, max=EDSL_MAX_BACKOFF_SEC
    ),  # Exponential back-off starting at 1s, doubling, maxing out at 60s
    stop=stop_after_attempt(EDSL_MAX_ATTEMPTS),  # Stop after 5 attempts
    # retry=retry_if_exception_type(Exception),  # Customize this as per your specific retry-able exception
    before_sleep=print_retry,  # Use custom print function for retries
)
