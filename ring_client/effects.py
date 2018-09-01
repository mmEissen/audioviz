import typing as t
from itertools import count

import numpy as np
from numpy.fft import fft as fourier_transform, fftfreq
from scipy.stats import binned_statistic, circmean

from audio_tools import AbstractAudioInput
from ring_client import AbstractClient, RGBWPixel
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


class FourierEffect:
    _max_frequency = 20000
    _bins_per_octave = 7

    def __init__(self, audio_input: AbstractAudioInput, ring_client: AbstractClient, window_size=0.001):
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
        harmonic_bins = self._harmonic_bins_from_input()

        quarter_frame = self._ring_client.num_leds // 4

        colors = [FancyColor(0, brightness=0) for _ in range(quarter_frame)]
        for bin_number, amplitude in enumerate(harmonic_bins):
            color = FancyColor(bin_number / self._bins_per_octave)
            num_leds = int(len(colors) * amplitude)
            for i in range(num_leds):
                colors[i] += color

        frame = self._ring_client.clear_frame()
        quarters = zip(
            reversed(frame[0:quarter_frame]),
            frame[quarter_frame:2 * quarter_frame],
            reversed(frame[2 * quarter_frame:3 * quarter_frame]),
            frame[3 * quarter_frame:],
        )
        for pixels_to_set, color in zip(quarters, colors):
            for pixel in pixels_to_set:
                pixel.set_hsl(color.to_hsl())

        return frame
    
    @Profiler.profile
    def _harmonic_bins_from_input(self):
        data = np.array(self._audio_input.get_data(length=self._window_size))
        normalized_data = np.clip(
            data / 400,
            -1,
            1,
        )
        return self._harmonic_fourier_bins(normalized_data)

    @Profiler.profile
    def _binned_frequencies(self, audio_data):
        fourier_data = np.absolute(
            fourier_transform(
                np.multiply(
                    audio_data,
                    self._hanning_window,
                ),
            ),
        )
        binned_frequencies = np.append(
            np.clip(
                np.nan_to_num(
                    binned_statistic(
                        self._fourier_frequencies,
                        fourier_data,
                        statistic='max',
                        bins=self._bins,
                    ).statistic,
                    copy=False,
                ),
                0,
                1,
            ),
            self._zero_bins,
        )
        return np.reshape(
            binned_frequencies,
            (-1, self._bins_per_octave),
        )

    def _harmonic_fourier_bins(self, audio_data):
        return np.maximum.reduce(
            self._binned_frequencies(audio_data),
        )

    def _bin_generator(self):
        x_values = count(0)
        for x in x_values:
            next_value = 2 ** (x / self._bins_per_octave)
            yield next_value
            if next_value > self._max_frequency:
                return

class CircularFourierEffect(FourierEffect):

    def __init__(self, audio_input: AbstractAudioInput, ring_client: AbstractClient, window_size=0.05):
        self._bins_per_octave = ring_client.num_leds
        super().__init__(audio_input, ring_client, window_size=0.05)

    @Profiler.profile
    def _convert_bins(self, bins):
        return [RGBWPixel(red=amp, green=amp, blue=amp) for amp in bins]

    @Profiler.profile
    def __call__(self, timestamp: float) -> t.List[RGBWPixel]:
        harmonic_bins = self._harmonic_bins_from_input()
        return self._convert_bins(harmonic_bins)
        
    def _gaussian_window(self, offset: float, sigma: float=0.05):
        def f(x: float, mu: float=0.5) -> float:
            return np.exp(-np.power(x - mu, 2.) / (2 * np.power(sigma, 2.)))
        
        offset -= 0.5

        return np.array(
            [f(x % 1) for x in np.linspace(offset, offset + 1, num=self._ring_client.num_leds, endpoint=False)],
        )
