import abc
import math
import struct
import threading
import time
from collections import deque
import typing as t

import alsaaudio as alsa
import numpy

MS_IN_SECOND = 1000
SECONDS_IN_MINUTE = 60


class AbstractAudioInput(abc.ABC):
    number_channels = 1

    def __init__(
        self,
        sample_rate = 44100,
        period_size = 512,
        buffer_size = MS_IN_SECOND * 1,
    ) -> None:
        self.sample_rate = sample_rate
        self.period = sample_rate / period_size * MS_IN_SECOND
        self.sample_delta = 1 / sample_rate

    def seconds_to_samples(self, seconds):
        return int(seconds * self.sample_rate)

    @abc.abstractmethod
    def start(self):
        pass

    @abc.abstractmethod
    def stop(self):
        pass

    @abc.abstractmethod
    def get_samples(self, num_samples):
        pass

    def get_data(self, length = 0):
        num_samples = self.seconds_to_samples(length)
        return self.get_samples(num_samples)


class AudioError(Exception):
    pass


class AudioInput(AbstractAudioInput):
    def __init__(
        self,
        device = "default",
        sample_rate = 44100,
        period_size = 1024,
        buffer_size = MS_IN_SECOND * 1,
    ) -> None:
        super().__init__(sample_rate, period_size, buffer_size)
        self._is_running = False

        max_buffered_samples = buffer_size * sample_rate // MS_IN_SECOND
        self._buffer = deque(
            (0 for _ in range(max_buffered_samples)), maxlen=max_buffered_samples
        )
        self._buffer_lock = threading.Lock()

        self._mic = alsa.PCM(alsa.PCM_CAPTURE, alsa.PCM_NORMAL, device)
        self._mic.setperiodsize(period_size)
        self._mic.setrate(sample_rate)
        self._mic.setformat(alsa.PCM_FORMAT_U32_BE)
        self._mic.setchannels(self.number_channels)

    def _audio_loop(self) -> None:
        length, raw_data = self._mic.read()

        try:
            data = (float(value) for value, in struct.iter_unpack(">L", raw_data))
        except struct.error as error:
            raise AudioError(
                "Could not decode data: '{}', length: {}".format(raw_data, length),
            )

        self._buffer_lock.acquire()
        self._buffer.extend(data)
        self._buffer_lock.release()

    def _run(self):
        self._is_running = True
        while self._is_running:
            self._audio_loop()

    def start(self) -> None:
        thread = threading.Thread(target=self._run, name="audio-capture-thread")
        thread.start()

    def stop(self):
        self._is_running = False

    def get_samples(self, num_samples):
        self._buffer_lock.acquire()
        buffer_copy = [
            sample for _, sample in zip(range(num_samples), reversed(self._buffer))
        ]
        self._buffer_lock.release()
        return buffer_copy
