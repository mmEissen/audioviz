import abc
import struct
import threading
import time
from collections import deque
import typing as t

import alsaaudio as alsa


MS_IN_SECOND = 1000
SECONDS_IN_MINUTE = 60

DEVICE = "pulse"


class AudioError(Exception):
    pass


class LoopingThread(threading.Thread, abc.ABC):
    def __init__(self, *args: t.Any, max_loop_frequency: t.Optional[float] = None, **kwargs: t.Any):
        super().__init__(*args, daemon=True, **kwargs)
        self._is_running = False
        self._max_loop_frequency = max_loop_frequency
        self._last_update = 0

    @abc.abstractmethod
    def loop(self) -> None:
        pass

    def setup(self) -> None:
        self._is_running = True

    def tear_down(self) -> None:
        pass

    def _maybe_wait(self) -> None:
        if self._max_loop_frequency is None:
            return
        time_delta = 1 / self._max_loop_frequency
        wait = max(0, time_delta - (time.time() - self._last_update))
        time.sleep(wait)

    def run(self) -> None:
        self.setup()
        while self._is_running:
            self._maybe_wait()
            self.loop()
        self.tear_down()

    def stop(self) -> None:
        self._is_running = False


class AudioInput(LoopingThread):
    number_channels = 1

    def __init__(
        self,
        sample_rate = 22050,
        period_size = 1024,
        buffer_size = MS_IN_SECOND * 1,
        max_loop_frequency = 1 / 1,
    ) -> None:
        super().__init__(name="audio-capture-thread", max_loop_frequency=max_loop_frequency)
        self.sample_rate = sample_rate
        self.period = sample_rate / period_size * MS_IN_SECOND
        self.sample_delta = 1 / sample_rate

        self.buffer_length = buffer_size * sample_rate // MS_IN_SECOND
        self._buffer_lock = threading.Lock()

        self._clear_buffer()
        self._mic = alsa.PCM(type=alsa.PCM_CAPTURE, mode=alsa.PCM_NORMAL, device=DEVICE)
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
