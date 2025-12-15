"""
EXA API integration for creating ScenarioLists from web search and enrichment.

This module provides functionality to create EDSL ScenarioLists using the EXA API,
which allows for sophisticated web search with enrichment capabilities.
"""

import os
from typing import Optional, List, Dict

from ..scenario_list import ScenarioList


def from_exa(
    query: str,
    criteria: Optional[List[str]] = None,
    count: int = 100,
    enrichments: Optional[List[Dict[str, str]]] = None,
    api_key: Optional[str] = None,
    wait_for_completion: bool = True,
    max_wait_time: int = 120,
    **kwargs,
) -> "ScenarioList":
    """
    Create a ScenarioList from EXA API web search and enrichment.

    Args:
        query: The search query string (e.g., "Sales leaders at US fintech companies")
        criteria: List of search criteria to refine the search
        count: Number of results to return (default: 100)
        enrichments: List of enrichment parameters, each with 'description' and 'format' keys
        api_key: EXA API key (defaults to EXA_API_KEY environment variable)
        wait_for_completion: Whether to wait for webset completion (default: True)
        max_wait_time: Maximum time to wait for completion in seconds (default: 120)
        **kwargs: Additional parameters to pass to EXA webset creation

    Returns:
        ScenarioList containing the search results and enrichments

    Example:
        >>> from edsl.scenarios.exa import from_exa
        >>> scenarios = from_exa(
        ...     query="Sales leaders at US fintech companies",
        ...     criteria=[
        ...         "currently holds a sales leadership position",
        ...         "the company operates in the fintech industry",
        ...         "the company is based in the united states"
        ...     ],
        ...     enrichments=[
        ...         {"description": "Years of experience", "format": "number"},
        ...         {"description": "University", "format": "text"}
        ...     ],
        ...     count=50
        ... )
    """
    try:
        from exa_py import Exa
        from exa_py.websets.types import CreateWebsetParameters
    except ImportError:
        raise ImportError(
            "The 'exa-py' library is required to use EXA integration. "
            "Install it with: pip install exa-py"
        )

    # Validate query
    if not query or not query.strip():
        raise ValueError("Query cannot be empty. Please provide a valid search query.")

    # Get API key from parameter or environment
    if api_key is None:
        api_key = os.getenv("EXA_API_KEY")

    if not api_key:
        raise ValueError(
            "EXA API key is required. Provide it via the 'api_key' parameter "
            "or set the 'EXA_API_KEY' environment variable."
        )

    # Initialize EXA client
    exa = Exa(api_key)

    # Prepare search parameters
    search_params = {"query": query, "count": count}

    # Add criteria if provided
    if criteria:
        search_params["criteria"] = criteria

    # Prepare enrichment parameters
    enrichment_list = []
    if enrichments:
        for enrichment in enrichments:
            if not isinstance(enrichment, dict):
                raise ValueError(
                    f"Each enrichment must be a dictionary with 'description' and 'format' keys. "
                    f"Got: {enrichment}"
                )

            required_keys = ["description", "format"]
            for key in required_keys:
                if key not in enrichment:
                    raise ValueError(
                        f"Each enrichment must have a '{key}' key. "
                        f"Missing in: {enrichment}"
                    )

            enrichment_list.append(enrichment)

    # Create webset parameters
    webset_params = CreateWebsetParameters(
        search=search_params, enrichments=enrichment_list, **kwargs
    )

    try:
        # Create webset using EXA API
        webset = exa.websets.create(params=webset_params)
        webset_id = webset.id if hasattr(webset, "id") else str(webset)

        if wait_for_completion:
            webset = _wait_for_webset_completion(exa, webset_id, max_wait_time)

        # Extract results from the webset
        data_list = _extract_webset_results(webset, query, count, criteria, webset_id)

    except Exception as e:
        raise RuntimeError(f"Failed to create EXA webset: {str(e)}") from e

    if not data_list:
        # Create empty result with metadata if no data returned
        data_list = [
            {
                "exa_query": query,
                "exa_count": count,
                "exa_criteria": criteria or [],
                "exa_enrichments": enrichment_list,
                "exa_results_count": 0,
            }
        ]

    # Create and return ScenarioList
    return ScenarioList.from_list_of_dicts(data_list)


def _wait_for_webset_completion(exa, webset_id: str, max_wait_time: int):
    """Wait for webset to complete and return the completed webset."""
    import time

    poll_interval = 5  # Check every 5 seconds
    waited_time = 0
    last_status = None

    print(f"⏳ EXA webset {webset_id} processing...")

    while waited_time < max_wait_time:
        try:
            current_webset = exa.websets.get(webset_id)

            if hasattr(current_webset, "status"):
                status = current_webset.status

                # Print status only when it changes or every 30 seconds
                if status != last_status or (waited_time > 0 and waited_time % 30 == 0):
                    if status in ["running", "queued", "processing"]:
                        print(f"   {status}... ({waited_time}s)")
                    last_status = status

                if status == "completed":
                    print(f"✓ Completed in {waited_time}s")
                    return current_webset
                elif status == "failed":
                    error_msg = getattr(current_webset, "error", "Unknown error")
                    raise RuntimeError(f"EXA webset failed: {error_msg}")
                elif status in ["running", "queued", "processing"]:
                    # Continue polling
                    pass
                else:
                    # Unknown status, assume it's done
                    return current_webset
            else:
                # No status attribute, assume completed
                return current_webset

            time.sleep(poll_interval)
            waited_time += poll_interval

        except Exception as e:
            # If polling fails, try once more
            try:
                return exa.websets.get(webset_id)
            except Exception as final_e:
                raise RuntimeError(
                    f"Failed to retrieve webset {webset_id}: {final_e}"
                ) from e

    # Timeout - but still try to get results
    print(f"⏰ Timeout after {max_wait_time}s - checking for partial results...")
    try:
        return exa.websets.get(webset_id)
    except Exception as e:
        raise RuntimeError(f"Webset timed out after {max_wait_time}s: {e}")


def _extract_webset_results(
    webset, query: str, count: int, criteria: Optional[List[str]], webset_id: str
) -> List[Dict]:
    """Extract results from a webset into a list of dictionaries."""
    data_list = []

    # Get the EXA client to fetch items - need to import here
    try:
        import os
        from exa_py import Exa

        exa = Exa(os.getenv("EXA_API_KEY"))

        # Get webset items using the EXA client
        items_response = exa.websets.items.list(webset_id)
        items = list(items_response)

        # Extract actual items from the response tuples
        actual_items = []
        for item_tuple in items:
            if isinstance(item_tuple, tuple) and len(item_tuple) == 2:
                category, item_list = item_tuple
                if category == "data" and isinstance(item_list, list):
                    actual_items.extend(item_list)

        if actual_items:
            print(f"✓ {len(actual_items)} results")

            for item in actual_items:
                result_dict = {}

                # Extract data from the WebsetItem structure
                if hasattr(item, "properties") and hasattr(item.properties, "person"):
                    person = item.properties.person
                    result_dict.update(
                        {
                            "name": getattr(person, "name", None),
                            "position": getattr(person, "position", None),
                            "location": getattr(person, "location", None),
                            "company_name": (
                                getattr(person.company, "name", None)
                                if hasattr(person, "company")
                                else None
                            ),
                            "company_location": (
                                getattr(person.company, "location", None)
                                if hasattr(person, "company")
                                else None
                            ),
                            "picture_url": (
                                str(getattr(person, "picture_url", None))
                                if getattr(person, "picture_url", None)
                                else None
                            ),
                        }
                    )

                # Add general properties
                if hasattr(item, "properties"):
                    result_dict.update(
                        {
                            "profile_url": (
                                str(item.properties.url)
                                if hasattr(item.properties, "url")
                                else None
                            ),
                            "description": getattr(
                                item.properties, "description", None
                            ),
                            "type": getattr(item.properties, "type", None),
                        }
                    )

                # Add evaluation data
                if hasattr(item, "evaluations") and item.evaluations:
                    eval_data = item.evaluations[0]  # Use first evaluation
                    result_dict.update(
                        {
                            "criterion": getattr(eval_data, "criterion", None),
                            "reasoning": getattr(eval_data, "reasoning", None),
                            "satisfied": getattr(eval_data, "satisfied", None),
                        }
                    )

                # Add item metadata
                result_dict.update(
                    {
                        "exa_item_id": getattr(item, "id", None),
                        "exa_source": getattr(item, "source", None),
                        "exa_created_at": (
                            str(getattr(item, "created_at", None))
                            if getattr(item, "created_at", None)
                            else None
                        ),
                    }
                )

                # Add standard EXA metadata
                _add_metadata(result_dict, query, count, criteria, webset_id)
                data_list.append(result_dict)
        else:
            print("No items found in webset")

    except Exception as e:
        print(f"Error getting webset items: {e}")
        # Fall back to checking if webset is still processing
        webset_status = getattr(webset, "status", "unknown")
        if webset_status in ["running", "queued", "processing"]:
            data_list = [
                {
                    "exa_query": query,
                    "exa_count": count,
                    "exa_criteria": criteria or [],
                    "exa_webset_id": webset_id,
                    "exa_status": webset_status,
                    "exa_message": f'Still {webset_status} - use from_exa_webset("{webset_id}") to check later',
                }
            ]
        else:
            data_list = [
                {
                    "exa_query": query,
                    "exa_count": count,
                    "exa_criteria": criteria or [],
                    "exa_webset_id": webset_id,
                    "exa_status": webset_status,
                    "exa_message": f"Error retrieving results: {str(e)}",
                }
            ]

    # If still no results, create a fallback entry
    if not data_list:
        webset_status = getattr(webset, "status", "unknown")
        data_list = [
            {
                "exa_query": query,
                "exa_count": count,
                "exa_criteria": criteria or [],
                "exa_webset_id": webset_id,
                "exa_status": webset_status,
                "exa_message": "No results found",
            }
        ]

    return data_list


def _convert_result_to_dict(result) -> Dict:
    """Convert a result object to a dictionary."""
    if hasattr(result, "__dict__"):
        return dict(result.__dict__)
    elif isinstance(result, dict):
        return dict(result)
    else:
        try:
            return dict(result)
        except (TypeError, ValueError):
            return {"result": str(result)}


def _add_metadata(
    result_dict: Dict,
    query: str,
    count: int,
    criteria: Optional[List[str]],
    webset_id: str,
):
    """Add EXA metadata to a result dictionary."""
    result_dict["exa_query"] = query
    result_dict["exa_count"] = count
    result_dict["exa_webset_id"] = webset_id
    if criteria:
        result_dict["exa_criteria"] = criteria


def from_exa_webset(webset_id: str, api_key: Optional[str] = None) -> "ScenarioList":
    """
    Create a ScenarioList from an existing EXA webset ID.

    Args:
        webset_id: The ID of an existing EXA webset
        api_key: EXA API key (defaults to EXA_API_KEY environment variable)

    Returns:
        ScenarioList containing the webset results

    Example:
        >>> from edsl.scenarios.exa import from_exa_webset
        >>> scenarios = from_exa_webset("01k6m4wn1aykv03jq3p4hxs2m9")
    """
    try:
        from exa_py import Exa
    except ImportError:
        raise ImportError(
            "The 'exa-py' library is required to use EXA integration. "
            "Install it with: pip install exa-py"
        )

    # Get API key from parameter or environment
    if api_key is None:
        api_key = os.getenv("EXA_API_KEY")

    if not api_key:
        raise ValueError(
            "EXA API key is required. Provide it via the 'api_key' parameter "
            "or set the 'EXA_API_KEY' environment variable."
        )

    # Initialize EXA client
    exa = Exa(api_key)

    try:
        # Retrieve webset by ID
        webset = exa.websets.get(webset_id)

        # Extract webset data (similar logic to from_exa)
        if hasattr(webset, "results") and webset.results:
            data_list = []
            for result in webset.results:
                result_dict = {}

                if hasattr(result, "__dict__"):
                    result_dict.update(result.__dict__)
                elif isinstance(result, dict):
                    result_dict.update(result)
                else:
                    try:
                        result_dict = dict(result)
                    except (TypeError, ValueError):
                        result_dict = {"result": str(result)}

                # Add webset metadata
                result_dict["exa_webset_id"] = webset_id

                data_list.append(result_dict)

        elif hasattr(webset, "__dict__"):
            data_list = [webset.__dict__]
            data_list[0]["exa_webset_id"] = webset_id

        else:
            data_list = [{"exa_webset_id": webset_id, "exa_webset": str(webset)}]

    except Exception as e:
        raise RuntimeError(
            f"Failed to retrieve EXA webset '{webset_id}': {str(e)}"
        ) from e

    if not data_list:
        data_list = [{"exa_webset_id": webset_id, "exa_results_count": 0}]

    # Create and return ScenarioList
    return ScenarioList.from_list_of_dicts(data_list)
