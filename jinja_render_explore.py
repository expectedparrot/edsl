from jinja2 import Environment, Template

# Class to capture template variables from the Jinja2 template
class TemplateVars:
    def __init__(self):
        self.data = {}
    
    def set(self, name, value):
        """Store a variable with its name and value"""
        self.data[name] = value
        return ""  # Return empty to avoid outputting anything in the template
    
    def get(self, name, default=None):
        """Retrieve a stored variable"""
        return self.data.get(name, default)
    
    def get_all(self):
        """Return all captured variables"""
        return self.data

# Sample data for our market simulation
scenario_data = {
    'players': ['Alice', 'Bob', 'Charlie', 'Dave'],
    'value': {
        'Alice': 100,
        'Bob': 120,
        'Charlie': 90,
        'Dave': 110
    }
}

# The template as a string
template_string = """
You are a buyer in a market.
{% set player = scenario.players | random %}
{{ vars.set('player', player) }}

{% set value = scenario.value[player] %}
{{ vars.set('value', value) }}

{% set min_bid = value * 0.7 %}
{{ vars.set('min_bid', min_bid) }}

{% set max_bid = value * 0.9 %}
{{ vars.set('max_bid', max_bid) }}

{% set bid = (min_bid + max_bid) / 2 %}
{{ vars.set('bid', bid) }}

Your name is {{ player }}.
Your value for the commodity is {{ value }}.
You can call out a bid to other traders in the market. 
You would be happy to get the good at your value, but you'd like to get it for less.
Any price you pay less than your value is pure profit.

Your strategic bid (70-90% of your value): {{ bid }}
"""

# Setup Jinja environment
env = Environment()
template = env.from_string(template_string)

# Create our variable collector
template_vars = TemplateVars()

# Render the template
rendered_text = template.render(
    scenario=scenario_data,
    vars=template_vars
)

# Display the rendered template
print("=== RENDERED TEMPLATE ===")
print(rendered_text)

# Display the captured variables
print("\n=== CAPTURED VARIABLES ===")
for name, value in template_vars.get_all().items():
    print(f"{name}: {value}")