from itertools import count

import numpy as np
from numpy.fft import fft as fourier_transform, fftfreq
from scipy.stats import binned_statistic, circmean

from audio_tools import AbstractAudioInput
from ring_client import AbstractClient


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


class FourierEffect:
    _max_frequency = 20000
    _bins_per_octave = 360

    def __init__(self, audio_input: AbstractAudioInput, ring_client: AbstractClient, window_size=0.05):
        self._ring_client = ring_client
        self._audio_input = audio_input
        self._audio_input.start()
        self._window_size = window_size
        self._fourier_frequencies = fftfreq(
            self._audio_input.seconds_to_samples(window_size),
            d=self._audio_input.sample_delta,
        )
        self._bins = np.array(list(self._bin_generator()))
        number_bins = self._bins.shape[0] - 1
        number_zero_bins = (self._bins_per_octave - number_bins) % self._bins_per_octave
        self._zero_bins = np.zeros(number_zero_bins)
        # If there are zero bins then we have an additional octave
        self._octaves = number_bins // self._bins_per_octave + bool(number_zero_bins)
        self._hanning_window = np.hanning(self._audio_input.seconds_to_samples(window_size))

    def __call__(self, timestamp):
        data = np.array(self._audio_input.get_data(length=self._window_size))
        normalized_data = np.clip(
            data / 800,
            -1,
            1,
        )
        harmonic_bins = self._harmonic_fourier_bins(normalized_data)

        colors = [FancyColor(0, brightness=0) for _ in range(self._ring_client.num_leds)]
        for bin_number, amplitude in enumerate(harmonic_bins):
            color = FancyColor(bin_number / self._bins_per_octave)
            num_leds = int(self._ring_client.num_leds * amplitude)
            for i in range(num_leds):
                colors[i] += color

        frame = self._ring_client.clear_frame()
        for pixel, color in zip(frame, colors):
            pixel.set_hsl(color.to_hsl())

        return frame

    def _harmonic_fourier_bins(self, audio_data):
        fourier_data = np.absolute(
            fourier_transform(
                np.multiply(
                    audio_data,
                    self._hanning_window,
                ),
            ),
        )
        binned_frequencies = np.append(
            np.nan_to_num(
                binned_statistic(
                    self._fourier_frequencies,
                    fourier_data,
                    statistic='max',
                    bins=self._bins,
                ).statistic,
                copy=False,
            ),
            self._zero_bins,
        )
        return np.maximum.reduce(
            np.reshape(
                binned_frequencies,
                (-1, self._bins_per_octave),
            ),
        )

    def _bin_generator(self):
        x_values = count(0)
        for x in x_values:
            next_value = 2 ** (x / self._bins_per_octave)
            yield next_value
            if next_value > self._max_frequency:
                return
