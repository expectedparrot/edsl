from .macro import ClientFacingMacro as Macro
# Registry export
from .macro_registry import MacroRegistry
# Backwards-compat shim: export removed classes as aliases to Macro

# Common macro types
from .ranking_macro import create_ranking_macro
from .true_skill_macro import create_true_skill_macro
from .person_simulator import PersonSimulator

# Output formatting
from .output_formatter import OutputFormatter, OutputFormatters, ObjectFormatter
from .macro_run_output import MacroRunOutput

# Macro composition
from .composite_macro import CompositeMacro

# Macro collections
from .macro_collection import MacroCollection, load_examples_collection

# Head attachments and stub job utilities
from .head_attachments import HeadAttachments
from .stub_job import StubJob

# Macro helper modules (for advanced usage/extensions)
from .macro_param_preparer import MacroParamPreparer
from .macro_validator import MacroValidator
from .answers_collector import AnswersCollector
from .macro_serialization import MacroSerialization
from .macro_remote import MacroRemote


