import pandas as pd
import statsmodels.api as sm
import re
import numpy as np


def extract_variable_names(formula):
    # Use regular expressions to find all variable names within the formula
    variable_names = re.findall(r"\b\w+\b", formula)
    # what do we do if there is a variable named 'C'?
    return [variable_name for variable_name in variable_names if variable_name != "C"]


class RegressionMixin:
    def regression(self, formula):
        """
        This runs a linear regression
        https://www.statsmodels.org/stable/index.html
        formula = 'y ~ x1 + x2 + x3 + C(x4)'
        """

        variable_names = extract_variable_names(formula)

        df = self.select(*variable_names).to_pandas()

        # get rid of the headers
        column_mapping = {col: col.split(".")[-1] for col in df.columns}
        # Rename the columns using the dictionary
        df.rename(columns=column_mapping, inplace=True)

        model = sm.OLS.from_formula(formula, data=df)
        regression_result = model.fit()

        return regression_result


if __name__ == "__main__":
    formula = "y ~ x1 + x2 + C(customer_service)"
    print(extract_variable_names_with_indicator(formula))
