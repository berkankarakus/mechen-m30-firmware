# M30 evidence-driven emulator roadmap

Bu liste yalnızca mevcut kanıtın emulator geliştirmesine dönüşebileceği
alanları tutar. Firmware özelliği veya cihazda güvenli patch önerisi değildir.

## Sıradaki uygulanabilir alanlar

| Alan | Mevcut kanıt | Güvenli emulator kapsamı |
|---|---|---|
| FAT32/exFAT | 31 extension slotu, raw playlist maskeleri, reader-type seçimi, directory dispatch ve cluster/block sınırı | explicit-slot filtre, driver high-bit-first mask decoder, reader selector ve depth-8 walker modeli mevcut; callback ABI beklemede |
| Library scan capacity | stock `playlist.ap` RAM arrays and 4,000-record stop | fixed 4,000-record scan boundary modeled; file format and experimental large-library path remain separate |
| MUSIC.LIB layout | 0x200 header, 256-byte records, four section directories, 512-byte sectors, a repeated `<BBHHHHHHH` node shape, identical index-core Ghidra output across all twelve dated releases, reader-side use of `+0xf4..+0xfb` as an eight-byte file key, US212A `cluster_no`/`dir_entry` correspondence, and a real 4,000-record multi-group M30 image | header/section/record-area parser, bounded record codec, decoded little-endian file-key pair, bounded active-record lookup, typed section snapshots, read-only node-to-record span interpretation, fail-closed table/node-link validation, short-key tie-refinement plus nested run/group model, and a copy-safe offline editor; primary location blob, exact duplicate-key rebuild policy, and record links remain unverified |
| SD controller | 512-byte transfer, card detect/capacity yolları | sektör cihazı ve `sector_count * 512` capacity view mevcut; register polling/IRQ beklemede |
| MCG/RU3 UI | altı corpus'ta byte-identical node/group metadata | katalog mevcut; localized name ve node→app eşlemesi beklemede |
| USB host | altı `USBC` marker'ı, READ(10)/WRITE(10), 512-byte transfer birimi, CSW yok | block-request alanları ve SD byte aktarımı modelleniyor; testli 31-byte CBW-shaped educated guess mevcut; CSW, status anlamları ve controller davranışı beklemede |
| USB Audio ring | `usound.drv` 0x1000 ring, wrap ve short-read reset sınırı | gerçek ring bytes okuması ve state ilerlemesi mevcut; PCM/decoder callback semantiği beklemede |
| Key driver | ADC threshold tablosu, normalized event/repeat sınırı | 7-bit threshold classifier, repeat event state ve uygulama key-filter mevcut; fiziksel ADC→key mapping ve timing beklemede |
| Screen-off controls / volume limit / sleep setting | 12 HEX changelog'i, lock-screen control varyantları, `setting.mcg` node `182`, `setting.ap` içindeki 100 üst sınır/clamp akışı ve 2023-02 persistent sleep-timer notu | `WAKE_ONLY` / `MEDIA_KEYS_PASS`, decompile ile desteklenen UI/control-level `VolumeLimitState` ve opaque sleep-setting lifetime modeli mevcut; fiziksel button mapping, DAC ölçeği, timer unit/countdown ve volume setting storage layout beklemede |
| ASRC/EOF | `music.ap` mode-3 advance branch'i, community/V1.101.11 mode-4 delta'sı | mode-3/mode-4 control-flow boundary modeli mevcut; gerçek ASRC/DAC drain ve audible tail ölçümü beklemede |
| `mmm_bp` ring/fade | altı corpus'ta ortak ring/refill ve fade kontrol akışı | wrap-aware source-byte read ve doğrulanmış fade aritmetiği mevcut; DSP/callback semantiği beklemede |
| Metadata reader | community/V1.101.11 0x200 buffer boundary loop'u ve bounded caller'lar | boundary-split source-byte read ve trailing-skip aritmetiği mevcut; source/skip callback ABI'si ve metadata parser beklemede |
| Artwork fallback | community JPEG fallback'in 0xff yolu, 150x150 RGB565 cache sınırı, component/block guard'ları ve cihazdaki sabit 250-sektör `ALBUM.PIC` container'ı | bounded fallback policy, `OK`/`NO` cache record modeli ve ayrı `ALBUM.PIC` container decoder mevcut; JPEG decode, SD/CPU timing ve UI render beklemede |
| Decoder callback | community callback kesin `-1` döndürüyor | fail-closed boundary mevcut; PCM decoder yolu yok |
| Artwork playback | metadata/JPEG fallback yolları statik olarak ayrıştırıldı | placeholder/render state; async decode veya ses gecikmesi modeli yok |
| LCD transfer | `drv_lcd.drv` address-window commands `0x2a/0x2b/0x2c` | bounded RGB565 window-to-framebuffer sink modeled; controller timing, orientation and electrical behavior remain unresolved |
| Resident driver loader | kernel `yqhx` copy/BSS contract | sparse host memory applies declared segments and BSS clearing; entry execution and fixed-ROM handoff remain unresolved |

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
- Persistent play counter; atomic storage/recovery davranışı kanıtlanmadı.
- Yeni EQ preset'leri; menu callback ve coefficient mapping tamamlanmadı.
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
