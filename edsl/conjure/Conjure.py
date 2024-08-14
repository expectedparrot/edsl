from typing import List, Optional, Dict, Callable


class Conjure:
    def __new__(cls, datafile_name: str, *args, **kwargs):
        if datafile_name.endswith(".csv"):
            from edsl.conjure.InputDataCSV import InputDataCSV

            return InputDataCSV(datafile_name, *args, **kwargs)
        elif datafile_name.endswith(".sav"):
            from edsl.conjure.InputDataSPSS import InputDataSPSS

            return InputDataSPSS(datafile_name, *args, **kwargs)
        elif datafile_name.endswith(".dta"):
            from edsl.conjure.InputDataStata import InputDataStata

            return InputDataStata(datafile_name, *args, **kwargs)
        else:
            raise ValueError("Unsupported file type")

    def __init__(
        self,
        datafile_name: str,
        config: Optional[dict] = None,
        naming_function: Optional[Callable] = None,
        raw_data: Optional[List] = None,
        question_names: Optional[List[str]] = None,
        question_texts: Optional[List[str]] = None,
        answer_codebook: Optional[Dict] = None,
        question_types: Optional[List[str]] = None,
        question_options: Optional[List] = None,
        order_options=False,
        question_name_repair_func: Callable = None,
    ):
        # The __init__ method in Conjure won't be called because __new__ returns a different class instance.
        pass

    @classmethod
    def example(cls):
        from edsl.conjure.InputData import InputDataABC

        return InputDataABC.example()


if __name__ == "__main__":
    pass
    # import glob

    # for file in glob.glob("examples/*"):
    #     if file.endswith(".txt"):
    #         continue
    #     print("\n\n")
    #     print("Now processing:", file)
    #     conjure_instance = Conjure(file)
    #     print(conjure_instance)
    #     conjure_instance.to_results(dryrun=True)
    #     print("\n\n")

    #     # c = Conjure("mayors.sav")
    #     # al = c.to_agent_list()
    #     # s = c.to_survey()
    #     # r = c.results()
