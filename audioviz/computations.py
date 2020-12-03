from __future__ import annotations

import abc
import collections
import dataclasses
import enum
import time
import typing as t
import math

import numpy as np
from airpixel import client
from numpy import fft
import numpy

from audioviz import audio_tools, a_weighting_table


_T = t.TypeVar("_T")
_U = t.TypeVar("_U")
_V = t.TypeVar("_V")


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


class NoBenchmarker:
    def start(self):
        pass

    def stop(self):
        pass


@dataclasses.dataclass
class Benchmarker(NoBenchmarker):
    measurements: t.List[float] = dataclasses.field(default_factory=list)
    start_time: int = 0

    def average(self):
        if not self.measurements:
            return float("+inf")
        return sum(self.measurements) / len(self.measurements)

    def start(self):
        self.start_time = time.time()

    def stop(self):
        delta = time.time() - self.start_time
        self.measurements.append(delta)


class Computation(abc.ABC, t.Generic[_T]):
    computation_type: t.ClassVar[ComputationType] = ComputationType.INHERIT

    __hash__ = None

    def __post_init__(self):
        self._is_clean = True
        self.benchmark = NoBenchmarker()
        self._cycle_check = True

    @abc.abstractmethod
    def _compute(self) -> _T:
        raise NotImplementedError

    def value(self) -> _T:
        self.benchmark.start()
        if self._is_clean:
            self._value = self._compute()
            self._is_clean = False
        self.benchmark.stop()
        return self._value

    def volatile_value(self) -> _T:
        value = self.value()
        self.clean()
        return value

    def clean(self) -> None:
        if self.is_constant() or self._is_clean:
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

    def set_benchmark(self, value: bool) -> None:
        for input_ in self.inputs():
            input_.set_benchmark(value)
        if value:
            self.benchmark = Benchmarker()
        else:
            self.benchmark = NoBenchmarker()

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

    def __add__(self, other):
        return Add(self, other)

    def __sub__(self, other):
        return Subtract(self, other)

    def __mul__(self, other):
        return Multiply(self, other)

    def __truediv__(self, other):
        return Divide(self, other)

    def __floordiv__(self, other):
        return FloorDivide(self, other)


@computation()
class Constant(Computation[_T]):
    constant: _T

    computation_type: t.ClassVar[ComputationType] = ComputationType.CONSTANT

    def _compute(self) -> _T:
        return self.constant


@computation()
class _Operator(Computation[_T]):
    left: Computation[_U]
    right: Computation[_V]


@computation()
class Add(_Operator[_T]):
    def _compute(self):
        return self.left.value() + self.right.value()


@computation()
class Subtract(_Operator[_T]):
    def _compute(self):
        return self.left.value() - self.right.value()


@computation()
class Multiply(_Operator[_T]):
    def _compute(self):
        return self.left.value() * self.right.value()


@computation()
class Divide(_Operator[_T]):
    def _compute(self):
        return self.left.value() / self.right.value()


@computation()
class FloorDivide(Computation[_T]):
    left: Computation[_U]
    right: Computation[_V]

    def _compute(self):
        return self.left.value() // self.right.value()


@computation()
class Monitor(Computation[None]):
    input_: Computation[_T]
    name: str
    monitor_client: client.MonitorClient

    def _compute(self) -> None:
        self.monitor_client.send_np_array(self.name, self.input_.value())


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
class Slice(Computation[OneDArray]):
    input_: Computation[OneDArray]
    start: Computation[t.Optional[int]] = Constant(None)
    stop: Computation[t.Optional[int]] = Constant(None)

    def _compute(self) -> OneDArray:
        if self.start.value() is not None and self.stop.value() is not None:
            return self.input_.value()[self.start.value() : self.stop.value()]
        if self.start.value() is not None:
            return self.input_.value()[self.start.value() :]
        if self.stop.value() is not None:
            return self.input_.value()[: self.stop.value()]
        return self.input_.value()


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
class Multiply(Computation[_T]):
    left_input: Computation[_T]
    right_input: Computation[_T]

    def _compute(self) -> _T:
        return self.left_input.value() * self.right_input.value()


@computation()
class History(Computation[t.List[_T]]):
    input_: Computation[_T]
    size: int

    def __post_init__(self):
        super().__post_init__()
        self._memory = collections.deque(maxlen=self.size)

    def _compute(self) -> t.List[_T]:
        self._memory.append(self.input_.value())
        return list(self._memory)


@computation()
class ThresholdToggle(Computation[bool]):
    signal_history: Computation[t.List[OneDArray]]
    threshold: Computation[float]

    def _compute(self) -> bool:
        active = sum(
            1
            for samples in self.signal_history.value()
            if max(samples) > self.threshold.value()
        )
        return active > len(self.signal_history.value()) // 2


@computation()
class Add(Computation[_T]):
    left_input: Computation[_T]
    right_input: Computation[_T]

    def _compute(self) -> _T:
        return self.left_input.value() + self.right_input.value()


@computation()
class Subtract(Computation[_T]):
    left_input: Computation[_T]
    right_input: Computation[_T]

    def _compute(self) -> _T:
        return self.left_input.value() - self.right_input.value()


@computation()
class Divide(Computation[_T]):
    left_input: Computation[_T]
    right_input: Computation[_T]

    def _compute(self) -> _T:
        return self.left_input.value() / self.right_input.value()


@computation()
class Linspace(Computation[OneDArray]):
    start: Computation[float]
    stop: Computation[float]
    count: Computation[int]

    def _compute(self) -> OneDArray:
        return np.linspace(self.start.value(), self.stop.value(), self.count.value())


@computation()
class Log2(Computation[OneDArray]):
    input_: Computation[OneDArray]

    def _compute(self) -> OneDArray:
        return np.log2(self.input_.value())


@computation()
class Resample(Computation[OneDArray]):
    input_x: Computation[OneDArray]
    input_y: Computation[OneDArray]
    sample_points: Computation[OneDArray]

    def _compute(self) -> OneDArray:
        bucket_count = len(self.sample_points.value()) - 1
        masked_array = np.ma.empty((bucket_count, len(self.input_y.value())))
        masked_array.data[...] = self.input_y.value()
        bucket_indexes = np.arange(bucket_count)
        masked_array.mask = (
            np.digitize(self.input_x.value(), self.sample_points.value()) - 1
            != bucket_indexes[:, np.newaxis]
        )
        return masked_array.max(axis=1).filled(0)


@computation()
class Mirror(Computation[OneDArray]):
    input_: Computation[OneDArray]
    right_side: Computation[bool] = dataclasses.field(
        default_factory=lambda: Constant(True)
    )

    def _compute(self) -> OneDArray:
        if self.right_side.value():
            return np.concatenate([self.input_.value(), np.flip(self.input_.value())])
        else:
            return np.concatenate([np.flip(self.input_.value()), self.input_.value()])


@computation()
class Roll(Computation[OneDArray]):
    input_: Computation[OneDArray]
    amount: Computation[int]

    def _compute(self) -> OneDArray:
        return np.roll(self.input_.value(), self.amount.value())


@computation()
class Time(Computation[float]):
    computation_type: t.ClassVar[ComputationType] = ComputationType.DYNAMIC

    def _compute(self) -> OneDArray:
        return time.time()


@computation()
class VolumeNormalizer(Computation[OneDArray]):
    audio: Computation[OneDArray]
    time: Computation[float] = dataclasses.field(default_factory=Time)

    def __post_init__(self):
        self.normalizer = audio_tools.ContiniuousVolumeNormalizer()
        super().__post_init__()

    def _compute(self) -> OneDArray:
        return self.normalizer.normalize(self.audio.value(), self.time.value())


@computation()
class Maximum(Computation[float]):
    samples: Computation[OneDArray]

    def _compute(self) -> OneDArray:
        return np.max(self.samples.value())


@computation()
class BeamMasks(Computation[t.Any]):
    led_per_beam: Computation[int]
    resolution: Computation[int]

    ON = 1
    OFF = 0

    def _make_reverse_beam(self, value):
        return np.flip(self._make_beam(value), axis=0)

    def _make_beam(self, value):
        scaled_value = value * self.led_per_beam.value()
        return np.array(
            [self.ON for i in range(math.floor(scaled_value))]
            + [self.ON * (scaled_value - math.floor(scaled_value))]
            + [
                self.OFF
                for _ in range(self.led_per_beam.value() - math.floor(scaled_value) - 1)
            ]
        )

    def _compute(self) -> t.Any:
        resolution = self.resolution.value()
        strips = [self._make_beam(i / resolution) for i in range(resolution)]
        reverse = [self._make_reverse_beam(i / resolution) for i in range(resolution)]
        return np.array(strips + reverse)


@computation()
class ColorMask(Computation[t.Any]):
    led_per_beam: Computation[int]
    beams: Computation[int]

    def _compute(self) -> t.Any:
        return np.transpose(
            np.array(
                [np.array([0, 1, 1])] * self.led_per_beam.value() * self.beams.value()
            )
        )


@computation()
class Star(Computation[None]):
    strip_values: Computation[OneDArray]
    led_per_beam: Computation[int]
    resolution: Computation[int]
    beams: Computation[int]
    beam_mask: Computation[t.Any]
    brightness: Computation[float]
    ip_address: str
    port: int

    def __post_init__(self):
        self.client = client.AirClient(
            self.ip_address, int(self.port), client.ColorMethodGRB
        )
        self._colors = np.transpose(
            np.array(
                [np.array([0, 1, 1])] * self.led_per_beam.value() * self.beams.value()
            )
        )

        self._index_mask = np.zeros(self.beams.value(), dtype="int")
        self._index_mask[1::2] = self.resolution.value()

        self._blank_frame = np.zeros(
            self.beams.value() * self.led_per_beam.value() * 3
        ).reshape((self.beams.value() * self.led_per_beam.value(), 3))
        super().__post_init__()

    def _values_to_rgb(self, values):
        indexes = (
            np.clip(np.nan_to_num(values), 0, 0.999) * self.resolution.value()
        ).astype("int") + self._index_mask
        alphas = self.beam_mask.value()[indexes].reshape(-1)
        return np.transpose(alphas * self._colors) * self.brightness.value()

    def _compute(self) -> None:
        frame = [
            client.Pixel(r, g, b)
            for r, g, b in self._values_to_rgb(self.strip_values.value())
        ]
        self.client.show_frame(frame)
