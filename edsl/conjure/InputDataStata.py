from edsl.conjure.InputDataPyRead import InputDataPyRead


class InputDataStata(InputDataPyRead):
    def pyread_function(self, datafile_name):
        from pyreadstat import read_dta

        return read_dta(datafile_name)
