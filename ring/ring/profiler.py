import functools
import time
import typing as t
import threading
from collections import deque


class Profiler:
    _times: t.Dict[str, t.Tuple[t.Any, ...]] = {}
    enabled = False

    @classmethod
    def profile(cls, function):
        full_name = function.__module__ + "." + function.__qualname__
        cls._times[full_name] = deque()

        def noop(*args, **kwargs):
            return function(*args, **kwargs)
        
        def measure(*args, **kwargs):
            start = time.time()
            result = function(*args, **kwargs)
            end = time.time()
            cls._times[full_name].append(end - start)
            return result

        @functools.wraps(function)
        def decorated_function(*args, **kwargs):
            if cls.enabled:
                return measure(*args, **kwargs)
            return noop(*args, **kwargs)

        return decorated_function

    @classmethod
    def report(cls):
        def make_report_tuple(name, measurements):
            measurements = list(measurements)
            count = len(measurements)
            avg = sum(measurements) / count if count > 0 else float("+inf")
            max_ = max(measurements) if measurements else 0
            max_tail = max(measurements[-20:]) if count > 20 else 0
            return name, count, avg, max_, max_tail

        reports = (
            make_report_tuple(name, measurements)
            for name, measurements in cls._times.items()
        )
        return "\n".join(
            "{}: count: {}, avg: {}, max {}, max_20: {}".format(*report)
            for report in reports
        )


class ProfilingTread(threading.Thread):

    def __init__(self):
        super().__init__(name="profiling-thread")
        self._is_running = False

    def _loop(self):
        print(Profiler.report(), end="\n\n")
        for _ in range(50):
            time.sleep(0.1)
            if not self._is_running:
                return

    def run(self):
        self._is_running = True
        while self._is_running:
            self._loop()

    def stop(self):
        self._is_running = False
