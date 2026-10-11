"""Hash-pinned Wine payload for the GPTK 3.0 workflow."""
import hashlib
import struct

SOURCE_ID = "x64-sikarugir10.0_6-r21"
SOURCE_SHA = "dc40c864f9442c9299df2b75d40e78a9550cb7fbdab64dc0ff06941efcec64b9"
OFFSET = 0xd2c0
BEFORE = bytes.fromhex(
    "4885ff7437b8020000c0f6053f531000017428554889e54989f8448b4f04488d15767a0e00"
    "488d0d8a7a0e0031ff31c0e80bf6ffffb8020000c05dc3b80d0000c0c3"
)
# Generated from src/gptk30/hags-query.s; no relocations or external calls.
PAYLOAD = bytes.fromhex(
    "4885ff7429837f0446751d833f00741e837f10047218488b47084885c0740f"
    "c7000700000031c0c3b8020000c0c3b80d0000c0c3"
)
AFTER = PAYLOAD.ljust(len(BEFORE), b"\x90")
IDENTIFIER = "win32u-55554944b27f7b09a94c3cd692bbb7a6327e4726"


def patch(data):
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA:
        raise ValueError("Unsupported win32u.so SHA256; no bytes were changed.")
    if struct.unpack_from("<II", data) != (0xfeedfacf, 0x01000007):
        raise ValueError("Expected a thin x86_64 Mach-O.")
    if data[OFFSET:OFFSET + len(BEFORE)] != BEFORE or len(AFTER) != len(BEFORE):
        raise ValueError("Function bytes or payload length differ; stopped.")
    return data[:OFFSET] + AFTER + data[OFFSET + len(BEFORE):]
