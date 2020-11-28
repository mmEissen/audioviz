import abc
import struct
import threading
from collections import deque
import typing as t

import alsaaudio as alsa
import numpy as np

MS_IN_SECOND = 1000
SECONDS_IN_MINUTE = 60


class AudioError(Exception):
    pass


class LoopingThread(threading.Thread, abc.ABC):
    def __init__(self, *args: t.Any, **kwargs: t.Any):
        super().__init__(*args, daemon=True, **kwargs)
        self._is_running = False

    @abc.abstractmethod
    def loop(self) -> None:
        pass

    def setup(self) -> None:
        self._is_running = True

    def tear_down(self) -> None:
        pass

    def run(self) -> None:
        self.setup()
        while self._is_running:
            self.loop()
        self.tear_down()

    def stop(self) -> None:
        self._is_running = False


class AudioInput(LoopingThread):
    number_channels = 1

    def __init__(
        self,
        device = "default",
        sample_rate = 22050,
        period_size = 1024,
        buffer_size = MS_IN_SECOND * 1,
    ) -> None:
        super().__init__(name="audio-capture-thread")
        self.sample_rate = sample_rate
        self.period = sample_rate / period_size * MS_IN_SECOND
        self.sample_delta = 1 / sample_rate

        self.buffer_length = buffer_size * sample_rate // MS_IN_SECOND
        self._buffer_lock = threading.Lock()

        self._clear_buffer()

        for cardindex in range(5):
            try:
                self._mic = alsa.PCM(alsa.PCM_CAPTURE, alsa.PCM_NORMAL, device, cardindex=cardindex)
            except alsa.ALSAAudioError as e:
                last_error = e
            else:
                break
        else:
            raise last_error
        self._mic.setperiodsize(period_size)
        self._mic.setrate(sample_rate)
        self._mic.setformat(alsa.PCM_FORMAT_S32_LE)
        self._mic.setchannels(self.number_channels)

    def _clear_buffer(self) -> None:
        self._buffer_lock.acquire()
        self._buffer = deque(
            (0.0 for _ in range(self.buffer_length)), maxlen=self.buffer_length
        )
        self._buffer_lock.release()

    def loop(self) -> None:
        length, raw_data = self._mic.read()

        try:
            data = [value / (2 ** (8 * 4 - 1)) for value, in struct.iter_unpack("<l", raw_data)]
        except struct.error as error:
            self._clear_buffer()
            return

        self._buffer_lock.acquire()
        self._buffer.extend(data)
        self._buffer_lock.release()

    def get_samples(self, num_samples):
        self._buffer_lock.acquire()
        buffer_copy = [
            sample for _, sample in zip(range(num_samples), reversed(self._buffer))
        ]
        self._buffer_lock.release()
        return buffer_copy

    def get_data(self, length = 0):
        num_samples = self.seconds_to_samples(length)
        return self.get_samples(num_samples)
    
    def seconds_to_samples(self, seconds):
        return int(seconds * self.sample_rate)


class ContiniuousVolumeNormalizer:
    def __init__(self, min_threshold=0, falloff=1.1) -> None:
        self._min_threshold = min_threshold
        self._falloff = falloff
        self._current_threshold = self._min_threshold
        self._last_call = 0

    def _update_threshold(self, max_sample, timestamp):
        if max_sample >= self._current_threshold:
            self._current_threshold = max_sample
        else:
            target_threshold = max_sample
            factor = 1 / self._falloff ** (timestamp - self._last_call)
            self._current_threshold = (
                self._current_threshold * factor + target_threshold * (1 - factor)
            )
        self._last_call = timestamp

    def normalize(self, signal, timestamp):
        if self._last_call == 0:
            self._last_call = timestamp
        max_sample = np.max(np.abs(signal))
        self._update_threshold(max_sample, timestamp)
        if (
            self._current_threshold >= self._min_threshold
            and self._current_threshold != 0
        ):
            return signal / self._current_threshold
        return np.zeros_like(signal)
