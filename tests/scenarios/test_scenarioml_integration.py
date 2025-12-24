"""
Integration tests for ScenarioML package.

Tests the complete workflow from ScenarioList.predict() through
model training to making predictions on new data.
"""

import pytest
import pandas as pd
import warnings
import os
import tempfile
import sys
from pathlib import Path

# Add the parent directory to sys.path to import EDSL modules
parent_dir = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(parent_dir))

# Add tests directory to path for importing test data
tests_dir = Path(__file__).parent.parent
sys.path.insert(0, str(tests_dir))

from scenarios.test_scenarioml_data import get_sample_survey_data, get_minimal_test_data, get_prediction_test_scenarios


class TestScenarioMLIntegration:
    """Integration tests for the complete ScenarioML workflow."""

    def test_scenariolist_predict_basic_workflow(self):
        """Test basic predict workflow from ScenarioList."""
        # Create test data as if it came from ScenarioList
        survey_data = get_sample_survey_data()

        # Mock ScenarioList behavior
        class MockScenarioList:
            def __init__(self, data):
                self.data = data

            def __len__(self):
                return len(self.data)

            def to_pandas(self):
                return pd.DataFrame(self.data)

            def predict(self, y: str, **kwargs):
                """Implementation of the predict method we added to ScenarioList."""
                try:
                    # Import here to avoid circular imports
                    from edsl.scenarios.scenarioml.feature_processor import FeatureProcessor
                    from edsl.scenarios.scenarioml.model_selector import ModelSelector
                    from edsl.scenarios.scenarioml.prediction import Prediction
                    import pandas as pd
                except ImportError as e:
                    raise ImportError(
                        f"Missing required dependencies for ScenarioML: {str(e)}. "
                        "Please install with: pip install pandas scikit-learn"
                    ) from e

                # Validate inputs
                if not isinstance(y, str):
                    raise ValueError("Target variable 'y' must be a string column name")

                if len(self) == 0:
                    raise ValueError("Cannot train model on empty ScenarioList")

                # Convert to DataFrame
                df = self.to_pandas()

                # Validate target column
                if y not in df.columns:
                    available_cols = list(df.columns)
                    raise ValueError(
                        f"Target column '{y}' not found. Available columns: {available_cols}"
                    )

                # Check for minimum data requirements
                if len(df) < 10:
                    raise ValueError(
                        f"Insufficient data for training: {len(df)} samples. "
                        "Need at least 10 samples for reliable model training."
                    )

                # Initialize processors
                feature_processor = FeatureProcessor()
                model_selector = ModelSelector()

                # Process features
                X = feature_processor.fit_transform(df, y)
                y_values = df[y].values

                # Validate processed data
                model_selector.validate_data(X, y_values)

                # Compare models
                model_results = model_selector.compare_models(X, y_values, feature_processor.feature_names)

                if not model_results:
                    raise ValueError("No models could be trained successfully")

                # Select best model
                best_model = model_selector.select_best_model(model_results)

                # Create prediction object
                prediction = Prediction(
                    model_result=best_model,
                    feature_processor=feature_processor,
                    target_column=y
                )

                return prediction

        # Create mock ScenarioList
        scenario_list = MockScenarioList(survey_data)

        # Test the complete workflow
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # Ignore expected warnings about small dataset

            # Train model
            prediction = scenario_list.predict(y='will_renew')

            # Should return a Prediction object
            assert prediction is not None
            assert hasattr(prediction, 'predict')
            assert hasattr(prediction, 'predict_proba')
            assert hasattr(prediction, 'diagnostics')

            # Test prediction on new data
            test_scenarios = get_prediction_test_scenarios()

            for scenario in test_scenarios:
                # Should make predictions without errors
                pred = prediction.predict(scenario)
                proba = prediction.predict_proba(scenario)

                assert isinstance(pred, str)
                assert pred in ['Yes', 'No']
                assert isinstance(proba, dict)
                assert abs(sum(proba.values()) - 1.0) < 1e-6

    def test_feature_type_detection_integration(self):
        """Test automatic feature type detection in complete workflow."""
        # Data with all feature types
        mixed_data = [
            {
                'numeric_feature': 100,
                'categorical_feature': 'Category A',
                'ordinal_feature': 'Very Satisfied',
                'text_list_feature': "['Tool A', 'Tool B']",
                'target': 'Positive'
            },
            {
                'numeric_feature': 200,
                'categorical_feature': 'Category B',
                'ordinal_feature': 'Satisfied',
                'text_list_feature': "['Tool C']",
                'target': 'Negative'
            },
            {
                'numeric_feature': 150,
                'categorical_feature': 'Category A',
                'ordinal_feature': 'Neutral',
                'text_list_feature': "['Tool A', 'Tool D']",
                'target': 'Positive'
            },
            {
                'numeric_feature': 80,
                'categorical_feature': 'Category C',
                'ordinal_feature': 'Dissatisfied',
                'text_list_feature': "['Tool B', 'Tool C']",
                'target': 'Negative'
            },
            {
                'numeric_feature': 300,
                'categorical_feature': 'Category B',
                'ordinal_feature': 'Very Satisfied',
                'text_list_feature': "['Tool A']",
                'target': 'Positive'
            },
            {
                'numeric_feature': 120,
                'categorical_feature': 'Category A',
                'ordinal_feature': 'Satisfied',
                'text_list_feature': "['Tool D']",
                'target': 'Negative'
            }
        ] * 3  # Repeat to have enough samples

        from edsl.scenarios.scenarioml.feature_processor import FeatureProcessor
        from edsl.scenarios.scenarioml.model_selector import ModelSelector
        from edsl.scenarios.scenarioml.prediction import Prediction

        df = pd.DataFrame(mixed_data)

        # Process features
        feature_processor = FeatureProcessor()
        X = feature_processor.fit_transform(df, 'target')

        # Check that different feature types were detected correctly
        feature_info = feature_processor.get_feature_info()
        feature_types = {info['column']: info['type'] for info in feature_info}

        assert feature_types['numeric_feature'] == 'numeric'
        assert feature_types['categorical_feature'] == 'categorical'
        assert feature_types['ordinal_feature'] == 'ordinal'
        assert feature_types['text_list_feature'] == 'list_dummy'

        # Train model
        model_selector = ModelSelector()
        y_values = df['target'].values

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model_results = model_selector.compare_models(X, y_values, feature_processor.feature_names)
            best_model = model_selector.select_best_model(model_results)

        # Create prediction object
        prediction = Prediction(
            model_result=best_model,
            feature_processor=feature_processor,
            target_column='target'
        )

        # Test prediction with mixed feature types
        test_scenario = {
            'numeric_feature': 180,
            'categorical_feature': 'Category B',
            'ordinal_feature': 'Satisfied',
            'text_list_feature': "['Tool A', 'Tool B']"
        }

        pred = prediction.predict(test_scenario)
        proba = prediction.predict_proba(test_scenario)

        assert isinstance(pred, str)
        assert isinstance(proba, dict)

    def test_persistence_workflow(self):
        """Test save/load workflow in realistic scenario."""
        from edsl.scenarios.scenarioml.feature_processor import FeatureProcessor
        from edsl.scenarios.scenarioml.model_selector import ModelSelector
        from edsl.scenarios.scenarioml.prediction import Prediction

        # Train a model
        survey_data = get_sample_survey_data()
        df = pd.DataFrame(survey_data)

        feature_processor = FeatureProcessor()
        X = feature_processor.fit_transform(df, 'will_renew')
        y_values = df['will_renew'].values

        model_selector = ModelSelector()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model_results = model_selector.compare_models(X, y_values, feature_processor.feature_names)
            best_model = model_selector.select_best_model(model_results)

        # Create prediction object
        original_prediction = Prediction(
            model_result=best_model,
            feature_processor=feature_processor,
            target_column='will_renew'
        )

        # Test scenario
        test_scenario = {
            'business_type': 'SMB',
            'company_size': '21-100',
            'industry': 'Technology',
            'satisfaction_level': 'Satisfied'
        }

        # Get prediction from original model
        original_pred = original_prediction.predict(test_scenario)
        original_proba = original_prediction.predict_proba(test_scenario)

        # Save and load
        with tempfile.NamedTemporaryFile(delete=False, suffix='.joblib') as tmp_file:
            tmp_path = tmp_file.name

        try:
            # Save
            original_prediction.save(tmp_path)

            # Load
            loaded_prediction = Prediction.load(tmp_path)

            # Test that loaded prediction gives same results
            loaded_pred = loaded_prediction.predict(test_scenario)
            loaded_proba = loaded_prediction.predict_proba(test_scenario)

            assert loaded_pred == original_pred

            # Probabilities should be very close
            for class_name in original_proba.keys():
                assert abs(original_proba[class_name] - loaded_proba[class_name]) < 1e-6

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_error_handling_integration(self):
        """Test error handling in integrated workflow."""
        from edsl.scenarios.scenarioml.feature_processor import FeatureProcessor
        from edsl.scenarios.scenarioml.model_selector import ModelSelector

        # Test insufficient data
        insufficient_data = get_minimal_test_data()[:2]  # Only 2 samples
        df_insufficient = pd.DataFrame(insufficient_data)

        feature_processor = FeatureProcessor()

        with pytest.raises(ValueError, match="Insufficient data"):
            feature_processor.fit_transform(df_insufficient, 'target')

        # Test missing target column
        df_valid = pd.DataFrame(get_sample_survey_data())

        with pytest.raises(ValueError, match="not found"):
            feature_processor.fit_transform(df_valid, 'nonexistent_column')

        # Test single-class target
        single_class_data = [
            {'feature': 'A', 'target': 'Same'},
            {'feature': 'B', 'target': 'Same'},
            {'feature': 'C', 'target': 'Same'},
        ]
        df_single_class = pd.DataFrame(single_class_data)

        feature_processor_single = FeatureProcessor()
        X_single = feature_processor_single.fit_transform(df_single_class, 'target')
        y_single = df_single_class['target'].values

        model_selector = ModelSelector()

        with pytest.raises(ValueError, match="at least 2 classes"):
            model_selector.validate_data(X_single, y_single)

    def test_model_comparison_integration(self):
        """Test model comparison and selection in realistic scenario."""
        from edsl.scenarios.scenarioml.feature_processor import FeatureProcessor
        from edsl.scenarios.scenarioml.model_selector import ModelSelector

        # Use larger dataset for better model comparison
        survey_data = get_sample_survey_data() * 2  # Double the data
        df = pd.DataFrame(survey_data)

        feature_processor = FeatureProcessor()
        X = feature_processor.fit_transform(df, 'will_renew')
        y_values = df['will_renew'].values

        model_selector = ModelSelector()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model_results = model_selector.compare_models(X, y_values, feature_processor.feature_names)

        # Should have multiple models
        assert len(model_results) >= 2

        # All models should have valid scores
        for result in model_results:
            assert 0 <= result.cv_score <= 1
            assert 0 <= result.test_score <= 1
            assert result.overfitting_gap >= 0

        # Select best model
        best_model = model_selector.select_best_model(model_results)

        # Best model should have selection score assigned
        assert hasattr(best_model, 'selection_score')
        assert best_model.selection_score is not None

        # Get diagnostics
        diagnostics_df = model_selector.get_model_diagnostics(model_results)
        assert len(diagnostics_df) == len(model_results)
        assert 'Selection Score' in diagnostics_df.columns

    def test_robustness_to_missing_data(self):
        """Test robustness when predicting on data with missing values."""
        from edsl.scenarios.scenarioml.feature_processor import FeatureProcessor
        from edsl.scenarios.scenarioml.model_selector import ModelSelector
        from edsl.scenarios.scenarioml.prediction import Prediction

        # Train on complete data
        complete_data = get_sample_survey_data()
        df_train = pd.DataFrame(complete_data)

        feature_processor = FeatureProcessor()
        X = feature_processor.fit_transform(df_train, 'will_renew')
        y_values = df_train['will_renew'].values

        model_selector = ModelSelector()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model_results = model_selector.compare_models(X, y_values, feature_processor.feature_names)
            best_model = model_selector.select_best_model(model_results)

        prediction = Prediction(
            model_result=best_model,
            feature_processor=feature_processor,
            target_column='will_renew'
        )

        # Test scenarios with missing values
        incomplete_scenarios = [
            {'business_type': 'SMB'},  # Many features missing
            {'satisfaction_level': 'Satisfied', 'company_size': '21-100'},  # Some features missing
            {}  # All features missing
        ]

        for scenario in incomplete_scenarios:
            # Should handle gracefully without throwing errors
            try:
                pred = prediction.predict(scenario)
                proba = prediction.predict_proba(scenario)

                assert isinstance(pred, str)
                assert isinstance(proba, dict)
                assert abs(sum(proba.values()) - 1.0) < 1e-6

            except Exception as e:
                # If it fails, should be with a helpful error message
                assert "Prediction failed" in str(e)

    def test_diagnostics_integration(self):
        """Test comprehensive diagnostics in real scenario."""
        from edsl.scenarios.scenarioml.feature_processor import FeatureProcessor
        from edsl.scenarios.scenarioml.model_selector import ModelSelector
        from edsl.scenarios.scenarioml.prediction import Prediction

        # Train model
        survey_data = get_sample_survey_data()
        df = pd.DataFrame(survey_data)

        feature_processor = FeatureProcessor()
        X = feature_processor.fit_transform(df, 'will_renew')
        y_values = df['will_renew'].values

        model_selector = ModelSelector()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model_results = model_selector.compare_models(X, y_values, feature_processor.feature_names)
            best_model = model_selector.select_best_model(model_results)

        prediction = Prediction(
            model_result=best_model,
            feature_processor=feature_processor,
            target_column='will_renew'
        )

        # Test diagnostics
        diagnostics = prediction.diagnostics()

        # Should contain all expected information
        required_keys = [
            'model_name', 'cv_score', 'test_score', 'overfitting_gap',
            'feature_count', 'target_column', 'target_classes',
            'feature_names', 'feature_info'
        ]

        for key in required_keys:
            assert key in diagnostics

        # Verify content makes sense
        assert diagnostics['target_column'] == 'will_renew'
        assert len(diagnostics['target_classes']) == 2  # Yes/No
        assert diagnostics['feature_count'] > 0
        assert isinstance(diagnostics['feature_info'], list)

        # Test feature importance
        importance = prediction.get_feature_importance()
        assert isinstance(importance, dict)
        assert len(importance) > 0
        assert abs(sum(importance.values()) - 1.0) < 1e-6

        # Test summary
        summary = prediction.summary()
        assert isinstance(summary, str)
        assert 'ScenarioML' in summary
        assert diagnostics['model_name'] in summary

    def test_dummy_encoding_integration(self):
        """Test integration of dummy encoding for list features."""
        from edsl.scenarios.scenarioml.feature_processor import FeatureProcessor
        from edsl.scenarios.scenarioml.model_selector import ModelSelector
        from edsl.scenarios.scenarioml.prediction import Prediction

        # Create test data with list features
        list_data = [
            {'tools_used': "['Salesforce', 'HubSpot']", 'company_size': '50', 'will_renew': 'Yes'},
            {'tools_used': "['Slack', 'Zoom']", 'company_size': '100', 'will_renew': 'No'},
            {'tools_used': "['Salesforce', 'Slack']", 'company_size': '200', 'will_renew': 'Yes'},
            {'tools_used': "['HubSpot', 'Zoom']", 'company_size': '25', 'will_renew': 'No'},
            {'tools_used': "['Salesforce', 'HubSpot', 'Slack']", 'company_size': '150', 'will_renew': 'Yes'},
            {'tools_used': "['Zoom']", 'company_size': '75', 'will_renew': 'No'},
            {'tools_used': "['Salesforce', 'Zoom', 'HubSpot']", 'company_size': '300', 'will_renew': 'Yes'},
            {'tools_used': "['Slack', 'HubSpot']", 'company_size': '80', 'will_renew': 'No'},
            {'tools_used': "['Salesforce']", 'company_size': '120', 'will_renew': 'Yes'},
            {'tools_used': "['Slack', 'Zoom', 'HubSpot']", 'company_size': '90', 'will_renew': 'No'},
        ]

        df = pd.DataFrame(list_data)

        # Test with dummy encoding (default behavior)
        feature_processor_dummy = FeatureProcessor()
        X_dummy = feature_processor_dummy.fit_transform(df, 'will_renew')

        # Should have dummy variables for each unique tool
        tools_processor = feature_processor_dummy.processors['tools_used']
        assert tools_processor['type'] == 'list_dummy'
        expected_tools = ['HubSpot', 'Salesforce', 'Slack', 'Zoom']
        assert tools_processor['unique_items'] == expected_tools

        # Should have feature names for each tool
        expected_feature_names = ['tools_used_HubSpot', 'tools_used_Salesforce', 'tools_used_Slack', 'tools_used_Zoom']
        assert tools_processor['feature_names'] == expected_feature_names

        # Compare with TF-IDF encoding
        feature_processor_tfidf = FeatureProcessor(list_encoding="tfidf")
        X_tfidf = feature_processor_tfidf.fit_transform(df, 'will_renew')

        # TF-IDF should create different features
        tools_processor_tfidf = feature_processor_tfidf.processors['tools_used']
        assert tools_processor_tfidf['type'] == 'text_list'

        # Train models and compare
        y_values = df['will_renew'].values
        model_selector = ModelSelector()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")

            # Train with dummy encoding
            model_results_dummy = model_selector.compare_models(X_dummy, y_values, feature_processor_dummy.feature_names)
            best_model_dummy = model_selector.select_best_model(model_results_dummy)

            # Train with TF-IDF encoding
            model_results_tfidf = model_selector.compare_models(X_tfidf, y_values, feature_processor_tfidf.feature_names)
            best_model_tfidf = model_selector.select_best_model(model_results_tfidf)

        # Both should produce valid models
        assert len(model_results_dummy) >= 1
        assert len(model_results_tfidf) >= 1
        assert 0 <= best_model_dummy.cv_score <= 1
        assert 0 <= best_model_tfidf.cv_score <= 1

        # Create predictions and test
        prediction_dummy = Prediction(
            model_result=best_model_dummy,
            feature_processor=feature_processor_dummy,
            target_column='will_renew'
        )

        prediction_tfidf = Prediction(
            model_result=best_model_tfidf,
            feature_processor=feature_processor_tfidf,
            target_column='will_renew'
        )

        # Test predictions on new data
        new_customer = {'tools_used': "['Salesforce', 'Slack']", 'company_size': '100'}

        pred_dummy = prediction_dummy.predict(new_customer)
        pred_tfidf = prediction_tfidf.predict(new_customer)

        # Both should return valid predictions
        assert pred_dummy in ['Yes', 'No']
        assert pred_tfidf in ['Yes', 'No']

        # Test that feature info contains the dummy variables
        feature_info_dummy = feature_processor_dummy.get_feature_info()
        tools_info = next((info for info in feature_info_dummy if info['column'] == 'tools_used'), None)
        assert tools_info is not None
        assert tools_info['type'] == 'list_dummy'
        assert 'unique_items' in tools_info
        assert set(tools_info['unique_items']) == {'HubSpot', 'Salesforce', 'Slack', 'Zoom'}