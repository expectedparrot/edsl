from fastapi import FastAPI
from pydantic import BaseModel, create_model
from typing import Callable, Optional, Type, Dict, Any, List, Union


class SurveyToApp:
    def __init__(self, survey):
        self.survey = survey
        self.app = FastAPI()

    def parameters(self):
        return self.survey.parameters

    def create_input(self) -> Type[BaseModel]:
        """
        Creates a Pydantic model based on the survey parameters.
        Returns:
            Type[BaseModel]: A dynamically created Pydantic model class
        """
        # Get parameters from survey - now calling the method
        params = self.parameters()

        # Create field definitions dictionary
        fields: Dict[str, Any] = {}

        # Since params is a set, we'll handle each parameter directly
        # Assuming each parameter in the set has the necessary attributes
        for param in params:
            # You might need to adjust these based on the actual parameter object structure
            param_name = getattr(param, "name", str(param))
            param_type = getattr(param, "type", "string")
            is_required = getattr(param, "required", True)

            # Map survey parameter types to Python types
            type_mapping = {
                "string": str,
                "integer": int,
                "float": float,
                "boolean": bool,
                "array": List,
                # Add more type mappings as needed
            }

            # Get the Python type from mapping
            python_type = type_mapping.get(param_type, str)

            if is_required:
                fields[param_name] = (python_type, ...)
            else:
                fields[param_name] = (Optional[python_type], None)

        # Add the template variable 'name' that's used in the question text
        fields["name"] = (str, ...)

        # Create and return the Pydantic model
        model_name = f"{self.survey.__class__.__name__}Model"
        return create_model(model_name, **fields)

    def create_route(self) -> Callable:
        """
        Creates a FastAPI route handler for the survey.
        Returns:
            Callable: A route handler function
        """
        input_model = self.create_input()

        async def route_handler(input_data: input_model):
            """
            Handles the API route by processing the input data through the survey.
            Args:
                input_data: The validated input data matching the created Pydantic model
            Returns:
                dict: The processed survey results
            """
            # Convert Pydantic model to dict
            data = input_data.dict()
            print(data)
            from edsl.scenarios.Scenario import Scenario

            # Process the data through the survey
            try:
                s = Scenario(data)
                results = self.survey.by(s).run()
                return {
                    "status": "success",
                    "data": results.select("answer.*").to_scenario_list().to_dict(),
                }
            except Exception as e:
                return {"status": "error", "message": str(e)}

        return route_handler

    def add_to_app(
        self, app: FastAPI, path: str = "/survey", methods: List[str] = ["POST", "GET"]
    ):
        """
        Adds the survey route to a FastAPI application.
        Args:
            app (FastAPI): The FastAPI application instance
            path (str): The API endpoint path
            methods (List[str]): HTTP methods to support
        """
        route_handler = self.create_route()
        input_model = self.create_input()

        app.add_api_route(
            path, route_handler, methods=methods, response_model=Dict[str, Any]
        )

    def create_app(self, path: str = "/survey", methods: List[str] = ["POST", "GET"]):
        """
        Creates a FastAPI application with the survey route.
        Args:
            path (str): The API endpoint path
            methods (List[str]): HTTP methods to support
        Returns:
            FastAPI: The FastAPI application instance
        """
        app = FastAPI()
        self.add_to_app(app, path=path, methods=methods)
        return app


from edsl import QuestionFreeText, QuestionList

# q = QuestionFreeText(
#     question_name="name_gender",
#     question_text="Is this customarily a boy's name or a girl's name: {{ name}}",
# )

q = QuestionList(
    question_name="examples",
    question_text="Give me {{ num }} examples of {{ thing }}",
)

survey_app = SurveyToApp(q.to_survey())

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(survey_app.create_app(path="/examples"), host="127.0.0.1", port=8000)
