"""
Tests for ModelSelector class.

Tests model comparison, selection algorithms, overfitting prevention,
and diagnostic capabilities.
"""

import pytest
import numpy as np
import pandas as pd
import warnings
import sys
from pathlib import Path

# Add tests directory to path for importing test data
tests_dir = Path(__file__).parent.parent
sys.path.insert(0, str(tests_dir))

from edsl.scenarios.scenarioml.model_selector import ModelSelector, ModelResult
from edsl.scenarios.scenarioml.feature_processor import FeatureProcessor
from scenarios.test_scenarioml_data import get_sample_dataframe, get_minimal_test_data


class TestModelSelector:
    """Test suite for ModelSelector class."""

    def test_initialization(self):
        """Test ModelSelector initialization."""
        selector = ModelSelector()

        # Should initialize with default random state
        assert selector.random_state == 42

        # Should have models configured
        assert len(selector._models) > 0
        assert 'logistic_ridge' in selector._models
        assert 'logistic_lasso' in selector._models

    def test_model_comparison_basic(self):
        """Test basic model comparison functionality."""
        selector = ModelSelector()

        # Prepare sample data
        df = get_sample_dataframe()
        processor = FeatureProcessor()
        X = processor.fit_transform(df, 'will_renew')
        y = df['will_renew'].values

        # Run model comparison
        results = selector.compare_models(X, y, processor.feature_names)

        # Should return results
        assert len(results) > 0
        assert all(isinstance(result, ModelResult) for result in results)

        # Each result should have required fields
        for result in results:
            assert hasattr(result, 'name')
            assert hasattr(result, 'cv_score')
            assert hasattr(result, 'test_score')
            assert hasattr(result, 'overfitting_gap')
            assert result.cv_score > 0
            assert result.test_score > 0
            assert result.overfitting_gap >= 0

    def test_best_model_selection(self):
        """Test best model selection algorithm."""
        selector = ModelSelector()

        # Prepare sample data
        df = get_sample_dataframe()
        processor = FeatureProcessor()
        X = processor.fit_transform(df, 'will_renew')
        y = df['will_renew'].values

        # Run model comparison and selection
        results = selector.compare_models(X, y, processor.feature_names)
        best_model = selector.select_best_model(results)

        # Should select a valid model
        assert isinstance(best_model, ModelResult)
        assert best_model in results
        assert hasattr(best_model, 'selection_score')

        # Selection score should be computed for all models
        for result in results:
            assert hasattr(result, 'selection_score')
            assert result.selection_score is not None

    def test_overfitting_detection(self):
        """Test overfitting detection and penalization."""
        selector = ModelSelector()

        # Create mock results with different overfitting levels
        mock_results = [
            ModelResult(
                name='low_overfitting',
                model=None,
                cv_score=0.8,
                cv_std=0.1,
                test_score=0.75,
                overfitting_gap=0.05,  # Low overfitting
                preprocessing_pipeline={},
                feature_names=['f1', 'f2'],
                train_score=0.8
            ),
            ModelResult(
                name='high_overfitting',
                model=None,
                cv_score=0.8,
                cv_std=0.1,
                test_score=0.6,
                overfitting_gap=0.3,  # High overfitting
                preprocessing_pipeline={},
                feature_names=['f1', 'f2'],
                train_score=0.9
            )
        ]

        # Select best model
        best_model = selector.select_best_model(mock_results)

        # Should prefer low overfitting model despite lower training score
        assert best_model.name == 'low_overfitting'

    def test_data_validation(self):
        """Test data validation functionality."""
        selector = ModelSelector()

        # Test valid data
        X_valid = np.random.rand(100, 5)
        y_valid = np.random.choice(['A', 'B'], 100)

        # Should not raise error
        selector.validate_data(X_valid, y_valid)

        # Test invalid data - empty
        with pytest.raises(ValueError, match="Feature matrix is empty"):
            selector.validate_data(np.array([]), np.array([]))

        # Test mismatched dimensions
        with pytest.raises(ValueError, match="Feature matrix rows"):
            selector.validate_data(np.random.rand(10, 5), np.random.choice(['A', 'B'], 5))

        # Test insufficient classes
        y_single_class = np.array(['A'] * 10)
        with pytest.raises(ValueError, match="at least 2 classes"):
            selector.validate_data(np.random.rand(10, 5), y_single_class)

    def test_small_dataset_warning(self):
        """Test warnings for small datasets."""
        selector = ModelSelector()

        # Small dataset should trigger warning
        X_small = np.random.rand(20, 2)  # Reduced features to avoid ratio warning
        y_small = np.random.choice(['A', 'B'], 20)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            selector.validate_data(X_small, y_small)

            # Should warn about small dataset
            assert len(w) > 0
            warning_messages = [str(warning.message).lower() for warning in w]
            assert any("small dataset" in msg for msg in warning_messages)

    def test_feature_importance_extraction(self):
        """Test feature importance extraction from models."""
        selector = ModelSelector()

        # Prepare sample data
        df = get_sample_dataframe()
        processor = FeatureProcessor()
        X = processor.fit_transform(df, 'will_renew')
        y = df['will_renew'].values

        # Train a model
        results = selector.compare_models(X, y, processor.feature_names)
        best_model = selector.select_best_model(results)

        # Extract feature importance
        importance = selector.get_feature_importance(best_model)

        # Should return valid importance scores
        assert isinstance(importance, dict)
        assert len(importance) > 0

        # All importance scores should be positive and sum to 1
        importance_values = list(importance.values())
        assert all(val >= 0 for val in importance_values)
        assert abs(sum(importance_values) - 1.0) < 1e-6

    def test_model_diagnostics(self):
        """Test model comparison diagnostics."""
        selector = ModelSelector()

        # Prepare sample data
        df = get_sample_dataframe()
        processor = FeatureProcessor()
        X = processor.fit_transform(df, 'will_renew')
        y = df['will_renew'].values

        # Run model comparison
        results = selector.compare_models(X, y, processor.feature_names)

        # Get diagnostics
        diagnostics_df = selector.get_model_diagnostics(results)

        # Should return a DataFrame
        assert isinstance(diagnostics_df, pd.DataFrame)
        assert len(diagnostics_df) == len(results)

        # Should have required columns
        required_columns = ['Model', 'CV Score', 'Test Score', 'Overfitting Gap', 'Selection Score']
        for col in required_columns:
            assert col in diagnostics_df.columns

        # Should be sorted by selection score
        selection_scores = []
        for _, row in diagnostics_df.iterrows():
            score_str = row['Selection Score']
            if score_str != "N/A":
                selection_scores.append(float(score_str))

        # Scores should be in descending order
        assert selection_scores == sorted(selection_scores, reverse=True)

    def test_minimal_data_handling(self):
        """Test handling of minimal datasets."""
        selector = ModelSelector()

        # Create minimal valid dataset
        minimal_data = get_minimal_test_data()
        df = pd.DataFrame(minimal_data)

        processor = FeatureProcessor()
        X = processor.fit_transform(df, 'target')
        y = df['target'].values

        # Should handle minimal data gracefully
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # Ignore expected warnings
            results = selector.compare_models(X, y, processor.feature_names)

        # Should get at least one working model
        assert len(results) > 0

    def test_model_failures_handling(self):
        """Test graceful handling of model training failures."""
        selector = ModelSelector()

        # Create problematic data that might cause some models to fail
        X_problematic = np.array([[1, 0], [1, 0], [0, 1], [0, 1]])  # Linearly separable
        y_problematic = np.array(['A', 'A', 'B', 'B'])

        # Should handle model failures gracefully and still return results
        results = selector.compare_models(X_problematic, y_problematic, ['f1', 'f2'])

        # Should get at least one working model (may skip failed ones)
        assert len(results) >= 1

    def test_cross_validation_scoring(self):
        """Test cross-validation scoring consistency."""
        selector = ModelSelector()

        # Prepare sample data
        df = get_sample_dataframe()
        processor = FeatureProcessor()
        X = processor.fit_transform(df, 'will_renew')
        y = df['will_renew'].values

        # Run comparison multiple times with same random state
        results1 = selector.compare_models(X, y, processor.feature_names)
        results2 = selector.compare_models(X, y, processor.feature_names)

        # Results should be consistent (same random state)
        assert len(results1) == len(results2)

        # Compare scores for same models
        model_scores1 = {r.name: r.cv_score for r in results1}
        model_scores2 = {r.name: r.cv_score for r in results2}

        for model_name in model_scores1.keys():
            if model_name in model_scores2:
                # Scores should be identical (same random state)
                assert abs(model_scores1[model_name] - model_scores2[model_name]) < 1e-10

    def test_selection_algorithm_properties(self):
        """Test properties of the selection algorithm."""
        selector = ModelSelector()

        # Create mock results to test selection logic
        mock_results = [
            ModelResult(
                name='high_gap',
                model=None,
                cv_score=0.8,
                cv_std=0.2,  # High variance
                test_score=0.7,
                overfitting_gap=0.2,  # High overfitting
                preprocessing_pipeline={},
                feature_names=['f1'],
                train_score=0.9
            ),
            ModelResult(
                name='stable_model',
                model=None,
                cv_score=0.75,
                cv_std=0.05,  # Low variance
                test_score=0.73,
                overfitting_gap=0.02,  # Low overfitting
                preprocessing_pipeline={},
                feature_names=['f1'],
                train_score=0.75
            )
        ]

        best_model = selector.select_best_model(mock_results)

        # Should prefer stable model despite slightly lower test score
        assert best_model.name == 'stable_model'

        # Selection scores should penalize overfitting and variance
        assert mock_results[0].selection_score < mock_results[1].selection_score