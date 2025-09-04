#!/usr/bin/env python3
import os
import subprocess
import time

# --- Configuration ---
# Directory containing the binary packet files to transmit.
INPUT_DIR = "./iraq/iraq/image_packets"

# Path to your corrected GNU Radio transmitter script.
FLOWGRAPH_PATH = "./tx_packet.py"

# Delay in seconds between each packet transmission.
PACKET_DELAY = 1
# -------------------


def main():
    """
    Finds all .bin packet files in the input directory and transmits them in sequence.
    """
    # Verify the input directory exists before starting.
    if not os.path.isdir(INPUT_DIR):
        print(f"❌ Error: Input directory not found at '{INPUT_DIR}'")
        return

    # Get a sorted list of files to ensure they are transmitted in order.
    # We filter for .bin files here.
    packet_files = sorted(
        [f for f in os.listdir(INPUT_DIR) if f.endswith(".bin")])

    if not packet_files:
        print(
            f"⚠️ Warning: No '.bin' files found in '{INPUT_DIR}'. Nothing to transmit.")
        return

    total_packets = len(packet_files)
    print(
        f"🚀 Starting batch transmission of {total_packets} packets from '{INPUT_DIR}'...")

    # Loop through each packet file.
    for i, filename in enumerate(packet_files):
        # Construct the full, absolute path to the packet file.
        input_path = os.path.join(INPUT_DIR, filename)

        print(
            f"\n--- [ Transmitting Packet {i+1} of {total_packets}: {filename} ] ---")

        # Construct the command to run the transmitter flowgraph.
        # THE FIX: Use "--payload_file" to match the argument expected by tx_packet.py.
        command = [
            "python3",
            FLOWGRAPH_PATH,
            f"--input_file={input_path}"
        ]

        # Execute the transmitter script as a subprocess.
        subprocess.run(command)

        # If this is not the last packet, wait for the specified delay.
        if i < total_packets - 1:
            print(f"    ...pausing for {PACKET_DELAY} second(s).")
            time.sleep(PACKET_DELAY)

    print("\n✅ Batch transmission complete.")


if __name__ == "__main__":
    main()
