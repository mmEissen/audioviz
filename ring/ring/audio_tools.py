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


class AudioError(Exception):
    pass


class AudioInput:
    number_channels = 1

    def __init__(
        self,
        device = "default",
        sample_rate = 22050,
        period_size = 1024,
        buffer_size = MS_IN_SECOND * 1,
    ) -> None:
        self.sample_rate = sample_rate
        self.period = sample_rate / period_size * MS_IN_SECOND
        self.sample_delta = 1 / sample_rate
        self._is_running = False

        self._buffer_length = buffer_size * sample_rate // MS_IN_SECOND
        self._buffer_lock = threading.Lock()

        self._clear_buffer()

        self._mic = alsa.PCM(alsa.PCM_CAPTURE, alsa.PCM_NORMAL, device)
        self._mic.setperiodsize(period_size)
        self._mic.setrate(sample_rate)
        self._mic.setformat(alsa.PCM_FORMAT_U32_LE)
        self._mic.setchannels(self.number_channels)

    def get_data(self, length = 0):
        num_samples = self.seconds_to_samples(length)
        return self.get_samples(num_samples)
    
    def seconds_to_samples(self, seconds):
        return int(seconds * self.sample_rate)

    def _clear_buffer(self) -> None:
        self._buffer_lock.acquire()
        self._buffer = deque(
            (0 for _ in range(self._buffer_length)), maxlen=self._buffer_length
        )
        self._buffer_lock.release()

    def _audio_loop(self) -> None:
        length, raw_data = self._mic.read()

        try:
            data = (float(value) for value, in struct.iter_unpack("<L", raw_data))
        except struct.error as error:
            self._clear_buffer()
            return

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
