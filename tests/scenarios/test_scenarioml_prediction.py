"""
Tests for Prediction class.

Tests prediction functionality, probability estimation, persistence,
and error handling for production scenarios.
"""

import pytest
import numpy as np
import pandas as pd
import tempfile
import os
import sys
from pathlib import Path
from unittest.mock import Mock

# Add tests directory to path for importing test data
tests_dir = Path(__file__).parent.parent
sys.path.insert(0, str(tests_dir))

from edsl.scenarios.scenarioml.prediction import Prediction
from edsl.scenarios.scenarioml.model_selector import ModelResult
from edsl.scenarios.scenarioml.feature_processor import FeatureProcessor
from scenarios.test_scenarioml_data import (
    get_sample_dataframe,
    get_prediction_test_scenarios
)


class TestPrediction:
    """Test suite for Prediction class."""

    def create_mock_prediction(self):
        """Create a mock prediction object for testing."""
        # Create mock model result
        mock_model = Mock()
        mock_model.predict.return_value = np.array([0, 1])
        mock_model.predict_proba.return_value = np.array([[0.8, 0.2], [0.3, 0.7]])

        # Create mock label encoder
        from sklearn.preprocessing import LabelEncoder
        label_encoder = LabelEncoder()
        label_encoder.fit(['No', 'Yes'])

        model_result = ModelResult(
            name='test_model',
            model=mock_model,
            cv_score=0.85,
            cv_std=0.05,
            test_score=0.80,
            overfitting_gap=0.05,
            preprocessing_pipeline={'label_encoder': label_encoder},
            feature_names=['feature1', 'feature2'],
            train_score=0.85,
            selection_score=0.75,
            problem_type='classification'
        )

        # Create mock feature processor
        feature_processor = Mock(spec=FeatureProcessor)
        feature_processor.transform.return_value = np.array([[1, 2], [3, 4]])
        feature_processor.get_feature_info.return_value = [
            {'column': 'feature1', 'type': 'numeric', 'feature_names': ['feature1']},
            {'column': 'feature2', 'type': 'categorical', 'feature_names': ['feature2']}
        ]
        feature_processor.processors = {
            'feature1': {'type': 'numeric', 'feature_names': ['feature1']},
            'feature2': {'type': 'categorical', 'feature_names': ['feature2']}
        }

        return Prediction(
            model_result=model_result,
            feature_processor=feature_processor,
            target_column='target'
        )

    def test_initialization(self):
        """Test Prediction object initialization."""
        prediction = self.create_mock_prediction()

        # Should initialize properly
        assert prediction.target_column == 'target'
        assert prediction.version == '0.1.0'
        assert prediction.label_encoder is not None
        assert prediction.model_result is not None

    def test_single_prediction(self):
        """Test making predictions on single scenarios."""
        prediction = self.create_mock_prediction()

        # Test single scenario
        scenario = {'feature1': 10, 'feature2': 'A'}
        result = prediction.predict(scenario)

        # Should return single string prediction
        assert isinstance(result, str)
        assert result in ['Yes', 'No']

    def test_batch_prediction(self):
        """Test making predictions on multiple scenarios."""
        prediction = self.create_mock_prediction()

        # Test multiple scenarios
        scenarios = [
            {'feature1': 10, 'feature2': 'A'},
            {'feature1': 20, 'feature2': 'B'}
        ]
        results = prediction.predict(scenarios)

        # Should return list of string predictions
        assert isinstance(results, list)
        assert len(results) == 2
        assert all(isinstance(r, str) for r in results)
        assert all(r in ['Yes', 'No'] for r in results)

    def test_single_prediction_proba(self):
        """Test probability predictions on single scenarios."""
        prediction = self.create_mock_prediction()

        # Test single scenario
        scenario = {'feature1': 10, 'feature2': 'A'}
        result = prediction.predict_proba(scenario)

        # Should return probability dictionary
        assert isinstance(result, dict)
        assert 'Yes' in result
        assert 'No' in result
        assert abs(result['Yes'] + result['No'] - 1.0) < 1e-6  # Should sum to 1

    def test_batch_prediction_proba(self):
        """Test probability predictions on multiple scenarios."""
        prediction = self.create_mock_prediction()

        # Test multiple scenarios
        scenarios = [
            {'feature1': 10, 'feature2': 'A'},
            {'feature1': 20, 'feature2': 'B'}
        ]
        results = prediction.predict_proba(scenarios)

        # Should return list of probability dictionaries
        assert isinstance(results, list)
        assert len(results) == 2
        assert all(isinstance(r, dict) for r in results)

        for result in results:
            assert 'Yes' in result
            assert 'No' in result
            assert abs(result['Yes'] + result['No'] - 1.0) < 1e-6

    def test_diagnostics(self):
        """Test diagnostics functionality."""
        prediction = self.create_mock_prediction()

        diagnostics = prediction.diagnostics()

        # Should return comprehensive diagnostics
        required_keys = [
            'model_name', 'cv_score', 'test_score', 'overfitting_gap',
            'feature_count', 'target_column', 'target_classes',
            'feature_names', 'version'
        ]

        for key in required_keys:
            assert key in diagnostics

        assert diagnostics['model_name'] == 'test_model'
        assert diagnostics['target_column'] == 'target'
        assert diagnostics['version'] == '0.1.0'

    def test_scenario_validation(self):
        """Test scenario validation functionality."""
        prediction = self.create_mock_prediction()

        # Valid scenario
        valid_scenario = {'feature1': 10, 'feature2': 'A'}
        validation = prediction.validate_scenario(valid_scenario)

        assert 'valid' in validation
        assert 'warnings' in validation
        assert 'errors' in validation

        # Scenario with missing features
        missing_scenario = {'feature1': 10}  # Missing feature2
        validation = prediction.validate_scenario(missing_scenario)

        assert validation['missing_features'] == ['feature2']

        # Scenario with extra features
        extra_scenario = {'feature1': 10, 'feature2': 'A', 'extra_feature': 'X'}
        validation = prediction.validate_scenario(extra_scenario)

        assert validation['extra_features'] == ['extra_feature']

    def test_feature_importance(self):
        """Test feature importance extraction."""
        prediction = self.create_mock_prediction()

        # Mock the model to have feature importance
        prediction.model_result.model.feature_importances_ = np.array([0.6, 0.4])

        importance = prediction.get_feature_importance()

        # Should return importance dictionary
        assert isinstance(importance, dict)
        assert len(importance) == 2
        assert 'feature1' in importance
        assert 'feature2' in importance

        # Should sum to 1
        total_importance = sum(importance.values())
        assert abs(total_importance - 1.0) < 1e-6

    def test_save_and_load(self):
        """Test saving and loading prediction objects."""
        # Create a prediction with real (serializable) objects instead of mocks
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.preprocessing import LabelEncoder

        # Create real model and fit it with dummy data
        real_model = RandomForestClassifier(n_estimators=10, random_state=42)
        X_dummy = np.array([[1, 2], [3, 4], [5, 6], [7, 8]])
        y_dummy = np.array([0, 1, 0, 1])
        real_model.fit(X_dummy, y_dummy)

        # Create real label encoder
        label_encoder = LabelEncoder()
        label_encoder.fit(['No', 'Yes'])

        # Create real model result
        model_result = ModelResult(
            name='test_model',
            model=real_model,
            cv_score=0.85,
            cv_std=0.05,
            test_score=0.80,
            overfitting_gap=0.05,
            preprocessing_pipeline={'label_encoder': label_encoder},
            feature_names=['feature1', 'feature2'],
            train_score=0.85,
            selection_score=0.75,
            problem_type='classification'
        )

        # Create real feature processor
        feature_processor = FeatureProcessor()
        # Initialize it with dummy data to make it serializable
        dummy_df = pd.DataFrame({
            'feature1': [1, 2, 3, 4],
            'feature2': ['A', 'B', 'A', 'B'],
            'target': ['No', 'Yes', 'No', 'Yes']
        })
        feature_processor.fit_transform(dummy_df, 'target')

        prediction = Prediction(
            model_result=model_result,
            feature_processor=feature_processor,
            target_column='target'
        )

        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.joblib') as tmp_file:
            tmp_path = tmp_file.name

        try:
            # Save prediction object
            prediction.save(tmp_path)

            # Check file was created
            assert os.path.exists(tmp_path)

            # Load prediction object
            loaded_prediction = Prediction.load(tmp_path)

            # Should have same properties
            assert loaded_prediction.target_column == prediction.target_column
            assert loaded_prediction.version == prediction.version

        finally:
            # Clean up
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_save_error_handling(self):
        """Test error handling during save operations."""
        prediction = self.create_mock_prediction()

        # Try to save to invalid path
        invalid_path = '/nonexistent/directory/file.joblib'

        with pytest.raises(ValueError, match="Failed to save"):
            prediction.save(invalid_path)

    def test_load_error_handling(self):
        """Test error handling during load operations."""
        # Try to load from nonexistent file
        with pytest.raises(ValueError, match="Failed to load"):
            Prediction.load('/nonexistent/file.joblib')

    def test_missing_model_features(self):
        """Test prediction with scenarios missing expected features."""
        prediction = self.create_mock_prediction()

        # Configure feature processor to handle missing columns
        def mock_transform(df):
            # Simulate handling missing columns by returning fixed-size array
            return np.array([[1, 0]] * len(df))

        prediction.feature_processor.transform = mock_transform

        # Scenario missing features
        scenario = {'feature1': 10}  # Missing feature2

        # Should handle gracefully
        result = prediction.predict(scenario)
        assert isinstance(result, str)

    def test_model_without_predict_proba(self):
        """Test handling of models without predict_proba method."""
        prediction = self.create_mock_prediction()

        # Remove predict_proba method
        delattr(prediction.model_result.model, 'predict_proba')

        scenario = {'feature1': 10, 'feature2': 'A'}

        # Should fallback to hard predictions
        result = prediction.predict_proba(scenario)

        assert isinstance(result, dict)
        assert sum(result.values()) == 1.0  # Should still sum to 1

    def test_summary_generation(self):
        """Test summary string generation."""
        prediction = self.create_mock_prediction()

        summary = prediction.summary()

        # Should return formatted string
        assert isinstance(summary, str)
        assert 'ScenarioML Prediction Model Summary' in summary
        assert 'test_model' in summary
        assert 'target' in summary

    def test_repr_method(self):
        """Test string representation."""
        prediction = self.create_mock_prediction()

        repr_str = repr(prediction)

        # Should contain key information
        assert 'Prediction' in repr_str
        assert 'test_model' in repr_str
        assert 'target' in repr_str

    def test_prediction_error_handling(self):
        """Test error handling during prediction."""
        prediction = self.create_mock_prediction()

        # Configure feature processor to raise an error
        prediction.feature_processor.transform.side_effect = Exception("Transform error")

        scenario = {'feature1': 10, 'feature2': 'A'}

        # Should raise ValueError with helpful message
        with pytest.raises(ValueError, match="Prediction failed"):
            prediction.predict(scenario)

    def test_version_compatibility_warning(self):
        """Test version compatibility checking."""
        # Create mock saved data with different version
        mock_save_data = {
            'model_result': Mock(),
            'feature_processor': Mock(),
            'target_column': 'target',
            'version': '0.0.1'  # Different version
        }

        with tempfile.NamedTemporaryFile(delete=False, suffix='.joblib') as tmp_file:
            tmp_path = tmp_file.name

        try:
            # Mock joblib.load to return our data
            import joblib
            original_load = joblib.load
            joblib.load = Mock(return_value=mock_save_data)

            # Should warn about version mismatch
            with pytest.warns(UserWarning, match="Version mismatch"):
                Prediction.load(tmp_path)

        finally:
            # Restore original function
            joblib.load = original_load
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_end_to_end_workflow(self):
        """Test complete end-to-end workflow with real data processing."""
        # This test uses actual components (not mocks) for integration testing
        df = get_sample_dataframe()

        # Skip if we don't have enough samples
        if len(df) < 10:
            pytest.skip("Insufficient data for end-to-end test")

        from edsl.scenarios.scenarioml.feature_processor import FeatureProcessor
        from edsl.scenarios.scenarioml.model_selector import ModelSelector

        # Process features
        feature_processor = FeatureProcessor()
        X = feature_processor.fit_transform(df, 'will_renew')
        y = df['will_renew'].values

        # Train model
        model_selector = ModelSelector()
        results = model_selector.compare_models(X, y, feature_processor.feature_names)
        best_model = model_selector.select_best_model(results)

        # Create prediction object
        prediction = Prediction(
            model_result=best_model,
            feature_processor=feature_processor,
            target_column='will_renew'
        )

        # Test predictions on new scenarios
        test_scenarios = get_prediction_test_scenarios()

        for scenario in test_scenarios:
            # Should make predictions without errors
            pred = prediction.predict(scenario)
            proba = prediction.predict_proba(scenario)

            assert isinstance(pred, str)
            assert isinstance(proba, dict)
            assert abs(sum(proba.values()) - 1.0) < 1e-6