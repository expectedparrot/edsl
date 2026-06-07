import pytest
from edsl.jobs.cost_estimation.cost_estimate_calibration import _percentile


def test_empty_list():
    assert _percentile([], 50) == 0


def test_single_element():
    assert _percentile([42], 50) == 42
    assert _percentile([42], 0) == 42
    assert _percentile([42], 100) == 42


def test_p0_returns_min():
    assert _percentile([10, 20, 30, 40], 0) == 10


def test_p100_returns_max():
    assert _percentile([10, 20, 30, 40], 100) == 40


def test_median_odd_length():
    # exact middle element, no interpolation needed
    assert _percentile([10, 20, 30], 50) == 20


def test_median_even_length():
    # p=50 on an even-length list interpolates between the two middle elements
    assert _percentile([10, 20, 30, 40], 50) == 25


def test_interpolation():
    # i = (4-1) * 0.75 = 2.25 → 30 + 0.25*(40-30) = 32.5 → 32
    assert _percentile([10, 20, 30, 40], 75) == 32


def test_unsorted_input():
    assert _percentile([40, 10, 30, 20], 50) == 25


def test_floats():
    assert _percentile([1.0, 2.0, 3.0, 4.0], 50) == 2
