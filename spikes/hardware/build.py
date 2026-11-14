"""Builds the phase H spike for the desktop and the 3DS.

Needs MICROPYTHON_DIR pointing at a MicroPython checkout with mpy-cross built,
MSYS2 (MSYS2_ROOT, default C:/msys64) for the embed package's make step, and
devkitPro (DEVKITPRO_ROOT, default C:/devkitPro). Temp files follow TMP.
"""
from __future__ import annotations

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"
EMBED = BUILD / "micropython_embed"

MICROPYTHON = Path(os.environ["MICROPYTHON_DIR"])
MSYS2 = Path(os.environ.get("MSYS2_ROOT", "C:/msys64"))
DEVKITPRO = Path(os.environ.get("DEVKITPRO_ROOT", "C:/devkitPro"))

ARM_GCC = DEVKITPRO / "devkitARM" / "bin" / "arm-none-eabi-gcc.exe"
ARM_FLAGS = ["-march=armv6k", "-mtune=mpcore", "-mfloat-abi=hard", "-mtp=soft", "-D__3DS__",
             "-I", str(DEVKITPRO / "libctru" / "include")]
COMMON_FLAGS = ["-std=gnu11", "-O2", "-DNDEBUG", "-Wall", "-ffunction-sections", "-fdata-sections",
                "-I", str(EMBED), "-I", str(HERE), "-I", str(BUILD)]


def posix(path: Path) -> str:
    """A Windows path as MSYS2 spells it."""
    p = path.resolve().as_posix()
    return f"/{p[0].lower()}{p[2:]}" if len(p) > 1 and p[1] == ":" else p


def msys_env() -> dict:
    # MSYS2's own bin directories first: Git for Windows ships same-named DLLs.
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([str(MSYS2 / "mingw64" / "bin"), str(MSYS2 / "usr" / "bin"),
                                   str(Path(sys.base_prefix)), env["PATH"]])
    return env


def run(cmd: list, **kw) -> None:
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def embed_package() -> None:
    script = (f"cd '{posix(HERE)}' && make -f micropython_embed.mk "
              f"MICROPYTHON_TOP='{posix(MICROPYTHON)}' USER_C_MODULES='{posix(HERE / 'charm_module')}' "
              f"BUILD='{posix(BUILD / 'embed-gen')}' PACKAGE_DIR='{posix(EMBED)}' PYTHON=python")
    run([MSYS2 / "usr" / "bin" / "bash.exe", "-c", script], env=msys_env())


MPY_BLOBS = (
    ("bench_mpy", "bench.py", []),
    ("frames_bc_mpy", "frames.py", []),
    ("frames_native_mpy", "frames.py", ["-march=armv6", "-X", "emit=native"]),
)


def mpy_header() -> None:
    out = []
    for name, src, flags in MPY_BLOBS:
        mpy = BUILD / f"{name}.mpy"
        run([MICROPYTHON / "mpy-cross" / "build" / "mpy-cross.exe", *flags, "-o", mpy, HERE / src])
        data = mpy.read_bytes()
        rows = ",\n".join(", ".join(str(b) for b in data[i:i + 24]) for i in range(0, len(data), 24))
        out.append(f"static const unsigned char {name}[] = {{\n{rows}\n}};\n")
    (BUILD / "mpy_blobs.h").write_text("".join(out))


def sources() -> list[Path]:
    srcs = [p for p in EMBED.rglob("*.c") if p.name != "mphalport.c"]  # runner.c supplies stdout
    return srcs + [HERE / "charm_module" / "modcharm.c", HERE / "runner.c"]


def compile_all(cc: Path, flags: list, out_dir: Path, env: dict) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)

    def one(src: Path) -> Path:
        obj = out_dir / (src.relative_to(HERE).as_posix().replace("/", "_") + ".o") \
            if src.is_relative_to(HERE) else out_dir / (src.name + ".o")
        run([cc, *COMMON_FLAGS, *flags, "-c", src, "-o", obj], env=env)
        return obj

    with ThreadPoolExecutor(os.cpu_count()) as pool:
        return list(pool.map(one, sources()))


def desktop() -> Path:
    env = msys_env()
    gcc = MSYS2 / "mingw64" / "bin" / "gcc.exe"
    objs = compile_all(gcc, [], BUILD / "desktop", env)
    exe = BUILD / "charm-spike-h.exe"
    run([gcc, "-static", "-Wl,--gc-sections", *objs, "-o", exe], env=env)
    return exe


def nintendo_3ds() -> Path:
    objs = compile_all(ARM_GCC, ARM_FLAGS, BUILD / "3ds", dict(os.environ))
    elf = BUILD / "charm-spike-h.elf"
    run([ARM_GCC, "-specs=3dsx.specs", "-march=armv6k", "-mtune=mpcore", "-mfloat-abi=hard", "-mtp=soft",
         "-Wl,--gc-sections", *objs, "-L", DEVKITPRO / "libctru" / "lib", "-lctru", "-lm", "-o", elf])
    tools = DEVKITPRO / "tools" / "bin"
    smdh = BUILD / "charm-spike-h.smdh"
    run([tools / "smdhtool.exe", "--create", "CHARM spike H", "Measures MicroPython and SD speed",
         "VN3DS-CHARM", DEVKITPRO / "libctru" / "default_icon.png", smdh])
    out = BUILD / "charm-spike-h.3dsx"
    run([tools / "3dsxtool.exe", elf, out, f"--smdh={smdh}"])
    return out


def main() -> None:
    BUILD.mkdir(exist_ok=True)
    embed_package()
    mpy_header()
    print("desktop:", desktop())
    print("3ds:", nintendo_3ds())


if __name__ == "__main__":
    main()
