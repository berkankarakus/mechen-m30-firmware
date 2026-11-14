# M30 özellik yol haritası

Bu liste, MECHEN M30 `V1.101.10` / 2025-06-26 firmware'i için hazırlanmıştır.
“Güvenli” ifadesi cihazda risksiz olduğu anlamına gelmez; değişikliğin sabit
modül boyutlarını koruması, offline doğrulamadan geçmesi ve mümkünse mevcut
topluluk firmware'inde fiziksel cihazda kabul edilmiş olması anlamına gelir.

## Öncelikli ve düşük riskli adaylar

| Özellik | Durum | Neden önce yapılabilir? | Not |
|---|---|---|---|
| Otomatik dosya listesi/index güncellemesini kapatma | İlk geçişte var | Topluluk firmware'inde cihaz üzerinde kabul edilmiş politika değişikliği; `config.ap` ve `udisk.ap` içinde iki kontrollü değişiklik | `Settings -> Update Playlist` ile manuel güncelleme kalır |
| Şarkı sonundaki ses kuyruğunu boşaltma | İlk geçişte topluluk delta'sı içinde var | `V1.101.11` hattında kabul edilmiş; normal EOF'tan önce ASRC/DAC kuyruğunun boşalmasını bekler | Audacity fade-out sonunun kesilmesi için en doğrudan aday |
| Metadata/UTF-8/UTF-16/ID3 güvenlik düzeltmeleri | Toplulukta kabul edilmiş | Sınır kontrolleri ve metin dönüşümü; normal oynatma yolunu mümkün olduğunca koruyor | Ayrı test matrisiyle doğrulanmalı |
| M3U satır sonu ve son satır düzeltmeleri | Toplulukta kabul edilmiş | CRLF, LF ve satır sonu olmayan son pathname destekleniyor | Playlist davranışını iyileştirir |
| CUE Repeat Folder | Toplulukta kabul edilmiş | Sanal CUE track'lerini doğru döngüye sokuyor | CUE dosyalarıyla test edilmeli |
| Uzun listelerde gezinme önbelleği | Toplulukta kabul edilmiş | Görünür satır konumlarını yeniden taramayı azaltıyor | Büyük listelerde UI tepkisini iyileştirir |
| Decimal track-number ve unsigned sıralama düzeltmeleri | Toplulukta kabul edilmiş | `12` değerinin `21` gibi okunması ve `128+` track numaralarının sırası düzeltiliyor | Metadata sıralama için doğrudan faydalı |
| V5 shuffle / shuffle-all / scroll acceleration | Mevcut araştırma projesinde var | QEMU harness'leri ve sabit patch kontrolleri mevcut | Ekran kapalı tuş davranışı zaten çalıştığı için değiştirilmemeli |
| Bitmap tabanlı koyu tema | Düşük firmware riski | `mainmenu.sty`, `common.sty` ve `music.sty` sabit boyutlu kaynaklar değiştirilebilir | Önce kaynak boyutu, palette ve checksum doğrulanmalı |

## Orta riskli ama değerli iyileştirmeler

### Dosya adına göre sıralama — düşük öncelik

İstenen davranış için önerilen politika:

1. Klasör görünümünde dosya adının uzantısız basename'i kullanılmalı.
2. Karşılaştırma case-insensitive yapılmalı.
3. Sayı blokları doğal sıralanmalı: `Track 2` < `Track 10`.
4. Eşitlikte tam pathname ve ardından mevcut copy-order fallback'i kullanılmalı.
5. Metadata görünümleri (Artist/Album/Genre) metadata tabanlı kalmalı.

Kullanıcının cihaz üzerinde çalıştırdığı yardımcı script bu ihtiyacı pratikte
karşılıyor; bu nedenle firmware içindeki browser sıralama patch'i artık düşük
öncelikli. Bu, mevcut topluluk düzeltmelerinin doğrudan bir parçası değildir.
İleride firmware tarafına dönülürse önce PC modeli ve sentetik dosya listesiyle
doğrulanmalı, sonra yalnızca browser/list karşılaştırma fonksiyonlarına patch
yapılmalıdır. Dosya adları değiştiğinde manuel **Update Playlist** gerekeceği
UI'da açıkça gösterilmelidir.

### Daha fazla EQ preset'i

Yüksek örnekleme oranını desteklemeden, mevcut 44.1/48 kHz DSP yolundaki
presets tablosunu genişletmek mantıklı ilk adımdır. Önerilen başlangıç seti:

`Flat`, `Classical`, `Jazz`, `Rock`, `Pop`, `Dance`, `Electronic`, `Hip-Hop`,
`Funk`, `Vocal`, `Acoustic`, `Bass Boost`, `Treble Boost`, `Custom`, `Off`.

`setting.sty` içinde Funk/Hip-Hop gibi kaynak adlarının bulunması, menü metni
tarafının bir kısmının zaten hazır olduğunu gösteriyor; bu, katsayı tablosunun
da hazır olduğu anlamına gelmez. Önce preset seçiminin mevcut katsayı tablosuna
nasıl bağlandığı statik olarak bulunmalı, sonra clipping/headroom ve preset
geçişi testleri eklenmelidir.

### Fade-out için kullanıcı ayarı

ASRC drain düzeltmesi ilk ve güvenli adaydır. Buna ek olarak “end padding” veya
“fade tail guard” gibi yeni bir kullanıcı ayarı önermek için önce sorunun
decoder EOF, ASRC kuyruğu, dosya boyu yuvarlaması veya Audacity export davranışı
olduğu ayrıştırılmalıdır. Körlemesine sabit süre eklemek sonraki parçanın
başlangıcına boşluk koyabilir.

### Albüm kapağı ve FLAC metadata

Topluluk firmware'inde bounded baseline-JPEG fallback ve 8 KiB dışındaki FLAC
metadata taraması kabul edilmiş durumda. Bunlar yararlı, ancak CPU fallback ve
cache okuyucu yolu içerdiği için ilk sade firmware'e ayrı bir patch seti olarak
eklenmeli; oynatma, pause, seek ve kapak gösterimi ayrı ayrı test edilmelidir.

### Kapak görseli ses başlangıcını geciktirmemeli

Bu, ayrı bir performans hedefi olarak ele alınmalı. Topluluk firmware'inin
bounded CPU JPEG fallback'i senkron çalıştığı için bazı kapaklarda ilk oynatma
öncesinde yaklaşık saniyeler mertebesinde bekleme kalabiliyor. En güvenli
tasarım sırası:

1. Decoder ve ilk PCM buffer'ı başlat.
2. Now Playing ekranını kapak placeholder'ı ile hemen göster.
3. Kapak okuma/decode işini küçük parçalara bölerek message pump'a geri dön.
4. Decode bittiğinde yalnızca bitmap alanını yenile; başarısızsa sesi durdurma.
5. Aynı dosya için mevcut cache yolunu kullan; her parça değişiminde yeniden
   tam decode yapma.

Bu değişiklik, “kapak geç gelsin ama şarkı hemen başlasın” politikasını mümkün
kılar. Ancak firmware'in tek CPU/task yapısı nedeniyle gerçek arka plan işinin
nasıl güvenli bölüneceği bulunmalı; körlemesine timeout kısaltmak yeterli değil.
Test matrisi: kapaksız dosya, stock decoder'ın açtığı JPEG, CPU fallback JPEG,
büyük FLAC PICTURE bloğu, pause/seek, hızlı next/prev ve ekran kapalı oynatma.

### Line-out'u headphone-out gibi ses seviyesine bağlama

M30'un ikinci 3.5 mm soketi bir mikrofon/line-in değil, line-out çıkışıdır.
Kılavuzda headphone ve line-out ayrı çıkışlar olarak geçiyor; ayrıca line-out
için `-6 dB` / `0 dB` ve volume synchronization seçenekleri listeleniyor.
Stock kaynaklarda da `s_line_out_type` ve bu iki seviye adı mevcut.

Bu nedenle tamamen imkânsız görünmüyor. Önce şu ayrım yapılmalı:

- **Yalnızca dijital attenuation farkıysa:** line-out'u headphone volume
  register/path'ine bağlamak mümkün olabilir.
- **Ayrı analog line driver veya sabit DAC çıkışıysa:** firmware yalnızca
  dijital seviyeyi değiştirebilir; headphone çıkışıyla elektriksel olarak
  birebir aynı davranış mümkün olmayabilir.

Güvenli patch tasarımı, line-out'u tam headphone davranışına zorlamak yerine
`Variable Line-out` seçeneği eklemek olur. Bunun varsayılanı mevcut sabit
seviyede kalır; kullanıcı açınca volume up/down line-out'u da attenuate eder.
Bir üst sınır ve güvenli açılış seviyesi konulmadan bu seçenek etkinleştirilmemeli:
line-out'a kulaklık takıldığında veya harici amfi yüksek gain'deyken ani yüksek
ses riski var.

İncelenecek yerler: `setting.ap` line-out ayar handler'ı, `music.ap` volume
event path'i ve `drv_dac.drv`/`aud_dev.drv` çıkış seçimi. İlk deney yalnızca
ayar byte'ını gözlemleyen offline patch olacak; donanım ölçümü olmadan line-out
seviyesini zorlayan bir `.HEX` üretmeyeceğiz.

## Mevcut kaynakta izleri bulunan ek fikirler

Stock resource isimlerinde bookmark, resume, sleep timer, playback speed ve LRC
lyrics akışlarına ait girdiler görülüyor. Bu özelliklerin menüde ne kadarının
aktif olduğunu cihaz üzerinde doğrulamak gerekir; ancak en düşük riskli yaklaşım
mevcut akışı değiştirmek yerine sınır durumlarını düzeltmektir.

| Fikir | Beklenen fayda | Risk / yaklaşım |
|---|---|---|
| Lyrics sınır ve zamanlama düzeltmeleri | Previous lyric altında taşmasın; aynı timestamp'te sonraki satır gösterilsin; son lyric gereğinden uzun kalmasın | Toplulukta V1.101.12 kapsamında zaten kabul edilmiş. Ayrı test dosyasıyla kolay doğrulanır |
| Bookmark + resume ergonomisi | Uzun kayıt/podcast/audiobook'ta kaldığı yerden devam; hızlı bookmark menüsü | Mevcut kayıt formatı ve yazma sıklığı incelenmeli; her oynatma saniyesinde karta yazılmamalı |
| Sleep timer seçenekleri | “Parça sonunda”, 15/30/60 dakika ve kapanma öncesi uyarı | Mevcut sleep/shutdown timer kaynakları bulunduğu için yeni scheduler yerine mevcut ayar yolu tercih edilmeli |
| Playback speed preset'leri | Konuşma ve audiobook için 0.75×, 1×, 1.25×, 1.5× gibi hızlı seçim | Resource'ta `play_speed` izi var; codec/DSP'nin gerçekten hız değişimini desteklediği doğrulanmalı |
| 4.000-entry M3U playlist sınırını yükseltme | Büyük playlist'lerde kesilmeyi önler | Whole-card library'den bağımsız ama playlist parser, storage ve UI tüketicilerinin birlikte incelenmesi gerekir |
| Index ilerleme ekranı | Manuel Update Playlist sırasında yüzde, geçen süre ve yaklaşık kalan süre | Önce yalnızca gösterge; iptal/rollback daha sonra. Uzun taramada watchdog ve message pump korunmalı |
| Index “dirty” göstergesi | Kullanıcı ne zaman manuel Update Playlist gerektiğini görür | Tam kart hash'i pahalı olabilir; önce güvenli bir “son güncelleme tarihi / manuel güncelleme gerekli” durumu düşünülmeli |
| Hızlı alfabetik atlama | Binlerce dosyada yukarı/aşağı ile uzun süre ilerlemeden A–Z / 0–9 sıçrama | Browser arama/pozisyon cache'iyle birleştirilmeli; mevcut uzun-list optimizasyonundan sonra yapılmalı |
| Playlist/favorite yönetimi | Seçili dosyayı doğrudan favoriye veya kullanıcı playlist'ine ekleme/çıkarma | `favorite position zero` düzeltmesinden sonra daha güvenli; yine de playlist kayıtlarının bozulma senaryosu test edilmeli |
| Ayarların yedeklenmesi | EQ, repeat, resume ve UI tercihlerini kartta küçük bir ayar dosyasına almak | Firmware'in mevcut settings commit/restore yolunu bulmadan storage I/O eklenmemeli |

Özellikle lyrics ve sleep timer, büyük bir mimari değişiklik gerektirmeden
değer sağlayabilecek iki alan. Bookmark/resume ise kullanıcı deneyimi açısından
çok yararlı, fakat flash/SD yazma sıklığı ve ani güç kesintisi davranışı çözülmeden
“güvenli” kategorisine alınmamalı.

## Şimdilik ertelenmesi gerekenler

| Özellik | Gerekçe |
|---|---|
| Gerçek gapless playback | İkinci kaynak veya atomik PCM handoff gerekiyor; yalnızca DAC'ı açık tutmak yetmiyor |
| 48 kHz üzeri EQ | DSP RAM/cycle bütçesi ve katsayı yükleme yolu araştırılmalı |
| 48 kHz üzeri FLAC kapısını zorlamak | Kart/model capability initializer'ı bulunmadan codec kararlılığı garanti edilemez |
| Yapılandırılabilir kilitli tuşlar | Ekran kapalı tuş yolunda process-wide politika sahibi bulunmalı; storage I/O tehlikeli |
| 24k+ kütüphane sınırını daha da büyütmek | Mevcut whole-card builder zaten deneysel ve uzun süren bir işlem |
| Tüm Rockbox UI/OS portu | Bu, mevcut patch yaklaşımından ayrı bir platform portu olur |

## Önerilen entegrasyon sırası

1. Manuel index politikası + ASRC drain + kabul edilmiş metadata/playlist/CUE
   düzeltmeleri.
2. Dosya adı doğal sıralaması; önce PC modeli, sonra offline firmware testleri.
3. Mevcut örnekleme oranlarında EQ preset tablosu.
4. Bitmap tema ve list/now-playing UI düzenlemeleri.
5. Lyrics, sleep timer ve playlist sınırı gibi mevcut kaynakta izi olan küçük
   iyileştirmeler.
6. Her grubu ayrı `.HEX` üretip, mümkünse cihaz üzerinde tek değişkenli test.

İlk geçişteki `MECHEN_M30-first-pass.HEX`, V5 tabanını ve `V1.101.11` müzik
delta'sını birlikte içerir. Bu nedenle yukarıdaki özellikleri tek tek
izole etmek için sonraki adımda “minimal güvenli profil” ve “geniş özellik
profili” olmak üzere iki ayrı build üretmek daha doğru olacaktır.

## Kaynaklar

- [Averagenative reverse-engineering projesi](https://github.com/averagenative/mechen-m30-firmware)
- [Mechen M30 community firmware](https://github.com/dev-zetta/mechen-m30-community-firmware)
- [M30 kılavuzu — EQ açıklaması](https://manuals.plus/ae/1005006075793786)

