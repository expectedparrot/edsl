from typing import Optional
from ..utilities.remove_edsl_version import remove_edsl_version


class CSSRuleMeta(type):
    _instances = []

    def __init__(cls, name, bases, dct):
        super().__init__(name, bases, dct)

    def __call__(cls, *args, **kwargs):
        instance = super().__call__(*args, **kwargs)
        cls._instances.append(instance)
        return instance

    @classmethod
    def get_instances(cls):
        return cls._instances


class CSSRule(metaclass=CSSRuleMeta):
    def __init__(self, selector: str, properties: Optional[dict[str, str]] = None):
        """
        A CSS rule object that represents a CSS rule with a selector and properties.

        >>> rule = CSSRule("survey_container", {"width": "80%", "margin": "0 auto"})
        >>> rule.generate_rule()
        '.survey_container {\\n    width: 80%;\\n    margin: 0 auto;\\n}'
        """
        self.selector = selector
        self.properties = properties if properties else {}

    def add_property(self, property_name: str, value: str) -> "CSSRule":
        """
        >>> rule = CSSRule("survey_container")
        >>> rule.add_property("width", "80%")
        CSSRule(select = survey_container, properties = {'width': '80%'})
        """
        self.properties[property_name] = value
        return self

    def remove_property(self, property_name) -> "CSSRule":
        """
        >>> rule = CSSRule("survey_container", {"width": "80%", "margin": "0 auto"})
        >>> rule.remove_property("margin")
        CSSRule(select = survey_container, properties = {'width': '80%'})
        """
        if property_name in self.properties:
            del self.properties[property_name]
        return self

    def generate_rule(self) -> str:
        """
        >>> rule = CSSRule("survey_container", {"width": "80%", "margin": "0 auto"})
        >>> rule.generate_rule()
        '.survey_container {\\n    width: 80%;\\n    margin: 0 auto;\\n}'
        """
        rule_lines = [f".{self.selector} {{"]
        for prop, value in self.properties.items():
            rule_lines.append(f"    {prop}: {value};")
        rule_lines.append("}")
        return "\n".join(rule_lines)

    def __repr__(self) -> str:
        return f"CSSRule(select = {self.selector}, properties = {self.properties})"

    def to_dict(self, add_esl_version: bool = True) -> dict:
        """
        >>> rule = CSSRule("survey_container", {"width": "80%", "margin": "0 auto"})
        >>> rule.to_dict()
        {'selector': 'survey_container', 'properties': {'width': '80%', 'margin': '0 auto'}, 'edsl_version': '...', 'edsl_class_name': '...'}
        """
        d = {"selector": self.selector, "properties": self.properties}

        if add_esl_version:
            from .. import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = self.__class__.__name__

        return d

    @classmethod
    @remove_edsl_version
    def from_dict(cls, rule_dict) -> "CSSRule":
        """
        >>> rule_dict = {'selector': 'survey_container', 'properties': {'width': '80%', 'margin': '0 auto'}}
        >>> CSSRule.from_dict(rule_dict)
        CSSRule(select = survey_container, properties = {'width': '80%', 'margin': '0 auto'})
        """
        return CSSRule(
            selector=rule_dict["selector"], properties=rule_dict["properties"]
        )

    @classmethod
    def example(cls):
        """
        >>> CSSRule.example()
        CSSRule(select = survey_container, properties = {'width': '80%', 'margin': '0 auto'})
        """
        return CSSRule(
            selector="survey_container",
            properties={
                "width": "80%",
                "margin": "0 auto",
            },
        )

    def __str__(self):
        return self.generate_rule()


survey_container = CSSRule(
    selector="survey_container",
    properties={
        "width": "80%",
        "margin": "0 auto",
        "padding": "20px",
        "background-color": "#f9f9f9",
        "border": "1px solid #ddd",
        "border-radius": "8px",
        "box-shadow": "0 2px 4px rgba(0, 0, 0, 0.1)",
    },
)

survey_question = CSSRule(
    selector="survey_question",
    properties={
        "margin-bottom": "20px",
        "padding": "15px",
        "background-color": "#fff",
        "border": "1px solid #ddd",
        "border-radius": "8px",
    },
)

question_text = CSSRule(
    selector="question_text",
    properties={
        "font-size": "18px",
        "font-weight": "bold",
        "margin-bottom": "10px",
        "color": "#333",
    },
)

question_options = CSSRule(
    selector="question_options",
    properties={
        "list-style-type": "none",
        "padding": "0",
        "margin": "0",
    },
)

question_options_li = CSSRule(
    selector="question_options li",
    properties={
        "margin-bottom": "10px",
        "font-size": "16px",
        "color": "#555",
    },
)

question_options_radio = CSSRule(
    selector="question_options input[type='radio']",
    properties={
        "margin-right": "10px",
    },
)

question_options_checkbox = CSSRule(
    selector="question_options input[type='checkbox']",
    properties={
        "margin-right": "10px",
    },
)

input_text = CSSRule(
    selector="input[type='text']",
    properties={
        "width": "100%",
        "padding": "10px",
        "font-size": "16px",
        "border": "1px solid #ddd",
        "border-radius": "4px",
        "box-sizing": "border-box",
    },
)


class SurveyCSS:
    def __init__(self, rules: Optional[list["CSSRule"]] = None):
        self.rules = {rule.selector: rule for rule in rules} if rules else {}

    def update_style(self, selector, property_name, new_value):
        """
        >>> css = SurveyCSS()
        >>> css.update_style("survey_container", "width", "100%").rules["survey_container"].properties["width"]
        '100%'
        """
        if selector not in self.rules:
            self.rules[selector] = CSSRule(selector)
        self.rules[selector].add_property(property_name, new_value)
        return self

    def remove_style(self, selector, property_name):
        """
        >>> css = SurveyCSS().update_style("survey_container", "width", "100%")
        >>> css.remove_style("survey_container", "width").rules["survey_container"].properties
        {}
        """
        if selector in self.rules:
            self.rules[selector].remove_property(property_name)
        return self

    def generate_css(self):
        """
        >>> SurveyCSS(rules = []).update_style("survey_container", "width", "100%").generate_css()
        '.survey_container {\\n    width: 100%;\\n}'

        """
        css_lines = []
        for rule in self.rules.values():
            css_lines.append(rule.generate_rule())
        return "\n".join(css_lines)

    def to_dict(self, add_edsl_version: bool = True) -> dict:
        """
        >>> css = SurveyCSS(rules = []).update_style("survey_container", "width", "100%")
        >>> css.to_dict()
        {'rules': [{'selector': 'survey_container', 'properties': {'width': '100%'}, 'edsl_version': '...', 'edsl_class_name': 'CSSRule'}], 'edsl_version': '...', 'edsl_class_name': 'SurveyCSS'}
        """
        d = {"rules": [rule.to_dict() for rule in self.rules.values()]}
        if add_edsl_version:
            from .. import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = self.__class__.__name__
        return d

    def __repr__(self) -> str:
        return f"SurveyCSS(rules = {[rule for rule in self.rules.values()]})"

    @classmethod
    @remove_edsl_version
    def from_dict(cls, css_dict) -> "SurveyCSS":
        """
        >>> s = SurveyCSS.example()
        >>> SurveyCSS.from_dict(s.to_dict())
        SurveyCSS(rules = [CSSRule(select = survey_container, properties = {'width': '80%', 'margin': '0 auto', 'padding': '20px', 'background-color': '#f9f9f9', 'border': '1px solid #ddd', 'border-radius': '8px', 'box-shadow': '0 2px 4px rgba(0, 0, 0, 0.1)'})])
        """
        return SurveyCSS(
            rules=[CSSRule.from_dict(rule_dict) for rule_dict in css_dict["rules"]]
        )

    @classmethod
    def default_style(cls):
        return SurveyCSS(rules=CSSRuleMeta.get_instances())

    @classmethod
    def example(cls):
        """
        >>> SurveyCSS.example()
        SurveyCSS(rules = [CSSRule(select = survey_container, properties = {'width': '80%', 'margin': '0 auto', 'padding': '20px', 'background-color': '#f9f9f9', 'border': '1px solid #ddd', 'border-radius': '8px', 'box-shadow': '0 2px 4px rgba(0, 0, 0, 0.1)'})])
        """
        return SurveyCSS(rules=[survey_container])


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
