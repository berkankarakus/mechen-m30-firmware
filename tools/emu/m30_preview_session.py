#!/usr/bin/env python3
"""Compose the evidence-backed M30 display and audio-boundary models.

The session deliberately joins two different levels of evidence: the real
``music.ap``/``music.sty`` host renderer is sent through the recovered LCD
command sink, while an injected callback boundary records the observed
four-argument usound trap.  The callback service is never executed because
the fixed-ROM dispatcher is not present in the extracted firmware.
"""

from __future__ import annotations

import json
import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from lcd_preview import render_preview
from lcd_transfer import LcdTransferBoundary
from m30_ui import NowPlaying


class CallbackBoundary(Protocol):
    """Minimal injected interface for the recovered callback envelope."""

    calls: list[Any]

    def trap(self, selector: int, args: tuple[int, int, int, int]) -> Any:
        ...


class AudioStream(Protocol):
    """Minimal injected interface for the observed USB-audio ring."""

    available: int

    def submit_packet(self, payload: bytes) -> int:
        ...


@dataclass
class M30PreviewSession:
    """One deterministic visible-frame plus boundary-observation session."""

    sink: LcdTransferBoundary
    ui: NowPlaying
    callback: CallbackBoundary
    audio: AudioStream
    submitted_packets: int = 0
    submitted_frames: int = 0

    @classmethod
    def create(
        cls,
        music_ap: Path,
        music_sty: Path,
        *,
        callback: CallbackBoundary,
        audio: AudioStream,
        title: str,
        artist: str,
        album: str,
        filename: str,
        scroll_offset: int,
    ) -> "M30PreviewSession":
        sink, ui = render_preview(
            music_ap,
            music_sty,
            title=title,
            artist=artist,
            album=album,
            filename=filename,
            scroll_offset=scroll_offset,
        )
        return cls(sink=sink, ui=ui, callback=callback, audio=audio)

    def observe_callback(
        self, selector: int, args: tuple[int, int, int, int]
    ) -> Any:
        """Record a callback trap without guessing its fixed-ROM effect."""

        return self.callback.trap(selector, args)

    def submit_audio_packet(self, payload: bytes) -> int:
        """Queue one observed USB packet and retain only framing statistics."""

        frames = self.audio.submit_packet(payload)
        self.submitted_packets += 1
        self.submitted_frames += frames
        return frames

    def trace(self) -> dict[str, object]:
        """Return JSON-safe evidence from the complete host session."""

        window = self.sink.window
        callbacks = []
        for call in self.callback.calls:
            callbacks.append(
                {
                    "selector": f"0x{int(call.selector):08x}",
                    "args": [f"0x{int(value):08x}" for value in call.args],
                }
            )
        return {
            "provenance": {
                "kind": "hybrid-host-session",
                "lcd": "real music.ap/music.sty renderer plus recovered LCD sink",
                "callback": "observed usound envelope; fixed-ROM service not executed",
            },
            "lcd": {
                "commands": [
                    {
                        "opcode": f"0x{command.opcode:02x}",
                        "payload": list(command.payload),
                    }
                    for command in self.sink.commands
                ],
                "pixels": window.pixel_count if window else 0,
                "remaining_pixels": self.sink.remaining_pixels,
            },
            "paint_dispatch": self.ui.paint_dispatch_trace(),
            "ui_calls": self.ui.observed_dispatch_trace(),
            "state_dispatch": self.ui.state_dispatch_traces(),
            "audio": {
                "submitted_packets": self.submitted_packets,
                "submitted_frames": self.submitted_frames,
                "queued_bytes": self.audio.available,
            },
            "callback": {"calls": callbacks},
        }

    def write_trace(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.trace(), indent=2) + "\n")


def _parse_int(value: str) -> int:
    return int(value, 0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--music-ap", type=Path, required=True)
    parser.add_argument("--music-sty", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--title", default="TITLE")
    parser.add_argument("--artist", default="ARTIST")
    parser.add_argument("--album", default="ALBUM")
    parser.add_argument("--file", dest="filename", default="FILE")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--callback-selector", type=_parse_int, default=0x10)
    parser.add_argument(
        "--callback-args",
        type=_parse_int,
        nargs=4,
        metavar=("ARG0", "ARG1", "ARG2", "ARG3"),
        default=(0, 0, 0, 0),
        help="four test inputs for the observed callback envelope",
    )
    parser.add_argument(
        "--submit-packet",
        action="store_true",
        help="submit one deterministic 200-byte USB-audio test packet",
    )
    args = parser.parse_args()

    # The emulator directories intentionally use direct-module imports.  Add
    # the simulation directory only at this CLI boundary so the shared host
    # models remain single-sourced without turning the tools tree into a
    # package with import-time side effects.
    sim_dir = Path(__file__).resolve().parents[1] / "sim"
    sys.path.insert(0, str(sim_dir))
    from usound_callback import UsoundCallbackBoundary
    from usb_audio_stream import UsbAudioStream

    session = M30PreviewSession.create(
        args.music_ap,
        args.music_sty,
        callback=UsoundCallbackBoundary(),
        audio=UsbAudioStream(),
        title=args.title,
        artist=args.artist,
        album=args.album,
        filename=args.filename,
        scroll_offset=args.offset,
    )
    session.observe_callback(args.callback_selector, tuple(args.callback_args))
    if args.submit_packet:
        packet_bytes = getattr(session.audio, "contract").packet_bytes
        session.submit_audio_packet(bytes(range(packet_bytes)))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    session.sink.framebuffer.ppm(args.out)
    session.write_trace(args.trace)
    trace = session.trace()
    print(
        f"M30 PREVIEW SESSION PASS image={args.out} "
        f"pixels={trace['lcd']['pixels']} "
        f"callbacks={len(trace['callback']['calls'])} "
        f"queued={trace['audio']['queued_bytes']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
