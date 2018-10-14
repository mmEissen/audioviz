import typing as t
from itertools import count

import numpy as np
import librosa
from numpy.fft import rfft as fourier_transform, rfftfreq
from scipy.stats import binned_statistic, circmean

from audio_tools import AbstractAudioInput
from ring_client import AbstractClient, Pixel
from profiler import Profiler


class ContiniousVolumeNormalizer:
    def __init__(self, min_threshold=0.0001, falloff=2) -> None:
        self._min_threshold = min_threshold
        self._falloff = falloff
        self._current_threshold = self._min_threshold
        self._last_call = 0

    def _update_threshold(self, max_sample, timestamp):
        if max_sample >= self._current_threshold:
            self._current_threshold = max_sample
        else:
            max_sample = max(max_sample, self._min_threshold)
            factor = 1 / self._falloff ** (timestamp - self._last_call)
            self._current_threshold = self._current_threshold * factor + max_sample * (
                1 - factor
            )
        self._last_call = timestamp

    @Profiler.profile
    def normalize(self, signal, timestamp):
        max_sample = np.max(np.abs(signal))
        self._update_threshold(max_sample, timestamp)
        return signal / self._current_threshold


class CircularFourierEffect:
    _octaves = 12

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
        self._a_weighting = librosa.db_to_amplitude(
            librosa.A_weighting(self._sample_points, min_db=None)
        )
        self._hanning_window = np.hanning(
            self._audio_input.seconds_to_samples(window_size)
        )
        self._signal_normalizer = ContiniousVolumeNormalizer()

    def _convert_bins(self, bins):
        return [Pixel(amp, amp, amp) for amp in bins]

    @Profiler.profile
    def _frequencies(self, audio_data):
        return np.absolute(
            fourier_transform(
                # np.multiply(audio_data, self._hanning_window),
                audio_data
            )
        )

    @Profiler.profile
    def __call__(self, timestamp: float) -> t.List[Pixel]:
        audio = np.array(self._audio_input.get_data(length=self._window_size))
        samples = np.interp(
            self._sample_points, self._fourier_frequencies, self._frequencies(audio)
        )
        frequencies = self._signal_normalizer.normalize(samples * self._a_weighting, timestamp)
        wrapped_data = np.maximum.reduce(
            np.reshape(frequencies, (-1, self._ring_client.num_leds))
        )
        return self._convert_bins(wrapped_data ** 2)
