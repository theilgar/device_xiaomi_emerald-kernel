#!/usr/bin/env python3
# Print "function kcfi_type_hash" for every FUNC symbol of an arm64 kernel module: with kCFI the
# 32-bit type hash sits in the 4 bytes right before the function entry. Used to compare our build
# with the stock module before loading it (a mismatch = CFI panic on the first indirect call).
import re
import struct
import subprocess
import sys

READELF, KO = sys.argv[1], sys.argv[2]
data = open(KO, "rb").read()

sections = {}
for line in subprocess.run([READELF, "-SW", KO], check=True, capture_output=True, text=True).stdout.splitlines():
    m = re.match(r"\s*\[\s*(\d+)\]\s+(\S+)\s+\S+\s+[0-9a-f]+\s+([0-9a-f]+)\s+([0-9a-f]+)", line)
    if m:
        sections[int(m.group(1))] = (m.group(2), int(m.group(3), 16), int(m.group(4), 16))

for line in subprocess.run([READELF, "-sW", KO], check=True, capture_output=True, text=True).stdout.splitlines():
    f = line.split()
    if len(f) < 8 or f[3] != "FUNC" or not f[6].isdigit():
        continue
    value, ndx, name = int(f[1], 16), int(f[6]), f[7]
    sec = sections.get(ndx)
    if not sec or value < 4:
        continue
    off = sec[1] + value - 4
    h, = struct.unpack_from("<I", data, off)
    print(f"{name} 0x{h:08x}")
