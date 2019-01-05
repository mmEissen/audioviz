import typing as t
import sys
import os

import audio_tools
import config
import profiler
import effects
from airpixel import client as air_client

if config.MOCK_RING:
    from PyQt5.QtWidgets import QApplication
    from airpixel import qt5_client

if config.MOCK_AUDIO:
    import mock_audio


def qtmock_client_and_wait():
    application = QApplication(sys.argv)
    client = qt5_client.Qt5Client(config.NUM_LEDS)
    def wait(loop) -> int:
        return application.exec_()
    return client, wait


def client_and_wait():
    print(__file__)
    client = air_client.AirClient(config.PORT, config.PORT + 1, config.NUM_LEDS)

    def wait(loop) -> int:
        while True:
            print("{:>5.1f}".format(loop.avg_frame_time * 1000), end="\r")
        return 0

    return client, wait


def main() -> None:
    if config.MOCK_RING:
        client, wait = qtmock_client_and_wait()
    else:
        client, wait = client_and_wait()

    if config.MOCK_AUDIO:
        audio_input = mock_audio.MockSinInput()
    else:
        audio_input = audio_tools.AudioInput()

    profiling_thread = profiler.ProfilingTread()
    profiler.Profiler.enabled = config.PROFILING_ENABLED
    if config.PROFILING_ENABLED:
        profiling_thread.start()

    volume_normalizer = effects.ContiniuousVolumeNormalizer(
        config.VOLUME_MIN_THRESHOLD,
        config.VOLUME_FALLOFF,
    )
    render_func = effects.FadingCircularEffect(
        audio_input,
        client,
        volume_normalizer,
    )

    loop = air_client.RenderLoop(client, render_func)
    loop.start()

    return_code = wait(loop)

    loop.stop()
    profiling_thread.stop()
    sys.exit(return_code)


if __name__ == "__main__":
    main()
