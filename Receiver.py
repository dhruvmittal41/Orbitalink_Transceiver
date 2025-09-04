#!/usr/bin/env python3
import argparse
import numpy
import pmt
import datetime
from gnuradio import gr, blocks, digital, filter, analog
import osmosdr

SYNC_WORD_HEX = "7e6D757368617272"
EXTRACT_LEN_BYTES = 256


class PacketExtractor(gr.basic_block):
    def __init__(self, packet_len_bytes):
        gr.basic_block.__init__(
            self, name="Packet Extractor",
            in_sig=[numpy.byte], out_sig=[numpy.byte])
        self.packet_len = packet_len_bytes
        self.start_key = pmt.intern("packet_start")
        self.state = 'SEARCHING'
        self.items_to_copy = 0

    def general_work(self, input_items, output_items):
        in0, out0 = input_items[0], output_items[0]
        read_ptr, write_ptr = 0, 0
        tags = self.get_tags_in_window(0, 0, len(in0))

        if self.state == 'SEARCHING':
            for tag in tags:
                if tag.key == self.start_key:
                    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    print(
                        f"[{timestamp}] Packet Detected! Saving {self.packet_len} bytes.")
                    self.state = 'COPYING'
                    self.items_to_copy = self.packet_len
                    tag_pos = int(tag.offset - self.nitems_read(0))
                    read_ptr = tag_pos
                    break
            if self.state == 'SEARCHING':
                self.consume(0, len(in0))
                return 0

        if self.state == 'COPYING':
            items_available = len(in0) - read_ptr
            items_to_process = min(
                items_available, self.items_to_copy, len(out0) - write_ptr)
            if items_to_process > 0:
                out0[write_ptr:write_ptr +
                     items_to_process] = in0[read_ptr:read_ptr + items_to_process]
                write_ptr += items_to_process
                read_ptr += items_to_process
                self.items_to_copy -= items_to_process
            if self.items_to_copy == 0:
                self.state = 'SEARCHING'

        self.consume(0, read_ptr)
        self.produce(0, write_ptr)
        return len(output_items[0])


class PacketRX(gr.top_block):
    def __init__(self, output_file, freq, samp_rate, sps, excess_bw, timing_loop_bw, costas_loop_bw, rx_gain, ppm):
        gr.top_block.__init__(self, "QPSK Packet RX")

        # Build bit-string of sync word (e.g., "0110...")
        SYNC_WORD_BITS = ''.join(f'{int(SYNC_WORD_HEX[i:i+2], 16):08b}'
                                 for i in range(0, len(SYNC_WORD_HEX), 2))

        # RTL-SDR source
        self.source = osmosdr.source(args="numchan=1 rtl=0")
        self.source.set_sample_rate(samp_rate)
        self.source.set_center_freq(freq, 0)
        self.source.set_gain(rx_gain, 0)
        self.source.set_freq_corr(ppm, 0)

        # RRC filter taps for the PFB clock sync block
        nfilts = 32
        ntaps = 11 * sps * nfilts
        rrc_taps = filter.firdes.root_raised_cosine(
            gain=1.0,
            sampling_freq=nfilts,    # matches PFB configuration
            symbol_rate=1.0,
            alpha=excess_bw,
            ntaps=ntaps
        )

        # PFB Clock Sync performs matched filtering and timing recovery
        self.clock_sync = digital.pfb_clock_sync_ccf(
            sps, timing_loop_bw, rrc_taps, nfilts, 16, 1.5
        )

        # Carrier recovery & symbol decisions
        self.costas_loop = digital.costas_loop_cc(costas_loop_bw, 4, False)
        self.constellation_decoder = digital.constellation_decoder_cb(
            digital.constellation_qpsk().base()
        )

        # Bits, sync-word correlate, and packet extraction
        self.symbol_to_bits = blocks.unpack_k_bits_bb(2)
        # Add differential decoder to resolve phase ambiguity from the transmitter
        self.diff_decoder = digital.diff_decoder_bb(4)  # Modulus 4 for QPSK
        self.correlate = digital.correlate_access_code_tag_bb(
            SYNC_WORD_BITS, 2, "packet_start")
        self.bit_packer = blocks.pack_k_bits_bb(8)
        self.packet_extractor = PacketExtractor(EXTRACT_LEN_BYTES)

        # File sink
        self.file_sink = blocks.file_sink(gr.sizeof_char, output_file, False)
        self.file_sink.set_unbuffered(True)

        # Wire it up
        self.connect((self.source, 0), (self.clock_sync, 0))
        self.connect((self.clock_sync, 0), (self.costas_loop, 0))
        self.connect((self.costas_loop, 0), (self.constellation_decoder, 0))
        self.connect((self.constellation_decoder, 0), (self.symbol_to_bits, 0))
        # Insert the differential decoder into the bitstream
        self.connect((self.symbol_to_bits, 0), (self.diff_decoder, 0))
        self.connect((self.diff_decoder, 0), (self.correlate, 0))
        self.connect((self.correlate, 0), (self.bit_packer, 0))
        self.connect((self.bit_packer, 0), (self.packet_extractor, 0))
        self.connect((self.packet_extractor, 0), (self.file_sink, 0))


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-o", "--output-file",
                        required=True, help="Output binary file")
    parser.add_argument("-f", "--freq", type=float,
                        default=985e6, help="Center frequency [Hz]")
    parser.add_argument("-s", "--samp-rate", type=float,
                        default=1e6, help="Sample rate [Hz]")
    parser.add_argument("--sps", type=int, default=8,
                        help="Samples per symbol")
    parser.add_argument("--excess-bw", type=float, default=0.35,
                        help="RRC filter excess bandwidth (alpha)")
    parser.add_argument("--timing-bw", type=float,
                        default=6.28e-2, help="Timing loop bandwidth")
    parser.add_argument("--costas-bw", type=float,
                        default=6.28e-2, help="Costas loop bandwidth")
    parser.add_argument("-g", "--rx-gain", type=float,
                        default=30, help="RX gain [dB]")
    parser.add_argument("-p", "--ppm", type=float, default=30,
                        help="Frequency correction [ppm]")
    args = parser.parse_args()

    tb = PacketRX(
        output_file=args.output_file, freq=args.freq, samp_rate=args.samp_rate,
        sps=args.sps, excess_bw=args.excess_bw, timing_loop_bw=args.timing_bw,
        costas_loop_bw=args.costas_bw, rx_gain=args.rx_gain, ppm=args.ppm)

    tb.start()
    print(f"[RX] Listening for packets at {args.freq / 1e6:.3f} MHz...")
    print(f"Using 64-bit Sync Word: {SYNC_WORD_HEX}")
    print(f"Saving {EXTRACT_LEN_BYTES}-byte payloads to {args.output_file}")
    try:
        input("Press Enter to quit...\n")
    except KeyboardInterrupt:
        pass
    finally:
        print("\n[RX] Stopping...")
        tb.stop()
        tb.wait()


if __name__ == "__main__":
    main()
