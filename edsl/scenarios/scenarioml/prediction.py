"""
Prediction: Production-ready prediction object with persistence.

Provides a user-friendly interface for making predictions on new data,
with comprehensive error handling, persistence capabilities, and diagnostics.
"""

import os
from typing import Dict, List, Any, Union, TYPE_CHECKING
import warnings

if TYPE_CHECKING:
    import pandas as pd

from .model_selector import ModelResult
from .feature_processor import FeatureProcessor

# Lazy-loaded pandas
_pandas = None


def _get_pandas():
    """Lazy import pandas."""
    global _pandas
    if _pandas is None:
        import pandas as _pandas
    return _pandas


class Prediction:
    """
    Production-ready prediction object with persistence and diagnostics.

    Handles single and batch predictions, provides probability estimates,
    and includes comprehensive error handling and validation.
    """

    def __init__(
        self,
        model_result: ModelResult,
        feature_processor: FeatureProcessor,
        target_column: str,
        version: str = "0.1.0",
    ):
        """
        Initialize prediction object.

        Args:
            model_result: Trained model result from ModelSelector
            feature_processor: Fitted feature processor
            target_column: Name of the target column
            version: Version for compatibility checking
        """
        self.model_result = model_result
        self.feature_processor = feature_processor
        self.target_column = target_column
        self.version = version

        # Check if this is classification or regression
        self.problem_type = getattr(model_result, "problem_type", "classification")

        # Extract label encoder from preprocessing pipeline (only for classification)
        if self.problem_type == "classification":
            self.label_encoder = model_result.preprocessing_pipeline.get(
                "label_encoder"
            )
            if self.label_encoder is None:
                raise ValueError(
                    "Label encoder not found in model preprocessing pipeline"
                )
        else:
            self.label_encoder = None

    def predict(
        self, scenario: Union[Dict, List[Dict]]
    ) -> Union[str, float, List[Union[str, float]]]:
        """
        Make predictions on new scenarios.

        Args:
            scenario: Single scenario dict or list of scenario dicts

        Returns:
            Predicted class label(s) as string(s) for classification or
            predicted value(s) as float(s) for regression
        """
        # Handle single scenario
        if isinstance(scenario, dict):
            scenarios = [scenario]
            single_input = True
        else:
            scenarios = scenario
            single_input = False

        try:
            # Convert to DataFrame
            pd = _get_pandas()
            df = pd.DataFrame(scenarios)

            # Transform features
            X = self.feature_processor.transform(df)

            # Make predictions
            y_pred = self.model_result.model.predict(X)

            if self.problem_type == "classification":
                # Decode predictions for classification
                predictions = self.label_encoder.inverse_transform(y_pred)
                # Return single value if single input
                if single_input:
                    return predictions[0]
                else:
                    return predictions.tolist()
            else:
                # For regression, return raw predictions
                if single_input:
                    return float(y_pred[0])
                else:
                    return y_pred.tolist()

        except Exception as e:
            self._handle_prediction_error(e, scenarios)

    def predict_proba(
        self, scenario: Union[Dict, List[Dict]]
    ) -> Union[Dict[str, float], List[Dict[str, float]]]:
        """
        Get prediction probabilities for scenarios (classification only).
        For regression, this method will raise an error.

        Args:
            scenario: Single scenario dict or list of scenario dicts

        Returns:
            Probability distribution(s) as dict(s) mapping class names to probabilities

        Raises:
            ValueError: If called on a regression model
        """
        if self.problem_type == "regression":
            raise ValueError(
                "predict_proba() is only available for classification models. "
                "For regression models, use predict() to get point predictions."
            )

        # Handle single scenario
        if isinstance(scenario, dict):
            scenarios = [scenario]
            single_input = True
        else:
            scenarios = scenario
            single_input = False

        try:
            # Convert to DataFrame
            pd = _get_pandas()
            df = pd.DataFrame(scenarios)

            # Transform features
            X = self.feature_processor.transform(df)

            # Get prediction probabilities
            if hasattr(self.model_result.model, "predict_proba"):
                y_proba = self.model_result.model.predict_proba(X)
                class_names = self.label_encoder.classes_

                # Convert to list of dicts
                proba_dicts = []
                for row in y_proba:
                    proba_dict = {
                        class_names[i]: float(prob) for i, prob in enumerate(row)
                    }
                    proba_dicts.append(proba_dict)

            else:
                # Fallback: create probabilities from predictions
                y_pred = self.model_result.model.predict(X)
                class_names = self.label_encoder.classes_

                proba_dicts = []
                for pred in y_pred:
                    proba_dict = {cls: 0.0 for cls in class_names}
                    pred_class = self.label_encoder.inverse_transform([pred])[0]
                    proba_dict[pred_class] = 1.0
                    proba_dicts.append(proba_dict)

            # Return single value if single input
            if single_input:
                return proba_dicts[0]
            else:
                return proba_dicts

        except Exception as e:
            self._handle_prediction_error(e, scenarios)

    def diagnostics(self) -> Dict[str, Any]:
        """
        Get comprehensive prediction object diagnostics.

        Returns:
            Dictionary with model performance and configuration details
        """
        diagnostics = {
            "model_name": self.model_result.name,
            "problem_type": self.problem_type,
            "cv_score": self.model_result.cv_score,
            "cv_std": self.model_result.cv_std,
            "test_score": self.model_result.test_score,
            "overfitting_gap": self.model_result.overfitting_gap,
            "selection_score": self.model_result.selection_score,
            "feature_count": len(self.model_result.feature_names),
            "target_column": self.target_column,
            "feature_names": self.model_result.feature_names.copy(),
            "feature_info": self.feature_processor.get_feature_info(),
            "version": self.version,
        }

        # Add problem-specific information
        if self.problem_type == "classification":
            diagnostics["target_classes"] = list(self.label_encoder.classes_)
            diagnostics["score_type"] = "accuracy"
        else:
            diagnostics["score_type"] = "r2_score"

        return diagnostics

    def get_feature_importance(self) -> Dict[str, float]:
        """
        Get feature importance from the trained model.

        Returns:
            Dictionary mapping feature names to importance scores
        """
        try:
            # Import here to avoid circular import
            from .model_selector import ModelSelector

            selector = ModelSelector()
            return selector.get_feature_importance(self.model_result)
        except Exception as e:
            warnings.warn(f"Could not get feature importance: {str(e)}")
            # Return equal importance as fallback
            feature_names = self.model_result.feature_names
            equal_importance = 1.0 / len(feature_names)
            return {name: equal_importance for name in feature_names}

    def save(self, filepath: str) -> None:
        """
        Save prediction object to disk.

        Args:
            filepath: Path where to save the prediction object

        Raises:
            ValueError: If save operation fails
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            # Prepare data for saving
            save_data = {
                "model_result": self.model_result,
                "feature_processor": self.feature_processor,
                "target_column": self.target_column,
                "version": self.version,
            }

            # Save using joblib
            import joblib

            joblib.dump(save_data, filepath)

        except Exception as e:
            raise ValueError(f"Failed to save prediction object: {str(e)}")

    @classmethod
    def load(cls, filepath: str) -> "Prediction":
        """
        Load prediction object from disk.

        Args:
            filepath: Path to saved prediction object

        Returns:
            Loaded Prediction object

        Raises:
            ValueError: If load operation fails or version incompatibility
        """
        try:
            # Load data
            import joblib

            save_data = joblib.load(filepath)

            # Check version compatibility
            saved_version = save_data.get("version", "0.0.0")
            if saved_version != "0.1.0":
                warnings.warn(
                    f"Version mismatch: saved {saved_version}, current 0.1.0. "
                    "Compatibility not guaranteed."
                )

            # Create prediction object
            prediction = cls(
                model_result=save_data["model_result"],
                feature_processor=save_data["feature_processor"],
                target_column=save_data["target_column"],
                version=save_data["version"],
            )

            return prediction

        except Exception as e:
            raise ValueError(f"Failed to load prediction object: {str(e)}")

    def validate_scenario(self, scenario: Dict) -> Dict[str, Any]:
        """
        Validate a scenario and return validation results.

        Args:
            scenario: Scenario dictionary to validate

        Returns:
            Dictionary with validation results
        """
        validation_results = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "missing_features": [],
            "extra_features": [],
            "feature_types": {},
        }

        try:
            # Get expected features
            expected_features = set()
            for col, processor_info in self.feature_processor.processors.items():
                expected_features.add(col)

            scenario_features = set(scenario.keys())

            # Check for missing features
            missing_features = expected_features - scenario_features
            if missing_features:
                validation_results["missing_features"] = list(missing_features)
                validation_results["warnings"].append(
                    f"Missing features will be imputed: {missing_features}"
                )

            # Check for extra features
            extra_features = scenario_features - expected_features
            if extra_features:
                validation_results["extra_features"] = list(extra_features)
                validation_results["warnings"].append(
                    f"Extra features will be ignored: {extra_features}"
                )

            # Check feature types
            for col, value in scenario.items():
                if col in self.feature_processor.processors:
                    processor_info = self.feature_processor.processors[col]
                    feature_type = processor_info["type"]
                    validation_results["feature_types"][col] = feature_type

            if validation_results["warnings"] or validation_results["errors"]:
                validation_results["valid"] = False

        except Exception as e:
            validation_results["valid"] = False
            validation_results["errors"].append(f"Validation error: {str(e)}")

        return validation_results

    def _handle_prediction_error(self, error: Exception, scenarios: List[Dict]) -> None:
        """Handle prediction errors with helpful messages."""
        error_msg = f"Prediction failed: {str(error)}"

        # Add helpful context
        if len(scenarios) > 0:
            sample_scenario = scenarios[0]
            validation_result = self.validate_scenario(sample_scenario)

            if not validation_result["valid"]:
                error_msg += "\\n\\nValidation issues found:"
                for warning in validation_result["warnings"]:
                    error_msg += f"\\n  Warning: {warning}"
                for error in validation_result["errors"]:
                    error_msg += f"\\n  Error: {error}"

        raise ValueError(error_msg)

    def generate_report(self) -> str:
        """
        Generate a comprehensive markdown report for LLM consumption.

        Returns:
            Detailed markdown report with model performance, diagnostics, and insights
        """
        diag = self.diagnostics()
        importance = self.get_feature_importance()

        # Sort features by importance
        sorted_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)

        # Generate timestamp
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        report_lines = [
            "# ScenarioML Model Performance Report",
            "",
            f"**Generated:** {timestamp}  ",
            f"**Model Type:** {diag['problem_type'].title()}  ",
            f"**Target Variable:** `{diag['target_column']}`  ",
            f"**Model Algorithm:** {diag['model_name']}  ",
            "",
            "## 📊 Performance Summary",
            "",
            "| Metric | Value | Interpretation |",
            "|--------|-------|----------------|",
        ]

        if self.problem_type == "classification":
            accuracy_interpretation = self._interpret_accuracy(diag["test_score"])
            report_lines.extend(
                [
                    f"| **Test Accuracy** | {diag['test_score']:.3f} ({diag['test_score']:.1%}) | {accuracy_interpretation} |",
                    f"| **Cross-Validation Score** | {diag['cv_score']:.3f} ± {diag['cv_std']:.3f} | Average performance across 5 folds |",
                ]
            )
        else:
            r2_interpretation = self._interpret_r2_score(diag["test_score"])
            report_lines.extend(
                [
                    f"| **Test R² Score** | {diag['test_score']:.3f} | {r2_interpretation} |",
                    f"| **Cross-Validation R²** | {diag['cv_score']:.3f} ± {diag['cv_std']:.3f} | Average R² across 5 folds |",
                ]
            )

        overfitting_interpretation = self._interpret_overfitting(
            diag["overfitting_gap"]
        )
        cv_stability_interpretation = self._interpret_cv_stability(diag["cv_std"])

        report_lines.extend(
            [
                f"| **Overfitting Gap** | {diag['overfitting_gap']:.3f} | {overfitting_interpretation} |",
                f"| **CV Stability** | ±{diag['cv_std']:.3f} | {cv_stability_interpretation} |",
                f"| **Selection Score** | {diag['selection_score']:.3f} | Combined metric favoring generalization |",
                "",
                "## 🎯 Model Quality Assessment",
                "",
            ]
        )

        # Overall assessment
        overall_quality = self._assess_overall_quality(diag)
        report_lines.extend(
            [
                f"**Overall Quality:** {overall_quality['level']}  ",
                f"**Confidence Level:** {overall_quality['confidence']}  ",
                "",
                "### Key Insights:",
            ]
        )

        for insight in overall_quality["insights"]:
            report_lines.append(f"- {insight}")

        report_lines.extend(
            [
                "",
                "### Recommendations:",
            ]
        )

        for recommendation in overall_quality["recommendations"]:
            report_lines.append(f"- {recommendation}")

        # Feature analysis
        report_lines.extend(
            [
                "",
                "## 🔍 Feature Analysis",
                "",
                f"**Total Features:** {diag['feature_count']}  ",
                "**Feature Engineering Applied:** Automatic type detection and preprocessing  ",
                "",
                "### Feature Importance Rankings",
                "",
                "| Rank | Feature | Importance | Type | Description |",
                "|------|---------|------------|------|-------------|",
            ]
        )

        feature_info_lookup = {info["column"]: info for info in diag["feature_info"]}

        for rank, (feature, importance_score) in enumerate(sorted_features[:10], 1):
            # Find original column name for this feature
            original_col = self._find_original_column(feature, feature_info_lookup)
            feature_info = feature_info_lookup.get(original_col, {})
            feature_type = feature_info.get("type", "unknown")

            description = self._get_feature_description(
                feature, feature_type, feature_info
            )

            report_lines.append(
                f"| {rank} | `{feature}` | {importance_score:.3f} | {feature_type} | {description} |"
            )

        if len(sorted_features) > 10:
            report_lines.append(
                f"| ... | ... | ... | ... | *{len(sorted_features) - 10} more features* |"
            )

        # Data quality section
        report_lines.extend(
            [
                "",
                "## 📋 Data Quality & Training Details",
                "",
                "### Feature Processing Summary",
                "",
            ]
        )

        for info in diag["feature_info"]:
            feature_type = info["type"]
            feature_count = len(info["feature_names"])
            processing_desc = self._get_processing_description(feature_type, info)

            if feature_count == 1:
                report_lines.append(
                    f"- **{info['column']}** ({feature_type}): {processing_desc}"
                )
            else:
                report_lines.append(
                    f"- **{info['column']}** ({feature_type}): Expanded to {feature_count} features. {processing_desc}"
                )

        # Usage examples
        report_lines.extend(
            [
                "",
                "## 🚀 Usage Examples",
                "",
                "### Making Predictions",
                "",
                "```python",
                "# Single prediction",
            ]
        )

        # Create example scenario based on features
        example_scenario = self._create_example_scenario(diag["feature_info"])
        scenario_str = ", ".join(
            [f"'{k}': {repr(v)}" for k, v in example_scenario.items()]
        )

        if self.problem_type == "classification":
            report_lines.extend(
                [
                    f"prediction = model.predict({{{scenario_str}}})",
                    "# Returns: class label (string)",
                    "",
                    "# Get prediction probabilities",
                    f"probabilities = model.predict_proba({{{scenario_str}}})",
                    "# Returns: {'Class1': 0.7, 'Class2': 0.3}",
                ]
            )
        else:
            report_lines.extend(
                [
                    f"prediction = model.predict({{{scenario_str}}})",
                    "# Returns: predicted value (float)",
                ]
            )

        report_lines.extend(
            [
                "",
                "# Batch predictions",
                f"scenarios = [{{{scenario_str}}}, {{{scenario_str}}}]",
                "predictions = model.predict(scenarios)",
                "```",
                "",
                "### Model Diagnostics",
                "",
                "```python",
                "# Get detailed diagnostics",
                "diagnostics = model.diagnostics()",
                "",
                "# Get feature importance",
                "importance = model.get_feature_importance()",
                "",
                "# Save model for later use",
                "model.save('my_model.joblib')",
                "",
                "# Load saved model",
                "from scenarioml import Prediction",
                "loaded_model = Prediction.load('my_model.joblib')",
                "```",
                "",
                "---",
                f"*Report generated by ScenarioML v{diag['version']}*",
            ]
        )

        return "\n".join(report_lines)

    def _interpret_accuracy(self, accuracy: float) -> str:
        """Interpret accuracy score for classification."""
        if accuracy >= 0.9:
            return "Excellent performance"
        elif accuracy >= 0.8:
            return "Good performance"
        elif accuracy >= 0.7:
            return "Acceptable performance"
        elif accuracy >= 0.6:
            return "Below average performance"
        else:
            return "Poor performance"

    def _interpret_r2_score(self, r2: float) -> str:
        """Interpret R² score for regression."""
        if r2 >= 0.9:
            return "Excellent fit - explains >90% of variance"
        elif r2 >= 0.8:
            return "Good fit - explains >80% of variance"
        elif r2 >= 0.6:
            return "Moderate fit - explains >60% of variance"
        elif r2 >= 0.4:
            return "Weak fit - explains >40% of variance"
        else:
            return "Poor fit - explains <40% of variance"

    def _interpret_overfitting(self, gap: float) -> str:
        """Interpret overfitting gap."""
        if gap <= 0.05:
            return "No overfitting detected"
        elif gap <= 0.1:
            return "Minimal overfitting"
        elif gap <= 0.2:
            return "Moderate overfitting"
        else:
            return "Significant overfitting"

    def _interpret_cv_stability(self, cv_std: float) -> str:
        """Interpret cross-validation stability."""
        if cv_std <= 0.05:
            return "Very stable performance"
        elif cv_std <= 0.1:
            return "Stable performance"
        elif cv_std <= 0.2:
            return "Moderate stability"
        else:
            return "Unstable performance"

    def _assess_overall_quality(self, diag: Dict[str, Any]) -> Dict[str, Any]:
        """Assess overall model quality and provide insights."""
        test_score = diag["test_score"]
        overfitting_gap = diag["overfitting_gap"]
        cv_std = diag["cv_std"]

        quality_score = test_score - 2 * overfitting_gap - cv_std

        if quality_score >= 0.8:
            level = "🟢 High"
            confidence = "High confidence in predictions"
        elif quality_score >= 0.6:
            level = "🟡 Medium"
            confidence = "Moderate confidence in predictions"
        else:
            level = "🔴 Low"
            confidence = "Low confidence in predictions"

        insights = []
        recommendations = []

        # Performance insights
        if self.problem_type == "classification":
            if test_score >= 0.9:
                insights.append(
                    f"Model achieves {test_score:.1%} accuracy on test data"
                )
            elif test_score >= 0.7:
                insights.append(f"Model shows reasonable accuracy of {test_score:.1%}")
            else:
                insights.append(
                    f"Model accuracy of {test_score:.1%} indicates room for improvement"
                )
                recommendations.append("Consider collecting more diverse training data")
        else:
            if test_score >= 0.8:
                insights.append(
                    f"Model explains {test_score:.1%} of variance in target variable"
                )
            elif test_score >= 0.5:
                insights.append(
                    f"Model captures {test_score:.1%} of target variable patterns"
                )
            else:
                insights.append(
                    f"Model only explains {test_score:.1%} of variance - weak predictive power"
                )
                recommendations.append(
                    "Consider adding more relevant features or checking data quality"
                )

        # Overfitting insights
        if overfitting_gap <= 0.05:
            insights.append("No signs of overfitting - good generalization expected")
        elif overfitting_gap <= 0.1:
            insights.append(
                "Minimal overfitting detected - model should generalize well"
            )
        else:
            insights.append(
                f"Overfitting gap of {overfitting_gap:.3f} suggests model may not generalize well"
            )
            recommendations.append(
                "Consider regularization or collecting more training data"
            )

        # Stability insights
        if cv_std <= 0.05:
            insights.append("Cross-validation shows very consistent performance")
        elif cv_std <= 0.1:
            insights.append(
                "Model performance is reasonably stable across different data splits"
            )
        else:
            insights.append(
                f"High CV variance (±{cv_std:.3f}) indicates unstable performance"
            )
            recommendations.append(
                "Model performance varies significantly - consider ensemble methods"
            )

        # Feature insights
        feature_count = diag["feature_count"]
        if feature_count == 1:
            insights.append(
                "Model uses only one feature - predictions may be limited in scope"
            )
            recommendations.append(
                "Consider adding more relevant features to improve prediction accuracy"
            )
        elif feature_count <= 5:
            insights.append(
                f"Model uses {feature_count} features - good balance of simplicity and information"
            )
        else:
            insights.append(
                f"Model uses {feature_count} features - comprehensive feature set"
            )

        if not recommendations:
            recommendations.append(
                "Model performance is satisfactory - ready for production use"
            )
            recommendations.append(
                "Monitor performance on new data and retrain as needed"
            )

        return {
            "level": level,
            "confidence": confidence,
            "insights": insights,
            "recommendations": recommendations,
            "quality_score": quality_score,
        }

    def _find_original_column(
        self, feature_name: str, feature_info_lookup: Dict
    ) -> str:
        """Find the original column that generated this feature."""
        for col, info in feature_info_lookup.items():
            if feature_name in info.get("feature_names", []):
                return col
        return feature_name.split("_")[0]  # Fallback

    def _get_feature_description(
        self, feature_name: str, feature_type: str, feature_info: Dict
    ) -> str:
        """Get description of feature processing."""
        if feature_type == "numeric":
            return "Numeric feature with median imputation"
        elif feature_type == "categorical":
            return "Categorical feature with label encoding"
        elif feature_type == "ordinal":
            return "Ordinal feature with pattern-based mapping"
        elif feature_type == "text_list":
            return "Text list converted to TF-IDF features"
        else:
            return "Automatically processed feature"

    def _get_processing_description(self, feature_type: str, feature_info: Dict) -> str:
        """Get detailed processing description."""
        if feature_type == "numeric":
            return "Scaled to standard normal distribution, missing values filled with median"
        elif feature_type == "categorical":
            return "Label encoded with 'Unknown' category for missing values"
        elif feature_type == "ordinal":
            mapping = feature_info.get("mapping", {})
            if mapping:
                return f"Mapped to numeric scale (e.g., {list(mapping.items())[:3]}...)"
            else:
                return "Mapped to numeric scale based on detected pattern"
        elif feature_type == "text_list":
            feature_names = feature_info.get("feature_names", [])
            return f"Converted to {len(feature_names)} TF-IDF features with stop word removal"
        else:
            return "Automatically detected and processed"

    def _create_example_scenario(self, feature_info: List[Dict]) -> Dict[str, Any]:
        """Create example scenario for documentation."""
        example = {}
        for info in feature_info[:3]:  # Show first 3 features
            col = info["column"]
            feature_type = info["type"]

            if feature_type == "numeric":
                example[col] = 100
            elif feature_type == "categorical":
                example[col] = "CategoryA"
            elif feature_type == "ordinal":
                mapping = info.get("mapping", {})
                if mapping:
                    example[col] = list(mapping.keys())[0]
                else:
                    example[col] = "Medium"
            elif feature_type == "text_list":
                example[col] = "['Item1', 'Item2']"
            else:
                example[col] = "value"

        return example

    def summary(self) -> str:
        """
        Get a human-readable summary of the prediction object.

        Returns:
            Formatted summary string
        """
        diag = self.diagnostics()

        summary_lines = [
            "ScenarioML Prediction Model Summary",
            "====================================",
            "",
            f"Model: {diag['model_name']}",
            f"Target: {diag['target_column']}",
        ]

        if self.problem_type == "classification":
            summary_lines.append(f"Classes: {', '.join(diag['target_classes'])}")
        else:
            summary_lines.append("Problem Type: Regression")

        summary_lines.extend(
            [
                "",
                "Performance Metrics:",
                f"  Cross-validation Score: {diag['cv_score']:.3f} ± {diag['cv_std']:.3f}",
                f"  Test Score: {diag['test_score']:.3f}",
                f"  Overfitting Gap: {diag['overfitting_gap']:.3f}",
                f"  Selection Score: {diag['selection_score']:.3f}",
                "",
                f"Features ({diag['feature_count']} total):",
            ]
        )

        # Add feature information
        feature_info = diag["feature_info"]
        for info in feature_info[:10]:  # Show first 10 features
            feature_type = info["type"]
            feature_names = info["feature_names"]
            if len(feature_names) == 1:
                summary_lines.append(f"  {info['column']} ({feature_type})")
            else:
                summary_lines.append(
                    f"  {info['column']} ({feature_type}, {len(feature_names)} derived features)"
                )

        if len(feature_info) > 10:
            summary_lines.append(f"  ... and {len(feature_info) - 10} more features")

        summary_lines.extend(
            [
                "",
                "Usage:",
                "  prediction.predict({'feature1': 'value1', 'feature2': 'value2'})",
            ]
        )

        if self.problem_type == "classification":
            summary_lines.append(
                "  prediction.predict_proba({'feature1': 'value1', 'feature2': 'value2'})"
            )

        return "\n".join(summary_lines)

    def _repr_html_(self) -> str:
        """Rich HTML representation for Jupyter notebooks."""
        diag = self.diagnostics()
        importance = self.get_feature_importance()
        sorted_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)

        # Overall quality assessment
        quality = self._assess_overall_quality(diag)

        # Generate timestamp
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Color coding based on quality
        if quality["quality_score"] >= 0.8:
            header_color = "#2E7D32"  # Green
            quality_badge = "🟢 High Quality"
        elif quality["quality_score"] >= 0.6:
            header_color = "#F57C00"  # Orange
            quality_badge = "🟡 Medium Quality"
        else:
            header_color = "#C62828"  # Red
            quality_badge = "🔴 Low Quality"

        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 100%; margin: 10px 0;">
            <div style="background: linear-gradient(135deg, {header_color} 0%, {header_color}AA 100%);
                        color: white; padding: 15px; border-radius: 8px 8px 0 0; margin-bottom: 0;">
                <h2 style="margin: 0; font-size: 24px;">📊 ScenarioML Model</h2>
                <p style="margin: 5px 0 0 0; opacity: 0.9; font-size: 14px;">
                    Generated: {timestamp} | {quality_badge}
                </p>
            </div>

            <div style="border: 1px solid #ddd; border-top: none; border-radius: 0 0 8px 8px; background: white;">
                <!-- Quick Stats -->
                <div style="padding: 15px; background: #f8f9fa; border-bottom: 1px solid #eee;">
                    <div style="display: flex; flex-wrap: wrap; gap: 20px;">
                        <div style="flex: 1; min-width: 200px;">
                            <strong style="color: #333;">Model:</strong> {diag['model_name']}<br>
                            <strong style="color: #333;">Problem Type:</strong> {diag['problem_type'].title()}<br>
                            <strong style="color: #333;">Target:</strong> <code>{diag['target_column']}</code>
                        </div>
                        <div style="flex: 1; min-width: 200px;">
        """

        # Add problem-specific metrics
        if self.problem_type == "classification":
            html += f"""
                            <strong style="color: #333;">Test Accuracy:</strong> {diag['test_score']:.3f} ({diag['test_score']:.1%})<br>
                            <strong style="color: #333;">Classes:</strong> {len(diag['target_classes'])} total<br>
            """
        else:
            html += f"""
                            <strong style="color: #333;">Test R²:</strong> {diag['test_score']:.3f}<br>
                            <strong style="color: #333;">Variance Explained:</strong> {diag['test_score']:.1%}<br>
            """

        html += f"""
                            <strong style="color: #333;">Features:</strong> {diag['feature_count']} total
                        </div>
                    </div>
                </div>

                <!-- Performance Details (Collapsible) -->
                <details style="border-bottom: 1px solid #eee;">
                    <summary style="padding: 15px; cursor: pointer; background: #f8f9fa; font-weight: bold;
                                   border-bottom: 1px solid #eee; user-select: none;">
                        📈 Performance Metrics
                    </summary>
                    <div style="padding: 15px;">
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px;">
                            <div style="background: #f1f3f4; padding: 12px; border-radius: 6px;">
                                <h4 style="margin: 0 0 8px 0; color: #1a73e8;">Cross-Validation</h4>
                                <p style="margin: 0; font-family: monospace;">
                                    Score: {diag['cv_score']:.3f} ± {diag['cv_std']:.3f}<br>
                                    Stability: {self._interpret_cv_stability(diag['cv_std'])}
                                </p>
                            </div>
                            <div style="background: #f1f3f4; padding: 12px; border-radius: 6px;">
                                <h4 style="margin: 0 0 8px 0; color: #1a73e8;">Overfitting Analysis</h4>
                                <p style="margin: 0; font-family: monospace;">
                                    Gap: {diag['overfitting_gap']:.3f}<br>
                                    Status: {self._interpret_overfitting(diag['overfitting_gap'])}
                                </p>
                            </div>
                            <div style="background: #f1f3f4; padding: 12px; border-radius: 6px;">
                                <h4 style="margin: 0 0 8px 0; color: #1a73e8;">Selection Score</h4>
                                <p style="margin: 0; font-family: monospace;">
                                    Combined: {diag['selection_score']:.3f}<br>
                                    Quality: {quality['level'].split()[1]}
                                </p>
                            </div>
                        </div>
                    </div>
                </details>

                <!-- Feature Importance (Collapsible) -->
                <details style="border-bottom: 1px solid #eee;">
                    <summary style="padding: 15px; cursor: pointer; background: #f8f9fa; font-weight: bold;
                                   border-bottom: 1px solid #eee; user-select: none;">
                        🎯 Feature Importance ({len(sorted_features)} features)
                    </summary>
                    <div style="padding: 15px;">
                        <div style="max-height: 300px; overflow-y: auto;">
        """

        # Feature importance bars
        max_importance = (
            max([score for _, score in sorted_features]) if sorted_features else 1
        )

        for i, (feature, score) in enumerate(sorted_features[:10]):  # Show top 10
            bar_width = (score / max_importance) * 100
            color_intensity = int(255 * (1 - score / max_importance))
            bar_color = f"rgb({color_intensity}, {255}, {color_intensity})"

            html += f"""
                            <div style="margin-bottom: 8px;">
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2px;">
                                    <span style="font-weight: 500; font-size: 14px;"><code>{feature}</code></span>
                                    <span style="font-family: monospace; font-size: 12px; color: #666;">{score:.3f}</span>
                                </div>
                                <div style="background: #e0e0e0; height: 8px; border-radius: 4px; overflow: hidden;">
                                    <div style="background: {bar_color}; height: 100%; width: {bar_width}%; border-radius: 4px;"></div>
                                </div>
                            </div>
            """

        if len(sorted_features) > 10:
            html += f"""
                            <div style="text-align: center; margin-top: 10px; color: #666; font-style: italic;">
                                ... and {len(sorted_features) - 10} more features
                            </div>
            """

        html += """
                        </div>
                    </div>
                </details>

                <!-- Model Insights (Collapsible) -->
                <details style="border-bottom: 1px solid #eee;">
                    <summary style="padding: 15px; cursor: pointer; background: #f8f9fa; font-weight: bold;
                                   border-bottom: 1px solid #eee; user-select: none;">
                        💡 Key Insights & Recommendations
                    </summary>
                    <div style="padding: 15px;">
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px;">
                            <div>
                                <h4 style="margin: 0 0 10px 0; color: #1a73e8;">✨ Key Insights</h4>
                                <ul style="margin: 0; padding-left: 20px; line-height: 1.6;">
        """

        for insight in quality["insights"]:
            html += f"<li style='margin-bottom: 5px;'>{insight}</li>"

        html += """
                                </ul>
                            </div>
                            <div>
                                <h4 style="margin: 0 0 10px 0; color: #1a73e8;">🎯 Recommendations</h4>
                                <ul style="margin: 0; padding-left: 20px; line-height: 1.6;">
        """

        for recommendation in quality["recommendations"]:
            html += f"<li style='margin-bottom: 5px;'>{recommendation}</li>"

        html += """
                                </ul>
                            </div>
                        </div>
                    </div>
                </details>

                <!-- Usage Examples (Collapsible) -->
                <details>
                    <summary style="padding: 15px; cursor: pointer; background: #f8f9fa; font-weight: bold;
                                   user-select: none;">
                        🚀 Usage Examples
                    </summary>
                    <div style="padding: 15px;">
                        <div style="background: #f8f9fa; padding: 15px; border-radius: 6px; border-left: 4px solid #1a73e8;">
                            <h4 style="margin: 0 0 10px 0;">Making Predictions</h4>
                            <pre style="background: #fff; padding: 10px; border-radius: 4px; margin: 0; overflow-x: auto; font-size: 13px;"><code># Single prediction
        """

        # Create example scenario
        feature_info = diag["feature_info"]
        example_scenario = self._create_example_scenario(feature_info)
        scenario_str = ", ".join(
            [f"'{k}': {repr(v)}" for k, v in example_scenario.items()]
        )

        if self.problem_type == "classification":
            html += f"""prediction = model.predict({{{scenario_str}}})
# Returns: class label (string)

# Get prediction probabilities
probabilities = model.predict_proba({{{scenario_str}}})
# Returns: {{'Class1': 0.7, 'Class2': 0.3}}"""
        else:
            html += f"""prediction = model.predict({{{scenario_str}}})
# Returns: predicted value (float)"""

        html += f"""

# Batch predictions
scenarios = [{{{scenario_str}}}, {{{scenario_str}}}]
predictions = model.predict(scenarios)</code></pre>
                        </div>

                        <div style="background: #f8f9fa; padding: 15px; border-radius: 6px; border-left: 4px solid #34a853; margin-top: 15px;">
                            <h4 style="margin: 0 0 10px 0;">Model Management</h4>
                            <pre style="background: #fff; padding: 10px; border-radius: 4px; margin: 0; overflow-x: auto; font-size: 13px;"><code># Get model diagnostics
diagnostics = model.diagnostics()

# Get feature importance
importance = model.get_feature_importance()

# Generate full report
report = model.generate_report()

# Save model for later use
model.save('my_model.joblib')

# Load saved model
from scenarioml import Prediction
loaded_model = Prediction.load('my_model.joblib')</code></pre>
                        </div>
                    </div>
                </details>
            </div>
        </div>

        <style>
            details > summary:hover {{
                background: #e8f0fe !important;
            }}
            details[open] > summary {{
                border-bottom: 1px solid #ddd;
            }}
        </style>
        """

        return html

    def __repr__(self) -> str:
        """String representation of the prediction object."""
        # Check if we're in a Jupyter environment
        try:
            from IPython import get_ipython

            if (
                get_ipython() is not None
                and get_ipython().__class__.__name__ == "ZMQInteractiveShell"
            ):
                # We're in Jupyter, but __repr__ is for text representation
                # The _repr_html_ method will be called automatically for rich display
                pass
        except ImportError:
            pass

        # Return concise text representation
        diag = self.diagnostics()
        quality = self._assess_overall_quality(diag)

        if self.problem_type == "classification":
            score_info = f"accuracy={diag['test_score']:.3f}"
        else:
            score_info = f"r2={diag['test_score']:.3f}"

        return (
            f"ScenarioML Prediction(\n"
            f"  model={self.model_result.name},\n"
            f"  problem_type={self.problem_type},\n"
            f"  target={self.target_column},\n"
            f"  {score_info},\n"
            f"  quality={quality['level']},\n"
            f"  features={diag['feature_count']}\n"
            f")"
        )
