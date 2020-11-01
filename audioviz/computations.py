from __future__ import annotations

import abc
import dataclasses
import typing as t

import numpy as np
from airpixel import client
from numpy.lib.arraysetops import isin

from audioviz import audio_tools


def computation():
    return dataclasses.dataclass()


_T = t.TypeVar("_T")


class ComputationCycleError(Exception):
    pass


class Computation(abc.ABC, t.Generic[_T]):
    __hash__ = None

    def __post_init__(self):
        self._is_reset = True
        self._cycle_check = True

    @abc.abstractmethod
    def _compute(self) -> _T:
        raise NotImplementedError

    def value(self) -> _T:
        if self._is_reset:
            self._value = self._compute()
            self._is_reset = False
        return self._value

    def reset(self) -> None:
        self._is_reset = True
        for input_ in self._inputs():
            input_.reset()

    def _inputs(self) -> t.Iterable[Computation]:
        return (
            getattr(self, field.name)
            for field in dataclasses.fields(self)
            if isinstance(getattr(self, field.name), Computation)
        )

    def __setattr__(self, name: str, value: t.Any) -> None:
        super().__setattr__(name, value)
        if isinstance(value, Computation):
            self._check_cycle()

    def _check_cycle(self, seen_ids=None):
        if not hasattr(self, "_cycle_check"):
            return
        seen_ids = seen_ids or set()
        if id(self) in seen_ids:
            raise ComputationCycleError("Detected cycle in computations!")
        for input_ in self._inputs():
            input_._check_cycle(seen_ids=seen_ids | {id(self)})


@computation()
class Constant(Computation[_T]):
    constant: _T

    def _compute(self) -> _T:
        return self.constant


@computation()
class Monitor(Computation[_T]):
    input_: Computation[_T]
    monitor_client: client.MonitorClient

    def _compute(self) -> _T:
        self.monitor_client.send_np_array(self.input_.value())
        return self.input_.value()


class AudioSignal(np.ndarray):
    pass


@computation()
class AudioSource(Computation[AudioSignal]):
    audio_input: audio_tools.AudioInput
    samples: int

    def _compute(self) -> AudioSignal:
        samples = np.array(self._input_device.get_samples(self._samples))
        return t.cast(AudioSignal, samples)


@computation()
class Hamming(Computation[AudioSignal]):
    samples: int

    def __post_init__(self):
        pass

    def setup(self, samples, monitor_client=None):
        super().setup(monitor_client)
        self._window = np.hamming(samples)

    def run(self, data):
        self.emit(np.multiply(data, self._window))
