# M30 çalışma checkpoint'i

Bu belge yalnızca güncel çalışma durumunu ve değişmez güvenlik kurallarını
tutar. Ayrıntılı kanıtlar ilgili `findings-*.md` belgelerinde, emulator
kapsamı [`qemu-coverage.md`](qemu-coverage.md) içinde tutulur.

## Güncel durum — 2026-11-25

- Dal: `codex/fix-model-coverage`; linked worktree'nin Git deposu
  `/Users/berkankarakus/Projects/mechen-m30-firmware/.git` ile ortak. Bu turdaki
  p-code commit'leri `1c19b59` (scroll import-15 op-`0x31` çağrı ABI'si) ve
  `b96f78a` (kernel ROM copy yönü kontrolü). Bu handoff güncellemesi
  commit'lendikten sonra çalışma ağacı temiz olmalı; push yapılmadı. Yeni
  worktree açılırsa `git status --short --branch` ve
  `git log --oneline origin/main..HEAD` ile teyit et.
- Cihaza firmware, ROM payload veya başka veri yazılmadı.
- Son p-code çalışmaları ROM gövdesi yerine gerçek caller davranışını ölçüyor:
  `music.ap` scroll-next yolu import `0x0f`, selector `0x31`'e
  `(1,0,0,0x31)` ile ulaşıyor; aynı selector'ün playlist hata/yeniden deneme
  bağlamında `a0=0x23` kullanımı ve public `actions_flash` notundaki
  `sleep_ms(a0)` eşlemesi M30 için güçlü ama doğrulanmamış bir hipotez.
  Playlist op-9 çağrısı `(1,0,0,9)` için `0`/`-1` dönüşleri sınandı;
  US212D notundaki “Close Driver / File” etiketi M30'a aktarılmış dış kaynak
  hipotezi olarak kalıyor.
- `ker_init.bin` `FUN_bfc322f8` p-code probe'u için `forward` modunda gerçek
  caller'ın kaynak `0x9fc12000`'dan hedef `0x9fc1aad8`'e sentetik kopyayla
  callback'e ulaştığı, `reverse` kontrolünde hedef sıfır kalıp null indirect
  target'a gittiği doğrulandı. Bu, caller'ın kopya yönünü gerektirdiğini
  gösterir; `0xbfc04635` ROM gövdesinin kopyalama yaptığı kanıtı değildir.
  Ayrıntı: [`findings-kernel-loader.md`](findings-kernel-loader.md) ve
  [`findings-qemu-dispatch.md`](findings-qemu-dispatch.md).
- Aynı gerçek caller üzerinde `0xbfc045f5` clear adayı için sentetik
  zero-fill/no-effect karşılaştırması stock ve community `ker_init.bin`'de
  geçti. Gerçek çağrı `(0x9fc1a48c,0,0x7f4)`; iki model de aynı callback
  yoluna ulaşıyor. Zero-fill modeli aralıktaki her 32-bit sözcüğü sıfırlayıp
  exclusive-end canary'sini koruyor; no-effect modeli sentinel'leri koruyor.
  Sentetik dönüş değerini `0`, hedef adres ve `0xdeadbeef` yapınca da
  community caller aynı callback'e aynı argümanlarla ulaşıyor; stock'ta
  sentinel dönüşü tekrarlandı. Bu, yalnızca sınanan caller devam yolunda
  dönüşe bağlı kontrol akışı veya callback argümanı değişikliği
  gözlenmediğini gösterir.
  ROM gövdesinin gerçek etkisini veya açılış gerekliliğini çözmez. Sabit ROM
  dump'ı yok; ADFU okuma yolu yalnızca kaynakta incelendi, cihazda denenmedi.
- `FUN_bfc322f8` callback'ini sentetik no-op dönüşle geçince gerçek extracted
  caller `0xbfc323d4`'ten devam edip ikinci clear çağrısına
  `(0x13d00,0,0xe0)` ile ulaşıyor. Bu aralıkta exception vector'ın yazdığı
  `0x13dcc/0x13dd0/0x13dd4` sayısal adresleri var. Zero-fill/no-effect
  sentinel modelleri ve final `v0` dönüşü community'de; no-effect/sentinel
  kontrolü stock'ta geçti. Bu adres çakışması fiziksel RAM alias'ını,
  cihazdaki gerçek clear etkisini veya boot sırasını kanıtlamaz. Aralık
  taraması `ker_xsys.bin` içindeki `FUN_bfc344f4`'ün `0x13dcc..0x13ddc`
  aralığından beş sözcük okuyup her birini `exc:` descriptor'ıyla bir ROM
  callback'ine verdiğini gösterdi. Ghidra p-code bunu sentetik callback ve
  canary'lerle doğruladı. Aynı prob iki yolu da çalıştırdı: `0x9fc1aa5c`
  bit 1 clear → MMIO adresine `0x5d`; set → `0x69`. Peripheral rolü/etkisi ve
  missing fixed-ROM handler'la bağlantısı kanıtlanmadı. `FUN_bfc3416c` guard
  dalı da sentetik ROM dönüşleriyle gerçek p-code'da çalıştırıldı; iki tanı
  callback'inin argümanları, flag temizliği ve default-handler sınırı geçti.
  Guard sözcüğü eşleşirken mesafe `0x93` hata, `0x94` normal dönüş verdi;
  `0x180` mesafede sentinel uyuşmazlığı da hata dalına girdi. ROM servislerinin
  doğal dönüşleri ve bu fonksiyonlara gerçek caller bağı bilinmiyor.
  Ayrı `FUN_bfc340a4` p-code profili gerçek alternatif stack selector'ını
  doğruladı: `table=0x12000` için `sp&0x3ffff` değerleri `0x11fff` ve
  `0x12000` alternate stack'e, `0x12001` doğrudan ROM sınırına gidiyor.
  Alternate yolda 184-byte slot ayrılıyor, eski SP kaydediliyor ve iki sayaç
  artıyor; `0xbfc05f90` handler gövdesi çalıştırılmıyor.
  Callback bir diagnostic-format/emission helper adayı, çıkış hedefi bilinmiyor.
  Yerel tarihli firmware kopyalarında `ker_xsys.bin` byte-identical;
  raw literal taraması iki fonksiyonun doğrudan entry pointer'ını göstermedi.
  Sonraki adım missing
  fixed-ROM exception caller edge'ini mevcut dispatch ile eşleştirmek; bunu
  kanıtlamadan varsayımsal call edge eklememek.
- `bash tools/emu/run_static_suite.sh --host-only` 2026-11-24'te geçti:
  toplam 563 test, 3 skip. Tam `bash tools/emu/run_static_suite.sh` bu
  checkpoint'te çalıştırılmadı; bu yüzden merge edilmiş yeni Ghidra/QEMU
  probe'larının tümü için tam-suite pass iddiası yok.
- Tam suite; Ghidra driver/kernel, gerçek MIPS16 scroll/navigation ve altı
  firmware corpus'u üzerindeki host kontrollerini kapsar. QEMU leaf/chain
  probe'ları ayrıca çalıştırılır; bunlar tam ATJ2127 boot iddiası değildir.
- Loader sınırı: `kernel.drv` içindeki `FUN_bfc0a408`/`FUN_bfc0a578`
  adaylarının loader değil resident-table yardımcıları olduğu doğrulandı.
  `yqhx.py` ve sparse materializer yalnızca header/segment/BSS sözleşmesini
  modeller.
- `analysis/community/dec.bin` kritik extracted üyeleri birer kez içerir ve
  `0xbfc06d6c` handler işaretçisi içermez. `tools/emu/dec_container_probe.py`
  bu sınırı kontrol eder; eksik fixed-ROM handler'ı mevcut dump'tan çıkarılamaz.
- `tools/emu/kernel_syscall_scope_probe.py`, `ker_text.bin`, `ker_init.bin`
  ve `kernel.drv` içinde sıfır MIPS16 `break` noktası doğrular. Selector
  dispatcher'ı bu extracted kernel üyelerinde yoktur; `break 0` etkisi fixed
  ROM sınırında kalır.
- Upgrade sınırı da artık on iki dated `upgrade.ap` imajında tekrarlandı:
  `0x40014c30` entry, beş iterasyonlu screen loop'u ve `upgrade.sty`/
  `common.sty` resource-name literal'ları bütün corpus'ta aynı kaldı.
  `tools/ghidra/run_upgrade_ap_corpus_probe.sh` bunu geçici Ghidra çıktısını
  saklamadan yeniden üretir. `tools/emu/upgrade_flow.py` selector ve
  decrypt/search olaylarını trace-only taşır; fixed-ROM anlamı çözülmeden
  flash/reboot/success iddiası üretmez.
- `tools/sim/usound_callback.py` `break 0` zarfındaki modül kimliğini ve dört
  argümanı kaydeder. `0x10` libc modülü, `0x0f` çekirdek modülüdür; servis
  gövdeleri/etkileri host modelinde çalıştırılmaz.
- Yeni ses/indeks bulgularının ayrıntısı [`findings-auddev-driver.md`](findings-auddev-driver.md),
  [`findings-eq-usound.md`](findings-eq-usound.md),
  [`findings-music-lib-node-format.md`](findings-music-lib-node-format.md) ve
  [`findings-upgrade-flow.md`](findings-upgrade-flow.md)'te: YQHX dört segmenti
  parse edilir; stock/community EQ producer→MEngine builder zinciri iki hash
  eşleşmesinde p-code ile yürütüldü, fakat ROM copy-service etkisi sentetik;
  `usound`/`aud_dev` için `table[op]` hâlâ inference. MUSIC.LIB'de bir terminal
  converter adayı tek cihaz kütüphanesinin indeks tablolarını eşleştiriyor,
  ikinci public örneğe genellenmiyor.
- EQ Custom slider kodu artık community `mainmenu.ap` içinde bulundu:
  `FUN_40154f44` artış olayıyla p-code'da çalıştı ve `{7,7}` producer mesajına
  ulaştı; servisler sentetik. Ek disassembly raporu state pointer tablosunun
  selector/editor'e ulaştığını ve `0x38` bloğun yalnızca AP çıkışında
  kalıcılaştırıldığını bildiriyor. State-1 giriş öğesi bilinmiyor; iptal
  motoru yeniden güncellemeden yerel yedeği geri yüklüyor; üç yollu yerel
  p-code koşusu da RAM tamponlarının ayrışmasını doğruladı. Azaltma taraması
  sentetik `0x2904` için başlangıç `-3`'te no-op, `-2..+3`'te doğrudan `-3`
  gösterdi. Event ABI çıkarım olduğundan cihaz tuş semantiği açık.
  Ayrıntı ve tekrar üretim: [`findings-eq-selector-writer.md`](findings-eq-selector-writer.md)
  ve [`p-code çıktısı`](evidence/mainmenu-eq-slider-pcode-2026-11-24/README.md).
- `config.ap` `FUN_40dd4d60` factory band kayıtlarını `config.bin` öğe
  `0x86..0x95` içinden `dae_cfg` 16-band alanına kuruyor. EQ builder çağrısı
  bu 16 alanı yeniden yazar ve son dokuz bandı sıfırlar; FullSound/hoparlör
  telafisi olduğu veya açılışta duyulduğu kanıtlanmadı. Hash ve decode:
  [`config dae_cfg kanıtı`](evidence/config-dae-factory-2026-11-24/README.md).
- Config item `0x96` defaults the DAE image flag to `audiopp.dsp` through
  shared byte `+2`; `mmm_pp.al` chooses `adppext.dsp` when that byte is zero.
  Item `0x98` maps to builder guard `+0x0c` (default zero). The DSP's EQ role
  and linkage from config state to MEngine's separate active/selector globals
  remain unproven.
- DAC caller taraması da tekrar üretilebilir durumda:
  `tools/emu/dac_caller_scan.py`. Doğrudan helper pointer'ları yalnızca
  sürücü/container kopyalarında bulunur; codec register anlamı çözülmüş
  değildir.
- Başka bilgisayara geçiş için [`portable-handoff.md`](portable-handoff.md)
  ve `python3 tools/verify_persistent_evidence.py <evidence-root>` kullanılır;
  firmware, cihaz SD dosyaları ve Ghidra çıktıları Git dışında kalıcı kanıt
  kökünde tutulur.

## Önceki belgelerdeki düzeltmeler ve kanıt kökeni

- **Previous yaması parçayı başa döndürmeyi kanıtlamıyor.** `mengine.ap`
  içindeki `0x3a64` sabiti, `_play` fonksiyonunun hızlı geri sarma yolunda
  `bp_time_offset = -5000` olarak kullanılıyor; Previous mesajı `0x319` için
  motor handler'ında süre eşiği yok. `tools/patch_prev_restart.py` bu sabiti
  sıfırlasa da gerçek "Previous = başa sar" davranışını sağlamaz ve önceki
  parçanın sonuna yakın bir noktadan başlama/parça atlama riski taşır. Güvenli
  aday kapsamına alma. Ayrıntı: [`findings-artwork-start.md`](findings-artwork-start.md)
  §3 ve [`community-integration.md`](community-integration.md).
- **UTF-16 satır sonu:** `drv_ui.drv::FUN_300007c4`, `0x0000` değerini EOF,
  `0xfeff` değerini Unicode bayrağı, `0x000a` değerini LF ve `0x000d` ile
  `0x000d 0x000a` dizilerini CR/CRLF satır sonu olarak sınıflandırıyor.
  Host hizalama modeli `tools/sim/text_alignment.py` ve testleriyle bu
  davranışı kapsıyor; bu, firmware yaması veya cihaz testi değildir.
  Ayrıntı: [`discovery-environment.md`](discovery-environment.md).
- **İsim slotu:** SDK'daki 52 baytlık sabit, M30 browser'ın kullandığı 50
  baytlık slotla karıştırılmamalı. İsim, kayan yazı taramasından önce kesiliyor;
  slotu kaynağını anlamadan büyütmek güvenli değil. Ayrıntı:
  [`findings-browser-names-sort.md`](findings-browser-names-sort.md).
- **Artwork gecikmesi:** gözlenen artwork decode'u PLAY yanıtından sonra UI
  thread'inde çalışıyor. Bu nedenle UI'nin donması ile sesin başlama gecikmesi
  aynı iddia değildir; süre/CPU etkisi ölçülmedi. Ayrıntı:
  [`findings-artwork-start.md`](findings-artwork-start.md).

### Tekrarlanabilir test girişi

Tam host-only doğrulama için kanonik komut:

```sh
bash tools/emu/run_static_suite.sh --host-only
```

Komut `tools/sim`, `tools/emu` ve `tools/rom` testlerini çalıştırır ve başarılı
olduğunda `STATIC SUITE PASS host-only` yazar. Tam statik suite farklı
firmware corpus'ları ve Ghidra gerektirir. Bazı host testleri yerel
`common.sty`/RU3 fixture'ları olmadığında skip olur; skip sayısını test
çıktısından kontrol et.

Tek tek Python paketlerini çalıştırırken repo kökünü ve iki araç dizinini
import yolunda tut; `-I` kullanma, çünkü Python isolated mode `PYTHONPATH`'i
yok sayar:

```sh
PYTHONPATH=.:tools/emu:tools/sim python3 -m unittest discover \
  -s tools/emu -p 'test_*.py'
PYTHONPATH=.:tools/emu:tools/sim python3 -m unittest discover \
  -s tools/sim -p 'test_*.py'
```

2026-11-17 host-only suite çalıştırmasında sim için 268 test, emu için 229 test
(3 skip) ve ROM için 6 test geçti. Sayılar o çalıştırmaya aittir; sabit suite
sözleşmesi değildir. CI/review kapısı olarak yukarıdaki `run_static_suite.sh`
komutunu tercih et.

### MUSIC.LIB ve playlist.ap girdilerini seçme

- M30 SD kartından alınmış doğrulanmış kütüphane
  `<persistent-evidence-root>/device-sd/MUSIC.LIB` dosyasıdır; boyutu
  2,625,536 bayt, SHA-256'sı
  `e386db27a9f47641e8755e5a58a903e6e66f83afe2be84c97d5d7e59de0f3c88`.
- Kanıt kökündeki `<persistent-evidence-root>/MUSIC.LIB` başka kaynaktan
  alınmış 1,536,000 baytlık, 251 kayıtlı karşılaştırma örneğidir; SHA-256'sı
  `cc3f476c8edb50ea8493b726d46ac82b139a6e87a86cc04c2cdbc30fd3fb8afe`.
  Bu dosya M30 dump'ı değildir; cihaz indeksi/record eşleştirmesi için
  `device-sd/MUSIC.LIB` yerine kullanma.
- `playlist.ap` SHA-256 `7b1971f1496318a9682b0abc7681c058ded702aa533c97a32e428f5088b77b64`
  2023-07-26, 2024-03-19 ve 2025-06-26 tarihli extracted kopyalarda aynıdır.
  Bu hash payload'ı doğrular, fakat tarih tek başına firmware sürümünü
  tanımlamaz. Kaynağın tarihini ve tüm firmware imajının hash'ini ayrıca
  kaydet.

## Son dinamik kanıt checkpoint'i

- `9da84ad` ile `FUN_40154ddc` initial paint girişi gerçek MIPS16 p-code'da
  çalıştırıldı; üç firmware ailesinde 7 dispatcher çağrısı ve gerçek return
  sınırı aynı kaldı. `tools/ghidra/run_now_playing_paint_corpus_probe.sh` ile
  bu sınır on iki dated image'ın tamamında tekrarlandı: `0x18c3`/`0x39e7`
  band çağrıları, üç `0x12` clear payload'ı ve son `0x1002` artwork
  payload'ı aynı sırada kaldı.
  Paint wrapper artık Ghidra script error raporunu da başarısızlık sayıyor.
- `3ed9368` ile aynı girişin metadata `0x100`, transport/EQ `0x20` ve status
  `0x200`/`0x800` dalları üç firmware ailesinde gerçek kodla çalıştırıldı.
  Sıra sırasıyla `0x2005`, `0x1004`/`0x1003`, `0x1000`/`0x1001` kontrol
  kimlikleriyle doğrulandı; decoder/DAC çağrısı bu sınırda yok.
- Directory callback matrix probe'u `FUN_71352820` için before/inside/after
  current-index dallarını çalıştırdı. Üç dalda da 0x0c row stride, 0x32-byte
  slot, 25-unit FS çağrısı, mode 2 ve 0x4 converter limiti aynı kaldı; yalnızca
  provider preflight çağrı sayısı dal konumuna göre değişti.
- `RunBrowserRowProviderProbe.java`, gerçek `FUN_48714a20` → `FUN_48594510`
  zincirinde 20-byte kaydın little-endian `+0x02` halfword'unu converter'ın
  ilk argümanı olarak doğruladı. Sentinel kayıt `a0a1a2a3...` ile gözlenen
  değer `0xa3a2`; community ve stock AP'lerinde aynı. Bu alanın playlist
  anahtarı, directory kimliği veya başka bir fsel semantiği olduğu henüz
  adlandırılmadı; emulator'a yeni semantik eklenmedi.
- `RunNowPlayingStateProbe.java`, paint dispatcher payload'larında operation
  `0x02` için `a1 = a0 + 0x08`, operation `0x03` için `a1 = a0 + 0x10`
  ilişkisini gerçek stack bytes ile assertion olarak kontrol ediyor. Kontrol
  ID'si payload `+0x00` halfword'unda; bu, shared scroll renderer'daki
  `0x1012/0x1013` trace'inden ayrı bir paint sınırı. `flags=0x08` dalı ayrıca
  `0x1007,0x1006,0x1008,0x1005,0x1004` sırasını ve metadata glyph çağrılarında
  `a1=0` biçimini community/stock AP'lerinde doğruluyor. `metadata-table`
  dalı `state+0x19` ile seçilen sekiz op-`0x03` payload değerini ve
  `state+0x0e` byte kopyasını aynı corpus'larda doğruluyor; değerler host'ta
  opaque tutuluyor. 12-image taramasında 10 tablo aynı; `2024-04-24` sürümü
  indeks 1 ve 6'yı `0x004f`/`0x005e` olarak değiştiriyor ve gerçek p-code
  probe'u bu iki payload farkını üretiyor. Host değerleri AP'den okuyor,
  sabit anlam atamıyor.
- Community, stock ve 2024-04-24 AP'lerinde metadata payload'ın ilk 12 byte'ı
  sentinel-backed assertion ile kontrol ediliyor: firmware `+0x00`, `+0x02` ve
  `+0x04` alanlarını yazıyor; `+0x03` ve `+0x08` probe sentinel'ını koruyor.
  Bu, public SDK `textbox_private_t` yapısıyla sınırlı bir yapısal
  karşılaştırma sağlıyor; pointer/color semantiği kanıtlanmadığı için host'ta
  yalnızca yazıldığı kanıtlanan alanlar taşınıyor.
- `op=0x02` için `a1=a0+0x08` secondary payload'ı da sentinel ile ayrıştırıldı:
  `0x1000/0x1001` için word `0xff00`, `0x1002..0x1004` için `0xffff`; sonraki
  byte yalnızca `0x1003/0x1004` için `1`. Host bunu
  `NowPlaying.control_payload_trace()` ile opaque trace olarak taşır.
- Public PD196 header'ındaki `style_infor_t` + `picbox_private_t` ve
  `style_infor_t` + `textbox_private_t` düzenleri M30 payload'larıyla yapısal
  olarak eşleşiyor: `a0` style ID/type, `a1` ise op'a göre PicBox/TextBox
  adayı. Bu henüz ABI/semantic kanıt değil; özellikle `0xff00`, language ve
  color alanları bilinçli olarak opaque bırakılıyor.
- On iki dated image'ın tamamında style type byte'ı sabit eşleşiyor: `0x1003`
  için `1`, gözlenen diğer control/text ID'leri ve `0x2005` için `0`. Bu,
  public SDK'deki `UI_AP=0` / `UI_COM=1` düzeniyle yapısal olarak uyumlu; host
  alanı yalnızca ham `style_resource_type` olarak taşıyor ve tam resource-type
  semantiği ilan etmiyor. Wrapper ayrıca geçici logdan compact `PAYLOAD TYPES`
  özeti yazıyor.
- `common.sty` içinde doğrudan `0x1003/0x1004` PicBox ID'si bulunmadığı için
  bu byte'ın common-resource yönlendirmesi olduğu varsayılmıyor; `0x1000 +
  PicBox index` eşleşmesi ayrı M30 dispatcher kanıtı olarak korunuyor.
- `tools/ghidra/run_now_playing_corpus_probe.sh <evidence-root>` aynı kontrolü
  dated corpus'taki tüm `music.ap` dosyalarına uygular. Son tam tarama 12/12
  imajda 8/8 metadata index'i geçti. Ghidra 12.2 için Java seçimi
  `JAVA_HOME`/`JAVA_HOME_OVERRIDE` üzerinden yapılır.
- Dış PD196 SDK referansındaki `common_res.h` ve `music_res.h`, standart M30
  metadata tablosundaki sekiz halfword'ün tamamını string resource ID olarak
  adlandırıyor (`S_SECOND`, `S_SET_MENU`, `S_GENRE`,
  `S_IS_OVERRIDE_FAVLIST`, `S_LICENSE_FAIL`, `S_CLASSIC`, `S_THIS_ALBUM`,
  `S_CUSTOM`). Bu, ilk halfword için güçlü bir string-ID hipotezidir; M30
  `string_desc_t` ABI'si kanıtlanmadığından emulator'daki `table_value` hâlâ
  opaque kalır. Ayrıntı [`findings-now-playing-layout.md`](findings-now-playing-layout.md)
  içindedir.
- Sıradaki yüksek getirili iş resource/font pointer'larını gerçek LCD sink'e
  bağlamak. EOF mode-4 için dinamik callback patch'i, bank sonundaki
  kod/veri örtüşmesi nedeniyle güvenli bir probe sınırı oluşturmadı; bu alan
  mevcut statik delta ile fail-closed tutuluyor.

## Kanıt → emulator karşılıkları

- `tools/emu/folder_ui.py` ve `folder_input.py`: gerçek liste geometrisi,
  50-byte destination slotu ve 25-unit provider isteği; provider'ın uzun ad
  davranışı bilinmiyor. Marquee zamanlaması, navigation ve key-filter akışı.
- `tools/sim/browser_row_record.py`: gerçek `0x14` row stride ve
  `list_state + 4 + row * 0x14` kaynağını korur; yalnızca converter'a giden
  `+0x02` halfword'u açar, geri kalan alanları opaque bırakır.
- `tools/sim/key_filter.py`: ekran kapalı stock wake davranışı ve community
  keypass'in beş medya tuşu.
- `tools/sim/key_driver.py`: resident key driver ADC için 7-bit maske, yedi
  eşik, `0xff` unmapped sonucu, dışarıdan gelen normalize değer tablosu ve
  doğrulanmış repeat/special event sınırı.
- `tools/sim/usb_audio.py`, `usb_ring.py`, `usb_audio_stream.py`: doğrulanmış
  USB Audio descriptor, 200-byte azami paket ve ring sınırları; `RingConsumer`
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
- `tools/sim/m30_model.py`: EQ `0x303` mesaj zarfı ve `{eq_type, selector}`
  çifti yanında, p-code ile doğrulanan yedi bantlı builder çıktısını ve erken
  dönüş koşullarını modeller. `run_eq_builder_probe.sh` stock/community
  MIPS16 çıktısını byte-byte karşılaştırır. `mmm_pp.al` SHM+2'den DSP seçimini
  yapıp SHM işaretçisini modül `0x0c` op `0x12`'ye verir; ROM alıcısı,
  katsayı dönüşümü ve duyulabilir DSP etkisi hâlâ çözülmedi.
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
- `tools/sim/artwork_cache.py`: decompile ile doğrulanmış `OK`/`NO`, `x,y,w,h`
  ve RGB565 byte-payload sınırı ile cihaz SD görüntüsünde doğrulanan ayrı,
  250-sektör `ALBUM.PIC` container sınırı; pixel renk sırası ve container
  başlık alanlarının anlamı yorumlanmaz. Probe:
  `tools/emu/album_pic_evidence_probe.py`.
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
  nested run/group türetimi; ayrıca gerçek `FUN_40114d54` bounded tie
  refinement'ı ve stock quicksort'ı `refine_sort_record_indices()` adıyla
  opt-in taşır. `stale-tail` varsayılan conversion modelidir; SD corpus’unda
  ALBUM/ALLSONG eşleşmesini artıran `stop-zero` modeli ayrıca opt-in'dir.
  Varsayılan sorter değişmez; yazma veya M30 UI policy iddiası yoktur.
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
  hâlâ doğrulanmamıştır. `tools/emu/library_order_probe.py` önceki-section
  rank'ı sonraki candidate pass'e vererek comparator farkını izole eder; mevcut
  görüntüde GENRE sırası 4,000/4,000 eşleşir. Ayrıntı:
  [`findings-device-sd-library.md`](findings-device-sd-library.md).
- `tools/sim/library_walker.py`: stock walker’ın DFS, depth-8, `RECORD` skip ve
  target-count sözleşmesi; filesystem callback ABI’si modellenmez.
- MUSIC.LIB açık TODO'ları `docs/findings-music-lib-node-format.md` ve
  `docs/findings-device-sd-library.md` içindedir: `0xa9..0xf1` ve
  `0xfc..0xff` alanları opaque kalır; `0xf4..0xfb`
  `cluster_no`/`dir_entry` olarak okunur. Section reference `5` deepest-level
  mapping'i gerçek M30 görüntüsünde doğrulanmıştır, fakat duplicate-key
  tie-break ve primary location semantics açık kalır; reader lookup'ın
  doğrulanmış key boundary'si host'ta modellenmiştir.
- Son güvenli araç değişikliği `f09a4d5` (`feat: preserve library ordering on
  safe edits`): `tools/library/edit_library.py` değişikliksiz düzenlemeyi
  gerçek girdiyi byte-byte kopyalayarak sonlandırır; gerçek metadata
  değişikliklerinde mevcut section order tablolarını eşit anahtarlar için
  korur. `/Volumes` doğrudan çıktı yolu olarak reddedilir. Metadata değiştiren
  çıktı hâlâ yalnızca adaydır; `tools/library/libdiff.py` farkları görülmeden
  cihaza yazılmamalıdır.
- `c02057e` (`fix: model short-key library refinement`) ile host model,
  Ghidra'da doğrulanan kısa başlangıç anahtarı + eşit kümelerde artan yeniden
  karşılaştırma akışını ve section içi track/önceki-rank sıralamasını izliyor.
  Bu, gerçek metadata değişikliklerinin indeks farklarını azaltmak için yüksek
  getirili bir model düzeltmesidir; yine de cihaz üzerinde yeniden indeksleme
  ile doğrulanmadığı için edit çıktısını release/flash adayı yapmaz.
- `8d5c75a` (`feat: validate metadata library candidates`) ile editor; title,
  artist, album ve genre değerlerinde taşma/NUL girişini reddediyor, UTF-16/
  Latin-1 temsilini koruyor, unresolved location/link tail'i değiştirmiyor ve
  rebuilt section tabloları ile node bağlantılarını doğrulamadan çıktı
  üretmiyor. Kullanım: `python3 tools/library/edit_library.py INPUT OUTPUT
  --set RECORD.FIELD=VALUE`. OUTPUT `/Volumes` altında olamaz.
- `tools/emu/ui_resources.py`: altı corpus'ta doğrulanmış MCG node ve RU3
  group metadata'sı; user-facing isim veya node anlamı uydurulmaz.
- `tools/emu/ui_dispatcher.py`: now-playing op-`0x03` payload'ındaki doğrulanmış
  halfword, byte ve zero-word alanlarını `OpaqueMetadataPayload` olarak trace'e
  taşır; payload framebuffer'a çizilmez ve semantik atanmaz.
- `tools/emu/ui_dispatcher.py`, public SDK ile yapılan operation cross-check
  sayesinde `0x14` değerini arka plan rengi setter'ı, `0x12` değerini mevcut
  arka planla rectangle clear olarak modelliyor. M30 resident consumer ABI'si
  doğrudan çözülmediği için bu eşleme host'ta açıkça cross-build hypothesis
  olarak tutuluyor; M30 color/rectangle byte kanıtı ayrıdır.
- `NowPlaying.paint_dispatch_trace()` gerçek paint sınırını shared scroll
  trace'inden ayırır: üç doğrulanmış `(x,y,w,h)` clear rectangle'ı ve
  `0x1002` artwork control'ü yedi çağrılık sırayla taşır. Rectangle header'ı
  kanıtlanmıştır; payload tail'i opaque kalır. `observed_dispatch` adı artık
  yalnızca `0x1012`/`0x1013` içeren shared scroll zarfını ifade eder.
- `NowPlaying.state_dispatch_trace()` gerçek p-code state probe'unda ayrı ayrı
  çalıştırılan `0x100`, `0x20`, `0x200`, `0x800` ve `0x08` dallarının ham
  operation/identifier sırasını host JSON'daki `state_dispatch` altında taşır.
  Bu yalnızca dispatcher sınırıdır; frame/resource görsel anlamı tahmin
  edilmez.
- `lcd_preview.py` ve `m30_preview_session.py` aynı `state_dispatch` sözleşmesini
  LCD sink ve birleşik session trace'lerine de taşır; doğrulanmış RGB565 bant
  renkleri LCD round-trip testinde korunur.
- `tools/ghidra/run_now_playing_paint_decompile_probe.sh`, `FUN_40154ddc`
  decompile’ındaki dört halfword rectangle yazımını ve `&uStack_18` → op-`0x12`
  çağrısını koruyan dar bir static guard’dır. Probe dump’ındaki header sonrası
  stack byte’ları rectangle alanı kabul edilmez.
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
