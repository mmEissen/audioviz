from abc import ABC, abstractmethod, abstractproperty
from typing import List

from scipy.interpolate import interp1d
from numpy import array

from ring_client import RGBWPixel
from profiler import Profiler


class Effect(ABC):
    @abstractproperty
    def start(self):
        return 0
    
    @abstractproperty
    def end(self):
        return float('+inf')

    @abstractmethod
    def render(self, frame_buffer, timestamp):
        pass 

    def __call__(self, frame_buffer, timestamp):
        self.render(frame_buffer, timestamp)


class MaxEffect(Effect):
    def __init__(self, effects: List[Effect]):
        self._effects = effects
    
    @property
    def start(self):
        return min(effect.start for effect in self._effects)

    @property
    def end(self):
        return max(effect.end for effect in self._effects)

    def _max_rgbw(self, colors):
        reds, greens, blues, whites = zip(*(color.get_rgbw() for color in colors))
        return max(reds), max(greens), max(blues), max(whites)

    def render(self, frame_buffer, timestamp):
        frame_buffers = [
            [RGBWPixel() for pixel in frame_buffer]
            for effect in self._effects
        ]
        for effect, effect_frame_buffer in zip(self._effects, frame_buffers):
            effect(effect_frame_buffer, timestamp)
        color_columns = zip(*frame_buffers)
        for pixel, colors in zip(frame_buffer, color_columns):
            pixel.set_rgbw(self._max_rgbw(colors))


class PulseEffect(Effect):
    def __init__(self, start, length, color, interpolation='cubic'):
        self._start = start
        self._length = length
        self._end = start + length
        self._color = color
        self._interpolation_function = interp1d(
            array([self.start - 1, self.start, self.start + self._length / 2, self.end, self.end + 1]),
            array([0, 0, 1, 0, 0]),
            kind=interpolation,
        )
    
    @property
    def start(self):
        return self._start
    
    @property
    def end(self):
        return self._end
    
    def _interpolate(self, timestamp):
        return float(self._interpolation_function(timestamp))

    def _max_rgbw(self, *colors):
        reds, greens, blues, whites = zip(*(color.get_rgbw() for color in colors))
        return max(reds), max(greens), max(blues), max(whites)

    @Profiler.profile
    def _set_frame_buffer(self, frame_buffer, color):
        for pixel in frame_buffer:
            pixel.set_rgbw(self._max_rgbw(color, pixel))

    @Profiler.profile
    def render(self, frame_buffer, timestamp):
        if not (self.start < timestamp < self.end):
            return frame_buffer
        intensity = self._interpolate(timestamp)
        color = self._color * intensity
        self._set_frame_buffer(frame_buffer, color)
