"""
ScenarioML: AutoML for Survey and Scenario Data

ScenarioML provides a simple, powerful interface for building predictive models
with automatic feature engineering and built-in overfitting prevention, specifically
designed for survey and experimental data.

Core features:
- Zero configuration AutoML for survey/experimental data
- Automatic feature detection for common survey patterns
- Overfitting prevention built into model selection
- Production ready prediction objects with persistence

Basic usage:
    from edsl import ScenarioList

    scenarios = ScenarioList.from_csv('survey_data.csv')
    prediction = scenarios.predict(y='purchase_intent')
    result = prediction.predict({'business_type': 'Enterprise', 'size': 'Large'})
"""

from .prediction import Prediction

__all__ = ["Prediction"]
