# Phase H hardware spike

Measures what `docs/REWORK-PLAN.md` phase H needs before Enchantment is built
on MicroPython (D21): Python speed for one interaction and for per-frame
callbacks, the MicroPython heap, SD read speed and the app memory available.

`bench.py` is a synthetic workload sized from Mice Tea's scripts (see its
header). Real game code needs the `renpy` shim and is measured again in R2.

## Build

```
set MICROPYTHON_DIR=D:\dev-tools\micropython-1.29.0   (mpy-cross built in it)
python build.py
```

Needs MSYS2 (`MSYS2_ROOT`, default `C:/msys64`) for MicroPython's embed step
and devkitPro (`DEVKITPRO_ROOT`, default `C:/devkitPro`). Output:
`build/charm-spike-h.3dsx` and a desktop `build/charm-spike-h.exe`, whose
numbers only show the code works.

## Run on the console

Copy `charm-spike-h.3dsx` to `sdmc:/3ds/` and start it from the Homebrew
Launcher, or send it over Wi-Fi with `3dslink -a <console IP>` after pressing
Y in the launcher. It takes about two minutes. Results are shown on the top
screen and saved to `sdmc:/charm-spike-h.txt`; the 16 MB scratch file it
writes for the SD test is deleted at the end.

At the end, A tries the per-frame workload as native ARM code. That needs the
kernel to make memory executable (svcControlProcessMemory), which Azahar
doesn't implement and which can freeze a console that refuses it, so it runs
only on request, after everything else is saved. START exits.
