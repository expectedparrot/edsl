"""
ModelSelector: Compare multiple models and select the best one.

Implements conservative model selection with built-in overfitting prevention.
Prioritizes generalization over training performance and includes comprehensive
diagnostics for model evaluation.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from sklearn.model_selection import (
    cross_val_score,
    train_test_split,
    StratifiedKFold,
    KFold,
)
from sklearn.preprocessing import LabelEncoder
from sklearn.linear_model import LogisticRegressionCV, Ridge, Lasso
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, r2_score
import warnings

# Import XGBoost with fallback
try:
    import xgboost as xgb

    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False
    warnings.warn("XGBoost not available. Install with: pip install xgboost")


@dataclass
class ModelResult:
    """Container for model training results and diagnostics."""

    name: str
    model: Any
    cv_score: float
    cv_std: float
    test_score: float
    overfitting_gap: float
    preprocessing_pipeline: Dict[str, Any]
    feature_names: List[str]
    train_score: Optional[float] = None
    selection_score: Optional[float] = None
    problem_type: Optional[str] = None  # 'classification' or 'regression'
    training_data: Optional[tuple] = (
        None  # (X_train, y_train) for standard error calculation
    )


class ModelSelector:
    """
    Compare multiple models and select the best one with overfitting prevention.

    Uses conservative hyperparameters and prioritizes generalization over
    training performance. Includes comprehensive model diagnostics.
    """

    def __init__(self, random_state: int = 42):
        """
        Initialize the model selector.

        Args:
            random_state: Random state for reproducible results
        """
        self.random_state = random_state
        self._classification_models = self._initialize_classification_models()
        self._regression_models = self._initialize_regression_models()

    @property
    def _models(self) -> Dict[str, Any]:
        """
        Backward compatibility property for accessing all models.

        Returns:
            Combined dictionary of classification and regression models
        """
        return {**self._classification_models, **self._regression_models}

    def _initialize_classification_models(self) -> Dict[str, Any]:
        """Initialize classification model portfolio with conservative hyperparameters."""
        models = {
            "logistic_ridge": LogisticRegressionCV(
                penalty="l2",
                Cs=np.logspace(-4, 2, 20),
                cv=5,
                scoring="accuracy",
                random_state=self.random_state,
                max_iter=1000,
            ),
            "logistic_lasso": LogisticRegressionCV(
                penalty="l1",
                Cs=np.logspace(-4, 2, 20),
                cv=5,
                scoring="accuracy",
                random_state=self.random_state,
                max_iter=1000,
                solver="liblinear",
            ),
            "random_forest": RandomForestClassifier(
                n_estimators=100,
                max_depth=5,
                random_state=self.random_state,
                min_samples_split=10,
                min_samples_leaf=5,
            ),
        }

        # Add XGBoost if available
        if HAS_XGBOOST:
            models["xgboost_conservative"] = xgb.XGBClassifier(
                max_depth=3,
                n_estimators=50,
                learning_rate=0.05,
                reg_alpha=1.0,
                reg_lambda=10.0,
                random_state=self.random_state,
                min_child_weight=5,
                subsample=0.7,
                colsample_bytree=0.7,
                eval_metric="logloss",
            )

        return models

    def _initialize_regression_models(self) -> Dict[str, Any]:
        """Initialize regression model portfolio with conservative hyperparameters."""
        models = {
            "ridge": Ridge(alpha=1.0, random_state=self.random_state),
            "lasso": Lasso(alpha=0.1, random_state=self.random_state, max_iter=1000),
            "random_forest": RandomForestRegressor(
                n_estimators=100,
                max_depth=5,
                random_state=self.random_state,
                min_samples_split=10,
                min_samples_leaf=5,
            ),
        }

        # Add XGBoost if available
        if HAS_XGBOOST:
            models["xgboost_conservative"] = xgb.XGBRegressor(
                max_depth=3,
                n_estimators=50,
                learning_rate=0.05,
                reg_alpha=1.0,
                reg_lambda=10.0,
                random_state=self.random_state,
                min_child_weight=5,
                subsample=0.7,
                colsample_bytree=0.7,
            )

        return models

    def _detect_problem_type(self, y: np.ndarray) -> str:
        """
        Detect whether this is a classification or regression problem.

        Args:
            y: Target array

        Returns:
            'classification' or 'regression'
        """
        # Convert to string to handle mixed types
        y_str = [str(val) for val in y]
        unique_values = len(set(y_str))

        # If numeric and many unique values, likely regression
        if self._is_numeric_array(y):
            if unique_values > 20 or unique_values / len(y) > 0.1:
                return "regression"

        return "classification"

    def _is_numeric_array(self, y: np.ndarray) -> bool:
        """Check if array contains numeric values."""
        try:
            # Try to convert to float
            [float(val) for val in y]
            return True
        except (ValueError, TypeError):
            return False

    def compare_models(
        self, X: np.ndarray, y: np.ndarray, feature_names: List[str]
    ) -> List[ModelResult]:
        """
        Compare multiple models and return results.

        Args:
            X: Feature matrix
            y: Target vector
            feature_names: Names of features

        Returns:
            List of ModelResult objects with performance metrics
        """
        # Detect problem type
        problem_type = self._detect_problem_type(y)

        if problem_type == "classification":
            return self._compare_classification_models(X, y, feature_names)
        else:
            return self._compare_regression_models(X, y, feature_names)

    def _compare_classification_models(
        self, X: np.ndarray, y: np.ndarray, feature_names: List[str]
    ) -> List[ModelResult]:
        """Compare classification models."""
        # Encode target labels
        label_encoder = LabelEncoder()
        y_encoded = label_encoder.fit_transform(y)

        # Handle small datasets gracefully
        n_samples = len(y_encoded)
        unique_classes, class_counts = np.unique(y_encoded, return_counts=True)
        min_class_count = min(class_counts)

        # For very small datasets, use the whole dataset for both training and testing
        # or adjust test size to ensure at least 1 sample per class in test set
        if n_samples <= 10 or min_class_count < 2:
            # Too small for proper train/test split, use whole dataset
            X_train, X_test = X, X
            y_train, y_test = y_encoded, y_encoded
        else:
            # Calculate appropriate test size to ensure stratification works
            test_size = max(0.1, min(0.3, 2.0 / min_class_count))

            try:
                X_train, X_test, y_train, y_test = train_test_split(
                    X,
                    y_encoded,
                    test_size=test_size,
                    random_state=self.random_state,
                    stratify=y_encoded,
                )
            except ValueError:
                # Fallback: no stratification for problematic cases
                X_train, X_test, y_train, y_test = train_test_split(
                    X, y_encoded, test_size=test_size, random_state=self.random_state
                )

        results = []

        for model_name, model in self._classification_models.items():
            try:
                result = self._evaluate_classification_model(
                    model,
                    model_name,
                    X_train,
                    X_test,
                    y_train,
                    y_test,
                    feature_names,
                    label_encoder,
                )
                results.append(result)
            except Exception as e:
                warnings.warn(f"Model {model_name} failed: {str(e)}")
                continue

        return results

    def _compare_regression_models(
        self, X: np.ndarray, y: np.ndarray, feature_names: List[str]
    ) -> List[ModelResult]:
        """Compare regression models."""
        # Convert target to float
        y_float = np.array([float(val) for val in y])

        # Handle small datasets gracefully
        n_samples = len(y_float)

        if n_samples <= 10:
            # Too small for proper train/test split, use whole dataset
            X_train, X_test = X, X
            y_train, y_test = y_float, y_float
        else:
            # Create train/test split with appropriate test size
            test_size = max(0.1, min(0.3, 2.0 / n_samples))
            X_train, X_test, y_train, y_test = train_test_split(
                X, y_float, test_size=test_size, random_state=self.random_state
            )

        results = []

        for model_name, model in self._regression_models.items():
            try:
                result = self._evaluate_regression_model(
                    model, model_name, X_train, X_test, y_train, y_test, feature_names
                )
                results.append(result)
            except Exception as e:
                warnings.warn(f"Model {model_name} failed: {str(e)}")
                continue

        return results

    def _evaluate_classification_model(
        self,
        model,
        model_name: str,
        X_train: np.ndarray,
        X_test: np.ndarray,
        y_train: np.ndarray,
        y_test: np.ndarray,
        feature_names: List[str],
        label_encoder: LabelEncoder,
    ) -> ModelResult:
        """Evaluate a single model with comprehensive metrics."""

        # Cross-validation on training set - adapt to small datasets
        n_samples = X_train.shape[0]
        if n_samples < 5:
            # Too few samples for cross-validation, use train score as proxy
            model.fit(X_train, y_train)
            cv_score = accuracy_score(y_train, model.predict(X_train))
            cv_std = 0.0
        else:
            # Use appropriate number of folds for dataset size
            n_splits = min(5, n_samples)
            cv_scores = cross_val_score(
                model,
                X_train,
                y_train,
                cv=StratifiedKFold(
                    n_splits=n_splits, shuffle=True, random_state=self.random_state
                ),
                scoring="accuracy",
            )
            cv_score = cv_scores.mean()
            cv_std = cv_scores.std()

        # Train on full training set
        model.fit(X_train, y_train)

        # Evaluate on training and test sets
        train_score = accuracy_score(y_train, model.predict(X_train))
        test_score = accuracy_score(y_test, model.predict(X_test))

        # Calculate overfitting gap
        overfitting_gap = max(0, train_score - test_score)

        # Store preprocessing info
        preprocessing_pipeline = {
            "label_encoder": label_encoder,
            "feature_scaling": "StandardScaler applied in FeatureProcessor",
        }

        return ModelResult(
            name=model_name,
            model=model,
            cv_score=cv_score,
            cv_std=cv_std,
            test_score=test_score,
            overfitting_gap=overfitting_gap,
            preprocessing_pipeline=preprocessing_pipeline,
            feature_names=feature_names,
            train_score=train_score,
            problem_type="classification",
            training_data=(X_train, y_train),
        )

    def _evaluate_regression_model(
        self,
        model,
        model_name: str,
        X_train: np.ndarray,
        X_test: np.ndarray,
        y_train: np.ndarray,
        y_test: np.ndarray,
        feature_names: List[str],
    ) -> ModelResult:
        """Evaluate a single regression model with comprehensive metrics."""

        # Cross-validation on training set (using R² score) - adapt to small datasets
        n_samples = X_train.shape[0]
        if n_samples < 5:
            # Too few samples for cross-validation, use train score as proxy
            model.fit(X_train, y_train)
            cv_score = r2_score(y_train, model.predict(X_train))
            cv_std = 0.0
        else:
            # Use appropriate number of folds for dataset size
            n_splits = min(5, n_samples)
            cv_scores = cross_val_score(
                model,
                X_train,
                y_train,
                cv=KFold(
                    n_splits=n_splits, shuffle=True, random_state=self.random_state
                ),
                scoring="r2",
            )
            cv_score = cv_scores.mean()
            cv_std = cv_scores.std()

        # Train on full training set
        model.fit(X_train, y_train)

        # Evaluate on training and test sets using R² score
        train_score = r2_score(y_train, model.predict(X_train))
        test_score = r2_score(y_test, model.predict(X_test))

        # Calculate overfitting gap
        overfitting_gap = max(0, train_score - test_score)

        # Store preprocessing info
        preprocessing_pipeline = {
            "feature_scaling": "StandardScaler applied in FeatureProcessor",
            "target_type": "regression",
        }

        return ModelResult(
            name=model_name,
            model=model,
            cv_score=cv_score,
            cv_std=cv_std,
            test_score=test_score,
            overfitting_gap=overfitting_gap,
            preprocessing_pipeline=preprocessing_pipeline,
            feature_names=feature_names,
            train_score=train_score,
            problem_type="regression",
            training_data=(X_train, y_train),
        )

    def select_best_model(self, results: List[ModelResult]) -> ModelResult:
        """
        Select the best model with overfitting prevention.

        Uses a scoring algorithm that prioritizes generalization:
        score = test_accuracy - 2 * max(0, overfitting_gap) + cv_stability_bonus

        Args:
            results: List of ModelResult objects

        Returns:
            Best ModelResult based on selection criteria
        """
        if not results:
            raise ValueError("No valid model results to select from")

        for result in results:
            # Calculate selection score
            cv_stability_bonus = 0.1 * (1 - result.cv_std)  # Lower std is better
            selection_score = (
                result.test_score - 2 * result.overfitting_gap + cv_stability_bonus
            )
            result.selection_score = selection_score

        # Select model with highest selection score
        best_result = max(results, key=lambda r: r.selection_score)

        return best_result

    def get_model_diagnostics(self, results: List[ModelResult]) -> pd.DataFrame:
        """
        Get comprehensive model comparison diagnostics.

        Args:
            results: List of ModelResult objects

        Returns:
            DataFrame with model comparison metrics
        """
        diagnostics_data = []

        for result in results:
            diagnostics_data.append(
                {
                    "Model": result.name,
                    "CV Score": f"{result.cv_score:.3f} ± {result.cv_std:.3f}",
                    "Test Score": f"{result.test_score:.3f}",
                    "Train Score": (
                        f"{result.train_score:.3f}" if result.train_score else "N/A"
                    ),
                    "Overfitting Gap": f"{result.overfitting_gap:.3f}",
                    "Selection Score": (
                        f"{result.selection_score:.3f}"
                        if result.selection_score
                        else "N/A"
                    ),
                }
            )

        df = pd.DataFrame(diagnostics_data)
        return df.sort_values("Selection Score", ascending=False).reset_index(drop=True)

    def validate_data(self, X: np.ndarray, y: np.ndarray) -> None:
        """
        Validate input data for model training.

        Args:
            X: Feature matrix
            y: Target vector

        Raises:
            ValueError: If data validation fails
        """
        # Check basic requirements
        if X.shape[0] == 0:
            raise ValueError("Feature matrix is empty")

        if len(y) == 0:
            raise ValueError("Target vector is empty")

        if X.shape[0] != len(y):
            raise ValueError(
                f"Feature matrix rows ({X.shape[0]}) != target vector length ({len(y)})"
            )

        # Check for overfitting risk
        n_samples, n_features = X.shape
        feature_to_sample_ratio = n_features / n_samples

        if feature_to_sample_ratio > 0.1:
            warnings.warn(
                f"High feature-to-sample ratio ({feature_to_sample_ratio:.3f}). "
                f"Risk of overfitting with {n_features} features and {n_samples} samples."
            )

        if n_samples < 50:
            warnings.warn(
                f"Very small dataset ({n_samples} samples). "
                "Results may not be reliable."
            )

        # Detect problem type and validate accordingly
        problem_type = self._detect_problem_type(y)

        if problem_type == "classification":
            # Check target distribution for classification
            unique_targets = np.unique(y)
            if len(unique_targets) < 2:
                raise ValueError("Target variable must have at least 2 classes")

            min_class_count = min([np.sum(y == target) for target in unique_targets])
            if min_class_count < 2:
                raise ValueError("Each target class must have at least 2 samples")
        else:
            # For regression, just check for valid numeric values
            try:
                float_y = [float(val) for val in y]
                if any(np.isnan(val) or np.isinf(val) for val in float_y):
                    raise ValueError(
                        "Target variable contains invalid values (NaN or Inf)"
                    )
            except (ValueError, TypeError):
                raise ValueError(
                    "Target variable for regression must contain numeric values"
                )

    def get_feature_importance(self, model_result: ModelResult) -> Dict[str, float]:
        """
        Get feature importance from trained model.

        Args:
            model_result: Trained model result

        Returns:
            Dictionary mapping feature names to importance scores
        """
        model = model_result.model
        feature_names = model_result.feature_names

        try:
            # Try to get feature importance (for tree-based models)
            if hasattr(model, "feature_importances_"):
                importances = model.feature_importances_
            # For linear models, use coefficient magnitudes
            elif hasattr(model, "coef_"):
                importances = (
                    np.abs(model.coef_[0])
                    if model.coef_.ndim > 1
                    else np.abs(model.coef_)
                )
            else:
                # Fallback: equal importance
                importances = np.ones(len(feature_names)) / len(feature_names)

            # Normalize to sum to 1
            importances = importances / np.sum(importances)

            return dict(zip(feature_names, importances))

        except Exception as e:
            warnings.warn(f"Could not extract feature importance: {str(e)}")
            # Return equal importance as fallback
            equal_importance = 1.0 / len(feature_names)
            return {name: equal_importance for name in feature_names}

    def get_coefficients_and_errors(
        self, model_result: ModelResult
    ) -> Dict[str, Dict[str, float]]:
        """
        Get model coefficients and standard errors for linear models.

        Args:
            model_result: Trained model result

        Returns:
            Dictionary with feature names as keys and dictionaries containing
            'coefficient' and 'std_error' as values. Returns None if model
            doesn't support coefficients.
        """
        model = model_result.model
        feature_names = model_result.feature_names

        # Check if model supports coefficients
        if not hasattr(model, "coef_"):
            return None

        try:
            # Get coefficients
            if model.coef_.ndim > 1:
                coefficients = model.coef_[0]  # For binary classification
            else:
                coefficients = model.coef_

            # Calculate standard errors (simplified approach for now)
            std_errors = self._calculate_standard_errors(model_result)

            # Create result dictionary
            result = {}
            for i, feature_name in enumerate(feature_names):
                result[feature_name] = {
                    "coefficient": float(coefficients[i]),
                    "std_error": (
                        float(std_errors[i]) if std_errors is not None else None
                    ),
                    "z_score": (
                        float(coefficients[i] / std_errors[i])
                        if std_errors is not None and std_errors[i] != 0
                        else None
                    ),
                    "p_value": (
                        self._calculate_p_value(coefficients[i], std_errors[i])
                        if std_errors is not None and std_errors[i] != 0
                        else None
                    ),
                }

            return result

        except Exception as e:
            warnings.warn(
                f"Could not extract coefficients and standard errors: {str(e)}"
            )
            return None

    def _calculate_standard_errors(self, model_result: ModelResult) -> np.ndarray:
        """
        Calculate standard errors for model coefficients using bootstrap method.

        For linear models, we use a simplified bootstrap approach to estimate
        standard errors when analytical methods aren't available.
        """
        model = model_result.model

        try:
            # Store training data in model_result if available
            if hasattr(model_result, "training_data"):
                X_train, y_train = model_result.training_data
                return self._bootstrap_standard_errors(model, X_train, y_train)
            else:
                # If no training data stored, return None
                # This could be improved by storing training data during model fitting
                return None

        except Exception as e:
            warnings.warn(f"Could not calculate standard errors: {str(e)}")
            return None

    def _bootstrap_standard_errors(
        self, model, X: np.ndarray, y: np.ndarray, n_bootstrap: int = 100
    ) -> np.ndarray:
        """
        Calculate standard errors using bootstrap resampling.

        Args:
            model: Fitted model
            X: Feature matrix
            y: Target vector
            n_bootstrap: Number of bootstrap samples

        Returns:
            Array of standard errors for each coefficient
        """
        try:
            from sklearn.utils import resample

            n_samples, n_features = X.shape
            coefficients_bootstrap = np.zeros((n_bootstrap, n_features))

            # Create bootstrap samples and refit model
            for i in range(n_bootstrap):
                # Resample with replacement
                X_boot, y_boot = resample(X, y, random_state=i)

                # Create new model instance with same parameters
                boot_model = type(model)(**model.get_params())

                # Fit on bootstrap sample
                boot_model.fit(X_boot, y_boot)

                # Extract coefficients
                if boot_model.coef_.ndim > 1:
                    coefficients_bootstrap[i] = boot_model.coef_[0]
                else:
                    coefficients_bootstrap[i] = boot_model.coef_

            # Calculate standard errors as standard deviation across bootstrap samples
            std_errors = np.std(coefficients_bootstrap, axis=0)
            return std_errors

        except Exception as e:
            warnings.warn(f"Bootstrap standard error calculation failed: {str(e)}")
            return None

    def _calculate_p_value(self, coefficient: float, std_error: float) -> float:
        """Calculate p-value for coefficient using z-test approximation."""
        if std_error is None or std_error == 0:
            return None

        try:
            from scipy import stats

            z_score = coefficient / std_error
            # Two-tailed test
            p_value = 2 * (1 - stats.norm.cdf(abs(z_score)))
            return float(p_value)
        except ImportError:
            # scipy not available
            return None
