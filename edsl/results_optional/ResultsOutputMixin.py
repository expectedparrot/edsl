from edsl.report.ReportOutputs import RegisterElementMeta as registery


class ResultsOutputMixin:
    def add_output_functions(self) -> None:
        """Iterates through all output classes and adds a function to the Results class for each one."""
        output_classes = registery.get_registered_classes().values()
        self.analysis_options = []
        for output_class in output_classes:
            new_function_name = output_class.function_name
            new_function = output_class.create_external_function(self)
            self.__dict__[new_function_name] = new_function

            self.analysis_options.append({new_function_name: output_class.__doc__})
