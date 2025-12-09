#!/usr/bin/env python3
"""
ScenarioML Basic Example

This example demonstrates the core functionality of ScenarioML with a
simple customer satisfaction prediction scenario.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
parent_dir = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(parent_dir))

from edsl.scenarios import ScenarioList  # noqa: E402


def create_sample_data():
    """Create sample customer satisfaction survey data."""
    return [
        {
            "business_type": "Enterprise",
            "company_size": "101-500",
            "industry": "Technology",
            "tools_used": "['Salesforce', 'HubSpot', 'Slack']",
            "features_used": "['Analytics', 'Automation', 'Integration']",
            "satisfaction_level": "Very Satisfied",
            "support_interactions": "1-2",
            "will_renew": "Yes",
        },
        {
            "business_type": "SMB",
            "company_size": "21-100",
            "industry": "Healthcare",
            "tools_used": "['Excel', 'QuickBooks']",
            "features_used": "['Basic', 'Reporting']",
            "satisfaction_level": "Satisfied",
            "support_interactions": "3-5",
            "will_renew": "Yes",
        },
        {
            "business_type": "SMB",
            "company_size": "1-5",
            "industry": "Retail",
            "tools_used": "['Excel']",
            "features_used": "['Basic']",
            "satisfaction_level": "Neutral",
            "support_interactions": "0",
            "will_renew": "No",
        },
        {
            "business_type": "Enterprise",
            "company_size": "More than 500",
            "industry": "Financial Services",
            "tools_used": "['Salesforce', 'Microsoft Teams', 'Tableau']",
            "features_used": "['Analytics', 'Automation', 'Integration', 'Security']",
            "satisfaction_level": "Very Satisfied",
            "support_interactions": "1-2",
            "will_renew": "Yes",
        },
        {
            "business_type": "SMB",
            "company_size": "6-20",
            "industry": "Education",
            "tools_used": "['Zoom', 'Google Workspace']",
            "features_used": "['Basic', 'Collaboration']",
            "satisfaction_level": "Satisfied",
            "support_interactions": "3-5",
            "will_renew": "Yes",
        },
        {
            "business_type": "Enterprise",
            "company_size": "101-500",
            "industry": "Manufacturing",
            "tools_used": "['SAP', 'Microsoft Office']",
            "features_used": "['Integration', 'Reporting']",
            "satisfaction_level": "Dissatisfied",
            "support_interactions": "6-10",
            "will_renew": "No",
        },
        {
            "business_type": "SMB",
            "company_size": "21-100",
            "industry": "Technology",
            "tools_used": "['Slack', 'GitHub', 'Jira']",
            "features_used": "['Integration', 'Automation']",
            "satisfaction_level": "Very Satisfied",
            "support_interactions": "1-2",
            "will_renew": "Yes",
        },
        {
            "business_type": "Enterprise",
            "company_size": "More than 500",
            "industry": "Healthcare",
            "tools_used": "['Epic', 'Microsoft Teams']",
            "features_used": "['Security', 'Integration']",
            "satisfaction_level": "Neutral",
            "support_interactions": "3-5",
            "will_renew": "No",
        },
        {
            "business_type": "SMB",
            "company_size": "1-5",
            "industry": "Retail",
            "tools_used": "['Square', 'Excel']",
            "features_used": "['Basic', 'Reporting']",
            "satisfaction_level": "Satisfied",
            "support_interactions": "0",
            "will_renew": "Yes",
        },
        {
            "business_type": "SMB",
            "company_size": "6-20",
            "industry": "Professional Services",
            "tools_used": "['QuickBooks', 'Zoom']",
            "features_used": "['Basic', 'Collaboration']",
            "satisfaction_level": "Very Satisfied",
            "support_interactions": "1-2",
            "will_renew": "Yes",
        },
    ] * 3  # Repeat to have enough data for training


def main():
    """Main example workflow."""
    print("ScenarioML Basic Example")
    print("=" * 40)

    # Create sample data
    print("1. Creating sample customer satisfaction survey data...")
    sample_data = create_sample_data()

    # Create ScenarioList
    scenarios = ScenarioList(sample_data)
    print(f"   Created ScenarioList with {len(scenarios)} scenarios")

    # Train predictive model
    print("\\n2. Training predictive model...")
    print("   Processing features and comparing models...")

    try:
        # This will use the predict() method we added to ScenarioList
        model = scenarios.predict(y="will_renew")
        print("   ✓ Model trained successfully!")

        # Show model diagnostics
        print("\\n3. Model Diagnostics:")
        diagnostics = model.diagnostics()
        print(f"   Model: {diagnostics['model_name']}")
        print(
            f"   Cross-validation score: {diagnostics['cv_score']:.3f} ± {diagnostics['cv_std']:.3f}"
        )
        print(f"   Test accuracy: {diagnostics['test_score']:.3f}")
        print(f"   Overfitting gap: {diagnostics['overfitting_gap']:.3f}")
        print(f"   Number of features: {diagnostics['feature_count']}")

        # Show feature importance
        print("\\n4. Feature Importance:")
        importance = model.get_feature_importance()
        sorted_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)

        for i, (feature, score) in enumerate(sorted_features[:10]):  # Top 10
            print(f"   {i+1:2d}. {feature:<30} {score:.3f}")

        # Make predictions on new scenarios
        print("\\n5. Making Predictions:")

        test_scenarios = [
            {
                "business_type": "SMB",
                "company_size": "21-100",
                "industry": "Technology",
                "tools_used": "['Slack', 'GitHub']",
                "features_used": "['Integration', 'Automation']",
                "satisfaction_level": "Satisfied",
                "support_interactions": "1-2",
            },
            {
                "business_type": "Enterprise",
                "company_size": "More than 500",
                "industry": "Financial Services",
                "tools_used": "['Salesforce', 'Tableau']",
                "features_used": "['Analytics', 'Security']",
                "satisfaction_level": "Very Satisfied",
                "support_interactions": "3-5",
            },
            {
                "business_type": "SMB",
                "company_size": "1-5",
                "industry": "Retail",
                "tools_used": "['Excel']",
                "features_used": "['Basic']",
                "satisfaction_level": "Dissatisfied",
                "support_interactions": "6-10",
            },
        ]

        for i, scenario in enumerate(test_scenarios, 1):
            prediction = model.predict(scenario)
            probabilities = model.predict_proba(scenario)

            print(f"\\n   Scenario {i}:")
            print(
                f"   Business: {scenario['business_type']}, Size: {scenario['company_size']}"
            )
            print(f"   Industry: {scenario['industry']}")
            print(f"   Satisfaction: {scenario['satisfaction_level']}")
            print(f"   → Prediction: {prediction}")
            print(f"   → Confidence: {probabilities[prediction]:.1%}")

        # Model summary
        print("\\n6. Model Summary:")
        print(model.summary())

        print("\\n" + "=" * 40)
        print("Example completed successfully! 🎉")

    except ImportError as e:
        print(f"   ✗ Missing dependencies: {e}")
        print("   Install with: pip install pandas scikit-learn")
    except Exception as e:
        print(f"   ✗ Error: {e}")


if __name__ == "__main__":
    main()
