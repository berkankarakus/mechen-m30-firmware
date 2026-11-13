<!-- Statik analiz bulgusu (cihazda test edilmedi). Alt ajan çıktısı; ana oturum aşağıdaki noktaları baytlardan doğruladı: SDK'da LIST_ITEM_BUFFER_LEN=52, browser.ap slot 0x32, playlist.ap 0xa5ed ve browser.ap 0x46cc baytları. Diğer iddialar ajanın okumasına dayanır; VERIFIED/V = dump veya baytta okundu, HYPOTHESIS/H = çıkarım. Kaynak dosya: m30-work/findings/browser_names_sort.md. -->

# Browser list-name buffer and sort compare (M30, community V1.292.00)

Labels: VERIFIED = read in decompile/bytes. HYPOTHESIS = inferred.
Dumps: ghidra/browser_community.c (B), playlist_community.c (P), music_community.c (M).

## 1. List item name buffer

- VERIFIED: SDK has the constant. `PD196/case/inc/common_ui.h:32`: `#define LIST_ITEM_BUFFER_LEN 52`
  (GBK comment: "max string size of a list item, 52 bytes"). Unit = BYTES. Users: ap/common/common_ui/ui_directory.c:39
  (`g_list_buffer[LEN*(LIST_NUM_ONE_PAGE_MAX+1)]`), ui_directory_sub2.c:122-127 (init_directory_env), browser_scene_menu.c:397.
- VERIFIED: the firmware does NOT use 52. `FUN_48754574` (B:5158-5170; same in M:11730) is init_directory_env:
  `*(g_dir_browser+4) = 0x32; for i=1..7: slot[i].buf = i*0x32 + list_buffer; slot[i].len = 0x32`.
  So 8 slots (1 title + 7 items) x 50 bytes = 400 bytes. Stock and community bytes identical (file 0x19274 in browser.ap, bank 0x48754400 @ file 0x19100).
  g_dir_browser at 0x9fc15598 (len +4, buf +8), g_file_list at 0x9fc155a4 (stride 0xc). Literals read from file 0x193b8/0x193bc.
- VERIFIED: caller is gui_directory `FUN_40cd4e00` (B:1511-1560): calls init_directory_env as
  (dir_control=0x9fc15604, list_buffer=0x40cd4c00, path_info). Arg order matches SDK. Pointer to the function at file 0x12128.
- HYPOTHESIS: list buffer 0x40cd4c00 is a banked data page (512 bytes: 0x40cd4c00..0x40cd4e00, just below the code bank 0x40cd4e00).
  400 bytes of it are the buffer; listbox_data likely shares it, so growth beyond 512/8=64 per slot is impossible without moving it.
- Truncation, directory mode (fsel type 0): VERIFIED `FUN_71352820` (B:11883): per item it calls kernel fs op 2 with
  length `name_len >> 1` (= 25 UTF-16 units), then `FUN_71352ab0` (B:12004, 8.3 name -> "NAME.EXT" when no FF FE BOM).
  Max visible name: 25 units incl. BOM and terminator, so about 23-24 chars (HYPOTHESIS for exact count; kernel op 2 not in any dump).
- Truncation, library mode (fsel type 1): VERIFIED community `FUN_714d2658` (B:13681; copy at ~13790) copies `name_len-2` = 48 bytes
  from the record title (record+0, 64-byte field, FF FE BOM + UTF-16LE) then writes 2 zero bytes. 48 bytes = BOM + 23 chars. Cap 0x40 if len-2 > 0x3f.
  Stock twin: `FUN_714126e0` (B:12679). Playlist/other type 2 uses `FUN_71392658`; `FUN_71512628` (B:13936) caps 0x30 (album field).
- VERIFIED dispatch: `FUN_780db22c` (B:14849) indexes table at 0x780db5c8 (browser.ap file 0x46c8) with fsel type byte at 0x9fc15734:
  [0]=0x71352821 FAT dir, [1]=0x714d2659 library, [2]=0x71392659. Community changed [1] from 0x714126e1 to 0x714d2659 (file 0x46cc, 3 bytes `e12641`->`59264d`).
- drv_ui scroll scan of 0x66 (102) bytes is larger than the 50-byte list slot, so marquee width is not what cuts names; the 50-byte slot cuts first.
  The earlier doc guess "52 = chars" is wrong: 50 bytes, about 24 chars.

## 2. Sort / compare

- VERIFIED: browser.ap has NO sort and no case-fold compare (no `-0x20` upper-casing, no 0x71812500 bank). Directory mode lists in on-disk FAT/exFAT order
  (FUN_71352820 just walks entries sequentially via FUN_780db49c/FUN_780db460). Folders and files are not name-sorted by browser.ap.
- VERIFIED: sorting happens only in playlist.ap when it builds MUSIC.LIB. Shared bank 0x71812500 (playlist.ap file 0xa400):
  - `FUN_71812874` (P:12194) in-place quicksort of u16 index array, insertion sort (`FUN_718127cc`, P:12150) below 9 elements; mode byte param_5 selects compare.
  - mode 2 `FUN_71812548` (P:12016): byte-wise key compare, len capped at 100, ASCII a-z folded to upper (0x61..0x7a minus 0x20), ends when both bytes are 0.
    No numeric handling: "Track 10" < "Track 2". Non-ASCII compared as raw bytes (unsigned `byte`).
  - mode 0 `FUN_71812650` (P:12068): rank compare of u16 table. mode 1 `FUN_718126c0` (P:12092): track-number byte, then mode 0 rank.
  - Tie refinement `FUN_40114d54` (P:804) re-reads longer keys from file.
- VERIFIED: key is not purely ID3 or filename. `FUN_40094f2c` (P:401): tag reader for types <8 (sets tag-ok +0xa3=1). Otherwise, or on tag failure,
  `FUN_40094d60` (P:347) uses the file name from kernel op 2 (len 0x20) via `FUN_40094c8c` (P:315, 8.3 "NAME.EXT") as title, "No Artist/Album/Genre", track parsed from name digits.
  So All-songs order = title tag (ID3) if readable, else filename (HYPOTHESIS: LFN vs 8.3 depends on kernel op 2). Album view: album key, then track, then title rank.
- VERIFIED track storage: `FUN_40094fec` (P:435) stores `(char)record[+0xf2]` into a 1-byte-per-song array (so only the low 8 bits sort).
- Community diff mapping (playlist.ap, via bank table):
  - 0xa5ed, 3 bytes `844082`->`a440a2` = addr 0x718126ed inside `FUN_718126c0`: MIPS16 LB(0x84/0x82 high bits 10000) -> LBU (10100). VERIFIED bytes; decode is standard MIPS16.
    Matches decompile: track bytes compared as unsigned `byte`. This is the "unsigned track order" fix (128+ were negative).
  - 0x310c, 22 bytes = addr 0x4009510c inside `FUN_40094fec`: the decimal track fallback (`a0` digit *10 + `a1` digit). This is the "12 read as 21" fix.
  - 0x8e2e, 0x8ff4, 0x9078, 0x92ac (4-8 bytes each) plus new code 0x9318-0x9381: bank 0x480d4400 (0x480d462e..0x480d4b81) inside the function
    Ghidra mis-decompiles as `FUN_480d45e8` (all blocks "unreachable"). HYPOTHESIS: tag/track parsing patch with call sites into new code; not decoded.
  - 0x8e2e..0x92ac not in the sort bank. No community change to FUN_71812548 (string compare is stock).
- browser.ap community diff: 0x46cc = dispatch entry (see above); 0xec58-0xf12f = new `FUN_714d2658` (bank 0x714d2500, +0x158..0x62f, 1240 bytes);
  0x18e6a/0x18ef0 `04`->`08` = single constants in bank 0x48714400 (purpose not identified). None touch sorting.
- Repo docs agree: docs/library-builder.md "Sort, compare, and refinement" (same function list).

## 3. What a filename-natural sort would need (no patch written)

Two separate behaviours exist, so first decide the target:
- A. Directory browse (FAT order): browser.ap has no sort. Needs a new sort over the directory entries at the listing layer
  (`FUN_71352820` + fsel enter-dir/count code at 0x71352500 bank) plus an index map from sorted position to FS entry
  (fsel select-by-index calls). Not feasible without big new code and a RAM index (up to thousands of entries); unlikely in tight bank space. HYPOTHESIS.
- B. MUSIC.LIB order (playlist.ap): change title key source to filename (in `FUN_40094f2c`/`FUN_40094d60`: always take the name path, skip tag title)
  and replace mode-2 compare `FUN_71812548` (0x71812548..0x71812650, 0x108 bytes) with a natural compare (digit-run compare, fold case).
  The key buffers are fixed: 100-byte compare cap, key length 16 bytes at 4,000 songs refined by `FUN_40114d54`, so natural compare needs full-key re-read to be right.
- Free space: HYPOTHESIS only. Bank 0x71812500 has no free space: zeros from file 0xa99c (addr 0x7181299c) to 0xac00 are runtime scratch
  (key bufs 0x71812a9c/0x71812b00, stack frames 0x71812b64/0x71812c2c, 0x71812cf4). Compare would have to go into another bank tail
  (zero runs >=128 B in playlist.ap: 0x9382 (126, bank 0x480d4400 after community code), 0x3350 (176), 0x3b44 (188), 0xbb7c (132), 0x12580 (128)) after
  checking each is not bank data, or a whole unused bank. Reaching it needs a JAL/EXTEND call site: change the mode-2 compare-pointer literal at 0x71812a88 (FUN_71812874 stores 0x71812a80/a84/a88 into 0x9fc15500 for modes 0/1/2) -
  the compare is called through that pointer, so only that literal needs to change.
- Not verified: kernel op 2 name format (LFN vs 8.3), kernel text converter, fsel mode used by the Browser folder view at runtime.
