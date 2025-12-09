# ScenarioML: AutoML for Survey and Scenario Data

**ScenarioML** is a specialized AutoML module within EDSL designed for survey and experimental data. It provides a simple, powerful interface for building predictive models with automatic feature engineering and built-in overfitting prevention.

## 🎯 Key Features

- **Zero configuration** AutoML for survey/experimental data
- **Automatic feature detection** for common survey patterns (ordinal, categorical, text lists, numeric)
- **Overfitting prevention** built into model selection
- **Production ready** prediction objects with persistence
- **Robust handling** of missing values and unseen categories

## 🚀 Quick Start

```python
from edsl import ScenarioList

# Load your survey data
scenarios = ScenarioList.from_csv('customer_survey.csv')

# Build predictive model with one line of code
model = scenarios.predict(y='satisfaction_rating')

# Make predictions on new data
new_customer = {
    'industry': 'Technology',
    'company_size': '100-500',
    'features_used': "['Analytics', 'Automation']",
    'support_interactions': '1-2'
}

prediction = model.predict(new_customer)
confidence = model.predict_proba(new_customer)

print(f"Predicted satisfaction: {prediction}")
print(f"Confidence: {confidence}")
```

## 📊 Automatic Feature Engineering

ScenarioML automatically detects and processes different types of survey data:

### Supported Feature Types

1. **Numeric Features**: Direct numerical values (age, revenue, count)
2. **Categorical Features**: Text categories (industry, business_type)
3. **Ordinal Features**: Ordered categories with automatic pattern detection:
   - Company sizes: `'1-5', '6-20', '21-100', '101-500', 'More than 500'`
   - Satisfaction: `'Very Dissatisfied', 'Dissatisfied', 'Neutral', 'Satisfied', 'Very Satisfied'`
   - Frequency: `'Never', 'Rarely', 'Sometimes', 'Often', 'Always'`
4. **Text Lists**: Tool/feature lists like `"['Salesforce', 'HubSpot', 'Slack']"`

### Preprocessing Features

- **Smart missing value handling**: Context-appropriate imputation for each feature type
- **Unseen category handling**: Graceful handling of new categories during prediction
- **Automatic scaling**: Standard scaling applied to ensure model stability
- **TF-IDF processing**: Intelligent text list vectorization with stop word removal

## 🧠 Model Selection

ScenarioML compares multiple models and selects the best one using a sophisticated algorithm that prioritizes generalization over training performance:

### Model Portfolio

- **Logistic Regression** (Ridge & Lasso) - Linear models with regularization
- **Random Forest** - Tree-based ensemble with conservative parameters
- **XGBoost** (optional) - Gradient boosting with overfitting prevention

### Selection Algorithm

```python
selection_score = test_accuracy - 2 * overfitting_gap + cv_stability_bonus
```

This algorithm:
- **Penalizes overfitting** heavily (2x weight on training-test gap)
- **Rewards stability** (lower cross-validation variance)
- **Focuses on generalization** rather than training performance

## 📈 Usage Examples

### Customer Satisfaction Analysis

```python
# Load survey data
satisfaction_survey = ScenarioList([
    {
        'company_type': 'Enterprise',
        'industry': 'Technology',
        'features_used': "['Analytics', 'Integration']",
        'support_level': 'Premium',
        'satisfaction': 'Very Satisfied'
    },
    {
        'company_type': 'SMB',
        'industry': 'Healthcare',
        'features_used': "['Basic', 'Reporting']",
        'support_level': 'Standard',
        'satisfaction': 'Satisfied'
    },
    # ... more data
])

# Build satisfaction predictor
satisfaction_model = satisfaction_survey.predict(y='satisfaction')

# Predict for new customer
new_customer = {
    'company_type': 'SMB',
    'industry': 'Financial Services',
    'features_used': "['Analytics', 'Automation']",
    'support_level': 'Premium'
}

prediction = satisfaction_model.predict(new_customer)
probabilities = satisfaction_model.predict_proba(new_customer)
```

### A/B Testing Analysis

```python
# A/B test results
ab_test = ScenarioList([
    {'variant': 'A', 'price': '$10', 'features': "['Basic']", 'converted': 'Yes'},
    {'variant': 'B', 'price': '$15', 'features': "['Basic', 'Premium']", 'converted': 'No'},
    # ... more test data
])

# Build conversion predictor
conversion_model = ab_test.predict(y='converted')

# Test new pricing scenarios
scenarios_to_test = [
    {'variant': 'C', 'price': '$12', 'features': "['Basic', 'Analytics']"},
    {'variant': 'D', 'price': '$20', 'features': "['Premium', 'Analytics', 'Support']"}
]

predictions = conversion_model.predict(scenarios_to_test)
probabilities = conversion_model.predict_proba(scenarios_to_test)
```

## 🔧 Advanced Features

### Model Diagnostics

```python
# Get comprehensive model information
diagnostics = model.diagnostics()
print(f"Model: {diagnostics['model_name']}")
print(f"Cross-validation score: {diagnostics['cv_score']:.3f}")
print(f"Test accuracy: {diagnostics['test_score']:.3f}")
print(f"Overfitting gap: {diagnostics['overfitting_gap']:.3f}")

# Feature importance
importance = model.get_feature_importance()
for feature, score in sorted(importance.items(), key=lambda x: x[1], reverse=True):
    print(f"{feature}: {score:.3f}")
```

### Model Persistence

```python
# Save trained model
model.save('customer_satisfaction_model.joblib')

# Load model later
from edsl.scenarios.scenarioml import Prediction
loaded_model = Prediction.load('customer_satisfaction_model.joblib')

# Use loaded model for predictions
prediction = loaded_model.predict(new_data)
```

### Prediction Validation

```python
# Validate input scenarios
validation_result = model.validate_scenario(new_scenario)

if not validation_result['valid']:
    print("Warnings:", validation_result['warnings'])
    print("Errors:", validation_result['errors'])
    print("Missing features:", validation_result['missing_features'])
```

## ⚠️ Best Practices

### Data Requirements

- **Minimum samples**: 50+ recommended for reliable results
- **Feature-to-sample ratio**: Keep below 0.1 to avoid overfitting
- **Target classes**: At least 2 different values, with 2+ samples per class
- **Feature consistency**: Use consistent naming and formats across scenarios

### Handling Overfitting

ScenarioML includes built-in overfitting prevention:

- **Conservative hyperparameters** for all models
- **Automatic regularization** with cross-validation tuning
- **Selection algorithm** that penalizes overfitting gaps
- **Warnings** when overfitting is detected

### Data Preparation Tips

```python
# Good: Consistent ordinal scales
'satisfaction': 'Very Satisfied'  # Use standard patterns

# Good: Structured text lists
'tools_used': "['Salesforce', 'HubSpot']"

# Good: Meaningful categories
'industry': 'Technology'

# Avoid: Inconsistent formats
'satisfaction': 'very satisfied'  # Inconsistent capitalization
'tools_used': "Salesforce, HubSpot"  # Inconsistent list format
```

## 🧪 Testing and Validation

ScenarioML includes comprehensive testing:

```bash
# Run all ScenarioML tests
pytest edsl/scenarios/scenarioml/tests/

# Run specific test categories
pytest edsl/scenarios/scenarioml/tests/test_feature_processor.py
pytest edsl/scenarios/scenarioml/tests/test_model_selector.py
pytest edsl/scenarios/scenarioml/tests/test_prediction.py
pytest edsl/scenarios/scenarioml/tests/test_integration.py
```

## 🤝 Contributing

ScenarioML is part of the EDSL ecosystem. Contributions welcome!

### Development Setup

```bash
# Install EDSL in development mode
pip install -e .

# Run ScenarioML tests
pytest edsl/scenarios/scenarioml/tests/

# Format code (from project root)
black edsl/scenarios/scenarioml/
isort edsl/scenarios/scenarioml/

# Type checking
mypy edsl/scenarios/scenarioml/
```

## 📄 License

MIT License - see LICENSE file for details.

## 🆘 Support

- **Documentation**: [EDSL Documentation](https://docs.expectedparrot.com)
- **Issues**: [GitHub Issues](https://github.com/expectedparrot/edsl/issues)
- **Community**: [EDSL Community](https://discord.gg/expectedparrot)

---

**ScenarioML** makes machine learning accessible for survey and experimental data, with automatic feature engineering and robust overfitting prevention built-in. Perfect for researchers, analysts, and product teams working with survey data.