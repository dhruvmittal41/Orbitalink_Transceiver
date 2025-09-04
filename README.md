# QPSK Packet Transmitter & Receiver

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![GNU Radio](https://img.shields.io/badge/GNU%20Radio-3.10-green)
![HackRF](https://img.shields.io/badge/SDR-HackRF-orange)
![RTL-SDR](https://img.shields.io/badge/SDR-RTL--SDR-purple)


This project provides a **QPSK-based packet transmitter and receiver** implemented in Python using **GNU Radio** and **SDR hardware**. It demonstrates how to build an end-to-end digital communication system with modulation, synchronization, filtering, and packet extraction.

---

## 📑 Table of Contents

* [Overview](#overview)
* [System Flowcharts](#system-flowcharts)
* [Transmitter Script](#transmitter-script)

  * [Class: `PacketTX`](#class-packettx)
  * [Main Function](#main-function-tx)
* [Receiver Script](#receiver-script)

  * [Class: `PacketExtractor`](#class-packetextractor)
  * [Class: `PacketRX`](#class-packetrx)
  * [Main Function](#main-function-rx)
* [Usage](#usage)
* [Dependencies](#dependencies)

---

## 📡 Overview

This project implements **QPSK packet transmission and reception** over SDR hardware.

* **Transmitter (HackRF)**: Reads packets from a binary file, modulates them using QPSK, shapes the symbols with a Root-Raised Cosine filter, and transmits them over the air.
* **Receiver (RTL-SDR)**: Receives signals, synchronizes timing, recovers carrier phase, decodes QPSK symbols, searches for a predefined sync word, and extracts payloads into a file.

---

## 🖼 System Flowcharts

### Transmitter Flow

```mermaid
flowchart LR
    A[Binary Packet File] --> B[Unpack Bits]
    B --> C[Differential Encoder]
    C --> D[Chunks → QPSK Symbols]
    D --> E[RRC Pulse Shaper]
    E --> F[HackRF Sink]
```

### Receiver Flow

```mermaid
flowchart LR
    A[RTL-SDR Source] --> B[PFB Clock Sync]
    B --> C[Costas Loop]
    C --> D[Constellation Decoder]
    D --> E[Symbols → Bits]
    E --> F[Differential Decoder]
    F --> G[Access Code Correlator]
    G --> H[Bit Packer]
    H --> I[Packet Extractor]
    I --> J[File Sink]
```

---

## 🚀 Transmitter Script

### Class: `PacketTX`

Defines the **transmission chain**.

* **Constellation**: `digital.constellation_qpsk()` → 4 points (2 bits/symbol).
* **Pulse Shaping**: Root-Raised Cosine filter (`filter.firdes.root_raised_cosine`) with roll-off factor `excess_bw`.
* **Blocks**:

  * `blocks.file_source`: Reads binary data.
  * `blocks.unpack_k_bits_bb(8)`: Expands bytes into 8 bits.
  * `digital.diff_encoder_bb(4)`: Differentially encodes bitstream.
  * `digital.chunks_to_symbols_bc`: Maps bits to QPSK symbols.
  * `filter.interp_fir_filter_ccf`: Interpolates samples per symbol (SPS).
  * `osmosdr.sink`: Sends modulated samples to HackRF.

### Main Function (TX)

* Parses CLI args for the input file.
* Sets SDR parameters (frequency, sample rate, gain, ppm).
* Starts GNU Radio flowgraph and streams packets.

---

## 📡 Receiver Script

### Class: `PacketExtractor`

A **custom block** to extract fixed-length packets after detecting a sync word.

* **States**:

  * `SEARCHING`: Monitors tags for `packet_start`.
  * `COPYING`: Copies the detected payload of defined length.

### Class: `PacketRX`

Defines the **reception chain**.

* **Blocks**:

  * `osmosdr.source`: Captures IQ samples from RTL-SDR.
  * `digital.pfb_clock_sync_ccf`: Timing recovery with RRC matched filter.
  * `digital.costas_loop_cc`: Corrects carrier frequency/phase.
  * `digital.constellation_decoder_cb`: Maps received symbols back to bits.
  * `blocks.unpack_k_bits_bb(2)`: Converts 2-bit QPSK symbols into a bitstream.
  * `digital.diff_decoder_bb(4)`: Resolves phase ambiguity.
  * `digital.correlate_access_code_tag_bb`: Searches for sync word.
  * `blocks.pack_k_bits_bb(8)`: Packs bits back into bytes.
  * `PacketExtractor`: Extracts payload of fixed size.
  * `blocks.file_sink`: Stores extracted data in file.

### Main Function (RX)

* Parses CLI args (frequency, sample rate, gain, PPM, etc.).
* Prints configuration details.
* Runs GNU Radio flowgraph until user stops with Enter or Ctrl+C.

---

## 🛠 Usage

### Transmitter

```bash
python3 tx.py --input-file packets.bin
```

### Receiver

```bash
python3 rx.py -o received.bin -f 985e6 -s 1e6 -g 30
```

---

## 📦 Dependencies

* Python 3.8+
* GNU Radio 3.10+
* gr-osmosdr
* HackRF (for TX)
* RTL-SDR (for RX)

Install GNU Radio and osmosdr with:

```bash
sudo apt install gnuradio gr-osmosdr
```

---

