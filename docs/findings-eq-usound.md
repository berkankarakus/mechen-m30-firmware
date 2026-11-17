<!-- Statik analiz bulgusu (cihazda test edilmedi). Alt ajan çıktısı; ana oturum aşağıdaki noktaları baytlardan doğruladı: mengine.ap EQ tablosu/frekanslar/sıfır alanı, setting.ap tablosu/sıfır alanı, config.bin öğe 0x116 baytları. Diğer iddialar ajanın okumasına dayanır; VERIFIED/V = dump veya baytta okundu, HYPOTHESIS/H = çıkarım. Kaynak dosya: m30-work/findings/eq_usound.md. -->

# EQ + usound findings (read-only; V=VERIFIED, H=HYPOTHESIS)

## A. EQ
- Reproducible check: `bash tools/ghidra/run_eq_probe.sh` decompiles the
  community `mengine.ap` EQ loader and checks its pointer pool, seven-band
  frequency table, gain rows, and the `setting.ap` Custom row. It is a static
  AP/raw-byte check and does not validate audible output.
- `bash tools/ghidra/run_eq_builder_probe.sh` executes the real MIPS16 builder
  in Ghidra p-code against hash-verified stock and community `mengine.ap`.
  Eleven cases pass; both binaries produce the same structure digest. The
  probe uses synthetic RAM and stubs for missing ROM services, so it validates
  builder writes and call arguments only.
- V SDK: ap/ap_setting/menu_callback_sound_setting.c: eq_param[8][MAX_EQ_SEG] int8 (none,rock,funk,hiphop,jazz,classic,techno,custom); _set_real_eq() builds mmm_mp_eq_info_t{eq_type, eq_para[12]} and sends MSG_MENGINE_SET_EQ_SYNC (music_set_eq, line 81-88). Engine: mengine_event_volume.c mengine_set_real_eq() -> mmm_mp_cmd(MMM_MP_SET_EQ,&eq_info). Custom = g_setting_vars.music_comval.eq_parameter[12] (int8, setting_common.h:167), edited in music_setmenu_soundset_param.c. EQ_TOTAL=8 (ap_setting.h:27) incl. Off. config.txt SETTING_AP_ID_EQ_SETTING = 0[0..7].
- V Table A (setting.ap, community==stock): file 0x5a94..0x5b13, 8 rows x 16 B (12 int8 used + 4 pad; rock row 0x5aa4, funk 0x5ab4, hiphop 0x5ac4, jazz 0x5ad4, classic 0x5ae4, techno 0x5af4, custom 0x5b04 = {-9,0,0,0,0,0,6}). Zeros 0x5b14..0x5bff (236 B) then next sector at 0x5c00.
- V Table B (mengine.ap, same in stock): presets at 0x440c.., 7 B/row (7 signed-int8 gain values; row index is preset): Off 0x440c, Rock 0x4413, Funk 0x441a, Hip hop 0x4421, Jazz 0x4428, Classical 0x442f, Techno 0x4436 (selector 0..6). Frequencies are u16 values at 0x43ec (80,200,480,980,4000,8000,16000 Hz); Q values are raw u16s at 0x43fc (10,6,4,6,10,5,8). Calling those Q×10 is a hypothesis; the binary establishes the stored values only. Pointer pool file 0x41f4 = {0x601d10ec, 0x601d10fc, 0x9fc1a19c (RAM custom), 0x601d110c}; file = VA - 0x601ccd00.
- V `FUN_601d0d58` selects one 7-byte table row, or selector 7's seven RAM bytes at `0x9fc1a19c`, sign-extends each gain, multiplies by 10 and writes an s16 into each band. The ×10 conversion is verified; interpreting the result as 0.1 dB units is a strong inference, not a demonstrated DSP unit. Seven active bands use the eight-byte layout `{frequency u16, Q u16, gain s16, enable=1, reserved=0}` beginning at structure offset `0x10 + 8*i`.
- V Scratchpad MIPS16 p-code run of `FUN_601d0d58` used hash-verified stock and community `mengine.ap`; all 11 cases (selectors 0..7 with sentinel Custom, real Custom default, busy guard, and inactive guard) matched their byte expectations. It confirmed the argumentless entry, selector mirror at `0x9fc15db5`, active flag at `0x9fc15db4`, busy check at structure `+0x0c == 1`, and early return after mirroring the selector. In an active build, `+7=1`, `+0xd=(selector != 0)`, bands 0..6 are written, and bands 7..15 occupy and zero `0x48..0x8f`. Bytes `0x00..0x06`, `0x08..0x0b`, `0x0e..0x0f`, and `0x90..0xef` retain their initial `0xaa` values in the probe. The latter range is untouched, not the unused-band range.
- V The builder passes `{a1=0x9fc15dd4, a2=0xf0}` to the module `0x10` copy stub, then requests shared-memory id 3 with argument `0x49`, then invokes module `0x42` with command `0x1f`. The probe used a synthetic nonzero SHM handle; the message target value was zero because initialization was not run. These stub effects are not modeled as DSP behavior.
- V Free space: mengine.ap zeros 0x443d..0x47ff (0x443d-0x4443 would be a would-be 8th row; 956 B to 0x4800 sector end, but 0x4600 is also a sector edge -> 0x4600..0x47ff may be bank padding). setting.ap 236 B after table.
- V/H Extra presets: `run_eq_probe.sh` confirms `FUN_601d0d58` has a seven-iteration loop, uses `idx * 7` for non-Custom rows, and branches only on `idx == 7` to the Custom RAM pointer. No index clamp or default case is visible in this function. The UI count remains `EQ_TOTAL=8`; setting.ap table and music/setting menu strings/.mcg trees are separate. Adding presets therefore needs a code patch (new index mapping and bounds behavior) plus menu tree/sty edits. Not checked: music.mcg/setting.mcg node count, which AP writes `g+0x41` (H: copy of eq_type from SET_EQ msg).
- `run_eq_writer_probe.sh` performs a separate Ghidra instruction scan over `setting.ap`, `music.ap`, and `mengine.ap`. It finds no decoded direct `sb/sh/sw` store using an immediate `0x41` (or `0x141`) offset. This is a negative boundary result, not proof that the selector is never written: the writer may copy a message/structure, use a register-derived offset, or live in a shared resident component. It is enough to reject a simple “patch the first `+0x41` store” approach.
- `run_eq_chain_probe.sh` closes the message-path gap. The public PD196 reference defines `MSG_MENGINE_SET_EQ_SYNC` as `MENGINE_BASE + 3 = 0x303`; in the M30 binary, `FUN_60090d64` dispatches `0x303` through the pool entry at `0x60091014` to `FUN_601d0f30`. That handler copies the message payload through the resident memory helper and calls the pool entry at `0x601d0f74`, whose raw value is `0x601d0d59` (the MIPS16 entry of `FUN_601d0d58`). The builder then reads the selector from `0x9fc15c88 + 0x41`, chooses Custom only for `idx == 7`, and builds the seven-band structure. The producer side is resolved by the companion `music.ap` probe below.
- `run_eq_producer_probe.sh` resolves that producer in `music.ap`: `FUN_403d4e20` forwards a two-byte `{eq_type, selector}` payload through `FUN_40614f08`, which sends message `0x303`. The wrappers emit `0,0` for Off and `7,1` through `7,6` for the six built-in presets. `FUN_403d4ed0` copies the seven custom gains and then emits `7,7`. This closes the selector-producer gap; adding a preset would require extending this dispatch/menu set and the engine's coefficient mapping, not merely editing the EQ table.
- `tools/emu/eq_menu_probe.py` verifies the menu-side pointer topology in stock, community, V1.101.11, and V1.101.12: the seven built-in callback entry points occur once each in the `music.ap` table at file `0xdeec..0xdf64` with `0x14` (20-byte) spacing, and three repeated groups in `music.mcg` reference the same seven pointers at `0x2fea`, `0x3554`, and `0x3b90` with `0x2a` (42-byte) spacing. The Custom callback `FUN_403d4ed0` has no direct MCG pointer; its separate parameter-copy path is consistent with the producer decompilation. The probe deliberately does not assign language meaning to the three MCG groups.
- `tools/sim/m30_model.py` keeps an evidence-backed `FIRMWARE_EQ_PRESETS` contract separate from the older five-band UI proposal. It models raw u16 frequency/Q tables, signed-int8 gain rows, exact selector payloads (`Off = {0,0}`, built-ins `{7,1..6}`, `Custom = {7,7}`), the observed signed-int8 ×10 conversion, and the verified builder writes while preserving unknown bytes. Custom curves require seven explicit values; the model does not silently treat the proposed UI curves as device coefficients.
- The public twelve-image corpus shows one verified revision-specific exception: the 2024-04-24 `mengine.ap` uses `50 Hz` for the first band while the other checked releases use `80 Hz`. `FirmwareEqProfile` exposes both the current profile and this dated profile without weakening the default contract.
- `tools/emu/eq_binary_probe.py` cross-checks a selected profile against raw bytes: `mengine.ap` frequency/Q tables and all seven non-Custom gain rows, plus the default seven-value Custom row at `setting.ap` `0x5b04`. The default profile remains the current host target; the 2024-04 profile is selected explicitly for historical corpus validation.
- `run_eq_chain_probe.sh` verifies the message boundary: `0x303` dispatches to
  `FUN_601d0f30`, which reaches the coefficient builder at `FUN_601d0d58`.
  `music.ap` supplies the selector from `0x9fc15c88 + 0x41`; the host model
  exposes this as `FirmwareEqCommand` while leaving the indirect DSP calls
  unresolved.
- V Shared-memory chain: `config.ap` creates id 3 with a 0xf0-byte buffer and
  copies the source structure; `mengine.ap` builds/copies the same 0xf0-byte
  structure; `mmm_pp.al` attaches id 3 and stores its handle at object offset
  +156. `mmm_pp.al` then calls module `0x0c`, op `0x12`, with `a0=1` and the
  SHM handle as `a1`; the same op is called with `a0=2` for sample rate, `a0=3`
  for another context structure, and `a0=0` for a channel/rate structure.
  Calling `a0=1` the EQ/DAE payload is an inference from this call pattern.
  `mmm_pp.al` directly reads only SHM byte `+2`, selecting `adppext.dsp` when
  zero and `audiopp.dsp` when nonzero; it does not directly inspect the band
  range `+0x10..+0x8f`. The op-`0x12` recipient may read it, but that target is
  outside the available corpus. The actual storage backing and module `0x42`
  message recipient also remain unknown.
- V `config.ap` sets SHM byte `+2` and `+3` from an object flag before creating
  `dae_cfg`; the flag's meaning is unknown. This gives a concrete DSP-selection
  boundary, not proof that a particular EQ curve reaches or changes audible
  output.
- V The M30 `aud_dev.drv` container has one nonempty YQHX load segment:
  file `0x300`, length 8, destination `0xbfc09f58`. The raw file region
  `0x200..0x253` contains 21 words; word 18 is `0x2c149401`. Treating these as
  an op-to-ROM far-pointer table and mapping module `0x0c` to `aud_dev.drv` are
  inferences. The executable bytes at `0x300` are `10 6b 05 e8 0f 6b 05 e8`,
  two MIPS16 module-call stubs. No ROM implementation for op `0x12` is present.
- Data-only preset tuning is the lowest-risk firmware experiment currently
  identified, but it is not validated as safe. Existing gain values are signed
  bytes and the builder scales them by 10; interpreting them as dB is an
  inference. Keep candidate values within the range already present in the
  vendor's presets/custom default, change one byte first, preserve the original
  image, and verify repackaging checksums before any device test. No such image
  patch or flash test has been performed. The Q table's physical units and the
  DSP's clipping limits remain unknown. The 50 Hz first-band value in the
  2024-04-24 image proves that value was shipped in that image, not that it is
  safe on another revision or hardware path.
- V Negative corpus scan: the module 0x42 stub, command 0x1f, and EQ shared
  structure references are present in `mengine.ap`; the code that receives
  module 0x42 is absent from the scanned AP/driver/DSP corpus and is expected
  in fixed ROM or another unavailable component. `coeffi.bin` uses a separate
  six-block loader (six blocks of 0x1a00 bytes); the EQ builder does not refer
  to it, and the EQ frequency table was not found inside the DSP blobs. An EQ
  connection to `coeffi.bin` is therefore unproven. `audiopp.dsp` is listed
  for loading by `mmm_pp.al`, but that alone does not prove it consumes EQ data.
- V music.ap contains no eq table (no byte pattern match in any member except setting.ap, mengine.ap).

## B. usound
- `usound.drv` is now covered by two read-only checks:
  `PYTHONPATH=tools/emu python3 tools/emu/usound_binary_probe.py
  analysis/community/fw/usound.drv` validates the yqhx container and USB
  descriptor bytes; `bash tools/ghidra/run_usound_probe.sh
  analysis/community/fw/usound.drv` decompiles the resident code path. Both
  checks pass for the local community, stock, V1.101.11, V1.101.12, and V5
  copies because those members have the same SHA-256.
- `config.bin` is separately checked by
  `PYTHONPATH=tools/emu python3 tools/emu/config_usb_mode_probe.py
  analysis/community/fw/config.bin`; it resolves item `0x116` through the
  index at `0x8c0` to payload offset `0xe4a`, length 8, whose first u16 is
  zero (`00 00 00 00 01 00 01 00`). The earlier `0xe4a` wording refers to
  the payload, not the index record.
- V The embedded device descriptor is USB 1.1, VID `0x10d6`, PID `0xdd00`.
  The configuration advertises three distinct interfaces: audio control
  interface 0, audio streaming interface 1 (alternate settings 0 and 1),
  and HID interface 3. The audio format descriptor is two-channel, 16-bit
  PCM at the single advertised rate 48000 Hz. The streaming endpoint is
  isochronous OUT `0x01` with 200-byte packets; the HID endpoint is interrupt
  IN `0x82`. The raw strings are `USB Audio` and `Actions`.
- The configuration topology is now checked by `tools/emu/usound_binary_probe.py`:
  the USB streaming input terminal (`0x0101`) feeds a feature unit and a
  `0x0301` speaker output terminal. This upgrades the USB-DAC conclusion from
  “an Audio Class endpoint exists” to “the device descriptor advertises a USB
  speaker/sink.” It still does not prove that the M30 connector is wired for
  device mode or that the unresolved callback reaches the physical codec.
- V The extracted `usound.drv` is byte-identical across the six local
  corpora (`community`, `first-pass-verify`, `stock`, `v1.101.11`,
  `v1.101.12`, and `v5`; SHA-256
  `e593bdd29c2a96d4d745cf1b5cae4da2ee71c2211c551e415209b18f54e600fc`).
- V A dated-corpus extension of that check covered nine additional extracted
  releases (2022-09-14, 2022-11-17, 2023-02-20, 2023-07-26, 2024-02-28,
  2024-03-19, 2024-04-24, 2025-02-17, and 2025-06-26). Every `usound.drv`
  has the same SHA-256 and passes `usound_binary_probe.py` with the same
  UAC1/HID descriptor contract. This strengthens the cross-version stability
  of the driver boundary, but still does not prove PCM ownership or OTG
  hardware behavior.
- V Ghidra maps 9,904 payload bytes into 46 functions. The decompiled
  initialization writes the 200-byte streaming packet size and `0x84` control
  value; the request handler has standard/interface control branches and
  handles endpoint `0x82`. This ties the descriptor table to executable
  driver code rather than treating strings alone as proof.
- Consequence: the firmware contains a device-side UAC1/HID implementation,
  so “M30 as a USB DAC for a USB host” is statically plausible. This does not
  prove that the M30 hardware exposes OTG/VBUS correctly, that the firmware
  can reach the path with the stock configuration, or that the device can
  act as a USB host driving an external DAC. No device write or USB-mode test
  has been performed.
- `usound.ap` is now covered by a binary bank probe and a Ghidra AP probe:
  `FUN_40094e88` first loads `usound.sty` and `common.sty`, then, on its
  nonzero setup branch, calls the helper with the packaged `usound.drv`
  name at runtime address `0x4009502c` and handles `install_err` at
  `0x40095038`. This proves an application-side conditional driver-install
  path. It does not identify the helper's full ABI and does not yet prove
  that PCM samples are handed to the driver.
- V SDK has no usound. APP_ID_UDISK=0x12 in SDK (case_type.h:55); config_main.c:80-95 MSG_USB_STICK -> gui_usbconnect -> create APP_ID_UDISK (online_device==0) else MTP.
- V manager.ap name table 12-B entries at 0x2634: music0 browser1 record2 radio3 setting4 user1 user2 linein7 manager8 mainmenu9 playlist10 config11 udisk12 mengine13 fmengine14 alarm15 mtp16 upgrade17 usound18 (0x270c). manager FUN_7f0d6200 (manager_community.c:231) accepts app ids <0x13. H: id==index, so usound=0x12, udisk=0xc, mtp=0x10 (consistent with config values below).
- V config.ap FUN_40054c00 (config_community.c:55-98), msg 0x90 case: if (*0x9fc155d4==1) data0=0x12 (usound); else if (byte(*0x9fc15654+0xf)==0) data0=0xc (udisk); else 0x10 (mtp); then sends msg 0x201 {data0,param 1}. Pool at file 0x14b4 (addr = file+0x40053800).
- V Flag 0x9fc155d4 written once in FUN_40054ccc init (config_community.c:134-137): *flag = get_config(0x116). Only config.ap references that RAM address (0x14bc,0x16bc). config.bin id 278 entry (offset 0xe4a) = u16 (0,0,1,1) (community==stock); H: first u16 = default 0, so flag=0 -> usound branch dead by default; H: setting config id 278 default to 1 would make USB cable plug launch usound.ap (and skip udisk) - untested, and it is a config.bin change, no UI.
- The host selector model in `tools/sim/usb_mode.py` mirrors this exact branch: config item `0x116 == 1` selects `usound` before the online-device check; otherwise the normalized online-device state selects `udisk` or `mtp`. It is intentionally not a flash patch and does not claim that the M30 connector exposes the required USB device/VBUS path.
- `tools/emu/usound_dac_link_probe.py` adds a read-only cross-check of the next boundary. Across the six local `usound.drv` members there is no direct pointer into the separate `drv_dac.drv` resident range (`0xbfc18d00..0xbfc194ff`); the USB member instead retains the observed `0xbfc326a9` callback and `0xc0080084`/`0xc0080088` word-port pool. This is useful negative evidence only: an indirect resident callback or hardware DMA path could still connect USB samples to playback, so a config-only USB Audio switch is not yet a proven DAC-output feature.
- V No string "usound" in config/mainmenu/setting/music/udisk .ap; only manager.ap (0x270c). usound.ap loads usound.sty/common.sty/usound.drv (usound.ap 0x1114..). MAINMENU_AP_ID_ARRAY (config.bin id 1) = (1,5,0,1,2,3,4) -> no usound entry.
- The AP probe maps the packaged names more precisely: file `0x1114/0x1120/0x112c` maps to runtime `0x40095014/0x40095020/0x4009502c` in the `0x40094c00` bank. The setup branch is conditional; its condition and the subsequent PCM transfer ABI remain unresolved.
- The `usound.ap` PCM boundary remains unresolved: `FUN_400950c0` is an
  event/message loop, while `FUN_40095088` and `FUN_40095228` do not expose a
  direct sample-count/DMA handoff; `FUN_40095228` also crosses unresolved
  instructions around `0x40095246`/`0x4009524c`.
- A separate, stronger driver-side fact is now verified in `usound.drv`:
  MIPS16 function `FUN_bfc31654` copies from a 0x1000-byte circular
  region, splits a wrap into two callback copies, advances a read pointer, and
  tracks repeated insufficient-data events (reset after 100). This is a
  stream-buffer-shaped ABI. Its literal pool resolves the state to ring base
  `0x9fc34000`, read pointer `0x9fc33dec`, available-byte counter `0x9fc33df0`,
  short-read counter `0x9fc33df4`, reset signal `0x9fc33e13`, and callback entry
  `0xbfc326a9` (odd MIPS16 pointer). The aligned callback entry at
  `0xbfc326a8` is the MIPS16 pair `li v1,0x10; break 0`; the adjacent
  `0xbfc326ac` pair uses selector `0x0f`. A QEMU exception-vector probe
  executes the `0x10` target across all six local corpora and verifies that
  the ring consumer's four arguments survive the trap boundary. This resolves
  the callback's syscall envelope, not the kernel service or PCM ownership;
  the host emulator therefore models the ring only as an explicitly generic
  boundary, not as the firmware's PCM/DMA implementation.
- `tools/sim/usound_callback.py` now mirrors the proven part of that boundary:
  it records the selector and four trapped arguments, counts selector `0x10`,
  and refuses to execute either the fixed-ROM service or an unknown selector.
  This is a host observation model, not a PCM/DAC implementation.
- The callback QEMU probe now records the CP0 exception envelope as well as the
  arguments. The current run reports exception code `9` (breakpoint),
  `EPC=0x800526ab` (the relocated odd MIPS16 callback entry), `BadVAddr=0`,
  and `Status=0x2`, then returns through the interrupted continuation. This
  proves that the synthetic vector receives a genuine MIPS breakpoint trap;
  it does not identify the unavailable fixed-ROM service that the stock vector
  would invoke. Re-run it with `bash tools/emu/run_qemu_usound_callback_probe.sh`.
- `m30_preview_session.py` can now carry an explicitly supplied exception frame
  into its JSON trace with `--callback-exception CODE EPC BADVADDR STATUS`.
  The values are optional and the field is omitted when no context is supplied.
  The trace labels its input as caller-provided; the preview does not synthesize
  CP0 state or execute the missing fixed-ROM service. An optional
  `--callback-ra` adds a separately labeled `ker_xsys_entry_candidate` with
  the proven EPC/RA stores and jump target. This candidate does not claim the
  captured callback traversed that entry unless runtime evidence supplies the
  connection.
- `tools/emu/m30_preview_session.py` composes this callback observation with
  the real-resource now-playing renderer, recovered LCD command sink, and the
  bounded 200-byte USB-audio stream. Its JSON trace explicitly labels the
  session as hybrid and keeps the fixed-ROM callback effect unexecuted; the
  `--submit-packet` input is a framing test, not a claim of audible playback.
- A second driver boundary is also verified: `FUN_bfc318cc` transfers whole
  words through MMIO data port `0xc0080084` (mode 2 read, mode 1 write) or
  alternate port `0xc0080088` (mode 4 read), gated by `0x9fc33e12`. Its caller
  `FUN_bfc30dc4` prepares the 0x1000-byte scratch area before this transfer and
  then feeds a separate 0x6e40-byte software-ring path. The host model exposes
  only the observed word-port modes; it does not assign USB or PCM semantics to
  these registers.
- The two software-ring copy helpers are now distinguished: `FUN_bfc30cac`
  copies bytes directly, while `FUN_bfc30ce8` consumes complete 3-byte groups
  and emits `[0, b0, b1, b2]` 4-byte groups. The caller's format-1 size
  arithmetic is `byte_count * 4 / 3`; other formats use the direct byte count.
  This is an evidence-backed format boundary, not yet a claim about sample
  encoding or USB endpoint ownership.
- The producer-side software ring is now modeled separately at capacity
  `0x6e40`: write position `0x9fc33de8`, available count `0x9fc33df0`, direct
  ready threshold `0x3720`, expanded-format threshold `0x1b90`, and the
  observed overrun rule `available > capacity -> available = wrapped write
  position`. The host model covers direct and wrapped writes plus the
  format-specific ready edge; hardware FIFO timing and the downstream reader
  remain outside the model.
- `tools/emu/run_qemu_usound_chain_probe.sh` composes the two real driver
  functions in one guest using the producer's 16-byte output as the consumer's
  shared ring input. All six local corpora pass: producer state reaches 16,
  `FUN_bfc31654` returns 16 and drains its consumer state, and the real
  selector-`0x10` callback traps once. This is byte/state-level composition
  evidence only; it does not identify the stock callback's kernel service,
  PCM ownership, USB interrupt path, or DAC routing.
- uhost.drv (9216 B): V 6 aligned literals "USBC" (CBW sig 0x43425355) at 0xa08,0xd44,0xed0,0x18bc,0x1984,0x1ad0, no "USBS"; Ghidra also shows SCSI READ(10)/WRITE(10) and 512-byte transfers. It is therefore the Bulk-Only-Transport mass-storage host path (USB flash), not evidence of USB Audio host support. V referenced by config/mainmenu/music/setting .ap.

## Product-documentation cross-check

The available M30 user manual describes the USB port as Micro-USB 2.0 and
documents computer charging/data transfer, while listing the 3.5 mm headphone
and line outputs as the audio outputs. It does not advertise USB Audio or OTG:
[M30 manual](https://manuals.plus/mechen/m30-hifi-player-manual). This is
consumer documentation rather than a board schematic, so it cannot disprove
the hidden `usound` path recovered from the firmware. It does lower confidence
that the retail hardware exposes the required USB device/VBUS wiring; a
config-only experiment should therefore remain unflashed until a reversible
USB-enumeration test is available.
