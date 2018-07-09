import heapq
import time
from itertools import count

import effects
from audio_tools import BeatTracker
from ring_client import RenderLoop, RingClient, RGBWPixel


class EffectTimeline:
    def __init__(self):
        self._effects_start_heap = []
        self._effects_end_heap = []
        self._counter = count()
    
    def add_effect(self, effect: effects.Effect) -> None:
        heapq.heappush(self._effects_start_heap, (effect.start, next(self._counter), effect))
    
    def _next_effect_start_time(self):
        try:
            start_time, *_ = self._effects_start_heap[0]
        except IndexError:
            return float('+inf')
        return start_time
    
    def _next_effect_ending_time(self):
        try:
            ending_time, *_ = self._effects_end_heap[0]
        except IndexError:
            return float('+inf')
        return ending_time

    def _create_combined_effect(self, now):
        while self._next_effect_start_time() <= now:
            _, counter, effect = heapq.heappop(self._effects_start_heap)
            heapq.heappush(self._effects_end_heap, (effect.end, counter, effect))
        while self._next_effect_ending_time() < now:
            heapq.heappop(self._effects_end_heap)
        return effects.MaxEffect([effect for _, _, effect in self._effects_end_heap])
    
    def _clear_frame_buffer(self, frame_buffer):
        for pixel in frame_buffer:
            pixel.set_rgbw((0, 0, 0, 0))
    
    def render(self, frame_buffer, timestamp):
        self._clear_frame_buffer(frame_buffer)
        combined_effect = self._create_combined_effect(timestamp)
        combined_effect(frame_buffer, timestamp)

PULSE_TIME = 0.2

def main():
    rc = RingClient.from_config_header('../tcp_to_led/config.h')
    print(rc)
    beat_tracker = BeatTracker()
    beat_tracker.start()
    effect_timeline = EffectTimeline()
    render_loop = RenderLoop(rc, effect_timeline.render)
    render_loop.start()
    
    fixed_period = 0
    while True:
        now = time.time()
        predictions = beat_tracker.get_prediction()
        for prediction in predictions:
            if prediction - now < 1 and prediction > fixed_period:
                effect_timeline.add_effect(
                    effects.PulseEffect(prediction - PULSE_TIME / 2, PULSE_TIME, RGBWPixel(white=1)),
                )
                fixed_period = prediction + 0.01

    render_loop.stop()

if __name__ == '__main__':
    main()