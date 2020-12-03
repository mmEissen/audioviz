import time
import typing as t

import click

from audioviz import audio_tools, computations, star


CALIBRATION_SAMPLES = 100

CALIBRATION_FACTOR = 3


def make_computation():
    audio_input = audio_tools.AudioInput(sample_rate=star.SAMPLE_RATE)
    audio_input.start()
    sample_count = computations.Constant(
        audio_input.seconds_to_samples(star.WINDOW_SIZE_SEC)
    )
    return computations.Maximum(computations.AudioSource(audio_input, sample_count))


def get_value(computation):
    value = computation.volatile_value()
    time.sleep(star.WINDOW_SIZE_SEC)
    return value


@click.command()
def main() -> None:
    comp = make_computation()

    max_value = 0
    for i in range(CALIBRATION_SAMPLES):
        print(f"{i:4}/{CALIBRATION_SAMPLES}", end="\r")
        max_value = max(get_value(comp), max_value)

    calibration = max_value * CALIBRATION_FACTOR
    print(f"Done. Calibrated to {calibration}")
    with open(star.CALIBRATION_FILE, "w") as calibration_file:
        calibration_file.write(str(calibration))


if __name__ == "__main__":
    main()
