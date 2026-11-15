<!-- Statik analiz bulgusu (cihazda test edilmedi). Alt ajan çıktısı; ana oturum aşağıdaki noktaları baytlardan doğruladı: mengine.ap EQ tablosu/frekanslar/sıfır alanı, setting.ap tablosu/sıfır alanı, config.bin öğe 0x116 baytları. Diğer iddialar ajanın okumasına dayanır; VERIFIED/V = dump veya baytta okundu, HYPOTHESIS/H = çıkarım. Kaynak dosya: m30-work/findings/eq_usound.md. -->

# EQ + usound findings (read-only; V=VERIFIED, H=HYPOTHESIS)

## A. EQ
- Reproducible check: `bash tools/ghidra/run_eq_probe.sh` decompiles the
  community `mengine.ap` EQ loader and checks its pointer pool, seven-band
  frequency table, gain rows, and the `setting.ap` Custom row. It is a static
  AP/raw-byte check and does not validate audible output.
- V SDK: ap/ap_setting/menu_callback_sound_setting.c: eq_param[8][MAX_EQ_SEG] int8 (none,rock,funk,hiphop,jazz,classic,techno,custom); _set_real_eq() builds mmm_mp_eq_info_t{eq_type, eq_para[12]} and sends MSG_MENGINE_SET_EQ_SYNC (music_set_eq, line 81-88). Engine: mengine_event_volume.c mengine_set_real_eq() -> mmm_mp_cmd(MMM_MP_SET_EQ,&eq_info). Custom = g_setting_vars.music_comval.eq_parameter[12] (int8, setting_common.h:167), edited in music_setmenu_soundset_param.c. EQ_TOTAL=8 (ap_setting.h:27) incl. Off. config.txt SETTING_AP_ID_EQ_SETTING = 0[0..7].
- V Table A (setting.ap, community==stock): file 0x5a94..0x5b13, 8 rows x 16 B (12 int8 used + 4 pad; rock row 0x5aa4, funk 0x5ab4, hiphop 0x5ac4, jazz 0x5ad4, classic 0x5ae4, techno 0x5af4, custom 0x5b04 = {-9,0,0,0,0,0,6}). Zeros 0x5b14..0x5bff (236 B) then next sector at 0x5c00.
- V Table B (mengine.ap, same in stock): presets at 0x440c.. 7 B/row (7 int8 gains, row index = preset): none 0x440c, rock 0x4413, funk 0x441a, hiphop 0x4421, jazz 0x4428, classic 0x442f, techno 0x4436 (=7 rows, idx 0..6). Row values = first 7 bytes of SDK rows. Band centre freqs u16 at 0x43ec (80,200,480,980,4000,8000,16000 Hz), per-band u16 at 0x43fc (10,6,4,6,10,5,8; likely Q x10, H). Pointer pool file 0x41f4 = {0x601d10ec, 0x601d10fc, 0x9fc1a19c(RAM custom), 0x601d110c}; file = addr - 0x601ccd00.
- V Code: mengine.ap FUN_601d0d58 (mengine_community.c:1717-1790): idx=*(byte*)(g+0x41); loop 7 bands: freq,Q, gain = (idx==7 ? custom[b] : table[idx*7+b]) * 10 (0.1 dB units), flag 1; bands 7..15 zeroed; struct 0xf0 B (16 bands x 8 B) sent to DSP. So 7-band parametric EQ, int8 dB gains, custom = idx 7 read from RAM 0x9fc1a19c (not in table).
- V Free space: mengine.ap zeros 0x443d..0x47ff (0x443d-0x4443 would be a would-be 8th row; 956 B to 0x4800 sector end, but 0x4600 is also a sector edge -> 0x4600..0x47ff may be bank padding). setting.ap 236 B after table.
- V/H Extra presets: `run_eq_probe.sh` confirms `FUN_601d0d58` has a seven-iteration loop, uses `idx * 7` for non-Custom rows, and branches only on `idx == 7` to the Custom RAM pointer. No index clamp or default case is visible in this function. The UI count remains `EQ_TOTAL=8`; setting.ap table and music/setting menu strings/.mcg trees are separate. Adding presets therefore needs a code patch (new index mapping and bounds behavior) plus menu tree/sty edits. Not checked: music.mcg/setting.mcg node count, which AP writes `g+0x41` (H: copy of eq_type from SET_EQ msg).
- `run_eq_writer_probe.sh` performs a separate Ghidra instruction scan over `setting.ap`, `music.ap`, and `mengine.ap`. It finds no decoded direct `sb/sh/sw` store using an immediate `0x41` (or `0x141`) offset. This is a negative boundary result, not proof that the selector is never written: the writer may copy a message/structure, use a register-derived offset, or live in a shared resident component. It is enough to reject a simple “patch the first `+0x41` store” approach.
- `run_eq_chain_probe.sh` closes the message-path gap. The public PD196 reference defines `MSG_MENGINE_SET_EQ_SYNC` as `MENGINE_BASE + 3 = 0x303`; in the M30 binary, `FUN_60090d64` dispatches `0x303` through the pool entry at `0x60091014` to `FUN_601d0f30`. That handler copies the message payload through the resident memory helper and calls the pool entry at `0x601d0f74`, whose raw value is `0x601d0d59` (the MIPS16 entry of `FUN_601d0d58`). The builder then reads the selector from `0x9fc15c88 + 0x41`, chooses Custom only for `idx == 7`, and builds the seven-band structure. The producer side is resolved by the companion `music.ap` probe below.
- `run_eq_producer_probe.sh` resolves that producer in `music.ap`: `FUN_403d4e20` forwards a two-byte `{eq_type, selector}` payload through `FUN_40614f08`, which sends message `0x303`. The wrappers emit `0,0` for Off and `7,1` through `7,6` for the six built-in presets. `FUN_403d4ed0` copies the seven custom gains and then emits `7,7`. This closes the selector-producer gap; adding a preset would require extending this dispatch/menu set and the engine's coefficient mapping, not merely editing the EQ table.
- `tools/emu/eq_menu_probe.py` verifies the menu-side pointer topology in stock, community, V1.101.11, and V1.101.12: the seven built-in callback entry points occur once each in the `music.ap` table at file `0xdeec..0xdf64` with `0x14` (20-byte) spacing, and three repeated groups in `music.mcg` reference the same seven pointers at `0x2fea`, `0x3554`, and `0x3b90` with `0x2a` (42-byte) spacing. The Custom callback `FUN_403d4ed0` has no direct MCG pointer; its separate parameter-copy path is consistent with the producer decompilation. The probe deliberately does not assign language meaning to the three MCG groups.
- `tools/sim/m30_model.py` now keeps an evidence-backed `FIRMWARE_EQ_PRESETS` contract separate from the older five-band UI proposal. It models the seven recovered centre frequencies, Q values, exact selector payloads (`Off = {0,0}`, built-ins `{7,1..6}`, `Custom = {7,7}`), and the seven signed-int8 gain rows. Custom curves require seven explicit values; the model does not silently treat the proposed UI curves as device coefficients.
- `tools/emu/eq_binary_probe.py` cross-checks that contract against raw bytes: `mengine.ap` frequency/Q tables and all seven non-Custom gain rows, plus the default seven-value Custom row at `setting.ap` `0x5b04`. It passes against the four local firmware corpora, so the host model is now tied to binary evidence rather than duplicated documentation alone.
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
- V The extracted `usound.drv` is byte-identical across the six local
  corpora (`community`, `first-pass-verify`, `stock`, `v1.101.11`,
  `v1.101.12`, and `v5`; SHA-256
  `e593bdd29c2a96d4d745cf1b5cae4da2ee71c2211c551e415209b18f54e600fc`).
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
  `0xbfc326a9` (odd MIPS16 pointer). The adjacent aligned stubs at
  `0xbfc32680` and `0xbfc32694` decompile to zero-return functions, while the
  odd target's callback semantics remain unresolved. Its producer and PCM
  ownership are not proven;
  the host emulator therefore models the ring only as an explicitly generic
  boundary, not as the firmware's PCM/DMA implementation.
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
- uhost.drv (9216 B): V 6 aligned literals "USBC" (CBW sig 0x43425355) at 0xa08,0xd44,0xed0,0x18bc,0x1984,0x1ad0, no "USBS"; Ghidra also shows SCSI READ(10)/WRITE(10) and 512-byte transfers. It is therefore the Bulk-Only-Transport mass-storage host path (USB flash), not evidence of USB Audio host support. V referenced by config/mainmenu/music/setting .ap.
