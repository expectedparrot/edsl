
"""
The coop module provides connectivity with Expected Parrot's cloud services.

This module enables EDSL to interact with cloud-based resources for enhanced functionality:
1. Remote storage and sharing of EDSL objects (surveys, agents, models, results, etc.)
2. Remote inference execution for running jobs in the cloud
3. Caching of interview results for improved performance and cost savings
4. API key management and authentication
5. Price and model availability information

The primary interface is the Coop class, which serves as a client for the
Expected Parrot API. Most users will only need to interact with the Coop class directly.

Example:
    >>> from edsl.coop import Coop
    >>> coop = Coop()  # Uses API key from environment or stored location
    >>> survey = my_survey.push()  # Uploads survey to Expected Parrot
    >>> job_info = coop.remote_inference_create(my_job)  # Creates remote job
"""

from .utils import EDSLObject, ObjectType, VisibilityType, ObjectRegistry
from .coop import Coop
from .exceptions import CoopServerResponseError
__all__ = ["Coop"]