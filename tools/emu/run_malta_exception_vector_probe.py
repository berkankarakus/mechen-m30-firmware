#!/usr/bin/env python3
"""Execute the extracted M30 exception vector on QEMU's Malta MIPS CPU."""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EMU = ROOT / "tools" / "emu"
BUILD_TIMEOUT = 30


def tool(name: str, override: str | None = None) -> str:
    candidate = override or shutil.which(name)
    if not candidate:
        raise SystemExit(f"required tool not found: {name}")
    return candidate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("kernel_driver", type=Path)
    parser.add_argument("--qemu", help="QEMU executable (default: qemu-system-mipsel)")
    parser.add_argument("--as", dest="assembler", help="MIPS assembler override")
    parser.add_argument("--ld", dest="linker", help="MIPS linker override")
    parser.add_argument("--objcopy", help="MIPS objcopy override")
    parser.add_argument("--timeout", type=float, default=2.0)
    args = parser.parse_args()

    kernel = args.kernel_driver.resolve()
    if not kernel.is_file():
        raise SystemExit(f"missing kernel.drv: {kernel}")

    assembler = tool("mipsel-linux-gnu-as", args.assembler)
    linker = tool("mipsel-linux-gnu-ld", args.linker)
    objcopy = tool("mipsel-linux-gnu-objcopy", args.objcopy)
    qemu = tool("qemu-system-mipsel", args.qemu)

    with tempfile.TemporaryDirectory(prefix="m30-malta-vector-") as temp_name:
        temp = Path(temp_name)
        obj = temp / "probe.o"
        elf = temp / "probe.elf"
        harness = temp / "harness.bin"
        bios = temp / "m30-probe-bios.bin"

        commands = [
            [assembler, "-EL", "-march=24kc", "-mips32r2", "-o", str(obj),
             str(EMU / "malta_exception_vector_probe.S")],
            [linker, "-EL", "-T", str(EMU / "malta_exception_vector_probe.ld"),
             str(obj), "-o", str(elf)],
            [objcopy, "-O", "binary", str(elf), str(harness)],
            ["python3", str(EMU / "build_malta_exception_probe_bios.py"),
             str(kernel), str(harness), str(bios)],
        ]
        for command in commands:
            try:
                result = subprocess.run(
                    command,
                    text=True,
                    capture_output=True,
                    timeout=BUILD_TIMEOUT,
                )
            except subprocess.TimeoutExpired:
                raise SystemExit(
                    f"build command exceeded {BUILD_TIMEOUT}s: {shlex.join(command)}"
                )
            if result.returncode:
                raise SystemExit(
                    f"command failed: {shlex.join(command)}\n"
                    f"{result.stdout}{result.stderr}"
                )
            if result.stdout:
                print(result.stdout, end="")
            if result.stderr:
                print(result.stderr, end="")

        qemu_command = [
            qemu,
            "-M", "malta",
            "-cpu", "24Kf",
            "-m", "256M",
            "-bios", str(bios),
            "-display", "none",
            "-serial", "null",
            "-serial", "null",
            "-serial", "stdio",
            "-monitor", "none",
            "-no-reboot",
            "-no-shutdown",
        ]
        try:
            result = subprocess.run(
                qemu_command,
                text=True,
                capture_output=True,
                timeout=args.timeout,
                env={**os.environ, "QEMU_AUDIO_DRV": "none"},
            )
            stdout, stderr = result.stdout, result.stderr
            timed_out = False
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            timed_out = True
            if isinstance(stdout, bytes):
                stdout = stdout.decode(errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode(errors="replace")

        if stdout.strip() != "PASS" or not timed_out:
            raise SystemExit(
                "QEMU did not halt after emitting exactly the expected PASS marker.\n"
                f"timed_out={timed_out}\nstdout:\n{stdout}\nstderr:\n{stderr}"
            )
        if "FAIL" in stdout or "qemu: fatal:" in stderr:
            raise SystemExit(f"QEMU reported failure:\n{stdout}\n{stderr}")
        print("MALTA M30 EXCEPTION VECTOR PASS saved-EPC-RA-ExcCode=9")
        if stderr.strip():
            print(stderr.strip())


if __name__ == "__main__":
    main()
