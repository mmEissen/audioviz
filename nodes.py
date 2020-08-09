import time
import threading
import math
from functools import reduce

import numpy as np
import matplotlib

matplotlib.use("agg")

from airpixel import client as air_client
from numpy.fft import rfft as fourier_transform, rfftfreq
from pyPiper import Node, Pipeline
from scipy import ndimage

import a_weighting_table
import audio_tools


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
    def setup(self, window=None):
        if window is None:
            self.plot = self._no_plot
            return
        self._current_max_y = 0
        self.setup_plot(window)

    def setup_plot(self, window):
        window.nextRow()
        self._plot = window.addPlot(title=self.name)
        self._curve = self._plot.plot(pen="y")

    def _no_plot(self, data):
        pass

    def _fit_plot(self, points):
        self._current_max_y = max(max(points), self._current_max_y)
        self._plot.setRange(yRange=(0, self._current_max_y))

    def plot(self, data):
        if isinstance(data, tuple):
            _, points = data
            self._curve.setData(*data)
        else:
            points = data
            self._curve.setData(data)
        self._fit_plot(points)

    def emit(self, data):
        self.plot(data)
        return super().emit(data)


class AudioGenerator(PlottableNode):
    def setup(self, audio_input, samples, window=None):
        super().setup(window)
        self._samples = samples
        self._input_device = audio_input

    def run(self, data):
        samples = np.array(self._input_device.get_samples(self._samples))
        self.emit(samples)


class FastFourierTransform(PlottableNode):
    def setup(self, samples, sample_delta, window=None):
        super().setup(window)
        self.sample_delta = sample_delta
        self.fourier_frequencies = rfftfreq(samples, d=sample_delta)

    def run(self, data):
        self.emit(np.absolute(fourier_transform(data) * self.sample_delta))


class OctaveSubsampler(PlottableNode):
    def setup(
        self, start_octave, samples_per_octave, num_octaves, frequencies, window=None
    ):
        super().setup(window)
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
    def setup(self, frequencies, window=None):
        self.weights = np.interp(
            frequencies, a_weighting_table.frequencies, a_weighting_table.weights
        )
        super().setup(window)

    def setup_plot(self, window):
        super().setup_plot(window)
        self._plot.setLogMode(x=True, y=False)

    def run(self, data):
        self.emit(data * self.weights)


class Gaussian(PlottableNode):
    def setup(self, sigma, window=None):
        self._sigma = sigma
        super().setup(window)

    def setup_plot(self, window):
        super().setup_plot(window)
        self._plot.setLogMode(x=True, y=False)

    def run(self, data):
        self.emit(ndimage.gaussian_filter(data, sigma=self._sigma))


class Square(PlottableNode):
    def run(self, data):
        self.emit(data ** 2)


class FoldingNode(PlottableNode):
    def setup(self, num_octaves, window=None):
        self._num_octaves = num_octaves
        super().setup(window)

    def setup_plot(self, window):
        window.nextRow()
        self._plot = window.addPlot(title=self.name)
        self._curves = [
            self._plot.plot(
                pen=(
                    i / self._num_octaves * 255,
                    (1 - i / self._num_octaves) * 255,
                    255,
                )
            )
            for i in range(self._num_octaves)
        ]

    def plot(self, data):
        for sub_data, curve in zip(data, self._curves):
            curve.setData(sub_data)
            self._fit_plot(sub_data)

    def run(self, data):
        wrapped = np.reshape(data, (self._num_octaves, -1))
        self.emit(wrapped)


class SumMatrixVertical(PlottableNode):
    def run(self, data):
        self.emit(np.add.reduce(data))


class MaxMatrixVertical(PlottableNode):
    def run(self, data):
        self.emit(np.maximum.reduce(data))


class Logarithm(PlottableNode):
    def setup(self, summand=0, window=None):
        super().setup(window=window)
        self.summand = summand
        self.at_0 = self._logarithm(0)
        self.quotient = self._logarithm(1) - self.at_0

    def run(self, data):
        self.emit((self._logarithm(data) - self.at_0) / self.quotient)

    def _logarithm(self, data):
        return np.log(data + self.summand)


class Normalizer(PlottableNode):
    def setup(self, min_threshold=0, falloff=1.1, window=None):
        super().setup(window=window)
        self.normalizer = ContiniuousVolumeNormalizer(
            min_threshold=min_threshold, falloff=falloff
        )

    def run(self, data):
        self.emit(self.normalizer.normalize(data, time.time()))


class Fade(PlottableNode):
    def setup(self, falloff, window=None):
        super().setup(window=window)
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


class Ring(Node):
    def setup(self, color_rotation_period, ip_address, port):
        self._color_rotation_period = color_rotation_period
        self.client = air_client.AutoClient()
        self.client.begin(ip_address, int(port), air_client.ColorMethodRGBW)

    def _values_to_rgb(self, values, timestamp):
        hue = np.full(
            values.shape,
            (timestamp % self._color_rotation_period) / self._color_rotation_period,
        )
        saturation = values
        values_color = values
        hsvs = np.transpose(np.array((hue, saturation, values_color)))
        rgbs = matplotlib.colors.hsv_to_rgb(hsvs)
        return rgbs

    def run(self, data):
        frame = [
            air_client.Pixel(r, g, b)
            for r, g, b in self._values_to_rgb(data, time.time())
        ]
        self.client.show_frame(frame)


class Star(Node):
    def setup(self, ip_address, port, led_per_beam, beams, octaves):
        self.led_per_beam = led_per_beam
        self.beams = beams
        self.client = air_client.AutoClient()
        self.client.begin(ip_address, int(port), air_client.ColorMethodGRB)
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


class Sun(Ring):
    def setup(self, port, led_per_strip, num_strips, octaves):
        self.client = air_client.AirClient(
            port,
            port + 1,
            led_per_strip * num_strips,
            color_method=air_client.ColorMethod.GRB,
        )
        self._led_per_strip = led_per_strip
        self._resolution = led_per_strip * 8
        self._pre_computed_strips = self._pre_compute_strips(self._resolution)

        self._octaves = octaves
        self._index_mask = np.zeros(num_strips, dtype="int")
        self._index_mask[1::2] = self._resolution
        self._index_mask = np.repeat(self._index_mask[None, :], self._octaves, axis=0)

        self._colors = np.array(
            [
                np.array([1 - b, 0, b] * self._led_per_strip)
                for b in np.linspace(0, 1, num=self._octaves * num_strips)
            ]
        ).reshape((self._octaves, num_strips * self._led_per_strip, 3))

        self._blank_frame = np.zeros(num_strips * self._led_per_strip * 3).reshape(
            (num_strips * self._led_per_strip, 3)
        )

    def _make_strip(self, value):
        scaled_value = value * self._led_per_strip
        return np.array(
            [0.5 for _ in range(math.floor(scaled_value))]
            + [0.5 * (scaled_value - math.floor(scaled_value))]
            + [0 for _ in range(self._led_per_strip - math.floor(scaled_value) - 1)]
        )

    def _make_reverse_strip(self, value):
        return np.flip(self._make_strip(value), axis=0)

    def _pre_compute_strips(self, resolution):
        strips = [self._make_strip(i / resolution) for i in range(resolution)]
        reverse = [self._make_reverse_strip(i / resolution) for i in range(resolution)]
        return np.array(strips + reverse)

    def alpha_blend(self, background, foreground_and_alpha):
        foreground, alpha = foreground_and_alpha
        return foreground * alpha[..., None] + background * (1 - alpha[..., None])

    def _values_to_rgb(self, values, timestamp):
        indexes = (np.clip(np.nan_to_num(values), 0, 0.999) * self._resolution).astype(
            "int"
        ) + self._index_mask
        alphas = self._pre_computed_strips[indexes].reshape(self._octaves, -1)
        color_and_alpha = zip(self._colors, alphas)
        final = reduce(self.alpha_blend, color_and_alpha, self._blank_frame)
        return final

    def run(self, data):
        start_time = time.time()
        super().run(data)
        run_time = time.time() - start_time
        time.sleep(max(0, (1 / 30) - run_time))


class Void(Node):
    def run(self, data):
        pass
