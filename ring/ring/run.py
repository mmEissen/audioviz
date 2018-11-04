import typing as t
import sys
import os

import audio_tools
import config
from airpixel import client as air_client
import profiler
from effects import CircularFourierEffect

if config.MOCK_RING:
    from PyQt5.QtWidgets import QApplication
    from airpixel import qt5_client

if config.MOCK_AUDIO:
    import mock_audio


def qtmock_client_and_wait():
    application = QApplication(sys.argv)
    client = qt5_client.Qt5Client(config.NUM_LEDS)
    return client, application.exec_


def client_and_wait():
    print(__file__)
    client = air_client.AirClient(config.PORT, config.PORT + 1, config.NUM_LEDS)

    def wait() -> int:
        input()
        return 0

    return client, wait


def main() -> None:
    if config.MOCK_RING:
        client, wait = qtmock_client_and_wait()
    else:
        client, wait = client_and_wait()

    if config.MOCK_AUDIO:
        audio_input: audio_tools.AbstractAudioInput = mock_audio.MockSinInput()
    else:
        audio_input = audio_tools.AudioInput()

    profiling_thread = profiler.ProfilingTread()
    profiler.Profiler.enabled = config.PROFILING_ENABLED
    if config.PROFILING_ENABLED:
        profiling_thread.start()

    render_func = CircularFourierEffect(audio_input, client)

    loop = air_client.RenderLoop(client, render_func)
    loop.start()

    return_code = wait()

    loop.stop()
    profiling_thread.stop()
    sys.exit(return_code)


if __name__ == "__main__":
    main()
