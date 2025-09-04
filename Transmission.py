#!/usr/bin/env python3
import argparse
import os
from gnuradio import gr, blocks, digital, filter
import osmosdr
import numpy


class PacketTX(gr.top_block):
    def __init__(self, input_file, freq, samp_rate, sps, excess_bw, tx_gain, ppm):
        gr.top_block.__init__(self, "QPSK Packet Transmitter")

        # --- QPSK Constellation and RRC Filter Setup ---
        # QPSK has 4 points, representing 2 bits per symbol
        self.qpsk_constellation = digital.constellation_qpsk()

        # Root-Raised Cosine (RRC) filter for pulse shaping.
        # This helps control the signal's bandwidth.
        # The filter is designed with a normalized symbol rate of 1.0.
        ntaps = 11 * int(sps)  # A common rule of thumb for tap generation
        self.rrc_taps = filter.firdes.root_raised_cosine(
            1.0,              # Gain
            sps,              # Sampling frequency (in samples per symbol)
            1.0,              # Symbol rate
            excess_bw,        # Excess bandwidth (alpha)
            ntaps             # Number of taps
        )

        # --- The only data source is the packet file itself ---
        self.file_source = blocks.file_source(
            gr.sizeof_char, input_file, False)

        # --- Bit/Symbol processing chain ---
        # 1. Unpack bytes from file into a stream of bits (0s and 1s)
        self.unpack = blocks.unpack_k_bits_bb(8)

        # 2. Differentially encode the bitstream to resolve phase ambiguity at the receiver
        self.diff_encoder = digital.diff_encoder_bb(4)  # Modulus 4 for QPSK

        # 3. Map groups of 2 bits to complex QPSK symbols
        self.chunks_to_symbols = digital.chunks_to_symbols_bc(
            self.qpsk_constellation.points(), 1)

        # 4. Apply the RRC filter for pulse shaping and interpolate by sps
        self.pulse_shaper = filter.interp_fir_filter_ccf(sps, self.rrc_taps)

        # --- SDR Sink ---
        self.sink = osmosdr.sink(args="hackrf=0")
        self.sink.set_sample_rate(samp_rate)
        self.sink.set_center_freq(freq)
        self.sink.set_gain(tx_gain)
        self.sink.set_freq_corr(ppm)

        # --- Connections ---
        self.connect(self.file_source, self.unpack,
                     self.diff_encoder, self.chunks_to_symbols)
        self.connect(self.chunks_to_symbols, self.pulse_shaper, self.sink)


def main():
    # --- Configuration Parameters (Edit these values) ---
    FREQ = 985e6
    SAMP_RATE = 1e6
    SPS = 8      # Samples per Symbol
    EXCESS_BW = 0.35  # Excess bandwidth (Alpha) for RRC filter
    TX_GAIN = 35     # Transmission gain in dB
    PPM = 30         # Frequency correction
    # ----------------------------------------------------

    parser = argparse.ArgumentParser(
        description="QPSK Packet Transmitter for pre-formatted packets")
    parser.add_argument("--input-file", required=True,
                        help="Path to the binary packet file to transmit")
    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        print(f"Error: Input file not found at {args.input_file}")
        return

    tb = PacketTX(args.input_file, FREQ, SAMP_RATE, SPS,
                  EXCESS_BW, TX_GAIN, PPM)

    tb.start()
    print(
        f"[TX] Transmitting {os.path.getsize(args.input_file)} bytes from {args.input_file} at {FREQ/1e6:.3f} MHz...")
    tb.wait()
    print("[TX] Transmission finished.")


if __name__ == "__main__":
    main()
