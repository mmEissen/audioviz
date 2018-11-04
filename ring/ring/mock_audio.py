import typing as t
from threading import Thread

import numpy as np

import audio_tools


class MockSinInput(audio_tools.AbstractAudioInput):
    _frequency = 536
    _amplitude = 50

    def __init__(
        self,
        sample_rate: int = 44100,
        period_size: int = 512,
        buffer_size: int = audio_tools.MS_IN_SECOND * 10,
    ) -> None:
        super().__init__(sample_rate, period_size, buffer_size)

    def start(self):
        pass

    def stop(self):
        pass

    def get_samples(self, num_samples: int) -> t.Iterable[float]:
        return (
            np.sin(
                np.linspace(0, num_samples / self.sample_rate, num_samples)
                * np.pi
                * 2
                * self._frequency
            )
            * self._amplitude
        )
