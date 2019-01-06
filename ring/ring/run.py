import typing as t
import sys
import os

import audio_tools
import config
import effects
from airpixel import client as air_client

if config.MOCK_RING:
    from PyQt5.QtWidgets import QApplication
    from airpixel import qt5_client


def qtmock_client_and_wait():
    application = QApplication(sys.argv)
    client = qt5_client.Qt5Client(config.NUM_LEDS)
    def wait(loop_threads) -> int:
        return application.exec_()
    return client, wait


def client_and_wait():
    print(__file__)
    client = air_client.AirClient(config.PORT, config.PORT + 1, config.NUM_LEDS)

    return client, watch_threads


def watch_threads(loop_threads):
    try:
        print("Press Ctrl-C to stop")
        while True:
            print("{:>5.1f}".format(loop_threads[0].avg_frame_time * 1000), end="\r")
            if not all(thread.is_alive() for thread in loop_threads):
                print("A thread crashed! Quitting.")
                break
    except (KeyboardInterrupt, SystemExit):
        print("Quitting gracefully...")
    finally:
        for thread in loop_threads:
            thread.stop()
        return 0


def main() -> None:
    if config.MOCK_RING:
        client, wait = qtmock_client_and_wait()
    else:
        client, wait = client_and_wait()

    audio_input = audio_tools.AudioInput()
    audio_input.start()

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

    return_code = wait([loop, audio_input])

    sys.exit(return_code)


if __name__ == "__main__":
    main()
