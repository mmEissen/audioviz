import typing as t
from itertools import count

import numpy as np
from numpy.fft import rfft as fourier_transform, rfftfreq
import matplotlib
matplotlib.use("agg")
from scipy import ndimage

import a_weighting_table
from audio_tools import AbstractAudioInput
from airpixel.client import AbstractClient, Pixel
from profiler import Profiler


class ContiniuousVolumeNormalizer:
    def __init__(self, min_threshold=0.001, falloff=32) -> None:
        self._min_threshold = min_threshold
        self._falloff = falloff
        self._current_threshold = self._min_threshold
        self._last_call = 0

    def _update_threshold(self, max_sample, timestamp):
        if max_sample >= self._current_threshold:
            self._current_threshold = max_sample
        else:
            if max_sample > self._min_threshold:
                factor = 1 / self._falloff ** (timestamp - self._last_call)
                self._current_threshold = self._current_threshold * factor + max_sample * (
                    1 - factor
                )
            else:
                self._current_threshold = 0
        self._last_call = timestamp

    @Profiler.profile
    def normalize(self, signal, timestamp):
        if self._last_call == 0:
            self._last_call = timestamp
        max_sample = np.max(np.abs(signal))
        self._update_threshold(max_sample, timestamp)
        return signal / self._current_threshold


class CircularFourierEffect:
    _octaves = 8

    def __init__(
        self,
        audio_input: AbstractAudioInput,
        ring_client: AbstractClient,
        window_size=0.04,
    ) -> None:
        self._bins_per_octave = ring_client.num_leds
        self._ring_client = ring_client
        self._audio_input = audio_input
        self._audio_input.start()
        self._window_size = window_size
        self._fourier_frequencies = rfftfreq(
            self._audio_input.seconds_to_samples(window_size),
            d=self._audio_input.sample_delta,
        )
        self._sample_points = np.exp2(
            (
                np.arange(self._ring_client.num_leds * self._octaves)
                + self._ring_client.num_leds * 4
            )
            / self._ring_client.num_leds
        )
        self._a_weighting = np.interp(
            self._sample_points,
            a_weighting_table.frequencies,
            a_weighting_table.weights,
        )
        self._hanning_window = np.hanning(
            self._audio_input.seconds_to_samples(window_size)
        )
        self._signal_normalizer = ContiniuousVolumeNormalizer()

    @Profiler.profile
    def _frequencies(self, audio_data):
        return np.absolute(
            fourier_transform(
                np.multiply(audio_data, self._hanning_window),
                # audio_data
            )
        )  


    @Profiler.profile
    def __call__(self, timestamp):
        audio = np.array(self._audio_input.get_data(length=self._window_size))
        measured_frequencies = self._frequencies(audio)
        sampled_frequencies = np.interp(
            self._sample_points, self._fourier_frequencies, measured_frequencies
        )
        weighted_frequencies = (sampled_frequencies * self._a_weighting) ** 2
        normalized = self._signal_normalizer.normalize(weighted_frequencies, timestamp)
        frequencies = np.clip(np.log10(np.clip(normalized * 10, 0.9, 10)), 0, 1)
        f = self._to_colors(frequencies, timestamp)
        return f


class FadingCircularEffect(CircularFourierEffect):
    def __init__(
        self,
        audio_input: AbstractAudioInput,
        ring_client: AbstractClient,
        window_size=0.1,
    ) -> None:
        super().__init__(audio_input, ring_client, window_size)
        self._last_values = np.zeros(self._ring_client.num_leds)
        self._last_time = 0
        self._falloff = 64
        self._color_rotation_period = 180

    def _combine_values(self, new_values, timestamp):
        diff = timestamp - self._last_time
        self._last_time = timestamp
        factor = 1 / self._falloff ** (diff) if diff < 2 else 0
        self._last_values = self._last_values * factor
        self._last_values = np.maximum(self._last_values, new_values)
        return self._last_values
    
    def _values_to_rgb(self, values, timestamp):
        hue = np.full(
            values.shape, 
            (timestamp % self._color_rotation_period) / self._color_rotation_period,
        )
        saturation = np.clip(values * (-2), -2, -1) + 2
        values_color = np.clip(values * 2, 0, 1)
        hsvs = np.transpose(np.array((hue, saturation, values_color)))
        rgbs = matplotlib.colors.hsv_to_rgb(hsvs)
        return rgbs

    def _to_colors(self, data, timestamp):
        smoothed = ndimage.gaussian_filter(data, sigma=2)
        wrapped = np.reshape(smoothed, (-1, self._ring_client.num_leds))
        color_values = np.maximum.reduce(wrapped)
        new_values = self._combine_values(color_values, timestamp)
        return [
            Pixel(g, r, b)
            for r, g, b in self._values_to_rgb(new_values, timestamp)
        ]    
