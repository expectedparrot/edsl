"""
FeatureProcessor: Automatic feature type detection and preprocessing.

Handles automatic detection of feature types in survey/scenario data and applies
appropriate preprocessing transformations. Supports numeric, categorical, ordinal,
and text list features with robust handling of missing values and unseen categories.
"""

import re
import pandas as pd
import numpy as np
from typing import Dict, List, Any
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.feature_extraction.text import TfidfVectorizer


class FeatureProcessor:
    """
    Automatic feature type detection and preprocessing for survey data.

    Detects feature types (numeric, categorical, ordinal, text list) and applies
    appropriate preprocessing with robust handling of missing values and unseen data.
    """

    def __init__(self, list_encoding="dummy"):
        """
        Initialize the feature processor.

        Args:
            list_encoding: Method for encoding list features.
                          'dummy' for dummy/binary encoding (default)
                          'tfidf' for TF-IDF encoding
        """
        self.processors: Dict[str, Dict[str, Any]] = {}
        self.feature_names: List[str] = []
        self._ordinal_patterns = self._init_ordinal_patterns()
        self.list_encoding = list_encoding

    def _init_ordinal_patterns(self) -> Dict[str, Dict[str, int]]:
        """Initialize ordinal pattern mappings."""
        return {
            "employee_size": {
                "1-5": 1,
                "6-20": 2,
                "21-100": 3,
                "21 - 100": 3,
                "101-500": 4,
                "101 - 500": 4,
                "More than 500": 5,
                "more than 500": 5,
                "500+": 5,
                "Unknown": 0,
            },
            "project_count": {
                "0": 0,
                "1-2": 1,
                "3-5": 2,
                "6-10": 3,
                "More than 10": 4,
                "more than 10": 4,
                "10+": 4,
                "Unknown": -1,
            },
            "likert_5": {
                "Strongly Disagree": 1,
                "Disagree": 2,
                "Neutral": 3,
                "Agree": 4,
                "Strongly Agree": 5,
                "Unknown": 0,
            },
            "frequency_5": {
                "Never": 1,
                "Rarely": 2,
                "Sometimes": 3,
                "Often": 4,
                "Always": 5,
                "Unknown": 0,
            },
            "satisfaction_5": {
                "Very Dissatisfied": 1,
                "Dissatisfied": 2,
                "Neutral": 3,
                "Satisfied": 4,
                "Very Satisfied": 5,
                "Unknown": 0,
            },
        }

    def detect_feature_type(self, series: pd.Series) -> str:
        """
        Detect the feature type of a pandas Series.

        Args:
            series: Pandas Series to analyze

        Returns:
            Feature type: 'numeric', 'ordinal', 'text_list', or 'categorical'
        """
        # Remove null values for analysis
        non_null_series = series.dropna()

        if len(non_null_series) == 0:
            return "categorical"  # Default for empty series

        # Check if numeric
        if pd.api.types.is_numeric_dtype(series):
            return "numeric"

        # Convert to string for pattern matching
        str_series = non_null_series.astype(str)

        # Check for text lists
        if self._is_text_list(str_series):
            if self.list_encoding == "dummy":
                return "list_dummy"
            else:
                return "text_list"

        # Check for ordinal patterns
        if self._is_ordinal(str_series):
            return "ordinal"

        # Default to categorical
        return "categorical"

    def _is_text_list(self, series: pd.Series) -> bool:
        """Check if series contains text lists like "['item1', 'item2']"."""
        # Sample a few values to check
        sample_size = min(10, len(series))
        sample_values = series.head(sample_size)

        list_indicators = 0
        for value in sample_values:
            value_str = str(value).strip()
            # Check for actual list patterns (not just commas in numbers)
            if (value_str.startswith("[") and value_str.endswith("]")) or (
                value_str.startswith("['") and value_str.endswith("']")
            ):
                list_indicators += 1
            # Only consider comma-separated values if they look like actual lists
            elif "," in value_str and not self._looks_like_number_with_comma(value_str):
                # Additional check: must have multiple non-numeric tokens
                tokens = [t.strip() for t in value_str.split(",")]
                if len(tokens) > 1 and any(
                    not t.replace(".", "").replace("$", "").replace("%", "").isdigit()
                    for t in tokens
                ):
                    list_indicators += 1

        # If more than half look like lists, consider it a text list
        return list_indicators > sample_size * 0.5

    def _looks_like_number_with_comma(self, value_str: str) -> bool:
        """Check if a string looks like a number with comma separators (e.g., '$1,000')."""
        # Remove common currency symbols and check if it's mostly digits and commas
        cleaned = (
            value_str.replace("$", "")
            .replace("€", "")
            .replace("£", "")
            .replace("%", "")
            .strip()
        )
        # Pattern: digits, possibly with commas as thousands separators
        return bool(re.match(r"^\d{1,3}(,\d{3})*(\.\d+)?$", cleaned))

    def _is_ordinal(self, series: pd.Series) -> bool:
        """Check if series matches known ordinal patterns."""
        unique_values = set(series.unique())

        for pattern_name, pattern_mapping in self._ordinal_patterns.items():
            pattern_values = set(pattern_mapping.keys())
            # If most unique values match a pattern, consider it ordinal
            overlap = len(unique_values.intersection(pattern_values))
            if overlap > len(unique_values) * 0.6:
                return True

        return False

    def _get_ordinal_mapping(self, series: pd.Series) -> Dict[str, int]:
        """Get the appropriate ordinal mapping for a series."""
        unique_values = set(series.unique())

        best_match = None
        best_overlap = 0

        for pattern_name, pattern_mapping in self._ordinal_patterns.items():
            pattern_values = set(pattern_mapping.keys())
            overlap = len(unique_values.intersection(pattern_values))
            if overlap > best_overlap:
                best_overlap = overlap
                best_match = pattern_mapping

        return best_match if best_match else {}

    def fit_transform(self, df: pd.DataFrame, target_col: str) -> np.ndarray:
        """
        Fit processors and transform features.

        Args:
            df: Input DataFrame
            target_col: Name of target column to exclude from features

        Returns:
            Transformed feature matrix
        """
        # Validate inputs
        if len(df) < 3:
            raise ValueError(
                f"Insufficient data for training: {len(df)} samples. "
                "Need at least 3 samples for reliable feature processing."
            )

        if target_col not in df.columns:
            available_cols = list(df.columns)
            raise ValueError(
                f"Target column '{target_col}' not found. Available columns: {available_cols}"
            )

        # Exclude target column
        feature_cols = [col for col in df.columns if col != target_col]
        feature_df = df[feature_cols].copy()

        self.feature_names = []
        transformed_features = []

        for col in feature_cols:
            series = feature_df[col]
            feature_type = self.detect_feature_type(series)

            if feature_type == "numeric":
                processor_info = self._fit_numeric(series, col)
                features = self._transform_numeric(series, processor_info)

            elif feature_type == "ordinal":
                processor_info = self._fit_ordinal(series, col)
                features = self._transform_ordinal(series, processor_info)

            elif feature_type == "text_list":
                processor_info = self._fit_text_list(series, col)
                features = self._transform_text_list(series, processor_info)

            elif feature_type == "list_dummy":
                processor_info = self._fit_list_dummy(series, col)
                features = self._transform_list_dummy(series, processor_info)

            else:  # categorical
                processor_info = self._fit_categorical(series, col)
                features = self._transform_categorical(series, processor_info)

            self.processors[col] = processor_info
            transformed_features.append(features)

        # Combine all features
        combined_features = np.hstack(transformed_features)

        # Apply standard scaling
        self._scaler = StandardScaler()
        scaled_features = self._scaler.fit_transform(combined_features)

        return scaled_features

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        """
        Transform new data using fitted processors.

        Args:
            df: Input DataFrame

        Returns:
            Transformed feature matrix
        """
        transformed_features = []

        for col in self.processors.keys():
            # Handle missing columns
            if col not in df.columns:
                # Create a series of NaN values
                series = pd.Series([np.nan] * len(df), name=col)
            else:
                series = df[col]

            processor_info = self.processors[col]
            feature_type = processor_info["type"]

            if feature_type == "numeric":
                features = self._transform_numeric(series, processor_info)
            elif feature_type == "ordinal":
                features = self._transform_ordinal(series, processor_info)
            elif feature_type == "text_list":
                features = self._transform_text_list(series, processor_info)
            elif feature_type == "list_dummy":
                features = self._transform_list_dummy(series, processor_info)
            else:  # categorical
                features = self._transform_categorical(series, processor_info)

            transformed_features.append(features)

        # Combine all features
        combined_features = np.hstack(transformed_features)

        # Apply standard scaling
        scaled_features = self._scaler.transform(combined_features)

        return scaled_features

    def _fit_numeric(self, series: pd.Series, col_name: str) -> Dict[str, Any]:
        """Fit numeric feature processor."""
        median_value = series.median()
        self.feature_names.append(col_name)

        return {"type": "numeric", "median": median_value, "feature_names": [col_name]}

    def _transform_numeric(
        self, series: pd.Series, processor_info: Dict[str, Any]
    ) -> np.ndarray:
        """Transform numeric features."""
        # Fill missing values with median
        filled_series = series.fillna(processor_info["median"])
        return filled_series.values.reshape(-1, 1)

    def _fit_ordinal(self, series: pd.Series, col_name: str) -> Dict[str, Any]:
        """Fit ordinal feature processor."""
        mapping = self._get_ordinal_mapping(series)
        self.feature_names.append(col_name)

        return {
            "type": "ordinal",
            "mapping": mapping,
            "default_value": min(mapping.values()) if mapping else 0,
            "feature_names": [col_name],
        }

    def _transform_ordinal(
        self, series: pd.Series, processor_info: Dict[str, Any]
    ) -> np.ndarray:
        """Transform ordinal features."""
        mapping = processor_info["mapping"]
        default_value = processor_info["default_value"]

        # Convert to string and map
        str_series = series.astype(str)
        mapped_values = str_series.map(mapping).fillna(default_value)

        return mapped_values.values.reshape(-1, 1)

    def _fit_categorical(self, series: pd.Series, col_name: str) -> Dict[str, Any]:
        """Fit categorical feature processor."""
        # Add 'Unknown' to handle unseen categories
        unique_values = list(series.dropna().unique()) + ["Unknown"]

        encoder = LabelEncoder()
        encoder.fit(unique_values)
        self.feature_names.append(col_name)

        return {"type": "categorical", "encoder": encoder, "feature_names": [col_name]}

    def _transform_categorical(
        self, series: pd.Series, processor_info: Dict[str, Any]
    ) -> np.ndarray:
        """Transform categorical features."""
        encoder = processor_info["encoder"]

        # Fill missing values with 'Unknown'
        filled_series = series.fillna("Unknown").astype(str)

        # Handle unseen categories
        def safe_transform(value):
            try:
                return encoder.transform([value])[0]
            except ValueError:
                # Use 'Unknown' for unseen categories
                return encoder.transform(["Unknown"])[0]

        encoded_values = filled_series.apply(safe_transform)
        return encoded_values.values.reshape(-1, 1)

    def _fit_text_list(self, series: pd.Series, col_name: str) -> Dict[str, Any]:
        """Fit text list feature processor."""
        # Clean text lists
        cleaned_series = self._clean_text_lists(series)

        # Fit TF-IDF vectorizer
        vectorizer = TfidfVectorizer(
            max_features=10,
            stop_words="english",
            min_df=2,
            token_pattern=r"[a-zA-Z0-9_]+",
        )

        try:
            vectorizer.fit(cleaned_series.fillna(""))
            feature_names = [
                f"{col_name}_tfidf_{i}"
                for i in range(len(vectorizer.get_feature_names_out()))
            ]
        except ValueError:
            # Fallback if TF-IDF fails
            feature_names = [f"{col_name}_tfidf_0"]
            vectorizer = None

        self.feature_names.extend(feature_names)

        return {
            "type": "text_list",
            "vectorizer": vectorizer,
            "feature_names": feature_names,
        }

    def _transform_text_list(
        self, series: pd.Series, processor_info: Dict[str, Any]
    ) -> np.ndarray:
        """Transform text list features."""
        vectorizer = processor_info["vectorizer"]

        if vectorizer is None:
            # Return zeros if vectorizer failed during fitting
            return np.zeros((len(series), 1))

        # Clean text lists
        cleaned_series = self._clean_text_lists(series)

        try:
            # Transform using TF-IDF
            tfidf_matrix = vectorizer.transform(cleaned_series.fillna(""))
            return tfidf_matrix.toarray()
        except Exception:
            # Fallback if transformation fails
            return np.zeros((len(series), len(processor_info["feature_names"])))

    def _clean_text_lists(self, series: pd.Series) -> pd.Series:
        """Clean text list format for TF-IDF processing."""

        def clean_text(text):
            if pd.isna(text):
                return ""

            text_str = str(text)
            # Remove brackets and quotes
            cleaned = (
                text_str.replace("[", "")
                .replace("]", "")
                .replace("'", "")
                .replace('"', "")
            )
            # Replace commas with spaces
            cleaned = cleaned.replace(",", " ")
            return cleaned.strip()

        return series.apply(clean_text)

    def _fit_list_dummy(self, series: pd.Series, col_name: str) -> Dict[str, Any]:
        """Fit list dummy variable processor."""
        # Extract all unique items from all lists
        all_items = set()

        for value in series:
            if pd.isna(value):
                continue

            # Parse the list items
            items = self._parse_list_items(str(value))
            all_items.update(items)

        # Sort items for consistent ordering
        unique_items = sorted(list(all_items))

        # Create feature names
        feature_names = [f"{col_name}_{item}" for item in unique_items]
        self.feature_names.extend(feature_names)

        return {
            "type": "list_dummy",
            "unique_items": unique_items,
            "feature_names": feature_names,
        }

    def _transform_list_dummy(
        self, series: pd.Series, processor_info: Dict[str, Any]
    ) -> np.ndarray:
        """Transform list features into dummy variables."""
        unique_items = processor_info["unique_items"]
        n_samples = len(series)
        n_features = len(unique_items)

        # Initialize dummy matrix
        dummy_matrix = np.zeros((n_samples, n_features))

        for i, value in enumerate(series):
            if pd.isna(value):
                continue  # Leave as zeros for missing values

            # Parse the list items for this sample
            items = self._parse_list_items(str(value))

            # Set 1 for each item that appears in this sample
            for item in items:
                if item in unique_items:
                    item_idx = unique_items.index(item)
                    dummy_matrix[i, item_idx] = 1

        return dummy_matrix

    def _parse_list_items(self, value_str: str) -> List[str]:
        """Parse list items from string representation."""
        if not value_str or value_str.strip() == "":
            return []

        # Clean the string similar to _clean_text_lists but preserve individual items
        cleaned = (
            value_str.replace("[", "")
            .replace("]", "")
            .replace("'", "")
            .replace('"', "")
            .strip()
        )

        # Split by commas and clean each item
        items = [item.strip() for item in cleaned.split(",")]

        # Filter out empty items
        items = [item for item in items if item and item.strip()]

        return items

    def get_feature_info(self) -> List[Dict[str, Any]]:
        """
        Get information about processed features.

        Returns:
            List of feature information dictionaries
        """
        feature_info = []

        for col, processor_info in self.processors.items():
            info = {
                "column": col,
                "type": processor_info["type"],
                "feature_names": processor_info["feature_names"],
            }

            if processor_info["type"] == "ordinal" and "mapping" in processor_info:
                info["mapping"] = processor_info["mapping"]
            elif (
                processor_info["type"] == "categorical" and "encoder" in processor_info
            ):
                info["categories"] = list(processor_info["encoder"].classes_)
            elif (
                processor_info["type"] == "list_dummy"
                and "unique_items" in processor_info
            ):
                info["unique_items"] = processor_info["unique_items"]

            feature_info.append(info)

        return feature_info
