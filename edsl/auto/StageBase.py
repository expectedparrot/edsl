from abc import ABC, abstractmethod
from typing import Dict, List, Any, TypeVar, Generator, Dict, Callable
from dataclasses import dataclass, field, KW_ONLY, fields, asdict
import textwrap


class ExceptionPipesDoNotFit(Exception):
    pass


class StageProcessingClosure:
    def __init__(self, stage_func: Callable, reduction_func=lambda x: x):
        self.data = []
        self.stage_func = stage_func
        # reduction function is applied to self.data when complete
        # it might just return the list, or it might do something more complicated such as
        # reduce the list to a dictionary
        self.reduction_func = reduction_func

    def func(self, obj: "FlowDataBase") -> None:
        "Function to apply to each stage"
        self.data.append(self.stage_func(obj))

    def __call__(self):
        return self.reduction_func(self.data)


@dataclass
class FlowDataBase:
    """Base class for dataclasses that are passed between stages."""

    _: KW_ONLY
    # previous_stage: Dict = field(default_factory=dict)
    previous_stage: Any = None
    sent_to_stage_name: str = field(default_factory=str)
    came_from_stage_name: str = field(default_factory=str)

    def __getitem__(self, key):
        """Allows dictionary-style getting."""
        return getattr(self, key)

    def __setitem__(self, key, value):
        """Allows dictionary-style setting."""
        return setattr(self, key, value)

    def current_values(self):
        """Returns a dictionary of the current values of the dataclass"""
        to_exclude = ["sent_to_stage_name", "came_from_stage_name", "previous_stage"]
        d = asdict(self)
        [d.pop(key) for key in to_exclude]
        return d

    def stage_input_output(self):
        return {
            "came_from": self.came_from_stage_name,
            "sent_to": self.sent_to_stage_name,
        }

    def _align_values_with_padding(
        self, stages
    ) -> Generator[Dict[str, str], None, None]:
        "Pads out the the names of the stages so they are aligned when printing"

        def longest_value(stage):
            return max([len(v) for v in stage.values()])

        max_length = max([longest_value(stage) for stage in stages])
        for stage in stages:
            new_stage = {k: v.ljust(max_length) for k, v in stage.items()}
            yield new_stage

    def _reduce(self, stage_processor: StageProcessingClosure) -> Dict[str, dict]:
        """Applies some function defined in stage_processor to each stage in the chain, working from back to front

        The stage_processor will record the results of the function applied to each stage in
        an instance of the StageProcessingClosure class.
        The results can be accessed by calling the StageProcessingClosure instance.
        This somewhat convoluted approach is necessary because the stages are connected in a chain and
        we want a way to access the results of the function applied to each stage in the chain without
        writing the while-loop over and over again.
        """
        stage_processor.func(self)
        current_pipe = self
        while True:
            if current_pipe.previous_stage is None:
                break
            else:
                current_pipe = current_pipe.previous_stage
                stage_processor.func(
                    current_pipe
                )  # the result is getting stored in stage_processor.data

    def combined_results(self) -> Dict[str, dict]:
        stage_processor = StageProcessingClosure(
            stage_func=lambda obj: obj.current_values(),
            reduction_func=lambda x: {k: v for d in x for k, v in d.items()},
        )
        self._reduce(stage_processor)
        return stage_processor()

    def flow_history(self):
        stage_processor = StageProcessingClosure(
            stage_func=lambda obj: obj.stage_input_output()
        )
        self._reduce(stage_processor)
        return stage_processor()

    def visualize_flow(self) -> str:
        """Visualize the flow of data through the chain"""
        stages = self.flow_history()
        new_stages = list(self._align_values_with_padding(stages))
        new_stages.reverse()
        return tuple(new_stages)


class StageBase(ABC):
    input: FlowDataBase = NotImplemented
    output: FlowDataBase = NotImplemented

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

        if hasattr(self, "next_stage"):
            self._validate_connection(self.next_stage)
        else:
            self.next_stage = None

    @classmethod
    def func(cls, **kwargs):
        "This provides a shortcut for running a stage by passing keyword arguments to the input function."
        input_data = cls.input(**kwargs)
        return cls().process(input_data)

    @abstractmethod
    def handle_data(self, data):
        "This implements how the stage actually handles the passed in data"
        raise NotImplementedError

    def _validate_connection(self, stage):
        "Checks that the outputs of the first stage match the inputs of the second stage"
        if not self.output == stage.input:
            raise ExceptionPipesDoNotFit(
                textwrap.dedent(
                    f"""\
        Stage \"{self.__class__.__name__}\" cannot be connected to stage \"{stage.__class__.__name__}\".
        The outputs of the first stage {self.output} do not match the inputs of the second stage, {stage.input}."""
                )
            )

    def __init_subclass__(cls, **kwargs):
        "Checks that the subclass has the required class variables of input & output"
        super().__init_subclass__(**kwargs)
        if cls.input is NotImplemented:
            raise NotImplementedError(
                f"Class {cls.__name__} lacks required class variable 'inputs'"
            )
        if cls.output is NotImplemented:
            raise NotImplementedError(
                f"Class {cls.__name__} lacks required class variable 'outputs'"
            )

    def process(self, data):
        print(f"Running stage: {self.__class__.__name__}")
        data.sent_to_stage_name = self.__class__.__name__
        processed_data = self.handle_data(data)
        processed_data.came_from_stage_name = self.__class__.__name__
        processed_data.previous_stage = data
        if self.next_stage:
            return self.next_stage.process(processed_data)
        else:
            return processed_data


if __name__ == "__main__":
    try:

        class StageMissing(StageBase):
            def handle_data(self, data):
                return data

    except NotImplementedError as e:
        print(e)
    else:
        raise Exception("Should have raised NotImplementedError")

    try:

        class StageMissingInput(StageBase):
            output = FlowDataBase

    except NotImplementedError as e:
        print(e)

    else:
        raise Exception("Should have raised NotImplementedError")

    @dataclass
    class MockInputOutput(FlowDataBase):
        text: str

    class StageTest(StageBase):
        input = MockInputOutput
        output = MockInputOutput

        def handle_data(self, data):
            return self.output(text=data["text"] + "processed")

    result = StageTest().process(MockInputOutput(text="Hello world!"))
    print(result.text)

    pipeline = StageTest(next_stage=StageTest(next_stage=StageTest()))
    result = pipeline.process(MockInputOutput(text="Hello world!"))
    print(result.text)

    class BadMockInput(FlowDataBase):
        text: str
        other: str

    class StageBad(StageBase):
        input = BadMockInput
        output = BadMockInput

        def handle_data(self, data):
            return self.output(text=data["text"] + "processed")

    try:
        pipeline = StageTest(next_stage=StageBad(next_stage=StageTest()))
    except ExceptionPipesDoNotFit as e:
        print(e)
