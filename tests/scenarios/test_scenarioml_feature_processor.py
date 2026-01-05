"""
Tests for FeatureProcessor class.

Tests automatic feature type detection, preprocessing transformations,
and handling of edge cases like missing values and unseen categories.
"""

import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Add tests directory to path for importing test data
tests_dir = Path(__file__).parent.parent
sys.path.insert(0, str(tests_dir))

from edsl.scenarios.scenarioml.feature_processor import FeatureProcessor
from scenarios.test_scenarioml_data import get_sample_dataframe, get_problematic_data


class TestFeatureProcessor:
    """Test suite for FeatureProcessor class."""

    def test_numeric_feature_detection(self):
        """Test detection of numeric features."""
        processor = FeatureProcessor()

        # Test integer column
        int_series = pd.Series([1, 2, 3, 4, 5])
        assert processor.detect_feature_type(int_series) == 'numeric'

        # Test float column
        float_series = pd.Series([1.1, 2.2, 3.3, 4.4, 5.5])
        assert processor.detect_feature_type(float_series) == 'numeric'

    def test_categorical_feature_detection(self):
        """Test detection of categorical features."""
        processor = FeatureProcessor()

        # Test string categories
        cat_series = pd.Series(['A', 'B', 'C', 'A', 'B'])
        assert processor.detect_feature_type(cat_series) == 'categorical'

    def test_ordinal_feature_detection(self):
        """Test detection of ordinal features."""
        processor = FeatureProcessor()

        # Test employee size pattern
        size_series = pd.Series(['1-5', '6-20', '21-100', '101-500', 'More than 500'])
        assert processor.detect_feature_type(size_series) == 'ordinal'

        # Test satisfaction pattern
        satisfaction_series = pd.Series(['Strongly Disagree', 'Disagree', 'Neutral', 'Agree', 'Strongly Agree'])
        assert processor.detect_feature_type(satisfaction_series) == 'ordinal'

    def test_text_list_feature_detection(self):
        """Test detection of text list features."""
        # With default (dummy) encoding, lists should be detected as list_dummy
        processor = FeatureProcessor()

        # Test bracketed lists
        text_series = pd.Series(["['Tool A', 'Tool B']", "['Tool C']", "['Tool A', 'Tool D']"])
        assert processor.detect_feature_type(text_series) == 'list_dummy'

        # Test comma-separated lists
        comma_series = pd.Series(["Tool A, Tool B", "Tool C", "Tool A, Tool D"])
        assert processor.detect_feature_type(comma_series) == 'list_dummy'

        # Test with explicit TF-IDF encoding - should be text_list
        tfidf_processor = FeatureProcessor(list_encoding="tfidf")
        assert tfidf_processor.detect_feature_type(text_series) == 'text_list'

    def test_list_dummy_feature_detection(self):
        """Test detection of list dummy features when dummy encoding is enabled."""
        processor = FeatureProcessor(list_encoding="dummy")

        # Test bracketed lists - should be detected as list_dummy
        text_series = pd.Series(["['Tool A', 'Tool B']", "['Tool C']", "['Tool A', 'Tool D']"])
        assert processor.detect_feature_type(text_series) == 'list_dummy'

        # Test comma-separated lists - should be detected as list_dummy
        comma_series = pd.Series(["Tool A, Tool B", "Tool C", "Tool A, Tool D"])
        assert processor.detect_feature_type(comma_series) == 'list_dummy'

        # Test with TF-IDF encoding (default) - should still be text_list
        tfidf_processor = FeatureProcessor(list_encoding="tfidf")
        assert tfidf_processor.detect_feature_type(text_series) == 'text_list'

    def test_fit_transform_basic(self):
        """Test basic fit_transform functionality."""
        processor = FeatureProcessor()
        df = get_sample_dataframe()
        target_col = 'will_renew'

        # Should run without errors
        X = processor.fit_transform(df, target_col)

        # Check output shape
        assert X.shape[0] == len(df)  # Same number of rows
        assert X.shape[1] > 0  # At least some features
        assert len(processor.feature_names) > 0

    def test_transform_consistency(self):
        """Test that transform produces consistent results."""
        processor = FeatureProcessor()
        df = get_sample_dataframe()
        target_col = 'will_renew'

        # Fit on full data
        X1 = processor.fit_transform(df, target_col)

        # Transform same data again
        X2 = processor.transform(df)

        # Should be identical
        np.testing.assert_array_equal(X1, X2)

    def test_missing_values_handling(self):
        """Test handling of missing values."""
        processor = FeatureProcessor()

        # Create data with missing values
        data_with_missing = pd.DataFrame({
            'numeric_col': [1, 2, None, 4, 5],
            'cat_col': ['A', 'B', None, 'A', 'B'],
            'target': ['Yes', 'No', 'Yes', 'No', 'Yes']
        })

        # Should handle missing values gracefully
        X = processor.fit_transform(data_with_missing, 'target')
        assert not np.any(np.isnan(X))

    def test_unseen_categories(self):
        """Test handling of unseen categories during transform."""
        processor = FeatureProcessor()

        # Train data
        train_df = pd.DataFrame({
            'category': ['A', 'B', 'A', 'B'],
            'target': ['Yes', 'No', 'Yes', 'No']
        })

        # Test data with unseen category
        test_df = pd.DataFrame({
            'category': ['A', 'C', 'B']  # 'C' is unseen
        })

        # Fit on training data
        processor.fit_transform(train_df, 'target')

        # Should handle unseen category gracefully
        X_test = processor.transform(test_df)
        assert X_test.shape[0] == len(test_df)
        assert not np.any(np.isnan(X_test))

    def test_missing_columns_in_transform(self):
        """Test handling of missing columns during transform."""
        processor = FeatureProcessor()

        # Train data
        train_df = pd.DataFrame({
            'col1': [1, 2, 3, 4],
            'col2': ['A', 'B', 'A', 'B'],
            'target': ['Yes', 'No', 'Yes', 'No']
        })

        # Test data missing col2
        test_df = pd.DataFrame({
            'col1': [1, 2, 3]
            # col2 is missing
        })

        # Fit on training data
        processor.fit_transform(train_df, 'target')

        # Should handle missing column gracefully
        X_test = processor.transform(test_df)
        assert X_test.shape[0] == len(test_df)
        assert not np.any(np.isnan(X_test))

    def test_ordinal_mapping(self):
        """Test ordinal feature mapping."""
        processor = FeatureProcessor()

        # Create ordinal data
        df = pd.DataFrame({
            'size': ['1-5', '6-20', '101-500', '21-100'],
            'target': ['A', 'B', 'A', 'B']
        })

        processor.fit_transform(df, 'target')

        # Check that ordinal mapping was applied
        size_processor = processor.processors['size']
        assert size_processor['type'] == 'ordinal'
        assert 'mapping' in size_processor
        assert size_processor['mapping']['1-5'] < size_processor['mapping']['101-500']

    def test_text_list_processing(self):
        """Test text list feature processing with TF-IDF encoding."""
        # Explicitly use TF-IDF encoding since dummy is now default
        processor = FeatureProcessor(list_encoding="tfidf")

        # Create text list data
        df = pd.DataFrame({
            'tools': ["['Tool A', 'Tool B']", "['Tool C']", "['Tool A']"],
            'target': ['Yes', 'No', 'Yes']
        })

        X = processor.fit_transform(df, 'target')

        # Should create TF-IDF features
        tools_processor = processor.processors['tools']
        assert tools_processor['type'] == 'text_list'
        assert len(tools_processor['feature_names']) > 0

    def test_list_dummy_processing(self):
        """Test list dummy variable processing (default behavior)."""
        processor = FeatureProcessor()  # Should use dummy encoding by default

        # Create test data with your example format
        df = pd.DataFrame({
            'tools': ["['a', 'b', 'c']", "['b', 'c']", "['a']"],
            'target': ['Yes', 'No', 'Yes']
        })

        X = processor.fit_transform(df, 'target')

        # Check that dummy variables were created
        tools_processor = processor.processors['tools']
        assert tools_processor['type'] == 'list_dummy'

        # Should have unique items a, b, c
        expected_items = ['a', 'b', 'c']
        assert tools_processor['unique_items'] == expected_items

        # Should have 3 feature names (one for each item)
        expected_feature_names = ['tools_a', 'tools_b', 'tools_c']
        assert tools_processor['feature_names'] == expected_feature_names

        # Test transformation results
        # First row ['a', 'b', 'c'] should be [1, 1, 1] (after scaling)
        # Second row ['b', 'c'] should be [0, 1, 1] (after scaling)
        # Third row ['a'] should be [1, 0, 0] (after scaling)

        # Since StandardScaler is applied, we need to check the raw dummy matrix
        # Let's test the transform method on the same data to get raw dummies
        raw_dummies = processor._transform_list_dummy(df['tools'], tools_processor)

        # Check the binary patterns
        expected_dummies = np.array([
            [1.0, 1.0, 1.0],  # ['a', 'b', 'c'] -> a=1, b=1, c=1
            [0.0, 1.0, 1.0],  # ['b', 'c'] -> a=0, b=1, c=1
            [1.0, 0.0, 0.0]   # ['a'] -> a=1, b=0, c=0
        ])
        np.testing.assert_array_equal(raw_dummies, expected_dummies)

    def test_list_dummy_with_missing_values(self):
        """Test list dummy processing with missing values."""
        processor = FeatureProcessor()  # Uses dummy encoding by default

        df = pd.DataFrame({
            'tools': ["['a', 'b']", None, "['a', 'c']", ""],
            'target': ['Yes', 'No', 'Yes', 'No']
        })

        X = processor.fit_transform(df, 'target')

        # Missing/empty values should be handled gracefully
        tools_processor = processor.processors['tools']
        assert tools_processor['type'] == 'list_dummy'

        # Should still extract unique items from non-null values
        expected_items = ['a', 'b', 'c']
        assert tools_processor['unique_items'] == expected_items

        # Test raw transformation
        raw_dummies = processor._transform_list_dummy(df['tools'], tools_processor)
        expected_dummies = np.array([
            [1.0, 1.0, 0.0],  # ['a', 'b'] -> a=1, b=1, c=0
            [0.0, 0.0, 0.0],  # None -> a=0, b=0, c=0
            [1.0, 0.0, 1.0],  # ['a', 'c'] -> a=1, b=0, c=1
            [0.0, 0.0, 0.0]   # "" -> a=0, b=0, c=0
        ])
        np.testing.assert_array_equal(raw_dummies, expected_dummies)

    def test_list_dummy_different_formats(self):
        """Test list dummy processing with different input formats."""
        processor = FeatureProcessor()  # Uses dummy encoding by default

        df = pd.DataFrame({
            'tools': [
                "['Tool A', 'Tool B']",  # Bracketed with quotes
                "Tool A, Tool B",        # Comma-separated
                '["Tool C", "Tool A"]',  # Double quotes
                "Tool B,Tool C",         # No spaces after comma
            ],
            'target': ['A', 'B', 'A', 'B']
        })

        X = processor.fit_transform(df, 'target')

        tools_processor = processor.processors['tools']
        assert tools_processor['type'] == 'list_dummy'

        # Should extract all unique tools
        expected_items = ['Tool A', 'Tool B', 'Tool C']
        assert sorted(tools_processor['unique_items']) == expected_items

    def test_parse_list_items(self):
        """Test the _parse_list_items helper method."""
        processor = FeatureProcessor()  # Uses dummy encoding by default

        # Test different formats
        assert processor._parse_list_items("['a', 'b', 'c']") == ['a', 'b', 'c']
        assert processor._parse_list_items('["x", "y"]') == ['x', 'y']
        assert processor._parse_list_items("item1, item2") == ['item1', 'item2']
        assert processor._parse_list_items("single") == ['single']
        assert processor._parse_list_items("") == []
        assert processor._parse_list_items("  ") == []

    def test_get_feature_info(self):
        """Test feature information retrieval."""
        processor = FeatureProcessor()
        df = get_sample_dataframe()

        processor.fit_transform(df, 'will_renew')
        feature_info = processor.get_feature_info()

        # Should return info for all processed features
        assert len(feature_info) > 0

        # Each feature should have required fields
        for info in feature_info:
            assert 'column' in info
            assert 'type' in info
            assert 'feature_names' in info

    def test_problematic_data(self):
        """Test processing of problematic data."""
        processor = FeatureProcessor()

        # Convert problematic data to DataFrame
        problematic_df = pd.DataFrame(get_problematic_data())

        # Should handle problematic data gracefully
        X = processor.fit_transform(problematic_df, 'target')

        # Should produce valid output
        assert X.shape[0] == len(problematic_df)
        assert not np.any(np.isnan(X))

    def test_empty_data_handling(self):
        """Test handling of edge cases."""
        processor = FeatureProcessor()

        # Test with single-value column
        single_value_df = pd.DataFrame({
            'constant': ['A', 'A', 'A'],
            'target': ['Yes', 'No', 'Yes']
        })

        # Should handle constant features
        X = processor.fit_transform(single_value_df, 'target')
        assert X.shape[0] == 3

    def test_feature_scaling(self):
        """Test that features are properly scaled."""
        processor = FeatureProcessor()

        # Create data with different scales
        df = pd.DataFrame({
            'small_values': [0.1, 0.2, 0.3, 0.4],
            'large_values': [1000, 2000, 3000, 4000],
            'target': ['A', 'B', 'A', 'B']
        })

        X = processor.fit_transform(df, 'target')

        # Features should be standardized (approximately mean=0, std=1)
        for col_idx in range(X.shape[1]):
            col_mean = np.mean(X[:, col_idx])
            col_std = np.std(X[:, col_idx])

            # Should be approximately standardized
            assert abs(col_mean) < 1e-10  # Very close to 0
            assert abs(col_std - 1.0) < 0.1  # Close to 1