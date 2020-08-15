import time
import threading
import math
from functools import reduce

import numpy as np
import matplotlib

matplotlib.use("agg")


import io
from airpixel import client as air_client
import airpixel.monitoring
from numpy.fft import rfft as fourier_transform, rfftfreq
from pyPiper import Node, Pipeline
from scipy import ndimage

from audioviz import a_weighting_table, audio_tools


class ContiniuousVolumeNormalizer:
    def __init__(self, min_threshold=0, falloff=1.1) -> None:
        self._min_threshold = min_threshold
        self._falloff = falloff
        self._current_threshold = self._min_threshold
        self._last_call = 0

    def _update_threshold(self, max_sample, timestamp):
        if max_sample >= self._current_threshold:
            self._current_threshold = max_sample
        else:
            target_threshold = max_sample
            factor = 1 / self._falloff ** (timestamp - self._last_call)
            self._current_threshold = (
                self._current_threshold * factor + target_threshold * (1 - factor)
            )
        self._last_call = timestamp

    def normalize(self, signal, timestamp):
        if self._last_call == 0:
            self._last_call = timestamp
        max_sample = np.max(np.abs(signal))
        self._update_threshold(max_sample, timestamp)
        if (
            self._current_threshold >= self._min_threshold
            and self._current_threshold != 0
        ):
            return signal / self._current_threshold
        return np.zeros_like(signal)


class PlottableNode(Node):
    def setup(self, monitor_client=None):
        self.monitor_client = monitor_client

    def plot(self, data):
        if self.monitor_client is None:
            return
        self.monitor_client.send_np_array(self.name, data)

    def emit(self, data):
        self.plot(data)
        return super().emit(data)


class AudioGenerator(PlottableNode):
    def setup(self, audio_input, samples, monitor_client=None):
        super().setup(monitor_client)
        self._samples = samples
        self._input_device = audio_input

    def run(self, data):
        samples = np.array(self._input_device.get_samples(self._samples))
        self.emit(samples)


class FastFourierTransform(PlottableNode):
    def setup(self, samples, sample_delta, monitor_client=None):
        super().setup(monitor_client)
        self.sample_delta = sample_delta
        self.fourier_frequencies = rfftfreq(samples, d=sample_delta)

    def run(self, data):
        self.emit(np.absolute(fourier_transform(data) * self.sample_delta))


class OctaveSubsampler(PlottableNode):
    def setup(
        self, start_octave, samples_per_octave, num_octaves, frequencies, monitor_client=None
    ):
        super().setup(monitor_client)
        self._sample_points = np.exp2(
            (
                np.arange(samples_per_octave * num_octaves)
                + samples_per_octave * start_octave
            )
            / samples_per_octave
        )
        self.frequencies = frequencies

    def run(self, data):
        self.emit(
            np.interp(self._sample_points, self.frequencies, data, left=0, right=0)
        )


class AWeighting(PlottableNode):
    def setup(self, frequencies, monitor_client=None):
        self.weights = np.interp(
            frequencies, a_weighting_table.frequencies, a_weighting_table.weights
        )
        super().setup(monitor_client)

    def run(self, data):
        self.emit(data * self.weights)


class Gaussian(PlottableNode):
    def setup(self, sigma, monitor_client=None):
        self._sigma = sigma
        super().setup(monitor_client)

    def run(self, data):
        self.emit(ndimage.gaussian_filter(data, sigma=self._sigma))

class Square(PlottableNode):
    def run(self, data):
        self.emit(data ** 2)


class FoldingNode(PlottableNode):
    def setup(self, samples_per_octave, monitor_client=None):
        self._samples_per_octave = samples_per_octave
        super().setup(monitor_client)

    def run(self, data):
        wrapped = np.reshape(data, (-1, self._samples_per_octave))
        self.emit(wrapped)


class SumMatrixVertical(PlottableNode):
    def run(self, data):
        self.emit(np.add.reduce(data))


class MaxMatrixVertical(PlottableNode):
    def run(self, data):
        self.emit(np.maximum.reduce(data))


class Logarithm(PlottableNode):
    def setup(self, i_0=0, monitor_client=None):
        super().setup(monitor_client=monitor_client)
        self.i_0 = i_0
        self.at_1 = np.log(1 / self.i_0 + 1)

    def run(self, data):
        self.emit((np.log(data / self.i_0 + 1) / self.at_1))


class Normalizer(PlottableNode):
    def setup(self, min_threshold=0, falloff=1.1, monitor_client=None):
        super().setup(monitor_client=monitor_client)
        self.normalizer = ContiniuousVolumeNormalizer(
            min_threshold=min_threshold, falloff=falloff
        )

    def run(self, data):
        self.emit(self.normalizer.normalize(data, time.time()))


class Fade(PlottableNode):
    def setup(self, falloff, monitor_client=None):
        super().setup(monitor_client=monitor_client)
        self._falloff = falloff
        self.last_data = None
        self.last_update = None

    def run(self, data):
        now = time.time()
        if self.last_data is None:
            self.last_data = data
            self.last_update = now
            return
        diff = now - self.last_update
        self.last_update = now
        factor = 1 / self._falloff ** (diff) if diff < 2 else 0
        self.last_data = self.last_data * factor
        self.last_data = np.maximum(self.last_data, data)
        self.emit(self.last_data)


class Shift(Node):
    def setup(self, minimum=0, maximum=1):
        self.minimum = minimum
        self.factor = maximum - minimum

    def run(self, data):
        self.emit(data * self.factor + self.minimum)


class Star(Node):
    def setup(self, ip_address, port, led_per_beam, beams, octaves):
        self.led_per_beam = led_per_beam
        self.beams = beams
        self.client = air_client.AirClient(ip_address, int(port), air_client.ColorMethodGRB)
        self._resolution = led_per_beam * 16
        self._pre_computed_strips = self._pre_compute_strips(self._resolution)
        self._octaves = octaves
        # self._colors = np.array(
        #     [
        #         np.array([1 - b, 0, b] * led_per_beam)
        #         for b in np.linspace(0, 1, num=self._octaves * beams)
        #     ]
        # ).reshape((self._octaves, beams * led_per_beam, 3))
        self._colors = np.transpose(np.array([np.array([1, 0, 0])] * led_per_beam * beams))

        self._index_mask = np.zeros(beams, dtype="int")
        self._index_mask[1::2] = self._resolution

        self._blank_frame = np.zeros(beams * led_per_beam * 3).reshape(
            (beams * led_per_beam, 3)
        )

    def _make_strip(self, value):
        scaled_value = value * self.led_per_beam
        return np.array(
            [0.3 for i in range(math.floor(scaled_value))]
            + [0.3 * (scaled_value - math.floor(scaled_value))]
            + [0 for _ in range(self.led_per_beam - math.floor(scaled_value) - 1)]
        )

    def _make_reverse_strip(self, value):
        return np.flip(self._make_strip(value), axis=0)

    def _pre_compute_strips(self, resolution):
        strips = [self._make_strip(i / resolution) for i in range(resolution)]
        reverse = [self._make_reverse_strip(i / resolution) for i in range(resolution)]
        return np.array(strips + reverse)

    def _values_to_rgb(self, values, timestamp):
        indexes = (np.clip(np.nan_to_num(values), 0, 0.999) * self._resolution).astype(
            "int"
        ) + self._index_mask
        alphas = self._pre_computed_strips[indexes].reshape(-1)
        return np.transpose(alphas * self._colors)

    def run(self, data):
        frame = [
            air_client.Pixel(r, g, b)
            for r, g, b in self._values_to_rgb(data, time.time())
        ]
        self.client.show_frame(frame)

class Void(Node):
    def run(self, data):
        pass
