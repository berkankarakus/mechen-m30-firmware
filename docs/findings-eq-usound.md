<!-- Statik analiz bulgusu (cihazda test edilmedi). Alt ajan çıktısı; ana oturum mengine.ap EQ tablosu/frekanslar/sıfır alanı, setting.ap tablosu/sıfır alanı, config.bin öğe 0x116 baytları ve config.ap Custom-buffer başlangıç/kapanış yolunu ayrıca doğruladı. VERIFIED/V = dump veya baytta okundu, HYPOTHESIS/H = çıkarım. Kaynak dosya: m30-work/findings/eq_usound.md. -->

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
- A Ghidra 12.2 `LoadAP` scan mapped this table to VA `0x40255294` and checked raw pointer literals plus Ghidra references to all eight row starts (`0x40255294..0x40255304`, stride `0x10`): zero hits. This finds no direct row reader in the loaded `setting.ap` banks. It does not prove the table is dead; a computed address, generic settings reader, or shared resident path could still consume it. The initial `0x38`-byte state initializer separately leaves its own Custom buffer (`+0x2c..+0x32`) untouched.
- V Table B (mengine.ap, same in stock): presets at 0x440c.., 7 B/row (7 signed-int8 gain values; row index is preset): Off 0x440c, Rock 0x4413, Funk 0x441a, Hip hop 0x4421, Jazz 0x4428, Classical 0x442f, Techno 0x4436 (selector 0..6). Frequencies are u16 values at 0x43ec (80,200,480,980,4000,8000,16000 Hz); Q values are raw u16s at 0x43fc (10,6,4,6,10,5,8). Calling those Q×10 is a hypothesis; the binary establishes the stored values only. Pointer pool file 0x41f4 = {0x601d10ec, 0x601d10fc, 0x9fc1a19c (RAM custom), 0x601d110c}; file = VA - 0x601ccd00.
- Corpus comparison: the 49-byte block `0x440c..0x443c` is byte-identical in the available stock, official, community, and derived firmware copies. Interpreted as signed int8, the rows are Off `(0,0,0,0,0,0,0)`, Rock `(5,3,0,-1,0,4,5)`, Funk `(3,0,0,0,0,-1,-2)`, Hip-hop `(0,0,1,2,0,1,1)`, Jazz `(3,0,0,-1,0,2,4)`, Classical `(0,0,0,-1,-1,-2,-4)`, and Techno `(5,2,0,0,0,0,6)`. Values span -4..+6. The following bytes through `0x47ff` are zero in those copies, but this alone does not prove they are available patch space.
- V `FUN_601d0d58` selects one 7-byte table row, or selector 7's seven RAM bytes at `0x9fc1a19c`, sign-extends each gain, multiplies by 10 and writes an s16 into each band. The ×10 conversion is verified; interpreting the result as 0.1 dB units is a strong inference, not a demonstrated DSP unit. Seven active bands use the eight-byte layout `{frequency u16, Q u16, gain s16, enable=1, reserved=0}` beginning at structure offset `0x10 + 8*i`.
- V Scratchpad MIPS16 p-code run of `FUN_601d0d58` used hash-verified stock and community `mengine.ap`; all 11 cases (selectors 0..7 with sentinel Custom, real Custom default, busy guard, and inactive guard) matched their byte expectations. It confirmed the argumentless entry, selector mirror at `0x9fc15db5`, active flag at `0x9fc15db4`, busy check at structure `+0x0c == 1`, and early return after mirroring the selector. In an active build, `+7=1`, `+0xd=(selector != 0)`, bands 0..6 are written, and bands 7..15 occupy and zero `0x48..0x8f`. Bytes `0x00..0x06`, `0x08..0x0b`, `0x0e..0x0f`, and `0x90..0xef` retain their initial `0xaa` values in the probe. The latter range is untouched, not the unused-band range.
- V The builder passes `{a1=0x9fc15dd4, a2=0xf0}` to the module `0x10` copy stub, then requests shared-memory id 3 with argument `0x49`, then invokes module `0x42` with command `0x1f`. The probe used a synthetic nonzero SHM handle; the message target value was zero because initialization was not run. These stub effects are not modeled as DSP behavior.
- V Free space: mengine.ap zeros 0x443d..0x47ff (0x443d-0x4443 would be a would-be 8th row; 956 B to 0x4800 sector end, but 0x4600 is also a sector edge -> 0x4600..0x47ff may be bank padding). setting.ap 236 B after table.
- V/H Extra presets: `run_eq_probe.sh` confirms `FUN_601d0d58` has a seven-iteration loop, uses `idx * 7` for non-Custom rows, and branches only on `idx == 7` to the Custom RAM pointer. No index clamp or default case is visible in this function. The UI count remains `EQ_TOTAL=8`; setting.ap table and music/setting menu strings/.mcg trees are separate. Adding presets therefore needs a code patch (new index mapping and bounds behavior) plus menu tree/sty edits. Not checked: music.mcg/setting.mcg node count, which AP writes `g+0x41` (H: copy of eq_type from SET_EQ msg).
- `run_eq_writer_probe.sh` performs a separate Ghidra instruction scan over `setting.ap`, `music.ap`, and `mengine.ap`. It finds no decoded direct `sb/sh/sw` store using an immediate `0x41` (or `0x141`) offset. This is a negative boundary result, not proof that the selector is never written: the writer may copy a message/structure, use a register-derived offset, or live in a shared resident component. It is enough to reject a simple “patch the first `+0x41` store” approach.
- `run_eq_chain_probe.sh` closes the message-path gap. The public PD196 reference defines `MSG_MENGINE_SET_EQ_SYNC` as `MENGINE_BASE + 3 = 0x303`; in the M30 binary, `FUN_60090d64` dispatches `0x303` through the pool entry at `0x60091014` to `FUN_601d0f30`. That handler copies the message payload through the resident memory helper and calls the pool entry at `0x601d0f74`, whose raw value is `0x601d0d59` (the MIPS16 entry of `FUN_601d0d58`). The builder then reads the selector from `0x9fc15c88 + 0x41`, chooses Custom only for `idx == 7`, and builds the seven-band structure. The producer side is resolved by the companion `music.ap` probe below.
- `run_eq_producer_probe.sh` resolves that producer in `music.ap`: `FUN_403d4e20` forwards a two-byte `{eq_type, selector}` payload through `FUN_40614f08`, which sends message `0x303`. The wrappers emit `0,0` for Off and `7,1` through `7,6` for the six built-in presets. `FUN_403d4ed0` copies the seven custom gains and then emits `7,7`. This closes the selector-producer gap; adding a preset would require extending this dispatch/menu set and the engine's coefficient mapping, not merely editing the EQ table.
- The menu-side static path is now traced: `FUN_40095130` calls `FUN_40094dd4`, which reads the selector byte at state `+0x19` and dispatches through `FUN_40094d4c`; its `case 7` calls `FUN_403d4ed0`. The callback then copies Custom gains and sends `{7,7}` through the already documented producer chain. Stock/community producer and engine probes pass. This proves what the dispatcher does when its selector is 7, but not that the MCG Custom row or framework callback sets that state byte to 7. The Custom UI callback is present in `music.mcg` as the MIPS16 pointer `0x40414c01` (`FUN_40414c00`) at file offsets `0x3110` and `0x367a` (community `music.mcg` SHA-256 `f1037bc1…d597c3`); the MCG does not point directly to the separate producer `FUN_403d4ed0`. The callback's `0x8000` event currently reaches the type-3 unsupported branch, so the selector-setting path remains unknown.
- A targeted follow-up traced the MCG Custom callback `FUN_40414c00` one step farther. It reads state bytes `0x9fc15706..0x9fc15707` through `FUN_48a94798`; when that helper returns `-0x7fef`, the handler sends message `0x8000` with `{3,5,0xffff,0x54,0x7e}` through `0x48ad47b1`. That target is in the shared `music.ap` bank, not fixed ROM. The next bullet traces this request into the target; the path still does not reach `FUN_403d4ed0` or establish a write of selector `7`.
- `bash tools/ghidra/run_eq_custom_event_probe.sh` now reproduces the callback-to-target edge from the hash-pinned community `music.ap`. The target at `0x48ad47b0` receives mode `0x8000` and the payload pointer; its decompile reads payload type `3`, then returns `-0x7fec` through the unsupported-type branch (the same return is used for type `4`). That path exits before its event loop and does not reach the Custom producer or a seven-byte gain write. This explains why the `0x8000` request does not close the slider path; the meaning of the error code and the real slider scene/callback remain unknown.
- `bash tools/ghidra/run_eq_custom_event_dynamic_probe.sh` now executes the actual `FUN_40414c00` callback and `FUN_48ad47b0` target in Ghidra p-code against hash-pinned community and V1.101.12 `music.ap` images. In both, the callback emits mode `0x8000` with `{type=3,id=5,0xffff,ptr}` and the pointed bytes `54 00 00 00 7e`; with the helper return injected as `-0x7fef` and all three resident `0xbfc16404` calls (call-site values `0x14`, `0x12`, and `9`) plus four shared-AP import stubs returning zero, the target returns low-16-bit `0x8014` (`-0x7fec`); the event-loop entry was not reached. The callback helper return `-0x7fef` is injected to reach this branch, and all memory is synthetic. This proves the branch behavior and payload under the injected precondition, not that the physical UI invokes it, that the selector is changed, or that Custom gains reach audio.
- Follow-up checked community `music.ap` SHA-256 `662e379602707a9c4b0dcd6b94b591dd77c2b5f7a557fcb03b8c2a5c9b1baac3` and found no additional literal references to `0x9fc15706` or `0x9fc15707` beyond the known Custom handler. The first p-code attempt failed during script loading; the checked-in dynamic probe now executes the callback and receiver on both hash-pinned images. The next useful action is to trace the framework callback registration and locate the code that writes selector `0x9fc1570d`, not repeat the pointer scan.
- `run_setting_confirm_probe.sh` reaches a generic `setting.ap` confirmation request (`0x100a`, payload `0x48554680`); it is not evidence for the Custom EQ slider's confirm/save callback. Do not use that probe to claim the slider-to-persistence path is closed.
- The Custom producer's actual source is the `music.ap` pointer literal at file `0x86f8` / VA `0x403d4ef8`, whose baseline value is `0x9fc15720`; the function copies seven bytes through it into the engine-facing Custom buffer at `0x9fc1a19c` before sending `{7,7}`. Correction: `0x9fc15720` is **not** the `+0x20` field of the `0xf0`-byte block at `0x9fc15700`. Each overlay reads/writes its own `0x38`-byte persistent block (id `0`, length `0x38`, read op `0x12`, write op `0x13`) and takes its seven-byte Custom source from block offset `+0x2c`:

  | Overlay | Block base | Custom bytes (`base + 0x2c`) | Pool file offset | Reported write helper(s) |
  |---|---:|---:|---:|---|
  | `music.ap` | `0x9fc156f4` | `0x9fc15720` | `0x14cc` | `FUN_40054ce8`, `FUN_40294dc0` |
  | `config.ap` | `0x9fc15654` | `0x9fc15680` | `0x1694` | `FUN_40054f38`, `FUN_40054f84` |
  | `mainmenu.ap` | `0x9fc155f4` | `0x9fc15620` | `0x1490` | `FUN_40014d74`, `FUN_40014fac` |
  | `setting.ap` | `0x9fc15408` | `0x9fc15434` | `0x1548` | `FUN_40055200`, `FUN_402550b4` |

  Pool words were checked directly in this session; the per-overlay read/write call chains and negative writer scan are from the Ghidra report and have not been independently rerun here. Each helper uses the same persistent API shape: `(base, id=0, length=0x38, op=0x12/0x13)`. `setting.ap`'s `FUN_402550b4` sends message `0x8001`, writes its block, then sets flag `0x57` before the exit loop; interpreting this as menu-exit persistence is an inference. In `music.ap`, the selector byte is at block `+0x19`. `config.ap` copies its block's `+0x2c` bytes to the engine-facing buffer `0x9fc1a19c` during startup. The separate `0xf0`-byte config block at `0x9fc15700` is not established as EQ storage. The `music.ap` patch redirects the `0x9fc15720` source to its fixed seven-byte curve at file `0x8700` / VA `0x403d4f00`, so it bypasses that stored source on the patched producer path. The probe checks the pointer and curve; it does not establish that the Custom menu dispatch reaches the callback or that the curve affects audible output.
- `tools/ghidra/run_config_eq_state_probe.sh` checks the `config.ap` startup/exit call chain against SHA-256 `5b5687c0…56357580` and executes the default helper in p-code. `FUN_40054ccc` reads a `0x38`-byte block at `0x9fc15654` and a separate `0xf0`-byte block at `0x9fc15700`, applies their magic/default handling, then copies seven bytes from `0x9fc15680` to `0x9fc1a19c`. `FUN_40054f38` issues the corresponding writes for both blocks. Its cold/invalid `0x38`-byte-block path clears the block and calls `FUN_40dd4c00`; the real helper was run in Ghidra p-code with a sentinel tail and left `+0x2c..+0x32` untouched. Combining that result with the caller's clear-and-copy sequence means the first seven bytes copied to the engine Custom buffer are zero when the persistent block is invalid. This establishes the cold-start buffer value, but not which M30 UI callback later changes any overlay's `+0x2c` source.
- The selector state used by the menu dispatcher is based at `0x9fc156f4`; its `+0x19` byte is `0x9fc1570d`. `FUN_40094dd4` reads it, and value 7 dispatches to `FUN_403d4ed0`, which sends `{7,7}`. The `0x3301` AP row maps to `FUN_40414c00` at file `0xdf78` / VA `0x406d5178` in stock, community, V1.101.11, V1.101.12, and V5 images. This callback sends the scene/event request but does not write the selector byte. The code that sets `0x9fc1570d` to 7 remains unresolved.
- The slider writer remains unresolved. The reported scan found no direct literal store to the four `base+0x2c` source ranges (apart from copies), and no decompiled seven-value edit loop. The `music.ap` Custom menu entry (`id 0x3301`) starts another scene by sending message `0x8000` with `{3,5,0xffff,{0x54,0x7e}}`; it does not edit the gains there. The preset callbacks send `{7,i}` for `i=1..6`; `FUN_403d4ed0` has no known menu-table caller. `mainmenu.ap` also copies its block's `+0x2c` values into the engine buffer. Thus the actual slider scene/callback, its write timing, and the path that sets the Custom selector are still unknown. The new dynamic probe validates the callback branch and receiver return under injected helper/service behavior, but does not close these caller/state gaps.
- The earlier PD196 analogy that labeled block `+0x2c` as SRS is not evidence about M30. The four M30 overlay paths independently use their own block `+0x2c` as the seven-byte Custom source; the semantic name and UI writer for each block remain unresolved.
- The experimental V1.292 candidate combines this Custom source pointer and gain curve with the shared directory marquee timer changed from 80 ms to 50 ms. The initial curve `(4,3,0,-1,1,2,1)` was reported as too subtle, so the current curve is `(6,5,0,-2,0,4,3)`, a bass-forward shape within the corpus-wide observed gain envelope `-4..+6`. The bands are 80, 200, 480, 980, 4000, 8000, and 16000 Hz. This does not assign dB units or prove audibility. The candidate's member-level and full encrypted-HEX round-trip checks verify that only `music.ap` and `browser.ap` differ; `config.ap`, `config.bin`, and saved-settings member bytes remain identical. See [`release-candidate.md`](release-candidate.md#custom-eq--50-ms-experiment). Device execution is still required to establish behavior.
- `tools/emu/eq_menu_probe.py` verifies the menu-side pointer topology in stock, community, V1.101.11, and V1.101.12: the seven built-in callback entry points occur once each in the `music.ap` table at file `0xdeec..0xdf64` with `0x14` (20-byte) spacing, and three repeated groups in `music.mcg` reference the same seven pointers at `0x2fea`, `0x3554`, and `0x3b90` with `0x2a` (42-byte) spacing. The producer `FUN_403d4ed0` has no direct MCG pointer; the Custom UI callback is the separate `FUN_40414c00` entry at offsets `0x3110` and `0x367a`. The probe deliberately does not assign language meaning to the three built-in MCG groups.
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
  `a0=1` is the EQ/DAE payload by call shape; the aud_dev target below now
  supplies matching consumer evidence, while the ROM op-dispatch mapping is
  still an inference.
  `mmm_pp.al` directly reads only SHM byte `+2`, selecting `adppext.dsp` when
  zero and `audiopp.dsp` when nonzero; it does not directly inspect the band
  range `+0x10..+0x8f` itself. The bank-5 routine reached by table entry 18
  reads sixteen 8-byte band slots from that range under its `a0=1` path. The
  actual ROM rule that maps op `0x12` to table entry 18 remains unverified.
- V `config.ap` sets SHM byte `+2` and `+3` from an object flag before creating
  `dae_cfg`; the flag's meaning is unknown. This gives a concrete DSP-selection
  boundary, not proof that a particular EQ curve reaches or changes audible
  output.
- V `aud_dev.drv` has two nonempty YQHX segments: the resident module stubs at
  file `0x300` (8 bytes → `0xbfc09f58`) and the 21-word table at file `0x200`
  (`0x54` bytes → `0x9fc09f00`). Table entry 18 is `0x2c149401`; the static
  far-pointer/file correlation associates it with bank 5, candidate MIPS16
  address `0x9400`, file `0x1f00`. The generic bank-table assumptions in
  `inspect_drv.py` and `run_auddev_bank_probe.sh` do not validate this loader
  mapping. The reported static Ghidra analysis of the candidate bytes shows
  an `a0=1` path that reads sixteen 8-byte bands from the shared-memory pointer
  and applies per-band adjustments. Treat the code interpretation as static
  evidence and the bank-to-file execution mapping as a candidate. The
  table-index-equals-op relationship remains a strong inference because the
  fixed-ROM dispatcher is unavailable; neither point proves audible DSP effect.
- The reported static disassembly says the `id=1` path iterates over 16
  records and calls an indirect helper at `0x98fc` with source
  `param_2 + 0x10 + 8*i`, destination `_UNK_98f8 + 0x94 + 8*i`, length 8, and
  flag 0. This shape is consistent with copying engine band records into an
  audio-device working structure. No device execution or hardware/DSP effect
  was tested; do not treat this copy boundary as proof of playback.
- Device feedback for the experimental V1.292 Custom-curve/50 ms candidate:
  the user reported no audible difference between `Custom` and `Off`; a
  supplied EQ-screen photo shows all seven displayed sliders at the 0 dB
  line. The exact listening conditions and a controlled built-in-preset
  comparison were not recorded. The image patch redirects the music producer's
  source pointer but does not change the separate settings/UI data path, so
  flat displayed sliders are compatible with the patched producer sending a
  different fixed curve. The exact `music.ap` on the device was not identified
  by a member hash or by reading file offset `0x86f8`; the report therefore
  does not establish whether the patched producer was active. It also does not
  establish whether its coefficients reached the audible output.
  Treat the device result as a negative report, not a verified DSP failure;
  resolve the message-to-aud_dev/DSP/hardware path before tuning gains again.
- Cheapest device-side discriminator: read `music.ap` at file offset `0x86f8`.
  `20 57 c1 9f` is the stock source pointer; `00 4f 3d 40` points to the
  experimental in-bank fixed curve. The current producer p-code probe starts
  at `FUN_403d4ed0` directly, so it validates the callback boundary but not
  whether selecting Custom in the menu reaches that callback.
- Data-only preset tuning is the lowest-risk firmware experiment currently
  identified, but it is not validated as safe. Existing gain values are signed
  bytes and the builder scales them by 10; interpreting them as dB is an
  inference. The experimental Custom curve was packaged and reportedly tried,
  but produced no perceived difference from Off; its test conditions are not
  sufficiently controlled to locate the failure. Do not tune another curve
  before resolving the producer-to-audio-consumer path. The Q table's physical
  units and the DSP's clipping limits remain unknown. The 50 Hz first-band
  value in the 2024-04-24 image proves that value was shipped in that image,
  not that it is safe on another revision or hardware path.
- V Negative corpus scan: the module 0x42 stub, command 0x1f, and EQ shared
  structure references are present in `mengine.ap`; the code that receives
  module 0x42 is absent from the scanned AP/driver/DSP corpus and is expected
  in fixed ROM or another unavailable component. `coeffi.bin` uses a separate
  six-block loader (six blocks of 0x1a00 bytes); the EQ builder does not refer
  to it, and the EQ frequency table was not found inside the DSP blobs. An EQ
  connection to `coeffi.bin` is therefore unproven. `audiopp.dsp` is listed
  for loading by `mmm_pp.al`, but that alone does not prove it consumes EQ data.
- V Independent Ghidra decompilation of `mmm_pp.al` (SHA-256
  `9a7a6c2215b2594e2ef816b8a3e592968921afff7747f3cadbd6e71bf74047d6`)
  confirms resident `FUN_bfc138c0` switches on its second argument. Case
  `0x11` calls banked `FUN_68013118` through the pointer at `0xbfc13a34`
  (`0x68013119`, MIPS16 entry); that handler calls module `0x0c`, op `0x12`,
  with `a0=1` and the object's `+0x9c` handle. Value `0x1f` is not a switch
  case and reaches the default error path. This rejects a direct
  `FUN_bfc138c0(event=0x1f) -> FUN_68013118` mapping. It does not establish
  whether module `0x42` command `0x1f` is translated into another application
  event or handled outside `mmm_pp.al`; the command receiver remains unknown.
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
  isochronous OUT `0x01` with a 200-byte maximum packet size; the HID endpoint is interrupt
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
- V The fourth YQHX descriptor maps file `0x2900..0x2a53` to
  `0x9fc33c00..0x9fc33d53`. Its first 77 words are descriptor/config data;
  the final eight words at file `0x2a34` are code pointers
  `bfc3154d,bfc315f9,bfc31615,bfc31629,bfc31655,bfc31741,bfc31755,bfc318b9`.
  `usound_operation_table_probe.py` hash-checks this tail. Calls from
  `usound.ap` use module 5 op 3 with scalar index, buffer, and fixed lengths;
  the op-3 pointer at `bfc31629` reaches the parameter setter at `bfc31de8`.
  Direct indexing as `table[op]` is consistent with this and the independent
  `aud_dev.drv` call shapes, but the fixed-ROM dispatcher is unavailable, so
  the host candidate resolver marks this rule as an inference and never calls
  the candidate entry.
- A scratchpad Ghidra MIPS16 p-code run executed the real
  `FUN_bfc303c4` request handler with the `0xc0080000..0xc00803ff` MMIO window
  represented as zeroed RAM. It confirms the request-state behavior under
  those modeled registers: SET_CUR frequency writes the supplied 3-byte rate
  to `0x9fc33c00`, while GET_CUR frequency always returns the descriptor bytes
  at `0x9fc33ca3`, even after SET_CUR stores another requested rate.
  `SET_INTERFACE` resets the ring only for `bRequest=0x0b`, `wValue=1`, and
  `wIndex=1`; other alternate values are ACKed without resetting it. The run also exercises mute/volume
  GET/SET, HID idle, descriptor lookup, IN packet chunking, and the observed
  ACK/stall register writes. MMIO status transitions and real USB timing were
  not modeled, so these are software-handler results, not a device USB test.
- `tools/ghidra/run_usound_interface_probe.sh` now replays the real
  `SET_INTERFACE` handler from the hash-locked `usound.drv` in Ghidra p-code.
  With synthetic MMIO, alternate setting 1 clears the producer/consumer
  offsets, queued-byte count, and reset signal; alternate setting 0 is ACKed
  while those state fields retain their sentinels. This is a narrow
  reproducible part of the broader scratchpad EP0 run, not a USB-controller
  or hardware timing model.
- The same hash-locked p-code probe also runs Feature Unit `GET_MIN`, `GET_MAX`,
  and `GET_RES` (`bRequest` `0x82`, `0x83`, and `0x84`). It checks the returned
  two-byte values `0xe3a0`, `0xfff0`, and `0x0030`, the two-byte transfer length,
  and the ACK bit. `tools/sim/usb_audio.py` exposes this fixed observed mapping;
  the host model does not claim to emulate setup-packet routing or USB I/O.
- The tracked probe also round-trips five current controls through the real
  `FUN_bfc303c4` code: mute for entities `0x09` and `0x0b`, and master/left/right
  volume for entity `0x09`. Each SET_CUR payload is checked at its recovered RAM
  address, then GET_CUR must return the same bytes. The host model stores only
  these observed entity/selector slots and leaves their initial values unknown.
- The descriptor patcher's firmware-info path now has a tracked p-code case.
  The first module `0x1b` call is `(buffer, 0x4f, 1)`; its status is read from
  the output buffer, not `v0`. With status byte `0x02`, the real code calls
  `(0x9fc33d12, 0x50, 0x10)`. Supplying `M30-SERIAL-12345` there produces a
  34-byte USB string descriptor at `0x9fc33d10` (`0x22`, type `3`, UTF-16LE).
  With status `0`, the second call is skipped and the original serial index and
  descriptor bytes remain unchanged. With status `2` and sixteen zero bytes,
  the serial index is cleared and the in-place serial payload becomes zero;
  the existing `0x12, 0x03` descriptor prefix remains. These are synthetic ROM
  responses, so the real device status and serial value remain unknown.
- `tools/sim/usb_audio_stream.py::UsbAudioStream.set_interface()` carries that
  result into the host stream model. It resets the corresponding offsets,
  available-byte count, and reset signal for alternate setting 1, while
  preserving PCM storage and the short-read counter. Other alternate settings
  for interface 1 leave the stream state unchanged; other interfaces remain
  unmodeled.
- `tools/sim/usb_audio.py::patch_usound_descriptors()` now models the verified
  descriptor writes. Its hash-checked reproduction command is
  `python3 tools/emu/usound_descriptor_patch_probe.py
  analysis/community/fw/usound.drv analysis/community/fw/config.bin`. It
  produces VID/PID `10d6:dd01`, `M30`/`USB AUDIO` strings, interface count 3,
  16-bit/48 kHz fields and a 200-byte packet maximum from the stock config values.
  Unit cases also cover empty ID overrides, empty strings, interface flag 0,
  and item `0x115=1` selecting 24-bit/96 kHz. Item `0x116` remains the separate
  app-mode selector and is not consumed by the descriptor patch.
- `tools/ghidra/run_usound_descriptor_patch_probe.sh` now executes the real
  MIPS16 `FUN_bfc31f94` against four synthetic config sets, with the
  `usound.drv` SHA-256 pinned to `e593bdd2…e600fc`. It checks VID/PID, both
  generated UTF-16LE string descriptors, interface count, bit depth, sample
  rate, and endpoint packet size for stock values, 24-bit/96 kHz, a cleared
  interface flag, and empty VID/PID/string values. Only the ROM copy and
  firmware-info calls are stubbed; configuration values are synthetic, so
  this validates the patcher's writes rather than ROM config-item retrieval.
- `RunUsoundInterfaceProbe.java` also runs the real `FUN_bfc303c4` SET_CUR /
  GET_CUR sample-rate path against the stock MIPS16 bytes. SET_CUR's three-byte
  OUT data comes from MMIO `0xc0080140`, is stored as the requested rate at
  `0x9fc33c00`, and sets the two observed state flags. GET_CUR returns the
  descriptor's rate bytes from `0x9fc33ca3` even after the request stored a
  different rate. Reproduce with `bash tools/ghidra/run_usound_interface_probe.sh`;
  the probe uses 32 kHz SET_CUR against a 48 kHz descriptor.
  `UsbAudioControlState` models this distinction. It does not model USB
  controller timing or prove that the hardware accepts the request.
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
- V Flag 0x9fc155d4 written once in FUN_40054ccc init (config_community.c:134-137): *flag = get_config(0x116). The exact 32-bit literal `0x9fc155d4` occurs in config.ap at file offsets 0x14bc and 0x16bc. `mainmenu.ap` separately loads base `0x9fc155d0` and accesses `+4` as a lookup-table count; that computed address is numerically the same byte but belongs to a different overlay structure (see address caveat below), not a proven read of config item 0x116. config.bin id 278 entry (offset 0xe4a) = u16 (0,0,1,1) (community==stock); H: first u16 = default 0, so flag=0 -> usound branch dead by default; H: setting config id 278 default to 1 would make USB cable plug launch usound.ap (and skip udisk) - untested, and it is a config.bin change, no UI.
- Independent Ghidra decompilation of the current community `config.ap` (SHA-256 `5b5687c0…7580`) confirms the `FUN_40054ccc` initializer and `FUN_40054c00` message-`0x90` branch: the latter reads the byte at `0x9fc155d4`; value 1 selects manager app id `0x12`, while other values use the online-state byte at `0x9fc15654+0x0f` to select `0x0c` or `0x10`, then emit message `0x201`. This verifies config-app routing logic only; it does not prove connector/VBUS behavior or that `usound.ap` reaches an audible hardware path.
- Address caveat: `mainmenu.ap` has a different overlay function at the same numeric VA `0x40054c00`. Its code interprets `0x9fc155d0` as a lookup-table header (reads a 16-bit count at `+4`, scans 16-bit entries from `+6`, with a limit of 7); that is not evidence that mainmenu consumes config item `0x116`. The overlays have separate code and state lifetimes, and no transfer of the config selector into this mainmenu table has been established.
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
  `0xbfc326ac` pair uses module `0x0f`. A QEMU exception-vector probe
  executes the `0x10` target across all six local corpora and verifies that
  the ring consumer's four arguments survive the trap boundary. This resolves
  the callback's syscall envelope, not the kernel service or PCM ownership;
  the host emulator therefore models the ring only as an explicitly generic
  boundary, not as the firmware's PCM/DMA implementation.
- `tools/sim/usound_callback.py` now mirrors the proven part of that boundary:
  it records the module ID and four trapped arguments, counts module `0x10`,
  and refuses to execute either the fixed-ROM service or an unknown module.
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
  position`. The producer sets the shared ready latch `0x9fc33e13` when the
  format-specific threshold is crossed. The host model covers direct and
  wrapped writes plus that ready edge; hardware FIFO timing and the downstream
  reader remain outside the model.
- A second p-code run executed `FUN_bfc3125c` against synthetic MMIO. It subtracts
  `0x3720` from the available count and ORs `0x404` into the DMA control word.
  A signed result below 1 takes the empty path, zeroes available, clears
  `0x9fc33e13`, and calls `FUN_bfc314e0`, which writes `0x80` to `0xc005001c`.
  The host state model now clears the same ready latch on this path, allowing a
  later threshold crossing to raise a new edge.
  The stop meaning is inferred from the nearby `dac_dma_stop1` string. For
  nonempty results it clears the
  low two clock-control bits below 4410, preserves them from 4410 through 9702,
  and sets both at 9703 or above. The function does not read the format flag;
  thresholds apply to the post-subtraction count. The host ring model now carries
  these transitions. MMIO was plain RAM and the ROM service was stubbed, so this
  verifies code branches and writes, not physical clock or DMA effects.
- Static MIPS16 analysis of `FUN_bfc30dc4` and `FUN_bfc312e0` now ties the
  producer to the DMA input: FIFO data is staged at `0x9fc34000`, copied into
  the `0x6e40`-byte ring at `0x9fc24000 + write_offset`, and the DMA address
  register `0xc00c0044` receives the ring base, never the staging address.
  The producer derives transfer length from USB length registers
  `0xc0080008/0xc0080009` and forwards that length to the FIFO/ring path; the
  examined code does not require every packet to equal the descriptor's
  200-byte maximum. The host packet model therefore accepts shorter complete
  audio frames up to that maximum. Actual short-packet delivery by the USB
  controller remains untested.
  `FUN_bfc312e0` writes channel control `0x4b03` and raw size `14112` for the
  direct format, or `0x8b03` and `7056` for format flag 1; both common control
  registers receive `|= 0x404`. The host model records these observed register
  values. DMA size units, hardware wrap behavior, and physical transfer effects
  remain unverified; this evidence is static disassembly, not a p-code run.
- `tools/emu/run_qemu_usound_chain_probe.sh` composes the two real driver
  control paths in one guest, but it deliberately relocates the distinct
  firmware ring literals (`0x9fc24000`, capacity `0x6e40`; `0x9fc34000`,
  capacity `0x1000`) onto the same QEMU base `0x80061000`. All six local
  corpora pass: producer state reaches 16, its real byte-copy helper writes a
  seeded `0x10..0x1f` pattern into the aliased ring, `FUN_bfc31654` returns 16,
  and the module-`0x10` break-0 call observes the same source address and
  sixteen bytes. The exception shim still does not copy into the consumer
  destination at `0x80065000`. This verifies data flow under an injected alias,
  not the firmware's natural ring connection, the fixed-ROM service, PCM
  ownership, USB interrupt path, or DAC routing.
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
