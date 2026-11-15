# M30 USB host driver: static boundary

`uhost.drv` is now covered by a reproducible container check and a Ghidra
MIPS32 decompilation. The result classifies it as the device-side USB host
for block storage; it does not establish USB Audio or HID support.

## Reproducible checks

```sh
PYTHONPATH=tools/emu python3 tools/emu/uhost_binary_probe.py \
  analysis/community/fw/uhost.drv
bash tools/ghidra/run_uhost_probe.sh analysis/community/fw/uhost.drv
```

The member has the same SHA-256 in the local community, stock, first-pass,
V1.101.11, V1.101.12, and V5 extractions:

```text
cd2e3c32fa57551c71c2e90a20d50f090fb7acb33e2e408fe91e90c964ed532b
```

## Container and observed roles

| Field | Value |
|---|---:|
| file offset | `0x200` |
| length | `0x798` |
| destination | `0xbfc17400` |
| BSS | `0x9fc19528`, `0x50` bytes |
| entry field | `0x12009000` |
| Ghidra mapping | file byte zero at `0xbfc17200`, 1,944 bytes, 10 functions |

The decompiler exposes a block transfer path (`FUN_bfc17420`), command/data
packet setup (`FUN_bfc1752c`, `FUN_bfc17640`, `FUN_bfc1777c`), and controller
start/wait helpers (`FUN_bfc17a08`, `FUN_bfc17afc`, `FUN_bfc17b1c`). The code
uses 512-byte sectors and a `0x1f` command/control operation. The payload has
six `USBC` literals at file offsets `0xa08`, `0xd44`, `0xed0`, `0x18bc`,
`0x1984`, and `0x1ad0`; `USBC` is the USB Mass Storage Bulk-Only Transport
CBW signature. No `USBS` CSW literal occurs in the member.

## Consequence

This closes the remaining static gap around the external USB storage host,
but it does not make the M30 a USB DAC. `usound.ap` is a separate application
path and its activation/default configuration remains a separate, untested
question. No flashable patch is proposed from this driver analysis.
