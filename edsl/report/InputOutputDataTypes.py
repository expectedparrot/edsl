from dataclasses import dataclass, field


@dataclass
class BaseDataClass:
    example_data: dict = field(default_factory=dict)
    short_names_dict: dict = field(default_factory=dict)

    @classmethod
    def example(cls):
        data = cls.example_data
        return cls(**data)


@dataclass
class ChiSquareData:
    chi_square: float
    p_value: float
    text: str
    example_data: dict = field(
        default_factory=lambda: {
            "chi_square": 1.0,
            "p_value": 0.5,
            "text": "Debug",
        }
    )
    short_names_dict: dict = field(default_factory=dict)


@dataclass
class RegressionData:
    model_outcome: str
    outcome_description: str
    example_data: dict = field(
        default_factory=lambda: {
            "model_outcome": "Debug",
            "outcome_description": "Debug",
        }
    )
    short_names_dict: dict = field(default_factory=dict)


@dataclass
class FreeTextData:
    responses: list[str]
    text: str
    example_data: dict = field(
        default_factory=lambda: {
            "responses": ["Bad dog", "Bad cat", "Great chicken", "Great cow"],
            "text": "Debug",
        }
    )
    short_names_dict: dict = field(default_factory=dict)


@dataclass
class CategoricalData:
    responses: list[str]
    options: list[str]
    text: str
    example_data: dict = field(
        default_factory=lambda: {
            "responses": ["Bad", "Bad", "Great", "Great"],
            "options": ["Good", "Great", "OK", "Bad"],
            "text": "Debug",
        }
    )
    short_names_dict: dict = field(default_factory=dict)


@dataclass
class NumericalData:
    responses: list[float]
    text: str
    example_data: dict = field(
        default_factory=lambda: {"responses": [1, 2, 3, 4], "text": "Debug"}
    )
    short_names_dict: dict = field(default_factory=dict)


@dataclass
class TallyData:
    responses: dict
    text: str
    example_data: dict = field(
        default_factory=lambda: {
            "responses": {"Bad": 2, "Great": 2, "Good": 0, "OK": 0},
            "text": "Debug",
        }
    )
    short_names_dict: dict = field(default_factory=dict)


@dataclass
class CrossTabData:
    cross_tab: dict
    left_title: str
    right_title: str
    example_data: dict = field(
        default_factory=lambda: {
            "cross_tab": {
                "Bad": {"Bad": 2, "Great": 0, "Good": 0, "OK": 0},
                "Great": {"Bad": 0, "Great": 2, "Good": 0, "OK": 0},
                "Good": {"Bad": 0, "Great": 0, "Good": 0, "OK": 0},
                "OK": {"Bad": 0, "Great": 0, "Good": 0, "OK": 0},
            },
            "left_title": "Debug left question",
            "right_title": "Debug right question",
        }
    )
    short_names_dict: dict = field(default_factory=dict)


@dataclass
class PlotData:
    buffer: bytes
    title: str
    option_codes: dict[str, str]
    width_pct: int
    example_data: dict = field(
        default_factory=lambda: {
            "buffer": b"123",
            "title": "Debug",
            "option_codes": {},
            "width_pct": 100,
        }
    )
    short_names_dict: dict = field(default_factory=dict)


if __name__ == "__main__":
    print(CategoricalData.example())
    print(NumericalData.example())
