"""Hugging Face dataset loader for EDSL ScenarioList."""

import warnings
from typing import Optional

from ..scenario_list import ScenarioList


def from_hugging_face(
    dataset_name: str, config_name: Optional[str] = None, split: Optional[str] = None
) -> "ScenarioList":
    """Create a ScenarioList from a Hugging Face dataset.

    Args:
        dataset_name (str): The fully qualified name of the Hugging Face dataset
        config_name (str, optional): Specific configuration to load if the dataset has multiple configs
        split (str, optional): Specific split to load (e.g., 'train', 'test', 'validation')

    Returns:
        ScenarioList: A ScenarioList created from the dataset

    Raises:
        ValueError: If the dataset has multiple configurations and config_name is not specified,
                   or if the specified split doesn't exist
        ImportError: If the datasets library is not available

    Example:
        >>> from edsl.scenarios.hugging_face import from_hugging_face
        >>> # Load a dataset with a single configuration
        >>> sl = from_hugging_face("squad")

        >>> # Load a specific configuration from a dataset with multiple configs
        >>> sl = from_hugging_face("glue", config_name="cola")

        >>> # Load a specific split
        >>> sl = from_hugging_face("Anthropic/AnthropicInterviewer", split="creatives")
    """
    # Import ScenarioList here to avoid circular imports
    from ..scenario_list import ScenarioList

    try:
        from datasets import load_dataset
    except ImportError:
        raise ImportError(
            "The 'datasets' library is required to load from Hugging Face. "
            "Install it with: pip install datasets"
        )

    # Load the dataset info to check for multiple configurations
    try:
        from datasets import get_dataset_config_names

        available_configs = get_dataset_config_names(dataset_name)

        # If multiple configs exist and none specified, raise error
        if len(available_configs) > 1 and config_name is None:
            raise ValueError(
                f"Dataset '{dataset_name}' has multiple configurations: {available_configs}. "
                f"Please specify one using the config_name parameter."
            )

        # If config_name specified, validate it exists
        if config_name is not None and config_name not in available_configs:
            raise ValueError(
                f"Configuration '{config_name}' not found in dataset '{dataset_name}'. "
                f"Available configurations: {available_configs}"
            )

    except Exception:
        # If we can't get config info, proceed with the load and let it fail if needed
        pass

    # Load the dataset
    try:
        if config_name:
            dataset = load_dataset(dataset_name, config_name)
        else:
            dataset = load_dataset(dataset_name)
    except Exception as e:
        raise ValueError(f"Failed to load dataset '{dataset_name}': {e}")

    # Handle split selection
    available_splits = list(dataset.keys())

    if split is not None:
        # User specified a split
        if split not in available_splits:
            raise ValueError(
                f"Split '{split}' not found in dataset '{dataset_name}'. "
                f"Available splits: {available_splits}"
            )
        data_frame = dataset[split]
    elif len(dataset) > 1:
        # Multiple splits available, user didn't specify - use default logic
        if "train" in dataset:
            data_frame = dataset["train"]
        else:
            split_name = available_splits[0]
            data_frame = dataset[split_name]
            warnings.warn(
                f"Dataset has multiple splits: {available_splits}. "
                f"Using '{split_name}' split. To use a different split, "
                f"specify the split parameter: from_hugging_face('{dataset_name}', split='{split_name}')"
            )
    else:
        # Single split dataset
        data_frame = list(dataset.values())[0]

    # Convert to pandas DataFrame for easier manipulation
    df = data_frame.to_pandas()

    # Convert DataFrame to list of dictionaries
    data_list = df.to_dict("records")

    # Create ScenarioList using existing from_list_of_dicts method
    return ScenarioList.from_list_of_dicts(data_list)
