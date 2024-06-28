from edsl.conjure.InputDataPyRead import InputDataPyRead


class InputDataSPSS(InputDataPyRead):
    def pyread_function(self, datafile_name):
        from pyreadstat import read_sav

        return read_sav(datafile_name)
