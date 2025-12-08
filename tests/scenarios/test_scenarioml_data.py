"""
Test data for ScenarioML tests.

Provides realistic sample data for testing feature processing, model training,
and prediction functionality.
"""

import pandas as pd
from typing import List, Dict, Any


def get_sample_survey_data() -> List[Dict[str, Any]]:
    """
    Get sample survey data for testing.

    Returns realistic customer satisfaction survey data with mixed feature types:
    - Numeric features (company_size_employees)
    - Categorical features (business_type, industry)
    - Ordinal features (company_size, satisfaction_level)
    - Text list features (tools_used, features_used)
    """
    return [
        {
            'business_type': 'Enterprise',
            'company_size': '101-500',
            'company_size_employees': 250,
            'industry': 'Technology',
            'tools_used': "['Salesforce', 'HubSpot', 'Slack']",
            'features_used': "['Analytics', 'Automation', 'Integration']",
            'satisfaction_level': 'Very Satisfied',
            'support_interactions': '1-2',
            'will_renew': 'Yes'
        },
        {
            'business_type': 'SMB',
            'company_size': '21-100',
            'company_size_employees': 45,
            'industry': 'Healthcare',
            'tools_used': "['Excel', 'QuickBooks']",
            'features_used': "['Basic', 'Reporting']",
            'satisfaction_level': 'Satisfied',
            'support_interactions': '3-5',
            'will_renew': 'Yes'
        },
        {
            'business_type': 'SMB',
            'company_size': '1-5',
            'company_size_employees': 3,
            'industry': 'Retail',
            'tools_used': "['Excel']",
            'features_used': "['Basic']",
            'satisfaction_level': 'Neutral',
            'support_interactions': '0',
            'will_renew': 'No'
        },
        {
            'business_type': 'Enterprise',
            'company_size': 'More than 500',
            'company_size_employees': 1200,
            'industry': 'Financial Services',
            'tools_used': "['Salesforce', 'Microsoft Teams', 'Tableau']",
            'features_used': "['Analytics', 'Automation', 'Integration', 'Security']",
            'satisfaction_level': 'Very Satisfied',
            'support_interactions': '1-2',
            'will_renew': 'Yes'
        },
        {
            'business_type': 'SMB',
            'company_size': '6-20',
            'company_size_employees': 15,
            'industry': 'Education',
            'tools_used': "['Zoom', 'Google Workspace']",
            'features_used': "['Basic', 'Collaboration']",
            'satisfaction_level': 'Satisfied',
            'support_interactions': '3-5',
            'will_renew': 'Yes'
        },
        {
            'business_type': 'Enterprise',
            'company_size': '101-500',
            'company_size_employees': 350,
            'industry': 'Manufacturing',
            'tools_used': "['SAP', 'Microsoft Office']",
            'features_used': "['Integration', 'Reporting']",
            'satisfaction_level': 'Dissatisfied',
            'support_interactions': '6-10',
            'will_renew': 'No'
        },
        {
            'business_type': 'SMB',
            'company_size': '21-100',
            'company_size_employees': 80,
            'industry': 'Technology',
            'tools_used': "['Slack', 'GitHub', 'Jira']",
            'features_used': "['Integration', 'Automation']",
            'satisfaction_level': 'Very Satisfied',
            'support_interactions': '1-2',
            'will_renew': 'Yes'
        },
        {
            'business_type': 'Enterprise',
            'company_size': 'More than 500',
            'company_size_employees': 850,
            'industry': 'Healthcare',
            'tools_used': "['Epic', 'Microsoft Teams']",
            'features_used': "['Security', 'Integration']",
            'satisfaction_level': 'Neutral',
            'support_interactions': '3-5',
            'will_renew': 'No'
        },
        {
            'business_type': 'SMB',
            'company_size': '1-5',
            'company_size_employees': 5,
            'industry': 'Retail',
            'tools_used': "['Square', 'Excel']",
            'features_used': "['Basic', 'Reporting']",
            'satisfaction_level': 'Satisfied',
            'support_interactions': '0',
            'will_renew': 'Yes'
        },
        {
            'business_type': 'SMB',
            'company_size': '6-20',
            'company_size_employees': 12,
            'industry': 'Professional Services',
            'tools_used': "['QuickBooks', 'Zoom']",
            'features_used': "['Basic', 'Collaboration']",
            'satisfaction_level': 'Very Satisfied',
            'support_interactions': '1-2',
            'will_renew': 'Yes'
        },
        # Additional samples for better model training
        {
            'business_type': 'Enterprise',
            'company_size': '101-500',
            'company_size_employees': 200,
            'industry': 'Technology',
            'tools_used': "['Slack', 'Salesforce', 'Zoom']",
            'features_used': "['Analytics', 'Integration']",
            'satisfaction_level': 'Satisfied',
            'support_interactions': '3-5',
            'will_renew': 'Yes'
        },
        {
            'business_type': 'SMB',
            'company_size': '21-100',
            'company_size_employees': 65,
            'industry': 'Financial Services',
            'tools_used': "['QuickBooks', 'Excel']",
            'features_used': "['Reporting', 'Basic']",
            'satisfaction_level': 'Dissatisfied',
            'support_interactions': 'More than 10',
            'will_renew': 'No'
        },
        {
            'business_type': 'Enterprise',
            'company_size': 'More than 500',
            'company_size_employees': 2000,
            'industry': 'Manufacturing',
            'tools_used': "['SAP', 'Microsoft Teams', 'Tableau']",
            'features_used': "['Integration', 'Analytics', 'Security']",
            'satisfaction_level': 'Very Satisfied',
            'support_interactions': '1-2',
            'will_renew': 'Yes'
        },
        {
            'business_type': 'SMB',
            'company_size': '1-5',
            'company_size_employees': 2,
            'industry': 'Education',
            'tools_used': "['Google Workspace']",
            'features_used': "['Basic']",
            'satisfaction_level': 'Neutral',
            'support_interactions': '6-10',
            'will_renew': 'No'
        },
        {
            'business_type': 'SMB',
            'company_size': '6-20',
            'company_size_employees': 18,
            'industry': 'Healthcare',
            'tools_used': "['Epic', 'Zoom']",
            'features_used': "['Security', 'Collaboration']",
            'satisfaction_level': 'Satisfied',
            'support_interactions': '1-2',
            'will_renew': 'Yes'
        }
    ]


def get_minimal_test_data() -> List[Dict[str, Any]]:
    """
    Get minimal test data for edge case testing.

    Returns a very small dataset for testing error handling and edge cases.
    """
    return [
        {
            'feature1': 'A',
            'feature2': 1,
            'target': 'Yes'
        },
        {
            'feature1': 'B',
            'feature2': 2,
            'target': 'No'
        },
        {
            'feature1': 'A',
            'feature2': 3,
            'target': 'Yes'
        },
        {
            'feature1': 'B',
            'feature2': 4,
            'target': 'No'
        }
    ]


def get_problematic_data() -> List[Dict[str, Any]]:
    """
    Get data with common problems for testing error handling.

    Returns data with missing values, inconsistent types, and other issues.
    """
    return [
        {
            'text_feature': "['item1', 'item2']",
            'numeric_feature': 10,
            'categorical_feature': 'Category A',
            'target': 'Positive'
        },
        {
            'text_feature': None,  # Missing value
            'numeric_feature': 20,
            'categorical_feature': 'Category B',
            'target': 'Negative'
        },
        {
            'text_feature': "['item3']",
            'numeric_feature': None,  # Missing numeric value
            'categorical_feature': 'Category A',
            'target': 'Positive'
        },
        {
            'text_feature': "item4, item5",  # Different text format
            'numeric_feature': 30,
            'categorical_feature': None,  # Missing categorical
            'target': 'Negative'
        },
        {
            'text_feature': "[]",  # Empty list
            'numeric_feature': 40,
            'categorical_feature': 'Category C',  # New category
            'target': 'Positive'
        }
    ]


def get_sample_dataframe() -> pd.DataFrame:
    """Get sample data as a pandas DataFrame."""
    return pd.DataFrame(get_sample_survey_data())


def get_prediction_test_scenarios() -> List[Dict[str, Any]]:
    """
    Get scenarios for testing predictions on new data.

    Returns scenarios that may have missing features or different formats
    to test robustness of the prediction system.
    """
    return [
        {
            'business_type': 'SMB',
            'company_size': '21-100',
            'company_size_employees': 75,
            'industry': 'Technology',
            'tools_used': "['Slack', 'GitHub']",
            'features_used': "['Integration', 'Automation']",
            'satisfaction_level': 'Satisfied',
            'support_interactions': '1-2'
            # Missing will_renew (target) - this is expected for prediction
        },
        {
            'business_type': 'Enterprise',
            'company_size': 'More than 500',
            'industry': 'Financial Services',  # Missing some features
            'tools_used': "['Salesforce', 'Tableau']",
            'satisfaction_level': 'Very Satisfied'
        },
        {
            'business_type': 'New Business Type',  # Unseen category
            'company_size': '1-5',
            'company_size_employees': 4,
            'industry': 'Consulting',
            'tools_used': "['New Tool']",  # Unseen tool
            'features_used': "['Advanced Feature']",  # Unseen feature
            'satisfaction_level': 'Satisfied',
            'support_interactions': '0'
        }
    ]