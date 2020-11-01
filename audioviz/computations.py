from __future__ import annotations

import abc
import pdb
from audioviz.nodes import AWeighting
import dataclasses
import enum
import typing as t
from _pytest.python_api import ApproxMapping

import numpy as np
from airpixel import client
from numpy import fft
from numpy.core.defchararray import multiply

from audioviz import audio_tools, a_weighting_table


_T = t.TypeVar("_T")


class ComputationCycleError(Exception):
    pass


class InvalidComputationTypeError(Exception):
    pass


def computation():
    return dataclasses.dataclass()


class ComputationType(enum.Enum):
    DYNAMIC = enum.auto()
    CONSTANT = enum.auto()
    INHERIT = enum.auto()


class Computation(abc.ABC, t.Generic[_T]):
    computation_type: t.ClassVar[ComputationType] = ComputationType.INHERIT

    __hash__ = None

    def __post_init__(self):
        self._is_clean = True
        self._cycle_check = True

    @abc.abstractmethod
    def _compute(self) -> _T:
        raise NotImplementedError

    def value(self) -> _T:
        if self._is_clean:
            self._value = self._compute()
            self._is_clean = False
        return self._value

    def clean(self) -> None:
        if self.is_constant():
            return
        for input_ in self.inputs():
            input_.clean()
        self._is_clean = True

    def is_constant(self) -> bool:
        if self.computation_type == ComputationType.CONSTANT:
            return True
        if self.computation_type == ComputationType.DYNAMIC:
            return False
        if self.computation_type == ComputationType.INHERIT:
            return all(input_.is_constant() for input_ in self.inputs())
        raise InvalidComputationTypeError("Unknown computation type.")

    def inputs(self) -> t.Iterable[Computation]:
        return (
            getattr(self, field.name)
            for field in dataclasses.fields(self)
            if isinstance(getattr(self, field.name), Computation)
        )

    def _check_cycle(self, seen_ids=None) -> None:
        if not hasattr(self, "_cycle_check"):
            return
        seen_ids = seen_ids or set()
        if id(self) in seen_ids:
            raise ComputationCycleError("Detected cycle in computations!")
        for input_ in self.inputs():
            input_._check_cycle(seen_ids=seen_ids | {id(self)})

    def __setattr__(self, name: str, value: t.Any) -> None:
        super().__setattr__(name, value)
        if isinstance(value, Computation):
            self._check_cycle()

    def __str__(self) -> str:
        attributes = [
            f"{field.name}={getattr(self, field.name)}"
            for field in dataclasses.fields(self)
            if not isinstance(getattr(self, field.name), Computation)
        ]
        return f"{self.__class__.__qualname__}({', '.join(attributes)})"


@computation()
class Constant(Computation[_T]):
    constant: _T

    computation_type: t.ClassVar[ComputationType] = ComputationType.CONSTANT

    def _compute(self) -> _T:
        return self.constant


@computation()
class Monitor(Computation[_T]):
    input_: Computation[_T]
    monitor_client: client.MonitorClient

    def _compute(self) -> _T:
        self.monitor_client.send_np_array(self.input_.value())
        return self.input_.value()


class OneDArray(np.ndarray):
    pass


_A1 = t.TypeVar("_A1", bound=OneDArray)


class AudioSignal(OneDArray):
    pass


class FrequencySpectrum(OneDArray):
    pass


@computation()
class AudioSource(Computation[AudioSignal]):
    audio_input: audio_tools.AudioInput
    samples: Computation[int]

    computation_type: t.ClassVar[ComputationType] = ComputationType.DYNAMIC

    def _compute(self) -> AudioSignal:
        return np.array(self.audio_input.get_samples(self.samples.value()))


@computation()
class HammingWindow(Computation[_A1]):
    sample_count: Computation[int]

    def _compute(self) -> _A1:
        return np.hamming(self.sample_count.value())


@computation()
class FastFourierTransformFrequencies(Computation[OneDArray]):
    sample_count: Computation[int]
    sample_delta: Computation[float]

    def _compute(self) -> OneDArray:
        return fft.rfftfreq(self.sample_count.value(), d=self.sample_delta.value())


@computation()
class FastFourierTransform(Computation[FrequencySpectrum]):
    amplitutde_spectrum: Computation[AudioSignal]
    sample_delta: Computation[float]

    def _compute(self) -> FrequencySpectrum:
        return np.absolute(
            fft.rfft(self.amplitutde_spectrum.value()) * self.sample_delta.value()
        )


@computation()
class AWeightingVector(Computation[FrequencySpectrum]):
    frequencies: Computation[OneDArray]

    def _compute(self) -> FrequencySpectrum:
        return np.interp(
            self.frequencies.value(),
            a_weighting_table.frequencies,
            a_weighting_table.weights,
        )


@computation()
class Multiply(Computation[OneDArray]):
    left_input: Computation[OneDArray]
    right_input: Computation[OneDArray]

    def _compute(self) -> OneDArray:
        return self.left_input.value() * self.right_input.value()


@computation()
class Log2(Computation[OneDArray]):
    input_: Computation[OneDArray]

    def _compute(self) -> OneDArray:
        return np.log2(self.input_.value())


@computation()
class Resample(Computation[OneDArray]):
    input_y: Computation[OneDArray]
    input_x: Computation[OneDArray]
    sample_points: Computation[OneDArray]

    def _compute(self) -> OneDArray:
        return np.interp(
            self.sample_points.value(),
            self.input_x.value(),
            self.input_y.value(),
            left=0,
            right=0,
        )


@computation()
class Mirror(Computation[OneDArray]):
    input_: Computation[OneDArray]
    right_side: Computation[bool]

    def _compute(self) -> OneDArray:
        if self.right_side:
            return np.concatenate([self.input_.value(), np.flip(self.input_.value())])
        else:
            return np.concatenate([np.flip(self.input_.value()), self.input_.value()])


@computation()
class Roll(Computation[OneDArray]):
    input_: Computation[OneDArray]
    amount: Computation[int]

    def _compute(self) -> OneDArray:
        return np.roll(self.input_.value(), self.amount.value())
