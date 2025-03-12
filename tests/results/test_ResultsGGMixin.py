import pytest
import subprocess
from edsl.dataset.r.ggplot import GGPlot

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

def test_ggplot_initialization():
    """Test basic GGPlot initialization"""
    r_code = "ggplot(self, aes(x=x, y=y)) + geom_point()"
    plot = GGPlot(r_code)
    assert plot.r_code == r_code
    assert plot.width == 6  # default width
    assert plot.height == 4  # default height
    assert plot._svg_data is None
    assert plot._saved is False

def test_ggplot_invalid_save_format():
    """Test that saving with invalid format raises error"""
    plot = GGPlot("ggplot()")
    with pytest.raises(ValueError, match="Only 'svg' and 'png' formats are supported"):
        plot.save("test.jpg")

def test_ggplot_error_handling():
    """Test that invalid R code raises appropriate error"""
    plot = GGPlot("invalid_r_code")
    with pytest.raises(RuntimeError, match="An error occurred while running Rscript"):
        plot._execute_r_code()