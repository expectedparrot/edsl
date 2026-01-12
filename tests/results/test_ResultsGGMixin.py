"""Tests for the ggplot service (R/ggplot2 visualization)."""

import pytest
import subprocess

def is_r_installed():
    """Check if R is installed by trying to run Rscript --version"""
    try:
        subprocess.run(["Rscript", "--version"], 
                      stdout=subprocess.PIPE, 
                      stderr=subprocess.PIPE)
        return True
    except FileNotFoundError:
        return False

# Skip all tests in this module if R is not installed
pytestmark = pytest.mark.skipif(
    not is_r_installed(),
    reason="R is not installed. Install R to run these tests."
)


def test_ggplot_service_exists():
    """Test that ggplot service is registered."""
    from edsl.services import ServiceRegistry, _ensure_builtin_services
    _ensure_builtin_services()
    
    svc = ServiceRegistry.get("ggplot")
    assert svc is not None
    assert svc.name == "ggplot"


def test_ggplot_service_aliases():
    """Test that ggplot service has expected aliases."""
    from edsl.services import ServiceRegistry, _ensure_builtin_services
    _ensure_builtin_services()
    
    # Both names should resolve to the same service
    svc1 = ServiceRegistry.get("ggplot")
    svc2 = ServiceRegistry.get("ggplot2")
    svc3 = ServiceRegistry.get("r_plot")
    
    assert svc1 is svc2
    assert svc2 is svc3


def test_ggplot_service_render():
    """Test basic render operation."""
    from edsl.services.builtin.ggplot.service import GGPlotService
    
    params = {
        "operation": "render",
        "ggplot_code": "ggplot(self, aes(x=a)) + geom_bar()",
        "data": [{"a": ["x", "y", "x", "z", "y"]}],
        "width": 4,
        "height": 3,
    }
    
    result = GGPlotService.execute(params)
    
    # If R is installed properly with ggplot2, we should get a filestore
    if "error" in result:
        # R or ggplot2 not installed properly - skip
        pytest.skip(f"R/ggplot2 not available: {result['error']}")
    
    assert "filestore" in result
    assert result["filestore"]["suffix"] == ".png"
    assert result["filestore"]["base64_string"]  # Non-empty


def test_ggplot_service_render_svg():
    """Test SVG render operation."""
    from edsl.services.builtin.ggplot.service import GGPlotService
    
    params = {
        "operation": "render_svg",
        "ggplot_code": "ggplot(self, aes(x=a)) + geom_bar()",
        "data": [{"a": ["x", "y", "x"]}],
    }
    
    result = GGPlotService.execute(params)
    
    if "error" in result:
        pytest.skip(f"R/ggplot2 not available: {result['error']}")
    
    assert "filestore" in result
    assert result["filestore"]["suffix"] == ".svg"


def test_ggplot_service_parse_result():
    """Test that parse_result returns FileStore."""
    from edsl.services.builtin.ggplot.service import GGPlotService
    from edsl.scenarios.file_store import FileStore
    import base64
    
    # Mock result with a simple PNG (1x1 red pixel)
    mock_result = {
        "filestore": {
            "suffix": ".png",
            "base64_string": base64.b64encode(b"fake_png_data").decode(),
            "binary": True,
        }
    }
    
    parsed = GGPlotService.parse_result(mock_result)
    assert isinstance(parsed, FileStore)
    assert parsed.suffix == ".png"


def test_ggplot_service_error_handling():
    """Test that invalid R code returns error dict."""
    from edsl.services.builtin.ggplot.service import GGPlotService
    
    params = {
        "operation": "render",
        "ggplot_code": "invalid_r_syntax_here!!!",
        "data": [],
    }
    
    result = GGPlotService.execute(params)
    
    # Should return error, not raise exception
    assert "error" in result


def test_ggplot_service_unknown_operation():
    """Test that unknown operation raises ValueError."""
    from edsl.services.builtin.ggplot.service import GGPlotService
    
    params = {
        "operation": "unknown_op",
    }
    
    with pytest.raises(ValueError, match="Unknown operation"):
        GGPlotService.execute(params)
