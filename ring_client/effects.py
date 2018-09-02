import typing as t
from itertools import count

import numpy as np
from numpy.fft import rfft as fourier_transform, rfftfreq
from scipy.stats import binned_statistic, circmean

from audio_tools import AbstractAudioInput
from ring_client import AbstractClient, Pixel
from profiler import Profiler

class FancyColor:
    def __init__(self, hue, brightness=1):
        self.hue = hue
        self.brightness = brightness
    
    def _hue_mean(self, other):
        return circmean(
            [self.hue] * self.brightness + [other.hue] * other.brightness,
            high=1,
        )

    def __add__(self, other):
        return self.__class__(
            self._hue_mean(other),
            brightness=self.brightness + other.brightness
        )
    
    def __iadd__(self, other):
        self.hue = self._hue_mean(other)
        self.brightness += other.brightness
        return self
    
    def to_hsl(self):
        return (self.hue, 1, 1 - 1 / 2 ** self.brightness)


class ContiniousVolumeNormalizer:
    def __init__(
        self,
        min_threshold=0.1,
        falloff=16,
    ) -> None:
        self._min_threshold = min_threshold
        self._falloff = falloff
        self._current_threshold = self._min_threshold
        self._last_call = 0
    
    def _update_threshold(self, max_sample, timestamp):
        self._last_call = timestamp
        if max_sample >= self._current_threshold:
            self._current_threshold = max_sample
            return
        max_sample = max(max_sample, self._min_threshold)
        factor = 1 / self._falloff ** (timestamp - self._last_call)
        self._current_threshold = self._current_threshold * factor + max_sample * (1 - factor)

    def normalize(self, signal, timestamp):
        max_sample = np.max(np.abs(signal))
        self._update_threshold(max_sample, timestamp)
        return signal / self._current_threshold



class FourierEffect:
    _octaves = 12

    def __init__(
        self, 
        audio_input: AbstractAudioInput, 
        ring_client: AbstractClient, 
        window_size=0.05,
        volume_threshold=2,
    ):
        self._ring_client = ring_client
        self._audio_input = audio_input
        self._audio_input.start()
        self._window_size = window_size
        self._fourier_frequencies = rfftfreq(
            self._audio_input.seconds_to_samples(window_size),
            d=self._audio_input.sample_delta,
        )
        self._hanning_window = np.hanning(self._audio_input.seconds_to_samples(window_size))
        self._signal_normalizer = ContiniousVolumeNormalizer()
    
    def _normalized_audio(self, timestamp):
        data = np.array(self._audio_input.get_data(length=self._window_size))
        normalized_data = self._signal_normalizer.normalize(
            data,
            timestamp,
        )
        return normalized_data

    @Profiler.profile
    def _frequencies(self, audio_data):
        fourier_data = np.absolute(
            fourier_transform(
                np.multiply(
                    audio_data,
                    self._hanning_window,
                ),
                # audio_data,
            ),
        ) / (self._window_size * self._audio_input.sample_rate / 4)
        return np.clip(fourier_data, 0, 1)


class CircularFourierEffect(FourierEffect):

    def __init__(self, audio_input: AbstractAudioInput, ring_client: AbstractClient, window_size=0.01):
        self._bins_per_octave = ring_client.num_leds
        super().__init__(audio_input, ring_client, window_size=window_size)

    def _convert_bins(self, bins):
        return [Pixel(amp, amp, amp) for amp in bins]

    def _sample_points(self):
        return np.exp2(
            (
                np.arange(
                    self._ring_client.num_leds * self._octaves,
                ) + self._ring_client.num_leds * 4
            ) / self._ring_client.num_leds,
        )

    @Profiler.profile
    def __call__(self, timestamp: float) -> t.List[Pixel]:
        audio = np.array(self._audio_input.get_data(length=self._window_size))
        sample_points = self._sample_points()
        frequencies = self._frequencies(audio)
        samples = np.interp(
            sample_points,
            self._fourier_frequencies,
            frequencies,
        )
        wrapped_data = np.maximum.reduce(
            np.reshape(samples, (-1, self._ring_client.num_leds)),
        )
        normalized_wrapped_data = self._signal_normalizer.normalize(wrapped_data, timestamp)
        return self._convert_bins(normalized_wrapped_data)
