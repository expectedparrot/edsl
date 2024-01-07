import re
import statsmodels.api as sm
from typing import List


def extract_variable_names(formula: str) -> List[str]:
    """
    Extracts the variable names from a formula
    TODO: improve the way we handle the case if there is a variable named 'C'
    """
    variable_names = re.findall(r"\b\w+\b", formula)
    return [variable_name for variable_name in variable_names if variable_name != "C"]


class RegressionMixin:
    def regression(
        self, formula: str
    ) -> sm.regression.linear_model.RegressionResultsWrapper:
        """Runs a linear regression"""
        variable_names = extract_variable_names(formula)
        df = self.select(*variable_names).to_pandas()
        # get rid of the headers
        column_mapping = {col: col.split(".")[-1] for col in df.columns}
        # Rename the columns using the dictionary
        df.rename(columns=column_mapping, inplace=True)
        model = sm.OLS.from_formula(formula, data=df)
        regression_result = model.fit()
        return regression_result
