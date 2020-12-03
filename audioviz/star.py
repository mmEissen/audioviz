import time
import typing as t

from airpixel import client as air_client
import click

from audioviz import audio_tools, computations


CALIBRATION_FILE = ".calibration"

SAMPLE_RATE = 44100

WINDOW_SIZE_SEC = 0.05

THRESHOLD_HISTORY = 6


def make_monitors(
    **kwargs: computations.Computation,
) -> t.List[computations.Computation]:
    monitor_client = air_client.MonitorClient("monitoring_uds")
    return [
        computations.Monitor(computation, name, monitor_client)
        for name, computation in kwargs.items()
    ]


def make_computation(ip_address: str, port: int, volume_threshold: float):
    audio_input = audio_tools.AudioInput(sample_rate=SAMPLE_RATE)
    audio_input.start()

    sample_count = computations.Constant(
        audio_input.seconds_to_samples(WINDOW_SIZE_SEC)
    )
    sample_delta = computations.Constant(audio_input.sample_delta)
    lowest_note = computations.Constant(6.02236781303)
    highest_note = computations.Constant(11.0313565963)
    beam_count = computations.Constant(36)
    half_beam_count_plus1 = beam_count // computations.Constant(
        2
    ) + computations.Constant(1)
    leds_per_beam = computations.Constant(8)
    slice_start = computations.Constant(1)

    fft_frequencies = computations.Slice(
        computations.FastFourierTransformFrequencies(sample_count, sample_delta),
        slice_start,
    )

    audio_source = computations.AudioSource(audio_input, sample_count,)

    on_toggle = computations.ThresholdToggle(
        computations.History(audio_source, THRESHOLD_HISTORY,),
        computations.Constant(volume_threshold),
    )

    hamming_audio = computations.Multiply(
        audio_source, computations.HammingWindow(sample_count)
    )
    fft_result = computations.Slice(
        computations.FastFourierTransform(hamming_audio, sample_delta,), slice_start,
    )
    a_weighted = computations.Multiply(
        computations.AWeightingVector(fft_frequencies), fft_result
    )
    resampled = computations.Resample(
        computations.Log2(fft_frequencies),
        a_weighted,
        computations.Linspace(lowest_note, highest_note, half_beam_count_plus1,),
    )
    final = computations.Roll(
        computations.Mirror(
            computations.Multiply(computations.VolumeNormalizer(resampled), on_toggle,),
        ),
        computations.Constant(16),
    )
    resolution = computations.Multiply(leds_per_beam, computations.Constant(16))

    return (
        computations.Star(
            final,
            leds_per_beam,
            resolution,
            beam_count,
            computations.BeamMasks(leds_per_beam, resolution),
            computations.Constant(0.5),
            ip_address,
            port,
        ),
        make_monitors(
            audio_source=audio_source,
            hamming_audio=hamming_audio,
            fft_result=fft_result,
            a_weighted=a_weighted,
            resampled=resampled,
            final=final,
        ),
    )


@click.command()
@click.argument("ip_address", required=True)
@click.argument("port", required=True, type=int)
@click.option("--graph", is_flag=True)
@click.option("--benchmark", is_flag=True)
def main(ip_address: str, port: int, graph: bool, benchmark: bool) -> None:
    try:
        with open(CALIBRATION_FILE) as calibration_file:
            volume_threshold = float(calibration_file.read().strip())
    except (OSError, ValueError):
        volume_threshold = 0

    comp, monitors = make_computation(ip_address, port, volume_threshold)

    if graph or benchmark:
        from audioviz import computation_graph

        print(computation_graph.make_graph(comp, benchmark))
        return

    while True:
        start = time.time()
        comp.value()
        for monitor in monitors:
            monitor.value()
        comp.clean()
        for monitor in monitors:
            monitor.clean()
        end = time.time()
        time.sleep(max(1 / 60 - (end - start), 0))


if __name__ == "__main__":
    main()
