import math
import struct
import threading
import time
from collections import deque

import alsaaudio as alsa
import librosa
import numpy


MS_IN_SECOND = 1000
SECONDS_IN_MINUTE = 60


class AudioInput(threading.Thread):
    number_channels = 1

    def __init__(
        self,
        device='default',
        sample_rate=44100,
        period_size=512,
        buffer_size=MS_IN_SECOND * 10
    ):
        self.sample_rate = sample_rate
        self.period = sample_rate / period_size * MS_IN_SECOND
        self.sample_delta = 1 / sample_rate
        self._is_running = False

        max_buffered_samples = buffer_size * sample_rate // MS_IN_SECOND
        self._buffer = deque(maxlen=max_buffered_samples)
        self._buffer_lock = threading.Lock()

        self._mic = alsa.PCM(alsa.PCM_CAPTURE, alsa.PCM_NORMAL, device)
        self._mic.setperiodsize(period_size)
        self._mic.setrate(sample_rate)
        self._mic.setformat(alsa.PCM_FORMAT_FLOAT_BE)
        self._mic.setchannels(self.number_channels)

        super().__init__()

    def _audio_loop(self):
        length, raw_data = self._mic.read()

        # working with timestamps here to keep types in the buffer immutable
        # we also want to make sure that we measure time close after the mic.read()
        now = time.time()
        data = (value for value, in struct.iter_unpack('>f', raw_data))
        times = ((now - i * self.sample_delta) for i in reversed(range(length)))

        # consume the iterators now to minimize time in the lock
        data_with_times = list(zip(times, data))

        self._buffer_lock.acquire()
        self._buffer.extend(data_with_times)
        self._buffer_lock.release()

    def has_data(self):
        return bool(self._buffer)

    def copy_data(self):
        self._buffer_lock.acquire()
        buffer_copy = self._buffer.copy()
        self._buffer_lock.release()
        return buffer_copy

    def run(self):
        self._is_running = True
        while self._is_running:
            self._audio_loop()

    def stop(self):
        self._is_running = False


class BeatTracker(threading.Thread):
    def __init__(self):
        self._audio_input = AudioInput()
        self._predictions = []
        super().__init__()

    def _beat_track(self):
        timestamps, data = zip(*self._audio_input.copy_data())
        np_data = numpy.array(data)
        tempo, beats = librosa.beat.beat_track(np_data, units='samples')
        return float(tempo), [timestamps[i] for i in beats]

    def _update_predictions(self):
        if not self._audio_input.has_data():
            return
        tempo, beats = self._beat_track()
        if not beats:
            return
        beat_delta = SECONDS_IN_MINUTE / tempo
        last_beat = beats[-1]
        predictions = [last_beat + i * beat_delta for i in range(1, 31)]
        self._predictions = predictions

    def run(self):
        self._audio_input.start()
        self._is_running = True
        while self._is_running:
            self._update_predictions()
        self._audio_input.stop()

    def stop(self):
        self._is_running = False

    def get_prediction(self):
        return self._predictions

