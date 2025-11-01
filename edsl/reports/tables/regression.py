import pandas as pd
import statsmodels.api as sm

from .base import TableOutput


class RegressionTable(TableOutput):
    """A table showing regression results when first variable is numeric."""

    def __init__(self, results, *question_names):
        if len(question_names) < 2:
            raise ValueError("RegressionTable requires at least two question names")
        super().__init__(results, *question_names)

        # Get questions
        self.dep_var = self.results.survey.get(self.question_names[0])
        self.ind_vars = [
            self.results.survey.get(name) for name in self.question_names[1:]
        ]

    @property
    def narrative(self):
        dep_var = self.dep_var.question_text
        ind_vars = [q.question_text for q in self.ind_vars]
        return f"A regression analysis table with '{dep_var}' as the dependent variable and {', '.join(ind_vars)} as independent variables, showing coefficients, standard errors, t-statistics, and p-values."

    @classmethod
    def can_handle(cls, *question_objs):
        """Check if this table type can handle the given questions."""
        if len(question_objs) < 2:
            return False
        # First question must be numerical or linear_scale
        if question_objs[0].question_type not in ["numerical", "linear_scale"]:
            return False
        # Other questions can be either numerical, linear_scale or multiple choice
        return all(
            q.question_type in ["numerical", "linear_scale", "multiple_choice"]
            for q in question_objs[1:]
        )

    def output(self):
        """
        Generate regression results table.

        Returns:
            A pandas DataFrame containing regression statistics
        """
        # Get dependent variable data
        y = self.results.select(f"answer.{self.question_names[0]}").to_list()

        # Create DataFrame for independent variables
        X_data = {}
        for question in self.ind_vars:
            answers = self.results.select(f"answer.{question.question_name}").to_list()
            if question.question_type == "multiple_choice":
                # Create dummy variables for categorical variables
                unique_vals = list(question.question_options)
                # Use n-1 dummies to avoid perfect multicollinearity
                for val in unique_vals[:-1]:
                    X_data[f"{question.question_text}: {val}"] = [
                        1 if x == val else 0 for x in answers
                    ]
            else:
                # For numerical variables, use as is
                X_data[question.question_text] = answers

        # Create X DataFrame and add constant
        X = pd.DataFrame(X_data)
        X = sm.add_constant(X)

        # Fit regression
        model = sm.OLS(y, X)
        results = model.fit()

        # Create results DataFrame
        stats_data = []

        # Add coefficients and their statistics
        for var_name in X.columns:
            if var_name == "const":
                var_display = "Intercept"
            else:
                var_display = var_name

            stats_data.append(
                {
                    "Variable": var_display,
                    "Coefficient": f"{results.params.loc[var_name]:.3f}",
                    "Std Error": f"{results.bse.loc[var_name]:.3f}",
                    "t-stat": f"{results.tvalues.loc[var_name]:.3f}",
                    "p-value": f"{results.pvalues.loc[var_name]:.3f}",
                }
            )

        # Create DataFrame with regression statistics
        df_stats = pd.DataFrame(stats_data)

        # Add model summary statistics
        summary_stats = pd.DataFrame(
            [
                {
                    "Variable": "R-squared",
                    "Coefficient": f"{results.rsquared:.3f}",
                    "Std Error": "",
                    "t-stat": "",
                    "p-value": "",
                },
                {
                    "Variable": "Adj R-squared",
                    "Coefficient": f"{results.rsquared_adj:.3f}",
                    "Std Error": "",
                    "t-stat": "",
                    "p-value": "",
                },
                {
                    "Variable": "F-statistic",
                    "Coefficient": f"{results.fvalue:.3f}",
                    "Std Error": "",
                    "t-stat": "",
                    "p-value": f"{results.f_pvalue:.3f}",
                },
                {
                    "Variable": "Number of observations",
                    "Coefficient": f"{len(y)}",
                    "Std Error": "",
                    "t-stat": "",
                    "p-value": "",
                },
            ]
        )

        # Combine coefficient and summary statistics
        df_final = pd.concat([df_stats, summary_stats], axis=0)

        # Set index but keep it visible in table
        df_final.set_index("Variable", inplace=True)

        return df_final
