"""Fetch the GPTK 3.0 NGX bridge from the runtime package used by Highball r21."""
import hashlib
from pathlib import Path
import tarfile
import tempfile
from urllib.request import Request, urlopen

from src.gptk import version_from_plist

# From the runtime component of Highball's x64-sikarugir10.0_6-r21 manifest.
# https://github.com/Sikarugir-App/Wrapper/releases/tag/v1.0
ARCHIVE_URL = "https://github.com/Sikarugir-App/Wrapper/releases/download/v1.0/Template-1.0.11.tar.xz"
ARCHIVE_SHA = "9fa15479e7ff6abd99c1d07be285fb95f41fc6991586502427152b1f7d6ccb8a"
ARCHIVE_SIZE = 84533420
PREFIX = "Template-1.0.11.app/Contents/Frameworks/renderer/d3dmetal/"
DLL_MEMBER = PREFIX + "wine/x86_64-windows/nvngx.dll"
INFO_MEMBER = PREFIX + "external/D3DMetal.framework/Versions/A/Resources/Info.plist"
DLL_SHA = "d7c0df74d9bb4de5e2a3cc357b2309148fd3fdc824fe7941e4d789dbd072ff99"
DLL_SIZE = 90576


def file_sha(path):
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def verify_archive(path):
    if path.is_symlink() or path.stat().st_size != ARCHIVE_SIZE or file_sha(path) != ARCHIVE_SHA:
        raise ValueError("Runtime archive checksum/size differs; no DLL was installed.")


def archive_dll(path):
    verify_archive(path)
    # Read only exact regular members; never extract archive paths or follow archive links.
    # https://docs.python.org/3.12/library/tarfile.html#tarfile.TarFile.extractfile
    with tarfile.open(path, "r:xz") as archive:
        def read_member(name, limit):
            member = archive.getmember(name)
            if not member.isfile() or not 0 < member.size <= limit:
                raise ValueError("Invalid runtime archive member: " + name)
            with archive.extractfile(member) as stream:
                data = stream.read(limit + 1)
            if len(data) != member.size:
                raise ValueError("Runtime archive member is incomplete: " + name)
            return data

        if version_from_plist(read_member(INFO_MEMBER, 16384)) != "3.0":
            raise ValueError("Downloaded runtime is not GPTK 3.0.")
        data = read_member(DLL_MEMBER, DLL_SIZE)
    if len(data) != DLL_SIZE or hashlib.sha256(data).hexdigest() != DLL_SHA:
        raise ValueError("Downloaded nvngx.dll checksum/size differs; no DLL was installed.")
    return data


def fetch_ngx(cache):
    cache = Path(cache).resolve()
    cache.mkdir(parents=True, exist_ok=True)
    dll = cache / "nvngx-gptk30.dll"
    if dll.exists() or dll.is_symlink():
        if dll.is_symlink() or dll.stat().st_size != DLL_SIZE or file_sha(dll) != DLL_SHA:
            raise ValueError("Cached NGX DLL differs; remove it and retry: " + str(dll))
        return dll
    archive = cache / "Template-1.0.11.tar.xz"
    if archive.is_symlink():
        raise ValueError("Runtime archive cache must not be a symlink.")
    with tempfile.TemporaryDirectory(prefix=".ngx-download-", dir=cache) as temp:
        staged = Path(temp)
        if not archive.exists():
            print("Downloading GPTK 3.0 runtime:", ARCHIVE_URL, flush=True)
            request = Request(ARCHIVE_URL, headers={"User-Agent": "highball_fg2x"})
            # Verified HTTPS with a socket timeout; SHA256 is checked before cache publication.
            with urlopen(request, timeout=30) as response, (staged / archive.name).open("wb") as output:
                received = 0
                for chunk in iter(lambda: response.read(1024 * 1024), b""):
                    received += len(chunk)
                    if received > ARCHIVE_SIZE:
                        raise ValueError("Runtime download exceeds the pinned size.")
                    output.write(chunk)
            verify_archive(staged / archive.name)
            (staged / archive.name).replace(archive)
        data = archive_dll(archive)
        (staged / dll.name).write_bytes(data)
        (staged / dll.name).replace(dll)
    return dll
