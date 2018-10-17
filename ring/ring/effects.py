import typing as t
from itertools import count

import numpy as np
from numpy.fft import rfft as fourier_transform, rfftfreq

import a_weighting_table
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
        if self._last_call == 0:
            self._last_call = timestamp
        max_sample = np.max(np.abs(signal))
        self._update_threshold(max_sample, timestamp)
        return signal / self._current_threshold


class CircularFourierEffect:
    _octaves = 12

    def __init__(
        self,
        audio_input: AbstractAudioInput,
        ring_client: AbstractClient,
        window_size=0.1,
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

    def dump(
        self,
        audio,
        measured_frequencies,
        sampled_frequencies,
        weighted_frequencies,
        frequencies,
        wrapped_data,
    ):
        with open("data_dump.py", "w") as f:
            f.write("import numpy as np\n\n")
            f.write(
                f"sample_times = np.array({np.ndarray.tolist(np.arange(audio.shape[0]) / self._audio_input.sample_rate)})\n"
            )
            f.write(f"audio = np.array({np.ndarray.tolist(audio)})\n")
            f.write(
                f"fourier_frequencies = np.array({np.ndarray.tolist(self._fourier_frequencies)})\n"
            )
            f.write(
                f"measured_frequencies = np.array({np.ndarray.tolist(measured_frequencies)})\n"
            )
            f.write(
                f"sample_points = np.array({np.ndarray.tolist(self._sample_points)})\n"
            )
            f.write(
                f"sampled_frequencies = np.array({np.ndarray.tolist(sampled_frequencies)})\n"
            )
            f.write(
                f"weighted_frequencies = np.array({np.ndarray.tolist(weighted_frequencies)})\n"
            )
            f.write(f"wrapped_data = np.array({np.ndarray.tolist(wrapped_data)})\n")

    @Profiler.profile
    def __call__(self, timestamp: float) -> t.List[Pixel]:
        audio = np.array(self._audio_input.get_data(length=self._window_size))
        measured_frequencies = self._frequencies(audio)
        sampled_frequencies = np.interp(
            self._sample_points, self._fourier_frequencies, measured_frequencies
        )
        weighted_frequencies = (sampled_frequencies * self._a_weighting) ** 2
        frequencies = self._signal_normalizer.normalize(weighted_frequencies, timestamp)
        wrapped_data = np.maximum.reduce(
            np.reshape(frequencies, (-1, self._ring_client.num_leds))
        )
        debug_values = (
            audio,
            measured_frequencies,
            sampled_frequencies,
            weighted_frequencies,
            frequencies,
            wrapped_data,
        )
        return self._convert_bins(wrapped_data)
