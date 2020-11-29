import time

from airpixel import client as air_client
import click

from audioviz import audio_tools, computations


CALIBRATION_FILE = ".calibration"

SAMPLE_RATE = 44100

WINDOW_SIZE_SEC = 0.05


def make_computation(ip_address: str, port: int):
    monitor_client = air_client.MonitorClient("monitoring_uds")

    audio_input = audio_tools.AudioInput(sample_rate=SAMPLE_RATE)
    audio_input.start()

    sample_count = computations.Constant(
        audio_input.seconds_to_samples(WINDOW_SIZE_SEC)
    )
    sample_delta = computations.Constant(audio_input.sample_delta)
    lowest_note = computations.Constant(6.02236781303)
    highest_note = computations.Constant(11.0313565963)
    beam_count = computations.Constant(36)
    half_beam_count_plus1 = computations.Constant(19)
    leds_per_beam = computations.Constant(8)

    slice_start = computations.Constant(1)
    fft_frequencies = computations.Slice(
        computations.FastFourierTransformFrequencies(sample_count, sample_delta),
        slice_start,
    )

    audio_source = computations.Monitor(
        computations.AudioSource(audio_input, sample_count,),
        "audio_in",
        monitor_client,
    )
    hamming_audio = computations.Monitor(
        computations.Multiply(audio_source, computations.HammingWindow(sample_count),),
        "hamming",
        monitor_client,
    )
    fft_result = computations.Monitor(
        computations.Slice(
            computations.FastFourierTransform(hamming_audio, sample_delta,),
            slice_start,
        ),
        "fft",
        monitor_client,
    )
    a_weighted = computations.Monitor(
        computations.Multiply(
            computations.AWeightingVector(fft_frequencies), fft_result
        ),
        "a_weighted",
        monitor_client,
    )
    resampled = computations.Monitor(
        computations.Resample(
            computations.Log2(fft_frequencies),
            a_weighted,
            computations.Linspace(lowest_note, highest_note, half_beam_count_plus1,),
        ),
        "resampled",
        monitor_client,
    )
    final = computations.Monitor(
        computations.Roll(
            computations.Mirror(computations.VolumeNormalizer(resampled),),
            computations.Constant(16),
        ),
        "final",
        monitor_client,
    )
    resolution = computations.Multiply(leds_per_beam, computations.Constant(16))

    return computations.Star(
        final,
        leds_per_beam,
        resolution,
        beam_count,
        computations.BeamMasks(leds_per_beam, resolution),
        computations.Constant(0.5),
        ip_address,
        port,
    )


@click.command()
@click.argument("ip_address", required=True)
@click.argument("port", required=True, type=int)
@click.option("--graph", is_flag=True)
@click.option("--benchmark", is_flag=True)
def main(ip_address: str, port: int, graph: bool, benchmark: bool) -> None:
    comp = make_computation(ip_address, port)

    if graph or benchmark:
        from audioviz import computation_graph

        print(computation_graph.make_graph(comp, benchmark))
        return

    while True:
        comp.value()
        comp.clean()
        time.sleep(1 / 60)


if __name__ == "__main__":
    main()
