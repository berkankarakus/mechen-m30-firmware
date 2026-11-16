# M30 çalışma checkpoint'i

Bu belge yalnızca güncel çalışma durumunu ve değişmez güvenlik kurallarını
tutar. Ayrıntılı kanıtlar ilgili `findings-*.md` belgelerinde, emulator
kapsamı [`qemu-coverage.md`](qemu-coverage.md) içinde tutulur.

## Güncel durum — 2026-11-16

- Dal: `main`; push yapılmadı.
- Cihaza firmware, ROM payload veya başka veri yazılmadı.
- Son teknik commit: `2c797ee feat: model SD sector transfers`.
- Host-only suite command: `bash tools/emu/run_static_suite.sh --host-only`.
- Tam suite, eksik historical corpus'lar (`first-pass-verify`, `v1.101.11`,
  `v1.101.12`, `v5`) nedeniyle preflight aşamasında duruyor.

## Kanıt → emulator karşılıkları

- `tools/emu/folder_ui.py` ve `folder_input.py`: gerçek liste geometrisi,
  50-byte UTF-16 slot, marquee zamanlaması, navigation ve key-filter akışı.
- `tools/sim/key_filter.py`: ekran kapalı stock wake davranışı ve community
  keypass'in beş medya tuşu.
- `tools/sim/usb_audio.py`, `usb_ring.py`, `usb_audio_stream.py`: doğrulanmış
  USB Audio descriptor, 200-byte packet ve ring sınırları.
- `tools/sim/decoder_output.py`: unconfigured/community decoder callback için
  fail-closed `-1`; bilinmeyen callback çalıştırılmaz.
- `tools/sim/m30_model.py`: Ghidra ile doğrulanan EQ `0x303` mesaj zarfı,
  `{eq_type, selector}` çifti ve selector kaynağı ofseti; opaque DSP çağrıları
  çalıştırılmaz.
- `tools/sim/sd_block_device.py`: kanıtlanmış 512-byte SD sektör sınırı,
  card presence ve bounds davranışı.
- `tools/sim/filesystem_extension.py`: FAT32/exFAT için byte kanıtlı 31-slot
  extension sözlüğü ve yalnızca explicit-slot kabul filtresi; caller maskesi
  ve directory walker modellenmez.
- `tools/sim/filesystem_extension.py` içindeki raw library maskeleri ve
  `tools/emu/library_mask_probe.py`: MUSIC `0x7e190ea0` (`0x2a20`), M3U
  `0x00080400` (`0x2a28`); aradaki pointer nedeniyle bit→slot sırası
  çözülmediği için yalnızca ham bit konumları tutulur.
- `tools/sim/library_tag_reader.py`: `playlist.ap` extension→reader type
  seçimi; reader ABI ve metadata parsing çalıştırılmaz.
- `tools/sim/library_record.py`: tag başarısızlığında short-name title ve sabit
  fallback text alanları; dört haneli track prefix selector modeli vardır.
- `tools/sim/library_record_codec.py`: documented 256-byte `MUSIC.LIB` record
  alanları; file-location byte dizileri opaque tutulur.
- `tools/sim/library_walker.py`: stock walker’ın DFS, depth-8, `RECORD` skip ve
  target-count sözleşmesi; filesystem callback ABI’si modellenmez.
- `tools/emu/ui_resources.py`: altı corpus'ta doğrulanmış MCG node ve RU3
  group metadata'sı; user-facing isim veya node anlamı uydurulmaz.
- `tools/emu/build_safe_ui_members.py`: yalnızca `music.sty` ve `setting.sty`
  değiştiren extracted-member candidate üretimi; flashable HEX üretmez.

## Bilinçli olarak uygulanmayanlar

- Tam ATJ2127 boot, bank loader'ın çözülmemiş exception yolu, gerçek LCD/DAC,
  fiziksel key ADC eşlemesi ve controller register/IRQ zamanlaması.
- USB mass-storage CBW/CSW emülasyonu; mevcut kanıt CBW marker'larıyla sınırlı
  ve CSW davranışı doğrulanmış değil.
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
- [`findings-ui-resources.md`](findings-ui-resources.md)
- [`findings-decoder-callback.md`](findings-decoder-callback.md)
- [`findings-cards-driver.md`](findings-cards-driver.md)
- [`discovery-environment.md`](discovery-environment.md)
- [`../tools/rom/README.md`](../tools/rom/README.md)

## Değişmez kurallar

- Orijinal HEX'i silme veya üzerine yazma; her değişiklikten önce ve sonra
  SHA-256 üret.
- FWU boyutu, sektör düzeni ve checksum/trailer korunur.
- Donanımda test edilmeyen davranışı kesin çalışır diye yazma.
- Test anahtarlarını ve gereksiz community anahtarlarını final HEX'e koyma.
