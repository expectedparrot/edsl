"""Scenario helper modules.

This package contains helper classes for scenario operations.
Import specific modules directly to avoid circular import issues:

    from edsl.scenarios.scenario_helpers.document_chunker import DocumentChunker
    from edsl.scenarios.scenario_helpers.scenario_factory import ScenarioFactory
"""

__all__ = [
    "DirectoryScanner",
    "DocumentChunker",
    "QRCode",
    "QRCodeList",
    "extract_urls_from_scenario",
    "ScenarioCombinator",
    "ScenarioFactory",
    "ScenarioGCS",
    "ScenarioJoin",
    "ScenarioListJoin",
    "PdfTools",
    "ScenarioListTo",
    "ScenarioListTransformer",
    "ScenarioOffloader",
    "ScenarioSelector",
    "ScenarioSerializer",
    "ScenarioSnakifier",
    "ScenarioSource",
    "ScenarioSourceInferrer",
    "TrueSkillAlgorithm",
]


def __getattr__(name: str):
    """Lazy import to avoid circular dependencies."""
    if name == "DirectoryScanner":
        from .directory_scanner import DirectoryScanner
        return DirectoryScanner
    elif name == "DocumentChunker":
        from .document_chunker import DocumentChunker
        return DocumentChunker
    elif name == "QRCode":
        from .qr_code import QRCode
        return QRCode
    elif name == "QRCodeList":
        from .qr_code import QRCodeList
        return QRCodeList
    elif name == "extract_urls_from_scenario":
        from .qr_code import extract_urls_from_scenario
        return extract_urls_from_scenario
    elif name == "ScenarioCombinator":
        from .scenario_combinator import ScenarioCombinator
        return ScenarioCombinator
    elif name == "ScenarioFactory":
        from .scenario_factory import ScenarioFactory
        return ScenarioFactory
    elif name == "ScenarioGCS":
        from .scenario_gcs import ScenarioGCS
        return ScenarioGCS
    elif name == "ScenarioJoin":
        from .scenario_join import ScenarioJoin
        return ScenarioJoin
    elif name == "ScenarioListJoin":
        from .scenario_list_joins import ScenarioListJoin
        return ScenarioListJoin
    elif name == "PdfTools":
        from .scenario_list_pdf_tools import PdfTools
        return PdfTools
    elif name == "ScenarioListTo":
        from .scenario_list_to import ScenarioListTo
        return ScenarioListTo
    elif name == "ScenarioListTransformer":
        from .scenario_list_transformer import ScenarioListTransformer
        return ScenarioListTransformer
    elif name == "ScenarioOffloader":
        from .scenario_offloader import ScenarioOffloader
        return ScenarioOffloader
    elif name == "ScenarioSelector":
        from .scenario_selector import ScenarioSelector
        return ScenarioSelector
    elif name == "ScenarioSerializer":
        from .scenario_serializer import ScenarioSerializer
        return ScenarioSerializer
    elif name == "ScenarioSnakifier":
        from .scenario_snakifier import ScenarioSnakifier
        return ScenarioSnakifier
    elif name == "ScenarioSource":
        from .scenario_source import ScenarioSource
        return ScenarioSource
    elif name == "ScenarioSourceInferrer":
        from .scenario_source_inferrer import ScenarioSourceInferrer
        return ScenarioSourceInferrer
    elif name == "TrueSkillAlgorithm":
        from .true_skill_algorithm import TrueSkillAlgorithm
        return TrueSkillAlgorithm
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
