# M30 çalışma checkpoint'i

Bu belge yalnızca güncel çalışma durumunu ve değişmez güvenlik kurallarını
tutar. Ayrıntılı kanıtlar ilgili `findings-*.md` belgelerinde, emulator
kapsamı [`qemu-coverage.md`](qemu-coverage.md) içinde tutulur.

## Güncel durum — 2026-11-16

- Dal: `main`; push yapılmadı.
- Cihaza firmware, ROM payload veya başka veri yazılmadı.
- Son teknik değişiklik ve commit kimliği için `git log -1 --oneline` kullanılır.
- Host-only suite command: `bash tools/emu/run_static_suite.sh --host-only`.
- Tam suite, eksik historical corpus'lar (`first-pass-verify`, `v1.101.11`,
  `v1.101.12`, `v5`) nedeniyle preflight aşamasında duruyor.
- Corpus gate: beklenen `analysis/*` dizinleri mevcut fakat boş; `m30-inputs`
  ve tracked firmware binary'leri yok. Corpus karşılaştırması, yeni Ghidra
  araması ve provider taraması bu dosyalar sağlanana kadar çalıştırılmaz.

## Kanıt → emulator karşılıkları

- `tools/emu/folder_ui.py` ve `folder_input.py`: gerçek liste geometrisi,
  50-byte UTF-16 slot, marquee zamanlaması, navigation ve key-filter akışı.
- `tools/sim/key_filter.py`: ekran kapalı stock wake davranışı ve community
  keypass'in beş medya tuşu.
- `tools/sim/key_driver.py`: resident key driver ADC için 7-bit maske, yedi
  eşik, `0xff` unmapped sonucu, dışarıdan gelen normalize değer tablosu ve
  doğrulanmış repeat/special event sınırı.
- `tools/sim/usb_audio.py`, `usb_ring.py`, `usb_audio_stream.py`: doğrulanmış
  USB Audio descriptor, 200-byte packet ve ring sınırları; `RingConsumer`
  gerçek 0x1000-byte kaynak üzerinden wrap-aware bytes okuyabilir.
- `tools/sim/dac_bus.py`: `drv_dac.drv` içindeki kanıtlanmış byte dizisi
  gönderme/alma ve byte başına 8-bit transfer sınırı; bit sırası, codec
  register map'i ve timing modellenmez.
- `tools/sim/usb_mass_storage.py`: `uhost.drv` içindeki `USBC`, READ(10)/WRITE(10),
  block address ve 512-byte transfer birimi; request bytes'ları
  `SdCardBlockDevice` sektörlerine taşınabilir; raw `0x1f`/`0x80`–`0x88`
  transport event'leri de anlam atanmadan korunur. CBW/CSW framing ve
  controller davranışı modellenmez.
- `tools/sim/decoder_output.py`: unconfigured/community decoder callback için
  fail-closed `-1`; bilinmeyen callback çalıştırılmaz.
- `tools/sim/m30_model.py`: Ghidra ile doğrulanan EQ `0x303` mesaj zarfı,
  `{eq_type, selector}` çifti ve selector kaynağı ofseti; opaque DSP çağrıları
  çalıştırılmaz.
- `tools/sim/sd_block_device.py`: kanıtlanmış 512-byte SD sektör sınırı,
  card presence, bounds ve `sector_count * 512` capacity davranışı.
- `tools/emu/driver_loader.py`: doğrulanmış `yqhx` segment bytes'larını sparse
  resident memory'ye kopyalama ve BSS sıfırlama; entry/fixed-ROM çağrısı yok.
- `tools/sim/mmm_bp_model.py`: `mmm_bp` ring read sınırı ve Ghidra ile doğrulanan
  60-step fade phase / ±1000 level arithmetic; wrap-aware source-byte read
  mevcut, callback ve attenuation opaque.
- `tools/emu/lcd_transfer.py`: LCD `0x36` orientation komutunun Ghidra’da
  görülen ham değerlerini ve `0x2a/0x2b/0x2c` window/pixel sınırını kaydeder;
  fiziksel yön semantiği ve panel davranışı modellenmez.
- `tools/sim/asrc_model.py`: `music.ap` EOF branch'inin doğrulanmış mode-3
  advance yolu ve community/V1.101.11 için eklenen mode-4 yolu; ASRC/DAC
  örnek kuyruğu ve audible tail modellenmez.
- `tools/sim/metadata_reader.py`: V1.101.11/community metadata okuyucusunun
  doğrulanmış 0x200 buffer boundary split planı, concrete source-byte read'i ve
  trailing-skip aritmetiği; source/skip callback ABI'si ve parser modellenmez.
- `tools/sim/artwork_fallback.py`: community JPEG fallback için doğrulanmış
  `0xff` tetikleyici, 150x150, 1/3-component ve pozitif `0x1000`-inclusive
  block sınırı; JPEG decoder ve UI zamanlaması çalıştırılmaz. Ham decompile
  yalnızca ignored `analysis/local-evidence/artwork-fallback-community.c`
  altında yerel olarak saklanır; public repository'ye alınmaz.
- `tools/sim/artwork_cache.py`: `ALBUM.PIC` için doğrulanmış `OK`/`NO`,
  `x,y,w,h` ve RGB565 byte-payload sınırı; pixel renk sırası yorumlanmaz.
- `tools/sim/filesystem_extension.py`: FAT32/exFAT için byte kanıtlı 31-slot
  extension sözlüğü, explicit-slot kabul filtresi ve driver high-bit-first mask
  decoder; caller product policy ve directory callback ABI modellenmez.
- `tools/sim/filesystem_extension.py` içindeki raw library maskeleri ve
  `tools/emu/library_mask_probe.py`: MUSIC `0x7e190ea0` (`0x2a20`), M3U
  `0x00080400` (`0x2a28`); resident matcher için slot 0→bit 31, slot 30→bit
  1 sırası `tools/ghidra/run_library_mask_mapping_probe.sh` ile doğrulanır.
- `tools/sim/library_tag_reader.py`: `playlist.ap` extension→reader type
  seçimi; reader ABI ve metadata parsing çalıştırılmaz.
- `tools/sim/library_record.py`: tag başarısızlığında short-name title ve sabit
  fallback text alanları; raw 8.3 `NAME.EXT` formatter ve dört haneli track
  prefix selector modeli vardır.
- `tools/sim/library_record_codec.py`: documented 256-byte `MUSIC.LIB` record
  alanları; `index.c`'nin gerçekten kullandığı text/track alanları ile
  file-location byte dizileri ayrıştırılır, `+0xf4..+0xfb` US212A
  `cluster_no`/`dir_entry` çifti olarak okunur, primary location blob opaque
  tutulur.
- `tools/sim/library_index_sort.py`: `index.c` karşılaştırma sırasının raw
  record üzerinde çalışan candidate order modeli ile ALBUM→ARTIST→GENRE
  nested run/group türetimi; yazma veya M30 UI policy iddiası yoktur.
- `tools/sim/library_scan.py`: stock fixed-array scanının 4,000-record
  kapasite sınırı; `MUSIC.LIB` formatı veya experimental large-library yolu
  bu modelle birleştirilmez.
- `tools/sim/library_file.py`: `MUSIC.LIB` 0x200 header, 256-byte record area,
  four section directory ve raw sector references; caller-supplied SD
  başlangıç sektöründen byte image, bounded `LibraryRecord`, raw/typed section
  `u16` table, typed section snapshot ve fail-closed table/node-link validation
  ile 16-byte section node kayıtları okunabilir.
  `interpret_library_section_index()` doğrulanmış node run'larını raw record
  indekslerine read-only olarak eşler; UI albüm/sanatçı anlamı atamaz.
  `tools/emu/musiclib_evidence_probe.py` harici `MUSIC.LIB` örneğinin hash'ini,
  SD sektör yolunu, örnek `cluster_no`/`dir_entry` değerlerini, reader lookup
  round-trip'lerini ve section span coverage'ını tek komutta doğrular.
  `find_library_record_index()` aktif kayıtlar arasında firmware'in 4,000
  kayıtlık bounded eight-byte key aramasını modeller.
  `decode_library_section_node()`
  local builder ve bağımsız public hex örneğiyle örtüşen little-endian alanları
  açar; gerçek cihaz `MUSIC.LIB` görüntüsünde tüm section node/table coverage'ı
  doğrulanmıştır. Cihazın duplicate-key tie-break sırası ve location semantics
  hâlâ doğrulanmamıştır. Ayrıntı: [`findings-device-sd-library.md`](findings-device-sd-library.md).
- `tools/sim/library_walker.py`: stock walker’ın DFS, depth-8, `RECORD` skip ve
  target-count sözleşmesi; filesystem callback ABI’si modellenmez.
- MUSIC.LIB açık TODO'ları `docs/findings-music-lib-node-format.md` ve
  `docs/findings-device-sd-library.md` içindedir: `0xa9..0xf1` ve
  `0xfc..0xff` alanları opaque kalır; `0xf4..0xfb`
  `cluster_no`/`dir_entry` olarak okunur. Section reference `5` deepest-level
  mapping'i gerçek M30 görüntüsünde doğrulanmıştır, fakat duplicate-key
  tie-break ve primary location semantics açık kalır; reader lookup'ın
  doğrulanmış key boundary'si host'ta modellenmiştir.
- `tools/emu/ui_resources.py`: altı corpus'ta doğrulanmış MCG node ve RU3
  group metadata'sı; user-facing isim veya node anlamı uydurulmaz.
- `tools/emu/music_bitmap.py`: 12 corpus'ta doğrulanmış `music.sty` resource
  table'ının format `0x2`, boyut ve doğrudan little-endian RGB565 sözleşmesi;
  bilinmeyen formatlar reddedilir. `NowPlaying` resource 0 bitmap'ini gerçek
  framebuffer çıktısına taşır.
- `tools/emu/build_safe_ui_members.py`: yalnızca `music.sty` ve `setting.sty`
  değiştiren extracted-member candidate üretimi; iki bilinen `music.sty`
  layout'ını ve iki bilinen `setting.sty` kaynağını payload hash'leriyle
  doğrular, bilinmeyen düzenlerde durur; flashable HEX üretmez. UI bulguları:
  [`findings-ui-resources.md`](findings-ui-resources.md).

## Bilinçli olarak uygulanmayanlar

- Tam ATJ2127 boot, bank loader'ın çözülmemiş exception yolu, gerçek LCD/DAC,
  fiziksel key ADC eşlemesi ve controller register/IRQ zamanlaması.
- Tam USB mass-storage CBW/CSW framing'i, status anlamları ve controller
  timing'i; mevcut host modeli yalnızca doğrulanmış block-request alanlarını
  taşır.
- MCG localized-name ve node→application eşlemesi.
- Decoder callback'i başarılı PCM yolu gibi kullanmak.
- Cihazda doğrulanmamış firmware veya HEX üretimini release olarak sunmak.

## Sıradaki çalışma kuralı

Yeni bir davranış ancak şu sırayla eklenir:

1. Kanıtı ilgili binary/probe/Ghidra bulgusuyla sınırla.
2. Kanıtlanmış kısmı host emulator modeline ekle.
3. Belirsiz kısmı fail-closed bırak.
4. Regression test ve ilgili finding dokümanını güncelle.
5. Tek anlamlı kapsamla commit et; push yapma.

## Kanonik belgeler

- [`qemu-coverage.md`](qemu-coverage.md)
- [`community-integration.md`](community-integration.md)
- [`release-candidate.md`](release-candidate.md)
- [`findings-kernel-loader.md`](findings-kernel-loader.md)
- [`findings-filesystem-drivers.md`](findings-filesystem-drivers.md)
- [`findings-music-lib-node-format.md`](findings-music-lib-node-format.md)
- [`library-builder.md`](library-builder.md): record storage, key conversion,
  index passes, node writer, and large-library constraints.
- [`findings-library-record-locations.md`](findings-library-record-locations.md)
- [`findings-ui-resources.md`](findings-ui-resources.md)
- [`findings-decoder-callback.md`](findings-decoder-callback.md)
- [`findings-cards-driver.md`](findings-cards-driver.md)
- [`findings-device-artifacts.md`](findings-device-artifacts.md): çevrimiçi
  M30 kaynakları, eksik cihaz artefaktları ve güvenlik sınırları.
- [`provenance-risk.md`](provenance-risk.md): public/private reverse-engineering
  artifact ayrımı ve MIT lisansının kapsam sınırı.
- [`discovery-environment.md`](discovery-environment.md)
- [`corpus-downloads.md`](corpus-downloads.md): dated Drive folder URLs,
  hashes, download verification, and extraction boundary.
- [`../tools/rom/README.md`](../tools/rom/README.md)

## Değişmez kurallar

- Orijinal HEX'i silme veya üzerine yazma; her değişiklikten önce ve sonra
  SHA-256 üret.
- FWU boyutu, sektör düzeni ve checksum/trailer korunur.
- Donanımda test edilmeyen davranışı kesin çalışır diye yazma.
- Test anahtarlarını ve gereksiz community anahtarlarını final HEX'e koyma.
