# M30 evidence-driven emulator roadmap

Bu liste yalnızca mevcut kanıtın emulator geliştirmesine dönüşebileceği
alanları tutar. Firmware özelliği veya cihazda güvenli patch önerisi değildir.

## Sıradaki uygulanabilir alanlar

| Öncelik | Alan | Bir sonraki kanıt/çıktı |
|---|---|---|
| P0 | Klasör marquee veri akışı | 50-byte slot, nonzero browser context, gerçek `0x14` row-provider → `0x1c` converter zinciri ve directory callback'in üç dalı dinamik doğrulandı; row kaydının `+0x02` little-endian alanının converter'a gittiği kanıtlandı; sırada bu alanın fsel/list-state içindeki semantik türünü ayırmak var |
| P0 | Now-playing UI | initial + metadata/transport/status state branch'leri dinamik doğrulandı; host resource renderer → LCD command/pixel sink hibriti mevcut; sırada gerçek AP payload'larının resource/font consumer'larına bağlandığını kanıtlamak var |
| P1 | MUSIC.LIB sort/index | stock MIPS/QEMU pass'leri seeded-rank koşusunda çalışıyor; 56 kayıtlık ARTIST tie grubunda önceki ALBUM sırası tek başına cihaz sırasını açıklamadı (0/56 eşleşme). Converter ve eşit anahtar sıralaması çözülmedi; Indelible/Indelible’ node-count farkı da açık. Scratchpad QEMU koşusunu repo içinde yeniden üretilebilir kıl ve gerçek dönüştürücü kanıtı ara |
| P1 | USB-DAC | Descriptor yaması, seri status tamponu ve boş/başarılı seri dalları, hız kontrolü, Feature Unit mute/volume/range ve SET_INTERFACE gerçek MIPS16 p-code probe'ları host modelinde. Sırada modül `0x10` sonrasında PCM/DAC sahipliğini çözmek |
| P1 | DAC caller/codec register | `drv_dac.drv` byte-transfer sınırını koru; caller ve register tablosu bulunmadan volume/fade patch’i üretme |
| P1 | EQ'nin duyulabilir yolu | Deneysel Custom eğri cihazda Off'tan farklı duyulmadı; dört overlay kendi tabanındaki `0x38`-byte kalıcı bloğun `+0x2c..+0x32` alanını Custom kaynağı olarak kullanıyor. `config.ap` bunu açılışta `0x9fc1a19c`'ye kopyalıyor; gerçek slider yazarı bulunamadı. Bilinen `0x8000` Custom olayı payload type `3` ile `FUN_48ad47b0` tarafından reddediliyor. `aud_dev` bank/function eşlemesi ve ROM dispatch hâlâ aday/çıkarım. Sıradaki iş doğru slider sahnesi/callback'ini bulmak; sabit eğriyi değiştirme |
| P1 | QEMU/exception | sabit ROM exception/provider bulunursa guest boundary’yi genişlet; bulunmazsa mevcut fail-closed probe’ları koru |
| P2 | Playback | ASRC/EOF, fade-out ve gapless için gerçek decoder/ASRC/DAC drain kanıtı ara |
| P3 | Metadata ve sayaç | MUSIC.LIB writer/recovery ve kalıcı sayaç formatını çöz; offline düzenleyiciyi cihaz eşdeğeri kabul etme |

## Dinamik inceleme havuzu

Statik decompile’dan ayrılan bu işler, gerçek AP/driver fonksiyonlarını
Ghidra p-code veya mevcut QEMU leaf harness’lerinde yürütür. Her satırda
resident/ROM/peripheral sınırı stub’lanır ve gözlenen callback/byte/state
değeri kaydedilir; bu sonuçlar tam cihaz boot’u sayılmaz.

| Öncelik | Alan | Dinamik deney | Beklenen yüksek getirili çıktı |
|---|---|---|---|
| P0 | Browser/fsel | Gerçek row provider + fsel/list-state kaynağını scene caller’dan yürüt | 20-byte kaydın `+0x02` alanı doğrulandı; playlist/directory semantik türü ve güvenli isim patch noktası hâlâ açık |
| P0 | Now-playing UI | `music.ap` çizim girişini gerçek `music.sty`/font/resource pointer’larıyla çalıştır; LCD sink’ine trace al | ikon hizası, üst/alt bant, marquee clipping ve gecikmenin gerçek çağrı sırası |
| P0 | Playback/EOF | `music.ap` → `mengine.ap` → `mmm_bp` çağrılarını PCM/read/EOF callback stub’larıyla yürüt | fade-out kesilmesinin decoder EOF mu, ASRC drain mi, DAC tüketimi mi olduğu |
| P1 | USB-DAC | Gerçek `usound.drv` producer/consumer zincirini exception ve DAC sink ile birleştir | module `0x10` sonrasında PCM sahibinin ve DAC’a giden byte akışının kanıtı |
| P1 | Upgrade | Gerçek `setting.ap` yolu 155 adımda stub UI sınırına kadar yürüdü; `0x85`, `0x100a`, status ve 250-byte payload yakalandı. Şimdi `0x48554680` payload'unu ve framework consumer'ını çözerek ekrandaki dikdörtgene bağla | screen selection ve preflight trace-only; prompt geometrisi, flash/reboot ve indirect callback dönüşleri çözülmemiş kalır |
| P1 | MUSIC.LIB metadata | gerçek writer/reader fonksiyonlarını RAM-backed `MUSIC.LIB` üzerinde yürüt | record alanları, tie-break ve sayaç için güvenli kalıcı alan adayı |
| P2 | Key/screen-off | gerçek key/common-filter path’ine event dizileri enjekte et | wake/media-key ayrımı, debounce/repeat state ve ekran açılma nedeni |
| P2 | SD/index trigger | card/USB/file-system callback’lerini gerçek scan caller’larına bağla | indekslemenin kart takma, boot ve USB event’lerinden hangisiyle tetiklendiği |

## Ara verilen noktadaki TODO

Bu liste bir sonraki oturumun başlangıç noktasıdır. Sıra, getirisi ve kanıt
kapısı dikkate alınarak yazılmıştır; hiçbir madde tek başına cihazda flash
denemesi anlamına gelmez.

1. **M30 sabit-ROM exception/dispatch yolunu daralt:** `ker_xsys` içindeki
   `0xbfc34074 -> 0xbfc06d6c` handoff'u, mevcut boot-ROM/ROM kanıtı veya yeni
   salt-okunur cihaz gözlemi olmadan tamamlanmış kabul etme. Önce yeni bir
   extracted üye içinde handler/provider kopyası var mı tekrar doğrula; yoksa
   `module=0x10` etkisini fail-closed bırak.
2. **DONE — upgrade akışını trace-only modelle:** doğrulanmış beş seçenekli
   ekran, `FUN_40014c30` selector'ları, decrypt/search metinleri ve
   `FUN_bfc37408` ilerleme normalizer'ı `tools/emu/upgrade_flow.py` ve
   `tools/emu/upgrade_ui.py` içinde sınırlandırılmış olarak taşınıyor.
   `run_upgrade_ap_corpus_probe.sh` bu ekran/selector sınırını on iki dated
   imajda doğruluyor. Indirect return değerleri çözülmeden `flash`, `reboot`
   veya başarılı update olayı üretilmiyor.
3. **Now-playing UI adayını paketlemeden önce delta kapısını güçlendir:**
   initial paint ve `0x100`/`0x20`/`0x200`/`0x800` state dalları üç firmware
   ailesinde dinamik doğrulandı. Sıradaki iş gerçek resource/font/LCD sink
   çağrılarını bağlamak; yalnızca `music.sty`/gerçek kaynak üyeleri üzerinde
   değişen byte'ları, boyutları, checksum'ları ve rollback kaynağını
   karşılaştır; host PNG'sini firmware çalışması gibi raporlama.
4. **QEMU kapsamını gerçekçi şekilde genişlet:** sabit exception handler veya
   ROM kanıtı gelirse CP0/stack handoff ve overlay-entry probe'u ekle; bu kanıt
   yokken tam ATJ2127 boot/machine modeline yatırım yapma.
5. **Ses tarafını sınırda tut:** `usound` producer/consumer ve DAC byte
   transferi geçişlerini birlikte trace et; decoder/DSP/ASRC/DAC'ın audible
   etkisi kanıtlanmadan USB-DAC, gapless veya fade-out sonucu çıkarma.
6. **EOF dinamik probe sınırı:** `FUN_40494e94` çevresindeki bank sonu
   kod/veri örtüşmesi nedeniyle callback literal'lerini güvenle RAM'e
   yönlendiren bir p-code probe kurulamadı. Mode-4 sonucu bu nedenle mevcut
   statik delta ile sınırlı; yanlış patch üretme.
7. **Düşük öncelikli işler:** MUSIC.LIB metadata yeniden kurma/tie-break,
   sayaç kalıcılığı, yeni EQ presetleri ve filename sıralama değişikliği;
   bunlar mevcut kanıtla cihaz eşdeğeri kabul edilemez.

## Önceliklendirilmiş QEMU/exception TODO

Bu sıra, gerçek firmware kontrol akışına en çok yaklaşan ve cihazı
değiştirmeden ölçülebilen işlerden düşük getirili tam donanım emülasyonuna
doğru gider. Her madde geçerli firmware corpus'unda tekrarlanabilir bir
PASS/FAIL koşuluyla kapatılacak.

| Öncelik | İş | Neden şimdi | Kapanış ölçütü |
|---|---|---|---|
| P0 | **DONE:** Gerçek `FUN_bfc31654` ring consumer’ını `break 0` modül çağrısıyla çalıştır | `0xbfc326a9` QEMU’da modül kimliği `0x10` olarak yakalanıyor | lineer ve wrap çağrılarında gerçek trap, iki modül çağrısı ve dört argüman kaydı altı corpus’ta doğrulandı |
| P0 | **DONE:** LCD resident komut/data ve window akışını QEMU’da çalıştır | `drv_lcd.drv` fonksiyonları ve `0x2a/0x2b/0x2c/0x36` akışı ekran sink’ine bağlandı | gerçek window/orientation akışı ve komut/data izleri altı corpus’ta geçti |
| P1 | MIPS16 `break 0` modül dispatch’ini resident exception yoluna bağla | zarf çözüldü, fakat modül `0x10` servisinin sabit-ROM etkisi bilinmiyor | exception handler veya kernel kaynaklı dispatch tablosu modül ve dönüş sözleşmesini kanıtlar; PCM/DAC sonucu iddia edilmez |
| P1 | `drv_dac.drv` gerçek byte-transfer fonksiyonlarını sentetik GPIO context ile çalıştır | DAC sürücüsü ortak ve küçük; register anlamı bilinmese de bit/byte transfer sınırı ölçülebilir | **DONE:** six corpus QEMU probe executes real 8-bit transmit, two-byte send, and all-high/all-low receive boundary; electrical/codec semantics remain unresolved |
| P1 | `usound.drv` producer/consumer ring ilişkisini sınırla | QEMU iki firmware ring adresini `0x80061000`'da alias'lıyor; `0x10..0x1f` bytes producer kopyasından consumer callback source'una doğrulandı | **PARTIAL:** synthetic alias altında state + kaynak baytları PASS; doğal ring bağlantısı ve callback destination copy kanıtlanmalı; ROM service/PCM/DAC ayrı kalır |
| P2 | Kernel loader/overlay entry ve exception handoff probe’u | YQHX header/segment sözleşmesi biliniyor; `kernel.drv` içindeki adaylar resident-table helper, gerçek loader ve sabit ROM handoff bilinmiyor | gerçek loader çağrısı ve giriş/çıkış CP0/stack sözleşmesi kanıtlanır |
| P3 | Tam ATJ2127 QEMU machine / boot | upstream model ve ROM/peripheral kodu yok; maliyeti yüksek, şu anki kanıtı az artırır | yalnızca ATJ2127 MMIO/ROM kaynağı veya cihaz dump’ı gelirse başlatılır; mevcut haliyle ertelenir |

| Alan | Mevcut kanıt | Güvenli emulator kapsamı |
|---|---|---|
| FAT32/exFAT | 31 extension slotu, raw playlist maskeleri, reader-type seçimi, directory dispatch ve cluster/block sınırı | explicit-slot filtre, driver high-bit-first mask decoder, reader selector ve depth-8 walker modeli mevcut; callback ABI beklemede |
| Library scan capacity | stock `playlist.ap` RAM arrays and 4,000-record stop | fixed 4,000-record scan boundary modeled; file format and experimental large-library path remain separate |
| MUSIC.LIB layout | 0x200 header, 256-byte records, four section directories, 512-byte sectors, a repeated `<BBHHHHHHH` node shape, identical index-core Ghidra output across all twelve dated releases, reader-side use of `+0xf4..+0xfb` as an eight-byte file key, US212A `cluster_no`/`dir_entry` correspondence, and a real 4,000-record multi-group M30 image | header/section/record-area parser, bounded record codec, decoded little-endian file-key pair, bounded active-record lookup, typed section snapshots, read-only node-to-record span interpretation, fail-closed table/node-link validation, short-key tie-refinement plus nested run/group model, and a copy-safe offline editor; primary location blob, exact duplicate-key rebuild policy, and record links remain unverified |
| SD controller | 512-byte transfer, card detect/capacity yolları | sektör cihazı ve `sector_count * 512` capacity view mevcut; register polling/IRQ beklemede |
| MCG/RU3 UI | altı corpus'ta byte-identical node/group metadata | katalog mevcut; localized name ve node→app eşlemesi beklemede |
| USB host | altı `USBC` marker'ı, READ(10)/WRITE(10), 512-byte transfer birimi, CSW yok | block-request alanları ve SD byte aktarımı modelleniyor; testli 31-byte CBW-shaped educated guess mevcut; CSW, status anlamları ve controller davranışı beklemede |
| USB Audio ring | `usound.drv` 0x1000 ring, wrap/short-read sınırı, 0x6e40 producer ring'i ve DMA tamamlanma doluluk eşikleri | gerçek ring okuma/yazma state'i ile `FUN_bfc3125c` post-subtraction clock bitleri host modelinde; PCM/decoder ve fiziksel DMA callback semantiği beklemede |
| USB Audio descriptors | stock `usound.drv` MIPS16 `FUN_bfc31f94` p-code; VID/PID, UTF-16LE strings, interface flag, 16/48 and 24/96 descriptor fields | dört sentetik config vakasıyla hash-pinned real-code probe mevcut; ROM config getter and USB hardware behavior remain outside scope |
| Key driver | ADC threshold tablosu, normalized event/repeat sınırı ve changelog'daki ekran-kapalı politikaları | ADC→repeat→application-filter host session, 512 gerçek-MIPS classifier matrix'i ve iki ekran-kapalı politikası mevcut; B+8..B+15 initializer'ı, fiziksel ADC→key mapping ve gerçek zamanlama beklemede |
| Screen-off controls / volume limit / sleep setting | 12 HEX changelog'i, lock-screen control varyantları, `setting.mcg` node `182`, `setting.ap` içindeki 100 üst sınır/clamp akışı ve 2023-02 persistent sleep-timer notu | `WAKE_ONLY` / `MEDIA_KEYS_PASS`, decompile ile desteklenen UI/control-level `VolumeLimitState` ve opaque sleep-setting lifetime modeli mevcut; fiziksel button mapping, DAC ölçeği, timer unit/countdown ve volume setting storage layout beklemede |
| ASRC/EOF | `music.ap` mode-3 advance branch'i, community/V1.101.11 mode-4 delta'sı | mode-3/mode-4 control-flow boundary modeli mevcut; gerçek ASRC/DAC drain ve audible tail ölçümü beklemede |
| `mmm_bp` ring/fade | altı corpus'ta ortak ring/refill ve fade kontrol akışı | wrap-aware source-byte read ve doğrulanmış fade aritmetiği mevcut; DSP/callback semantiği beklemede |
| Metadata reader | community/V1.101.11 0x200 buffer boundary loop'u ve bounded caller'lar | boundary-split source-byte read ve trailing-skip aritmetiği mevcut; source/skip callback ABI'si ve metadata parser beklemede |
| Artwork fallback | community JPEG fallback'in 0xff yolu, 150x150 RGB565 cache sınırı, component/block guard'ları ve cihazdaki sabit 250-sektör `ALBUM.PIC` container'ı | bounded fallback policy, `OK`/`NO` cache record modeli ve ayrı `ALBUM.PIC` container decoder mevcut; JPEG decode, SD/CPU timing ve UI render beklemede |
| Decoder callback | community callback kesin `-1` döndürüyor | fail-closed boundary mevcut; PCM decoder yolu yok |
| Artwork playback | `FUN_40154ddc` koşullu dalında artwork wrapper'ı, `0x311 PLAY` wrapper'ından önce çalışabiliyor; gerçek p-code koşusunda ayrı event/player flag'leriyle sıra doğrulandı | flag producer/ilk-play ilişkisi, gerçek decode süresi ve ses çıktısına etkisi hâlâ bilinmiyor; tam çağrı-tetikleyici zinciri gerekli |
| LCD transfer | `drv_lcd.drv` address-window commands `0x2a/0x2b/0x2c` | bounded RGB565 window-to-framebuffer sink and real-code QEMU window/orientation probe; controller timing, MMIO meanings and electrical behavior remain unresolved |
| YQHX header/materializer | kernel `yqhx` header, segment ve BSS alanları | sparse host memory applies declared segments and BSS clearing; gerçek resident loader, entry execution ve fixed-ROM handoff remain unresolved |

## MUSIC.LIB TODO

- Exact device sort/tie-break policy'yi, aynı görünen metadata anahtarlarını
  farklı firmware sürümleri veya kontrollü kart görüntüleriyle karşılaştır.
- `tools/library/edit_library.py` yalnızca offline aday üretir: değişikliksiz
  düzenleme gerçek M30 görüntüsünü byte-byte kopyalar; metadata değişikliğinde
  mevcut section sıralarını tie-break olarak korur ama yeniden kurulan düğüm ve
  grup tabloları henüz cihazla eşdeğer kabul edilmez. Başlık, sanatçı, albüm ve
  tür alanları taşma/NUL kontrolüyle düzenlenir; location/link tail korunur ve
  dört section yapısı doğrulanır. Çıktı `libdiff.py` ile incelenmeden flash
  adayı değildir.
- `0xa9..0xf1` primary location blob'unu source path/cluster değişimleriyle
  çöz; decoded `cluster_no`/`dir_entry` çiftini gerçek directory dump ile
  bağımsız doğrula.
- `0xfc..0xff` record predecessor/successor alanlarının gerçekten hangi
  consumer tarafından okunduğunu trace et.
- Reference `5` node/group table'ının local writer'daki deepest-level index
  davranışını gerçek multi-group M30 görüntüsüyle doğrula; level-zero artist
  group scratch akışını ayrıca takip et.

## Bilinçli olarak ertelenenler

- Tam ATJ2127 boot ve upstream QEMU machine model.
- Gerçek LCD, DAC, codec/DSP ve DMA davranışı.
- Filename natural sort için caller-side mask ve browser state modeli.
- Persistent play counter; MUSIC.LIB içinde güvenli boş alan yok. 8-byte
  `cluster_no`/`dir_entry` anahtarı sıralamada kalır ama taşınabilir dosya kimliği
  değil; sidecar için digest + normalize edilmiş yol düşünülüyor. İlk journal
  prototipinde bozuk `MOVE` atlanınca sonraki `SET` eski yolu yeniden
  gösterebiliyor; fail-closed recovery düzeltilip doğrulanana kadar güvenli
  sayılmayacak.
- Yeni EQ preset'leri: mevcut selector zinciri `0..6` built-in ve `7` Custom olarak kanıtlandı; 7×7 katsayı bloğu yerel stok/resmî/topluluk kopyalarında aynıdır. Yeni seçim için AP callback/menü ağacı ve engine katsayı eşlemesini genişletmek gerekir. Katsayı tablosu sonrasındaki sıfırlar boş patch alanı sayılmaz; duyulur sonuç ve güvenli paketleme kanıtı yok.
- Gerçek gapless playback ve ASRC/DAC audible tail ölçümü.

Her yeni satır için önce ilgili `findings-*.md` dosyası güncellenir; ardından
yalnızca doğrulanmış bölüm testli host modeline alınır.

## Kanıt gelmeden teslim edilemeyecek sonuçlar

Bu çalışma ağacındaki mevcut binary, QEMU ve host kanıtı aşağıdaki sonuçları
güvenilir biçimde üretemez. Bunlar eksik bir host modeliyle tamamlanacak işler
değil; yeni firmware corpus'u, donanım gözlemi veya cihaz testi gerektiren
sınırlardır:

- M30 firmware'ini gerçekten boot eden tam ATJ2127/QEMU makinesi ve overlay
  loader'ı;
- decoder, DSP, ASRC, DAC, codec register'ları ve audible fade/gapless playback
  davranışı;
- fiziksel ADC tuşlarının gerçek isim, debounce ve repeat zamanlaması ile LCD
  panel/elektriksel aktarım davranışı;
- MCG/RU3 localized name ve node-to-application eşlemesinin kesin anlamı;
- eksik resident/provider bankalarının gerçek çağrı ABI'leri ve bunların
  çalıştırılması;
- cihaz üzerinde boot, playback, tuş, ekran ve güvenli firmware release
  kabulü;
- firmware, resource dump, decompile veya türetilmiş patch'lerin public
  dağıtımı için hukuki/telif temizliği.

Bu sınırlar çözülmüş gibi görünmesi için host modeline varsayımsal davranış
eklenmez. Yeni kanıt geldiğinde önce ilgili bulgu belgesi, sonra fail-closed
model ve test güncellenir.
