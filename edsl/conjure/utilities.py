import subprocess
from io import StringIO

import pandas as pd


class Missing:
    def __repr__(self):
        return "Missing()"

    def __str__(self):
        return "Missing()"

    def value(self):
        return "missing"


def convert_value(x):
    try:
        float_val = float(x)
        if float_val.is_integer():
            return int(float_val)
        else:
            return float_val
    except ValueError:
        if len(x) == 0:
            return Missing().value()
        else:
            return str(x)


class RCodeSnippet:
    def __init__(self, r_code):
        self.r_code = r_code

    def __call__(self, data_file_name):
        return self.run_R_stdin(self.r_code, data_file_name)

    def __add__(self, other):
        return RCodeSnippet(self.r_code + other.r_code)

    def write_to_file(self, filename) -> None:
        """Writes the R code to a file; useful for debugging."""
        if filename.endswith(".R") or filename.endswith(".r"):
            pass
        else:
            filename += ".R"

        with open(filename, "w") as f:
            f.write(self.r_code)

    @staticmethod
    def run_R_stdin(r_code, data_file_name, transform_func=lambda x: pd.read_csv(x)):
        """Runs an R script and returns the stdout as a string."""
        cmd = ["Rscript", "-e", r_code, data_file_name]
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        stdout, stderr = process.communicate()
        if stderr != "":
            print("Warning: stderr is not empty.")
            print(f"Problem running: {r_code}")
            raise Exception(stderr)
        return transform_func(StringIO(stdout))
