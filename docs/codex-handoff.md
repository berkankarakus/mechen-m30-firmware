# Codex handoff: M30 keşif bulguları ve açık işler

Bu belge keşif aşamasının sonucunu ve Codex'in geliştirme yaparken
kullanacağı bulguları toplar. Burada yazan hiçbir şey cihazda test edilmiş
sayılmaz; "doğrulandı" yalnızca offline (hash, unpack, byte karşılaştırma)
doğrulaması demektir.

## Ortam

| Ne | Yol |
|---|---|
| Repo | `/Users/berkan/Projects/mechen-m30-firmware` (git yerel kimliği `berkankarakus`) |
| Docker imajı | `m30-build` (Fedora, `mips64-linux-gnu-gcc` 16.2.1, `qemu-mipsel-static`, Rockbox `atjboottool`). Tanım: `/Users/berkan/Projects/m30-docker/Dockerfile` |
| Stock V1.101.10 | `/Users/berkan/Projects/m30-inputs/stock/MECHEN_M30.HEX` |
| Community V1.292.00 | `/Users/berkan/Projects/m30-inputs/community/MECHEN_M30.HEX` |
| Aday (`red-back`) | `MECHEN_M30-community-v1.292-red-back.HEX` (repo kökünde, `.gitignore` dışında tutulur) |
| Açılmış member'lar | `/Users/berkan/Projects/m30-work/{stock,community,cand}/fw/` |
| Referans kaynak (Actions SDK) | `/Users/berkan/Projects/m30-inputs/ref/PD196` |

Docker notu: imaj amd64, ana makine arm64; emülasyonla çalışır. `docker run`
sırasında `--platform linux/amd64` verme (imaj bulunamıyor hatası veriyor);
parametresiz çalışır ve yalnızca platform uyarısı basar. Aday HEX'i ayrı bir
`-v` ile değil, repo dizinini salt-okunur bağlayarak ver (iç içe mount
başarısız oluyor).

Unpack komutu (her HEX için):

```sh
atjboottool -c --fwu -o dec.bin MECHEN_M30.HEX
atjboottool -c -o afi/ dec.bin
atjboottool -c --fw -o fw/ afi/FWIMAGE.FW
```

## Doğrulanan girdiler

| Dosya | SHA-256 |
|---|---|
| Stock | `6c7e27c8c90c4942664d66a0d6c9f9e48f8d3bc7d2d24223568255e233551258` |
| Community V1.292.00 | `5e17d883f697a67d4face6f624ddc30952c5542c918b219be974bf380383ed2c` |
| Aday | `f78bdf3bb9c2b29f3a9162150cf028aeef3d3f693a9230dc0fc7ee13d90b736c` |

Üç imajda da AFI 19/0 ve FW 201/0 (ok/mismatch), 99 member.
Stock ile community arasında farklı member'lar: `browser.ap`, `config.ap`,
`mainmenu.ap`, `mengine.ap`, `music.ap`, `playlist.ap`, `setting.ap`,
`udisk.ap`. Community ile aday arasında: `mengine.ap`, `music.sty`,
`setting.sty`.

## Kullanıcı kararları

- Önceki tuş: her basışta parçanın başına dönmesi yeterli. Başlangıçtayken
  ikinci basışta önceki parçaya geçme eklenmeyecek.
- Dört playback ikonu cihazda denendi (kullanıcı beyanı). Dokümanlarda
  "donanımda denendi" olarak işaretlenecek.
- Upgrade metni: kabul edilebilir, ancak ilk satır sola yaslı görünüyor,
  ikinci satır ortalı. İlk satırın da ortalanması isteniyor.
- Commit ve push yalnızca açık onayla yapılır. Force push yok.

## Upgrade metni: hizalama keşfi

### Doğrulanan bulgular

- `tools/patch_upgrade_prompt.py` `setting.sty` içinde 4 kopyayı değiştiriyor:
  `0x1bfc`, `0x3ac8`, `0x57f0`, `0x7448`. Eski ve yeni metin 26 karakter
  (52 bayt UTF-16LE); ardından 4 bayt sıfır (2 terminator karakteri) gelir.
- Bu 4 kopya 4 farklı dil tablosundadır. Komşu string'lere göre `0x57f0`
  İngilizce tablodadır (`Software version:[%s]` yanında); `0x1bfc` Çekçe,
  `0x3ac8` Yunanca, `0x7448` Danca tablodadır. Yani yama yalnızca İngilizce
  arayüzde ve bu üç dilde etkilidir. Diğer dillerdeki upgrade metinleri
  başka biçimde saklanıyor ve bu yama onlara dokunmuyor (keşfedilmedi).
- String tablosunda string başına hizalama bayrağı yok. Metinler sıfır
  sonlandırılmış paketli UTF-16LE dizileridir; hizalama string'de değil,
  onu çizen widget/scene kaydındadır.
- `[%s]` literal metin değildir; cihaz çalışma anında dosya adını koyar.
  Kullanıcı ekranda sorun görmediği için değiştirilmedi.
- Referans SDK kaynağında (`ref/PD196`) M30'un upgrade onay ekranı ve
  dialog çizim kodu yok; yalnızca `DIALOG_MSG/ASK` scene kimlikleri
  (`case/inc/common_sty.h`) bulundu.

### Kök neden (referans SDK + M30 `drv_ui.drv` statik okuması; cihazda doğrulanmadı)

Referans Actions UI sürücüsü kaynağı (`ref/PD196/case/drv/ui/`,
US212A, 2011-2012) dialog açıklamasını şöyle çiziyor:

- `bank_b_ui_show_dialogbox.c` `show_dialogbox_desc()` metni tek bölgeye,
  `DISP_LONGSTR_MULTI_ROW | DISP_DIVIDE_WORD_ENABLE` ve dialog `attrib` bit
  2-3'e göre hizalama (`DISP_ALIGN_MEDIACY` = ortala) ile çiziyor.
- `bank_b_ui_putstring.c` her satır için önce
  `get_string_length(metin, bölge_genişliği)` çağırıyor ve
  `cur_region.x = x + (genişlik - getlen_result.true_length) / 2` ile
  ortalıyor. Metin bölgeye sığmıyorsa `true_length`, **sözcük bölmeden
  önceki** ham karakter sığma genişliğidir; bölgeyi neredeyse doldurur.
- Ardından `DISP_DIVIDE_WORD_ENABLE` dalı `get_text_line()` ile satırı sözcük
  sınırında daha kısa keser, ama `x` zaten eski (geniş) genişlikle
  hesaplanmıştır. Sonuç: kırılan ilk satır neredeyse `x = bölge başı`
  konumundan çizilir, yani sola yaslı görünür.
- Tamamen sığan son satır (`[dosya adı]`) `str_len <= genişlik` dalına
  girer ve doğru ortalanır.

M30 ikilisinde karşılığı (Ghidra, `drv_ui.drv` düz haritalama, bkz. "Ghidra
durumu"): `FUN_30008600` çok satırlı `put_string`'dir. `get_string_length`
çağrısı (`_UNK_3000891c`) `uStack_30` (= `true_length`) ve `uStack_24`
(= `str_len`) üretir. Metin bölgeden uzunsa (`param_2[2] < uStack_24`) ve
mod `(param_3 & 0xc) == 4` (ortala) ile `(param_3 & 0xf0)` 0x10 veya 0x20
(NO_RECT / MULTI_ROW) ise `x = (param_2[2] - uStack_30) / 2 + param_2[0]`
hesaplanır. Sonra `param_3 & 0x1000` (DIVIDE_WORD) dalı `get_text_line`
karşılığını (`_UNK_30008934`) çağırıp satırı kısaltır, ama `x` yeniden
hesaplanmaz. Yani referans kaynakla aynı yapı M30 derlemesinde de var.

Satır sonu: `FUN_300007c4` UTF-16 karakter sınıflandırıcısıdır. `0x0000` →
EOF, `0xfeff` → Unicode bayrağı, `0x000a` → satır sonu (2 bayt), `0x000d` ve
`0x000d 0x000a` → satır sonu (2 / 4 bayt). 8-bit karşılığı `FUN_3000083c`.
Yani `0x000a` UTF-16 string'lerde satır sonu olarak tanınıyor.

Bu, kullanıcının gözlemiyle birebir uyuşuyor: ilk satır sola yaslı, ikinci
satır ortalı. Yani sorun metnin kendisinde değil, sürücünün sözcük-bölmeli
satırlarda `x` hesabındaki hata (yazılım kusuru). `common.sty` içindeki
hizalama bayrağı büyük olasılıkla zaten "ortala".

Çözüm adayı (yalnızca `setting.sty` metni, aynı uzunluk): satır sonu
karakteri sürücüde tanınıyor (`bank_b_ui_get_text_line.c`: `0x0a`, `0x0d`,
`0x0d 0x0a` → `CHAR_LR`). `get_string_length` satır sonunda durduğu için
`true_length` gerçek satır genişliği olur ve ilk satır doğru ortalanır.
`Confirm upgrade file: [%s]` içindeki boşluğu (UTF-16LE `20 00`) `0a 00` ile
değiştirmek uzunluğu 52 bayt olarak korur.

Riskler ve doğrulanmamış varsayımlar:

- Satır sonu tanıma ve `x` hesabı M30 `drv_ui.drv` içinde statik olarak
  doğrulandı. `get_string_length`'in (`_UNK_3000891c`) satır sonunda gerçekten
  durup `true_length`'i satır sonuna kadar ölçtüğü ise yalnızca referans
  kaynaktan çıkarıldı; bankalar arası çağrı hedefi çözülemediği için ikilide
  doğrulanmadı.
- Aynı string başka bir ekranda tek satırlık widget'ta da kullanılıyorsa
  `0x0a` orada kutu/boşluk glifi olarak görünebilir. String id'nin kullanıldığı
  tüm yerler henüz bulunmadı.
- `%s` yer tutucusunun nerede genişletildiği (satır kırılmadan önce mi sonra mı)
  bilinmiyor. `[%s]` önceden genişletiliyorsa dosya adı uzunsa üçüncü satır
  oluşabilir.
- Boşluk yerine yeni satır yazmanın `0x0d`/`0x0a` seçimi cihazda denenmeli.

### Önerilen sonraki adımlar (Codex için)

1. `drv_ui.drv` içinde `show_string` benzeri satır çizim fonksiyonunu bulun
   (aşağıdaki "Ghidra durumu" bölümüne bakın) ve `x` hesabının referans
   koddaki gibi `true_length` kullandığını doğrulayın.
2. `Confirm upgrade file:` + `0x000a` + `[%s]` yaması için
   `tools/patch_upgrade_prompt.py` içinde yeni `NEW` dizisini hazırlayın.
   Eski/yeni byte dizisini, 4 offset'i ve SHA-256'ları kaydedin. Boyut ve
   member sayısı değişmemeli; `common.sty` değişmez.
3. Önce yalnızca İngilizce kopyayı (`0x57f0`) yamalayıp cihazda deneyin.
   Üç diğer dilin kopyaları kullanıcı bu dilleri kullanmıyorsa dokunulmadan
   kalabilir.
4. Yeni satır işe yaramazsa alternatif: tüm metin tek satıra sığacak şekilde
   kısaltmak (ör. `Upgrade: [%s]`). Bunun için dialog `desc_width` ve font
   genişliği hesaplanmalı.

## Ghidra durumu

- Ghidra 12.2 + JDK 25, `m30-build` imajında (`$GHIDRA` = `analyzeHeadless`).
- `tools/ghidra/LoadAP.java` ve `DumpC.java` Ghidra 12.2'de çalışıyor. Community
  `browser.ap` için 75 blok, 449 fonksiyon; dump:
  `/Users/berkan/Projects/m30-work/ghidra/browser_community.c` (15.752 satır,
  repo dışında).
- Komut (Docker içinde):
  `$GHIDRA PROJE_DİZİNİ ad -import X.ap -loader BinaryLoader -processor "MIPS:LE:32:default" -noanalysis -scriptPath tools/ghidra -postScript LoadAP.java X.ap -postScript DumpC.java out.c`
- `drv_ui.drv` (75 KB) aynı `yqhx` header'ına sahip ama banka tablosu farklı.
  `0x80/0x100/0x180` bölgelerindeki byte-order `u16` başlangıç/bitiş çiftleri
  artık `tools/inspect_drv.py` ile okunuyor; üç overlay grubunda 10 A, 10 B,
  4 C bankası var. Kernel tarafındaki `FUN_bfc0a408` artık `kernel.drv`
  (`0xbfc08000`) içinde decompile edildi: `yqhx` başlığını, üç yükleme
  üçlüsünü ve BSS temizliğini tüketiyor. Public SDK `link_base.xn` de A/B/C
  pencerelerini `0x16024c00/0x26025000/0x36021a00` + `0x40000` adımıyla
  tanımlıyor. B3 bankası `0x260e5000` adresine remap edildiğinde statik
  `FUN_30009674` fonksiyonu `0x260e4ff4` adresinde temizce decompile oluyor;
  `0x7c` temizleme çağrısı ve iki kayıtlı metin yolu korunuyor. Bu güçlü bir
  statik doğrulama, fakat fiziksel cihaz trace'i değil. Bu nedenle dosya hâlâ düz
  haritalanıyor
  (adres = `0x30000000` + dosya ofseti, 0x200'den itibaren; script
  `FlatLoad.java`; kodu `docs/discovery-environment.md` içinde).
  Sonuç: 119 fonksiyon, dump
  `/Users/berkan/Projects/m30-work/ghidra/drvui_community.c` (9.217 satır).
  PC-göreli literal yüklemeleri doğru çözülür; fonksiyon işaretçisi
  üzerinden yapılan bankalar arası çağrılar (`(*_UNK_3000xxxx)(...)`) çözülmez.
  Bilinen fonksiyonlar: `FUN_300007c4` (UTF-16 karakter sınıfı),
  `FUN_3000083c` (8-bit karakter sınıfı), `FUN_30008600` (çok satırlı
  `put_string`, hizalama hesabı). Liste (`ui_show_listbox`) ve kayan yazı
  (`hori_scroll`/`scroll_string`) adımı `FUN_30009674` olarak işaretlendi;
  indirect helper'ların M30 runtime adresleri henüz bağlanmadı. Ayrıntı:
  `docs/findings-kernel-loader.md`.
- `browser.ap` içindeki `0x34` (52) eşleşmeleri liste buffer'ı değil;
  `FUN_48654884` başlık metni biçimleyicisinin (`%d`/`%x`) 52 baytlık
  buffer'ı. Çizim bölgesi `0x140 - x` genişliğinde; yani ekran genişliği 320
  piksel görünüyor (240 değil). Liste öğesi ad buffer'ı: bkz. Açık işler tablosu satır 1 (`FUN_48754574`, 50 bayt).
- `tools/ghidra/run_browser_layout_probe.sh` ile browser literal tablosu ve
  `FUN_40cd4e00` çağrı bağlamı da doğrulandı: `0x40cd4c00` liste buffer'ı,
  `0x40cd4d90` canlı `path_info` yapısıdır; değerler `8 * 0x32 = 0x190`
  byte aralığıyla ayrılır. Probe, buffer'ın directory initializer'a ve
  `path_info`'nin sonraki path/UI çağrılarına geçtiğini de decompile çıktısında
  kontrol eder. 64-byte yerinde büyütme bu nedenle güvenli aday değildir.

## Açık işler ve keşif durumu

Satır 1, 4, 6 ve 7 bu oturumda statik olarak (dump ve bayt okuma) incelendi
ve ayrıntıları aşağıda. Satır 2, 3, 5 ve 8 henüz büyük ölçüde belge
iddiasına veya referans SDK okumasına dayanıyor. Hiçbirinde cihaz testi
yok.

| # | İş | Bilinen ipucu | Sonraki keşif adımı |
|---|---|---|---|
| 1 | Uzun isim kayması / kesilmesi | **Doğrulandı (statik):** SDK'da `LIST_ITEM_BUFFER_LEN 52` bayt (`ref/PD196/case/inc/common_ui.h:32`); firmware'de 50 (`0x32`) bayt kullanılıyor: `browser.ap` `FUN_48754574` (`browser_community.c:5158`) ad uzunluğunu `0x32`, 7 slotun aralığını `0x32` yapıyor. Stock ve community aynı. Dizin modunda `FUN_71352820` adı çekirdek çağrısıyla `name_len>>1` = 25 UTF-16 birimi okuyor (görünür sınır ≈ 23-24 karakter; kesin sayı çekirdek çağrısı dump'ta olmadığı için doğrulanmadı). Kütüphane (MUSIC.LIB) modunda `FUN_714d2658` 48 bayt kopyalayıp 2 baytlık sonlandırıcı yazıyor (BOM + 23 karakter). Yani kesme `drv_ui`'nin 102 baytlık kayan yazı taramasından ÖNCE, 50 baytlık slotta oluyor. Çağıran `FUN_40cd4e00` (`gui_directory`) liste buffer'ını `0x40cd4c00` olarak veriyor (≈512 baytlık banka veri sayfası; hipotez), yerinde büyütmeye az yer var. Community kütüphane kopyalama fonksiyonunu yeniden yönlendirmiş: `browser.ap` `0x46cc` (3 bayt `e12641` → `59264d`), yeni fonksiyon 1240 bayt `0xec58`. Ayrıntı: `docs/findings-browser-names-sort.md` | 50 baytlık slotu büyütmenin yolunu bul: slot dizisi (7 × 50) RAM'de `0x9fc15598` civarı; komşu RAM boş mu, `FUN_40cd4e00`'ın `0x40cd4c00` sayfası nasıl ayrılıyor; alternatif: yalnızca kırpmayı değiştirmeden ilk 23 karakterden sonra sonekle kaydır (UI) |
| 2 | Kırmızı/siyah dikdörtgen artefaktı | **Güçlü statik/runtime eşleşme:** M30 B3 `FUN_260e4ff4` marquee adımı; `0x7c` clear çağrısı, ölçülen genişliğe göre x düzeltmesi ve iki metin kaydı var. `bfc0a8bd/bfc0a8c9` resident UI yardımcıları doğrudan bağlandı. `0x26089471/0x260894e9/0x26409401` bank-qualified girişleri ise lazy bank stub adayı; doğrudan çağrı olarak emüle edilmemeli. `ker_xsys` EPC’yi `0xbfc06d6c` sabit handler’ına yönlendiriyor ve `0x3ffff` maskeli bir guard içeriyor, ancak bunun bank loader olduğu kanıtlanmadı. Referans `load_bgpic_sd()` + `CHAR_FILL_SDIMAGE` yolunda yalnızca 1 px tail restore ediyor. | A19/B2/B16 stub girişlerini ROM/kernel dispatcher ile eşleştir; seçili öğenin `common.sty` `attrib` alanını doğrula; fiziksel test gerekli |
| 3 | Artwork oynatmayı geciktiriyor | **Statik bulgu (ajan, kısmen doğrulandı; ölçüm yok):** Motor `PLAY` mesajına ancak `SET_FILE`, `MEDIA_INFO`, `PLAY` bittikten sonra yanıt veriyor (`FUN_60090d64` → `FUN_600911b0` → `_play` `FUN_60190eec` → `FUN_60150fec`, `mmm_mp_cmd 0x19`); UI play mesajını paint döngüsünden ÖNCE gönderiyor. `mengine.ap` içinde artwork/APIC/ID3 kodu yok; `mmm_mp.al` ve `mmm_id.al` stock ile bayt bayt aynı. Community'nin 7 `mengine` bölgesi (248 bayt) artwork değil (durum işleyicisi ve tablo yükleyici). Gecikme UI iş parçacığında, yanıttan sonra: `FUN_4011508c` → `FUN_400951e4` → getid3 `FUN_401d51b8` → `FUN_781db200`; ardından `FUN_40154ddc` (paint) → `FUN_40154c00` → `FUN_480546e8` (`music_paint_albumart` karşılığı) → `FUN_4805447c` (ALBUM.PIC çizimi). `FUN_480546e8`'de SDK'daki `sys_os_time_dly(2)` bekleme döngüsü YOK: `mmm_id_cmd` decode bloklayıcı; sonuç `ALBUM.PIC` önbelleğine (RGB565, en çok 150×150) yazılıp okunuyor (stock'ta da var). APIC/FLAC PICTURE taraması sınırlı ve ucuz (`FUN_714127dc`, en çok 128 bayt, FFD8 arar; FLAC `FUN_714d284c`). Community CPU JPEG fallback'i yalnızca `mmm_id` başarısız olduğunda (durum `0xFF`) çalışıyor: `music.ap` `0xed50` (4 bayt dal) + `0xefa0-0xeff3` (84 bayt mağara) → `FUN_7111295e`; gövde `0x16550-0x168fb`, `0x20410-0x20ad7`, `0x2240c-0x239db`. Yani fallback başarısızlık yolunu yavaşlatır, başarılı yolu değil. Sesin başlamasını doğrudan geciktirmez; algılanan gecikme büyük olasılıkla UI'nin decode boyunca donması (tuş/ekran/süre 0:00'da takılı) ve olası CPU/SD çekişmesi (hipotez, ölçülmedi). Ayrıntı: `docs/findings-artwork-start.md` | Cihazda `FUN_480546e8` öncesi/sonrası süre ölç (ör. QEMU + SD imajı veya log); artwork decode'u UI'yı bloklamayacak şekilde bölmek için kod alanı ve `mmm_id_cmd` iptal/parçalama olanağını ara; ses yolunun etkilenip etkilenmediğini FS kilidi (`0x33/0x34` çiftleri) üzerinden ayır |
| 4 | Dosya adına göre sıralama | **Doğrulandı (statik):** `browser.ap` içinde sıralama yok; dizin görünümü FAT disk sırasında. Sıralama yalnızca `playlist.ap` içinde (MUSIC.LIB): banka `0x71812500` (dosya `0xa400`), `FUN_71812874` hızlı sıralama üç karşılaştırmaya dağıtıyor: mod 2 `FUN_71812548` (bayt bayt, ASCII a-z'yi büyük harfe katlar, 100 bayt sınırı, sayısal işleme YOK), mod 0 `FUN_71812650` (önceki sıra), mod 1 `FUN_718126c0` (track baytı sonra sıra). Anahtar ID3 başlığı okunabiliyorsa o, yoksa 8.3 dosya adı (`FUN_40094f2c`, `FUN_40094d60`). Community: `0xa5ed` (3 bayt, `844082` → `a440a2`) iki işaretli yüklemeyi işaretsiz yapıyor (`FUN_718126c0`, unsigned track düzeltmesi, **doğrulandı**); `0x310c` (22 bayt) `FUN_40094fec` içinde ondalık track fallback; `0x8e2e-0x9381` banka `0x480d4400` içinde, Ghidra yanlış çözüyor, amacı bilinmiyor. Mod 2 karşılaştırması stock ile aynı. Dizin görünümünde sıralama yok: dosya adı sıralaması MUSIC.LIB görünümleriyle sınırlı kalır ya da yeni bir sıralama + indeks eşlemesi gerekir (muhtemelen yer yok). Ayrıntı: `docs/findings-browser-names-sort.md` | Klasör görünümü için FAT sırasını değiştirmeden sıralamanın mümkün olup olmadığına karar ver (kullanıcı: klasör içi dosya adı sırası isteniyor). Adaylar: kütüphane için `FUN_40094f2c` anahtarını dosya adına zorla ve mod 2 karşılaştırıcısının işaretçi literalini (`0x71812a88`) yeni doğal-sıralı karşılaştırıcıya çevir; boş yer adayları (bank kuyruğu, hepsi hipotez): `0x9382` (126 bayt), `0x3350` (176), `0x3b44` (188), `0xbb7c` (132), `0x12580` (128). Bank `0x71812500` içinde boş yer yok (sıfır kuyruğu çalışma alanı). Tie-refine `FUN_40114d54` uzun anahtarları yeniden okuyor, yeni karşılaştırıcıyla tutarlı kalmalı |
| 5 | Dinleme sayacı | Önerilen tasarım `docs/community-integration.md` içinde (`M30PLAY.CNT`) | Stock'ta güvenilir yazma yolu ve yazma sınırı keşfedilmedi; bulunamazsa deneysel olarak belgele, yama yazma |
| 6 | EQ preset'leri | **Doğrulandı (bayt):** 8 preset sırası (indeks 0-7): Off, Rock, Funk, Hip hop, Jazz, Classical, Techno (menüde Electronica), Custom. `Pop`/`Soft` adları başka ekran metinlerinde var ama tabloda satırı yok. İki tablo (stock ile aynı): (1) `mengine.ap` dosya `0x440c`: 7 satır × 7 bayt (int8, 0,1 dB'e göre `×10`), 7 bant frekansı u16 `0x43ec`: 80, 200, 480, 980, 4000, 8000, 16000 Hz; `0x43fc`: 10, 6, 4, 6, 10, 5, 8 (muhtemelen Q×10). Satırlar: none `0x440c` [0,0,0,0,0,0,0], rock `0x4413` [5,3,0,-1,0,4,5], funk `0x441a` [3,0,0,0,0,-1,-2], hiphop `0x4421` [0,0,1,2,0,1,1], jazz `0x4428` [3,0,0,-1,0,2,4], classic `0x442f` [0,0,0,-1,-1,-2,-4], techno `0x4436` [5,2,0,0,0,0,6]. (2) `setting.ap` dosya `0x5a94`: 8 satır × 16 bayt (12 int8 kullanılıyor); Custom satırı `0x5b04` (satır 7) {-9,0,0,0,0,0,6}. `FUN_601d0d58` (`mengine_community.c:1717-1790`, ajan bulgusu): 7 bantlı parametrik EQ, `kazanç = tablo[idx*7+bant]*10`; indeks 7 = Custom ve tabloyu değil RAM `0x9fc1a19c`'yi okuyor. Dosya ofseti = adres − `0x601ccd00`. Boş yer (üye boyutu değişmeden, bayt olarak sıfır doğrulandı): `mengine.ap` `0x443d-0x47ff` (963 bayt), `setting.ap` `0x5b14-0x5bff` (236 bayt). **Hipotez:** yeni preset için kod yaması gerekir (indeks 7 Custom'a sabit, sınır denetimi görülmedi) ve menü ağacı + `.sty` düzenlemesi gerekir. Kontrol edilmedi: `music.mcg`/`setting.mcg` düğüm sayıları; indeks baytını (`g+0x41`) hangi uygulamanın yazdığı | `FUN_601d0d58` içinde indeks sınırını ve `0x9fc1a19c` Custom okumasını doğrula; menü ağacında (`setting.mcg`/`music.mcg`) preset düğümlerini ve `setting.sty` kaynak kimliklerini çıkar; FullSound etkileşimini ayır. Ayrıntı: `docs/findings-eq-usound.md` |
| 7 | Harici DAP/USB DAC | Bkz. "USB keşfi". **Doğrulandı (statik, ajan bulgusu + bayt kontrolü):** `config.ap` `FUN_40054c00` (`config_community.c:55-98`, mesaj `0x90`): RAM `0x9fc155d4` baytı 1 ise `usound` (uygulama kimliği `0x12`) başlatılıyor; değilse `online_device == 0` ise `udisk` (`0xc`), değilse MTP (`0x10`). Bayrak `FUN_40054ccc` içinde config öğesi `0x116`'dan (`config.bin` `0xe4a`, u16 `0,0,1,1`, stock ile aynı) bir kez ayarlanıyor. **Hipotez:** ilk u16 varsayılan, yani bayrak 0 ve `usound` dalı varsayılan olarak ölü. Öğe 278 varsayılanını 1 yapmak USB takılınca `usound` açar; denenmedi, yalnızca `config.bin` değişikliği olur. `manager.ap` ad tablosunda (`0x2634`, 12 baytlık girişler) `usound.ap` `0x270c`, indeks 18 (kimlik=indeks hipotez). Başka hiçbir `.ap` içinde \"usound\" dizgisi yok; arayüzde yol yok. `uhost.drv` yalnızca Bulk-Only Mass Storage host'u (6 `USBC` CBW imzası: `0xa08, 0xd44, 0xed0, 0x18bc, 0x1984, 0x1ad0`); HID/ses sınıfları desteği bilinmiyor | Hipotezi (öğe 278 → usound) yalnızca analiz için not et: cihazda denemeden yama yazma; USB bağlantısı bozulursa depolama erişimi kaybolur. Ayrıntı: `docs/findings-eq-usound.md` |
| 8 | QEMU kapsamı | Upstream'de ATJ2127 makinesi yok; yalnızca user-mode harness'leri çalışıyor | `build.sh --test` ile mevcut harness'lerin Docker'da geçtiğini doğrula |

## USB keşfi (statik, bu oturumda; cihazda test edilmedi)

Bulgular `community` ve `cand` imajında aynı (`usound.drv`, `udisk.drv`,
`uhost.drv` community'de değişmiyor).

| Sürücü | Bulgu |
|---|---|
| `udisk.drv` | USB 2.0 aygıt tanımlayıcısı (bcdUSB `0x0200`), VID `0x10d6`, PID `0x1101`. Arayüz: Mass Storage (class `08`, subclass `05`, protokol `50` BOT), bulk IN `0x81`, bulk OUT `0x02`, paket 512 (HS) / 64 (FS). Dize: `USB Udisk`, `Actions`. |
| `usound.drv` | USB 1.1 (bcdUSB `0x0100`) aygıt tanımlayıcısı, VID `0x10d6`, PID `0xdd00`. Config toplam 0x8a bayt. Audio Class 1.0: giriş terminali (USB streaming, 2 kanal) → feature unit (mute/volume) → çıkış terminali (hoparlör `0x0301`). Streaming arayüzü: PCM, 2 kanal, 16 bit, tek ayrık örnekleme hızı **48000 Hz**, isochronous OUT `0x01` (adaptive, paket 200 bayt). Ayrıca HID arayüzü: tüketici kontrol raporu (ses +/-, sessiz, oynat/duraklat, sonraki, önceki, dur), interrupt IN `0x82`. Dize: `USB Audio`, `Actions`. |
| `uhost.drv` | 9 KB USB host sürücüsü. `config.ap`, `mainmenu.ap`, `setting.ap` bu adı yüklüyor; `playlist.sty` içinde "Uhost disk/space error" iletileri var. Altı `USBC` (CBW imzası `0x43425355`) literali (`0xa08, 0xd44, 0xed0, 0x18bc, 0x1984, 0x1ad0`) var: Bulk-Only Mass Storage host'u. HID/ses sınıfı desteği bilinmiyor (ajan bulgusu, disassemble edilmedi). |
| Uygulama | `manager.ap` uygulama tablosunda `usound.ap` var (22 KB). `usound.sty` kaynakları: `s_usound_USB`, `s_usound_linking`, `s_usound_charging`, `s_usound_full_charged`. |

Çıkarımlar (varsayım, doğrulanmadı):

- Firmware, M30'u bilgisayara 16 bit / 48 kHz stereo USB ses kartı (UAC1,
  oynatma yönü: bilgisayar → M30 DAC'ı) olarak tanıtabilecek kod taşıyor.
  Bu, M30'un başka bir cihaza harici DAC olarak bağlanması anlamına gelir
  (kaynak cihaz USB host/OTG vermeli). M30'un başka bir DAC'a **kaynak**
  olması için UAC host sürücüsü gerekir; böyle bir sürücü bulunmadı.
- İngilizce arayüzde bu moda götüren bir seçenek bulunamadı. Bağlantı
  ekranı yalnızca MSC / MTP ve "Charge & play / Charge & transfer" sunuyor
  (`setting.sty`, `common.sty`). `usound.ap` büyük olasılıkla Actions
  SDK'dan kalma, MECHEN UI'ında açılmayan bir uygulama.
- `usound.drv` config tanımlayıcısında `bNumInterfaces = 3` iken arayüz
  numaraları 0, 1 ve 3 (HID için 3). Bu tutarsızlık sürücünün üründe hiç
  kullanılmadığını veya yarım kaldığını düşündürüyor.
- Elektriksel olarak USB portunun host/OTG kimliği (ID pini, VBUS çıkışı)
  firmware'den anlaşılamaz; donanım şeması gerekir.

Sonraki adımlar (Codex için): `manager.ap` uygulama tablosundaki `usound.ap`
indeksini ve onu çağıran yeri (`config.ap`/`udisk.ap`/`mainmenu.ap`) bul;
çağrı koşulunu (USB takıldığında hangi ayar/mod) belgele. Cihazda deneme
yapmadan firmware yaması yazma: yanlış mod, USB bağlantısını kullanılamaz
hale getirip depolama erişimini engelleyebilir.

## Emülatör / harness: eksik ve tutarsız noktalar

Kaynak: `tools/sim/*.py` (36 birim test, bu oturumda `python3 -I -m unittest
discover -s tools/sim` ile çalıştırıldı, hepsi geçti), `build.sh --test` ve
`tools/*/harness.c`. QEMU harness'leri bu oturumda çalıştırılmadı; yalnızca
okundu. Aşağıdakiler cihaz davranışına dair kanıt değil, test altyapısının
sınırlarıdır.

### Genel

- `tools/sim` testleri `build.sh --test` tarafından çalıştırılmıyor
  (`build.sh` içinde `sim`/`unittest` çağrısı yok). Yani `docs/qemu-coverage.md`
  tablosundaki "host model PASS" satırları otomatik test zincirinde yok.
- `build.sh` yalnızca araştırma firmware'ini (shuffle, shuffle-all, scroll
  hızlandırma, ekran kapalı tuşlar, isteğe bağlı kütüphane) stock'tan kuruyor.
  Adayın (community V1.292.00 + kırmızı ikonlar + önceki tuş + upgrade metni)
  değişikliklerini üreten bir giriş noktası yok: `tools/patch_prev_restart.py`,
  `patch_ui_*.py`, `patch_upgrade_prompt.py`, `patch_default_art.py` vb. 12
  betik var ama `build.sh` bunların hiçbirini çağırmıyor. Aday HEX bu
  depodan yeniden üretilebilir değil; yalnızca hash'i belgelenmiş.
- Hiçbir harness adayın değişikliklerini (önceki tuş eşiği, ikonlar, upgrade
  metni) ya da community'nin 8 üyesini (`docs/community-diff.md`) test etmiyor.
  QEMU kapsamı (shuffle, playall, scroll, keys, library) community tabanından
  önceki araştırma yamalarına ait.
- `build.sh` stock hash'i sabit (`STOCK_SHA`) olduğu için community
  üzerinde çalışmaz; adım yeniden yazılmadan community tabanına geçilemez.
- Sonuç denetimi var: `ALL PASS` satırı ve `FAIL|MISMATCH|INVARIANT|FLAGS`
  taranıyor; `|| true` yalnızca betiğin çıkış kodunu yutuyor. (Bu denetim
  `slow_same` ve scroll `events 30000 ... failures 0` için de var.)
- Gerçek ATJ2127 emülasyonu yok: LCD, SD/FAT, DAC/codec, bank yükleyici,
  tuş denetleyicisi modellenmiyor; harness'ler gerçek `.ap` bankalarını
  çıplak MIPS32 24Kc üzerinde, çekirdek/dosya sistemi/zamanlayıcı
  taklitleriyle çalıştırıyor. 24Kc MIPS16e kullanıyor; ATJ2127'nin gerçek
  çekirdeği (MIPS16e destekli) ile aynı olduğu belgelenmemiş.

### `tools/sim/atj2127.py`

- Hiçbir harness bu modeli kullanmıyor; yalnızca kendi birim testleri
  (`test_atj2127.py`) var. QEMU harness'leri bu MMIO modeline bağlı değil.
- Kayıt adresleri ve bit anlamları (`MRCR`, `WD_CTL`, `GPIO_BT_POWER`,
  `UART_TX_EMPTY`, `0x5F` watchdog değeri, ADFU işaretçisi
  `0x00130000`/`0xADF0ADF0`) başka bir projenin notlarına dayanıyor ve bu
  oturumda M30 ikilisinde doğrulanmadı. Belgeler iki farklı depo veriyor:
  `README.md` `ilyakurdyukov/actions_flash`, `docs/qemu-coverage.md`
  `kilicdev/actions_flash` (ikisi de var; hangisinin kaynak olduğu
  belirsiz).
- Bilinmeyen kayıtlar okunup yazılabiliyor ve sıfır dönüyor; salt-okunur
  davranış ve yazma etkileri yok. `UART_STAT` bit 0'ın "alma verisi var"
  anlamı varsayım. `step()` yalnızca sayaç artırıyor; zamanlayıcı/kesme
  yok. DMA yalnızca UART hedefi için ve elle tetiklenen tek geçiş.

### `tools/sim/listbox.py`

- `NAME_BUFFER_BYTES = 50` olarak düzeltilmiştir. SDK'daki 52 baytlık
  `LIST_ITEM_BUFFER_LEN` değerine rağmen M30 `browser.ap` bu ad buffer'ını
  `0x32` bayt olarak kuruyor (`FUN_48754574`), kesinti `drv_ui`'nin 102 baytlık
  kayan yazı taramasından önce oluşuyor.
- Eski karakter hücresi modeli geriye dönük uyumluluk için duruyor. Yeni
  `marquee_frame()` modeli ofseti piksel cinsinden ilerletiyor ve her frame'de
  tüm viewport'un temizlenmesini zorunlu kılıyor; kırmızı/siyah kalıntı için
  host regresyon testleri eklendi. Bu hâlâ vendor fontunu veya gerçek LCD
  rasterizer'ını emüle etmiyor.
- Kayan yazı sırasında ortalı yazının sola alınması (`scroll_string`),
  BOM atlama, resimli arka planın SD'den yeniden yüklenmesi ve yalnızca
  1 piksellik kenar temizleme modellenmiyor. Kullanıcının bildirdiği
  kırmızı/siyah dikdörtgen ve kaybolan karakter hatalarını bu model
  üretemez; test yok.
- `needs_active_scroll()` piksel genişliği alıyor, `scroll_window()` ise
  karakter sayısı: birim karışık. Ekran çözünürlüğü (320 genişlik
  izleri, `DIRECTORY_TEXT_X + WIDTH = 240`) ve renk paleti hiçbir yerde
  modellenmemiş; görev #10'daki "ekran çözünürlüğü ve renk paleti" maddesi
  boş.

### `tools/sim/m30_model.py`

- **Sıralama:** `natural_sort_key` NFKC + `casefold` kullanıyor; cihaz
  Latin-1 dönüştürücüsünü kullanıyor (modelin kendi yorumu bunu kabul
  ediyor). Klasör/dosya karışık sıralama, ID3 yerine dosya adı seçimi ve
  community'nin unsigned/track-number düzeltmeleri modellenmiyor. Gerçek
  `playlist.ap`/`browser.ap` karşılaştırma fonksiyonuyla karşılaştırma
  testi yok; yalnızca modelin kendi beklentileri test ediliyor.
- **EQ:** `EQ_PRESETS` 15 ad ve 5 bant dB değeri içeriyor. Firmware'de
  gerçek yapı: 7 bantlı parametrik EQ (80, 200, 480, 980, 4000, 8000,
  16000 Hz), 8 preset (`Off, Rock, Funk, Hip hop, Jazz, Classical, Techno`
  ve `Custom`), değerler int8 (×10 → 0,1 dB). Model bant sayısı (5 ≠ 7) ve
  preset kümesiyle uyuşmuyor: `Flat`, `Dance`, `Vocal`, `Acoustic`,
  `Bass Boost`, `Treble Boost`, `Pop`, `Soft` firmware tablosunda yok;
  `Electronic` / `Hip-Hop` ad farkı var (`Techno`/`Electronica`, `Hip hop`).
  Model değerleri firmware katsayısına bağlı değil (modelin kendi notu).
  Kafa payı/kırpılma testi yok.
- **İndeks:** `IndexStatus` bir durum makinesi; ilerleme, "dirty" durumu ve
  mesajlar firmware'de yok (öneri). Gerçek tetikleyicilerle
  (`config.ap` `0x1e0d`, `udisk.ap` `0x1909`) bağlantısı yok. "Manual
  policy never starts an update implicitly" testi yalnızca modelin kendi
  sınıfını sınıyor, firmware'de otomatik indekslemenin kapalı olduğunu
  göstermiyor.
- **Artwork:** `ArtworkSession` "önce ses, sonra kapak" sözleşmesini
  varsayıyor. Mevcut firmware'de kapak çözme UI iş parçacığında
  bloklayıcı döngüyle yapılıyor (referans SDK). Model, hedeflenen tasarımı
  doğruluyor; mevcut davranışı veya `mengine` tarafındaki etiket taramasını
  ölçmüyor, bu nedenle testin geçmesi gecikme düzeltmesi anlamına gelmiyor.
- Upgrade metni, dialog hizalaması, önceki tuş (0 ms eşik), dinleme
  sayacı ve USB modları için hiç model/test yok.

### Önerilen test boşlukları (öncelik sırasıyla)

1. Adayın üç değişikliği (`mengine.ap` önceki tuş, `music.sty` ikonlar,
   `setting.sty` metin) için baytlık regresyon testi: stock/community
   ile fark yalnızca belgelenmiş ofsetlerde olmalı.
2. `drv_ui.drv` `FUN_30008600` hizalama hatası için küçük bir host
   modeli: `true_length` ile ortalama vs satır sonu (`0x000a`) karşılaştırma.
3. `listbox.py` içine piksel başına kayma, 102 baytlık sınır ve
   arka plan yeniden çizimi.
4. Sıralama modelini gerçek karşılaştırma fonksiyonuyla (QEMU) çapraz doğrulama.

## Önceki belgelerdeki düzeltmeler

Aşağıdaki iddialar bu oturumdaki bulgularla çelişiyor veya eksik:

- `docs/qemu-coverage.md`: "`LIST_ITEM_BUFFER_LEN` 52 bayt, isim kayan yazıya
  girmeden kesilir." SDK'da sabit 52, firmware'de ise 50 (`0x32`) bayt
  kullanılıyor (`browser.ap` `FUN_48754574`); kesme dizin modunda 25 UTF-16
  birimi, kütüphane modunda BOM + 23 karakter. Bkz. `docs/findings-browser-names-sort.md`.
- `docs/feature-roadmap.md`, "Dosya adına göre sıralama": "yalnızca
  browser/list karşılaştırma fonksiyonlarına patch yapılmalı". `browser.ap`
  içinde sıralama yok (dizin görünümü FAT sırasında); sıralama yalnızca
  `playlist.ap`'de MUSIC.LIB oluşturulurken yapılıyor. Dizin görünümüne
  dosya adı sıralaması yeni bir sıralama + indeks eşlemesi gerektirir.
- `docs/feature-roadmap.md`, "Daha fazla EQ preset'i": "katsayı tablosunun
  hazır olduğu anlamına gelmez" doğru, ama tablolar artık bulundu
  (`mengine.ap` `0x440c`, `setting.ap` `0x5a94`) ve `Funk`/`Hip hop` satırları
  gerçekten var; önerilen 15 adlı listenin çoğu (`Flat`, `Dance`, `Vocal`,
  `Acoustic`, `Bass Boost`, `Treble Boost`) firmware'de yok, EQ 5 değil 7
  bantlı. Yeni preset kod yaması ister.
- `docs/feature-roadmap.md`, "Line-out": `drv_dac.drv`, `drv_lcd.drv`,
  `aud_dev.drv` ve `uhost.drv` artık statik olarak sınıflandırıldı; bunlar
  donanım/USB alt katmanı. `aud_dev.drv` yalnızca sekiz baytlık COP2 stub,
  `uhost.drv` yalnızca USB yığın-depolama host yolu gösteriyor. Line-out'un
  kulaklık çıkışıyla aynı ses davranışı hâlâ kanıtlanmış değil.
- `docs/qemu-coverage.md`, tablo: "Filename natural-order contract: PASS" ve
  "Artwork audio-first contract: PASS" yalnızca host modellerinin kendi
  beklentilerini sınar; firmware sıralaması (bayt bayt ASCII katlama, sayısal
  işleme yok) ve artwork akışıyla ilgisi yok. Bkz. "Emülatör / harness".
- **ÖNEMLİ, aday HEX:** `docs/community-integration.md`,
  `docs/release-candidate.md` ve `tools/patch_prev_restart.py` "önceki
  tuş eşiği 5.000 ms → 0 ms, Previous artık parçayı başa sarar" diyor. İkili
  okuması bunu desteklemiyor: `mengine.ap` içinde tek `li 5000` sitesi
  `0x3a64` (stock ve community aynı), `_play` (`FUN_60190eec`) içinde mod 3
  (`PLAY_FBON`, hızlı geri sarma) yolunda `bp_time_offset = -5000` olarak
  kullanılıyor ve hiçbir şeyle karşılaştırılmıyor. Motorun Previous
  işleyicisi (`0x319` → `FUN_60091370` → `FUN_600912cc`, mod 3) hiçbir süre
  testi yapmıyor; SDK'daki `cur_time > 5000` yeniden başlatma dalı bu
  ikilide yok. Yani yama "Previous = parçayı başa sar" davranışını
  sağlamıyor; yalnızca geri sarma devir ofsetini 0 yapıyor (hipotez:
  önceki parçanın sonundan başlayıp art arda parça atlayabilir). UI
  işleyicisi `FUN_bfc16718` (`music.ap`) da süre denetlemiyor, parça
  numarasını azaltıp `0x319` gönderiyor. Gerçek bir "başa sar" için hem
  motor işleyicisi hem UI işleyicisi değişmeli (seçenekler
  `docs/findings-artwork-start.md` bölüm 3'te). Adayı bu hâliyle flash'lamadan
  önce davranışı ve olası zincir atlamayı cihazda kontrol et; geri dönüş
  için stock HEX hazır tutulmalı.
- `docs/community-integration.md`: "Manual `Settings -> Update Playlist`
  remains available" ve "automatic regeneration disabled" iddiası ikilide
  tek baytlık iki değişiklikle uyuşuyor (`config.ap` `0x1e0d`, `udisk.ap`
  `0x1909`: `0x22` → `0x10`), ama baytların kod olarak ne yaptığı çözülmedi
  ve cihazda denenmedi.
- `README.md` ve `docs/flash-preflight.md` adayı "tavsiye edilen" olarak
  anıyor; aday `build.sh` ile yeniden üretilemiyor (bkz. "Emülatör / harness").

## Bekleyen işler (bu belge yazılırken)

- `build.sh --test` (Docker, stock HEX ile): Docker/QEMU ortamı erişilebilir
  olmadığından çalıştırılamadı; host tarafında `tools/sim` 36 ve `tools/emu`
  73 test geçti. Tam statik suite ayrıca browser layout boundary, tüm Ghidra
  driver/kernel probe'ları ve üç gerçek MIPS16 event probe'ını PASS etti.
  `tools/sim/bankmap.py`, Actions A/B/C pointer'larını overlay,
  lead-in ve lazy bank-stub olarak ayırıyor; `tools/sim/ui_calls.py` B3'teki
  çağrıları temkinli biçimde etiketliyor; `tools/emu/driver_banks.py` ise
  `drv_ui.drv` içindeki far-entry adaylarını payload konumuna çözüyor ama
  doğrulanmamış adrese doğrudan kod gibi atlamıyor; `tools/emu/bank_runtime.py`
  yükleme olayını ve doğrulanmış giriş filtresini host üzerinde izliyor.
  `LazyBankRuntime.boundary_trace()` artık kanıtlanan sınırı da açıkça
  kaydediyor: `overlay-exception -> bank-load -> retry-entry`; doğrulanmamış
  girişte iz güvenli biçimde `stop-unresolved-entry` ile sonlanıyor. Bu,
  eksik sabit exception handler'ı uydurmadan emülatöre taşınmış bir host
  sözleşmesidir.
  indirekt UI çağrılarını SDK imzalarına göre yalnızca kanıt düzeyinde
  etiketliyor.
- Dinleme sayacı için güvenli yazma yolu ve yazma sınırı: incelenmedi.
- Kayan yazı artefaktının (kırmızı/siyah dikdörtgen) M30 ikilisindeki
  karşılığı (`hori_scroll`, `load_bgpic_sd`): `FUN_30009674` artık gerçek
  marquee adımı olarak statik decompile ile işaretlendi; indirect helper
  pointer'larının runtime çözümü ve fiziksel LCD doğrulaması bekliyor.
- `[%s]` yer tutucusunun genişletildiği an ve aynı string'in başka
  ekranlarda kullanılıp kullanılmadığı: incelenmedi.
- EQ: `FUN_601d0d58` indeks sınırı, `music.mcg`/`setting.mcg` menü düğümleri,
  indeks baytını (`g+0x41`) yazan uygulama: bulunmadı. `mengine.ap`
  `0x4600-0x47ff` aralığı banka dolgusu olabilir; yeni satır için kullanmadan
  önce kontrol edilmeli.
- `usound`: SDK'da `APP_ID_UDISK` 0x12 iken bu firmware'in `manager.ap`
  tablosunda `udisk` 12 (`0xc`), `usound` 18 (`0x12`); kimlik=indeks eşlemesi
  hipotez.

## Boot ROM inceleme hazırlığı

ROM tarafı için `tools/rom/` altında yalnızca okuma yapan bir hazırlık akışı
eklendi. `dump_bootrom.sh` varsayılan olarak kuru çalışır; `--execute`
verilmediği sürece USB'ye bağlanmaz. Çalıştırılan gerçek akışta yalnızca
RAM'e `adfus.bin` yüklenir ve `0x9fc00000..0x9fc3ffff` aralığı
`read_mem2` ile okunur. `write_flash`, `read_lfi` ve NAND yazma komutları
wrapper içinde bulunmaz. `inspect_bootrom.py` boyutu, SHA-256'yı ve ROM'daki
`0x5f90` / `0x6d6c` aday handler ofsetlerini raporlar.

macOS'ta libusb host istemcisi `/private/tmp/actions_dump` olarak derlendi ve
kuru çalışma doğrulandı. Payload, geçici amd64 Fedora Docker konteynerinde
MIPS32/MIPS16 ve little-endian seçenekleriyle yeniden üretildi:

```text
/private/tmp/m30-adfus-output.s59Bow/adfus.bin
size:   1680 bytes
sha256: 778bff42fa636343a4bf3bb61aaa30cdbb1db93e7a84dd5a542103a74ae01924
ELF:    elf32-tradlittlemips, MIPS32, entry 0xbfc18000
```

Kaynak ve linker düzeni `/Users/berkankarakus/Projects/actions_flash/payload`
altında duruyor. Bu payload cihaza gönderilmedi. USB taramasında da M30'un
`10d6:1101` veya ADFU `10d6:10d6` kimliği görülmedi; dolayısıyla ROM okuma
denemesi yapılmadı.

## Belge dizini

| Belge | İçerik |
|---|---|
| `docs/codex-handoff.md` | Bu belge: ortam, kararlar, açık işler, düzeltmeler |
| `docs/community-diff.md` | Community V1.292.00'ın stock'a göre bayt/ofset farkı |
| `docs/discovery-environment.md` | Docker imajı, Ghidra komutları, `FlatLoad.java`, `drv_ui` fonksiyon eşlemesi |
| `docs/findings-browser-names-sort.md` | Liste ad buffer'ı (50 bayt) ve sıralama fonksiyonları |
| `docs/findings-eq-usound.md` | EQ tabloları ve `usound` başlatma yolu |
| `docs/findings-key-driver.md` | `key.drv` MIPS16 tarama, debounce/repeat ve ADC eşikleri |
| `docs/findings-dac-driver.md` | `drv_dac.drv` codec/DAC seri bus bit işlemleri |
| `docs/findings-lcd-driver.md` | `drv_lcd.drv` LCD pencere, yön ve piksel aktarımı |
| `docs/findings-auddev-driver.md` | `aud_dev.drv` sekiz baytlık COP2 stub/fragment sınırı |
| `docs/findings-uhost-driver.md` | `uhost.drv` USB yığın-depolama host sınırı |
| `docs/findings-cards-driver.md` | `cards.drv` SD denetleyici, blok I/O ve kart algılama sınırı |
| `docs/findings-card-driver.md` | `card.drv` iki segmentli SD adapter yolu; kısmi seeded decompile |
| `docs/findings-norud-driver.md` | `nor_ud.drv` harici NOR user-data dispatch tablosu |
| `docs/findings-artwork-start.md` | Artwork gecikmesi, community JPEG fallback'i ve önceki tuş |
| `docs/findings-scroll-static.md` | `drv_ui.drv` kayan yazı ve isim hazırlama bulguları |
| `docs/build-inventory.md` | Yerel HEX adaylarının decrypt/member karşılaştırması |
| `tools/rom/README.md` | ATJ2127 Boot ROM dump hazırlığı ve doğrulama akışı |

## Değişmez kurallar

- Orijinal HEX'i silme veya üzerine yazma. Her değişiklikten önce ve sonra
  SHA-256 üret.
- FWU boyutu, sektör düzeni ve checksum/trailer korunur; her yama için
  offset, eski byte, yeni byte ve gerekçe kaydedilir.
- Donanımda test edilmeyen hiçbir davranış "kesin çalışır" diye yazılmaz.
- Test anahtarlarını ve gereksiz community anahtarlarını final HEX'e koyma.
