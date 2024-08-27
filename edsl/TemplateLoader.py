from importlib import resources
from jinja2 import BaseLoader, TemplateNotFound
import os


class TemplateLoader(BaseLoader):
    def __init__(self, package_name, templates_dir):
        self.package_name = package_name
        self.templates_dir = templates_dir

    def get_source(self, environment, template):
        try:
            parts = [self.templates_dir] + template.split("/")
            template_path = os.path.join(*parts)

            # Use resources.files() to get a Traversable object
            templates = resources.files(self.package_name).joinpath(self.templates_dir)

            # Use the read_text() method of the Traversable object
            content = templates.joinpath(template).read_text()

            return content, None, lambda: True
        except FileNotFoundError:
            raise TemplateNotFound(template)
