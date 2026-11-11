"""G81b: host model of idle.c's checksum. Usage: idle_host.py <NPASS>"""
import sys
P, n = 10, int(sys.argv[1])
buf = [(i * 37 + 11) & 0xff for i in range(96)]
crc, passes = 0xffffffff, 0
for _ in range(P * n):
    for v in buf:
        crc ^= v
        for _ in range(8):
            crc = (crc >> 1) ^ (0xedb88320 & (-(crc & 1) & 0xffffffff))
    passes += 1
print("%08x" % ((~crc & 0xffffffff) ^ passes))
