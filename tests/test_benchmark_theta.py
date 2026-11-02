"""T29: tìm θ tại điểm TTFT P95 cắt latency mục tiêu."""
import numpy as np

from benchmark_theta import crossing, p95_with_unfinished


def test_crossing_interpolates_between_levels():
    assert np.isclose(crossing([100, 400], [1.0, 4.0], 2.0), 200)


def test_crossing_uses_first_failure_even_if_later_passes():
    assert crossing([100, 200, 400], [1.0, 9.0, 1.0], 5.0) < 200


def test_crossing_low_level_already_fails():
    assert crossing([100, 200], [9.0, 9.0], 5.0) is None


def test_crossing_never_fails_returns_highest_level():
    assert crossing([100, 200], [1.0, 1.0], 5.0) == 200


def test_crossing_infinite_p95_keeps_last_passing_level():
    assert crossing([100, 200], [1.0, np.inf], 5.0) == 100


def test_unfinished_requests_count_as_infinite():
    assert p95_with_unfinished(range(100), np.ones(100)) == 1.0
    assert p95_with_unfinished(range(100), np.ones(90)) == np.inf
