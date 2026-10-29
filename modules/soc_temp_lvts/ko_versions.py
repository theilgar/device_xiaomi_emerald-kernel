#!/usr/bin/env python3
# Print "crc symbol" pairs from the __versions section of kernel modules (6.12: 64-byte entries:
# u64 crc + char name[56]). Used to build a Module.symvers with the CRCs the running stock kernel accepts.
import os
import struct
import subprocess
import sys
import tempfile

OBJCOPY = sys.argv[1]
seen = {}
for ko in sys.argv[2:]:
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "versions.bin")
        subprocess.run([OBJCOPY, "-O", "binary", "--only-section=__versions", ko, out], check=True)
        with open(out, "rb") as f:
            raw = f.read()
    for off in range(0, len(raw) - 63, 64):
        crc, = struct.unpack_from("<Q", raw, off)
        name = raw[off + 8:off + 64].split(b"\0", 1)[0].decode()
        if name and name not in seen:
            seen[name] = crc
for name, crc in sorted(seen.items()):
    print(f"0x{crc:08x}\t{name}")
