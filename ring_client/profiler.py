import time
import typing as t
from collections import deque


class Profiler:
    _times: t.Dict[str, t.Tuple[t.Any, ...]] = {}

    @classmethod
    def profile(cls, function):
        full_name = function.__module__ + "." + function.__qualname__
        cls._times[full_name] = deque()

        def decorated_function(*args, **kwargs):
            start = time.time()
            result = function(*args, **kwargs)
            end = time.time()
            cls._times[full_name].append(end - start)
            return result

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

