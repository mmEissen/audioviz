import dataclasses
import typing as t
from unittest import mock

import pytest

from audioviz import computations


@pytest.fixture(name="computation_input")
def f_computation_input():
    return mock.MagicMock(spec=computations.Computation)


@computations.computation()
class OneInputComputation(computations.Computation):
    a: t.Any

    def _compute(self):
        return mock.MagicMock()


@computations.computation()
class TwoInputComputation(computations.Computation):
    a: t.Any
    b: t.Any

    def _compute(self):
        return mock.MagicMock()


@pytest.fixture(name="one_input_computation")
def f_one_input_computation(computation_input):
    return OneInputComputation(a=computation_input)


@pytest.fixture(name="two_input_computation")
def f_two_input_computation(computation_input):
    return TwoInputComputation(computation_input, computation_input)
    


def test_value_called_twice_returns_same_mock(one_input_computation):
    first_result = one_input_computation.value()
    
    second_result = one_input_computation.value()
    
    assert first_result is second_result


def test_reset_discards_result(one_input_computation):
    first_result = one_input_computation.value()

    one_input_computation.reset()
    second_result = one_input_computation.value()

    assert first_result is not second_result


def test_reset_resets_inputs(one_input_computation, computation_input):
    one_input_computation.reset()

    computation_input.reset.assert_called_once()


def test_creating_a_cycle_raises_cycle_error(one_input_computation):
    with pytest.raises(computations.ComputationCycleError):
        one_input_computation.a = one_input_computation


def test_creating_a_cycle_raises_cycle_error_for_second_input(two_input_computation):
    with pytest.raises(computations.ComputationCycleError):
        two_input_computation.b = two_input_computation


def test_creating_a_two_input_computation_doesnt_raise(computation_input):
    TwoInputComputation(computation_input, computation_input)
