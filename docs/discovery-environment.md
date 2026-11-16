# Keşif ortamı: Docker, Ghidra ve yeniden üretim

Bu belge, `docs/codex-handoff.md` içindeki bulguları yeniden üretmek için
kullanılan ortamı kaydeder. Burada üretilen Ghidra çıktıları (`*_community.c`)
satıcı firmware'inden türetildiği için depoya eklenmedi; aşağıdaki komutlarla
yeniden üretilir.

## Girdiler (repo dışında)

| Ne | Yol (yerel çalışma alanı) | SHA-256 |
|---|---|---|
| Stock V1.101.10 | `<local-workspace>/m30-inputs/stock/MECHEN_M30.HEX` (README'deki Google Drive linkinden) | `6c7e27c8c90c4942664d66a0d6c9f9e48f8d3bc7d2d24223568255e233551258` |
| Community V1.292.00 | `<local-workspace>/m30-inputs/community/MECHEN_M30.HEX` (`dev-zetta/mechen-m30-community-firmware` release `v1.292.00`) | `5e17d883f697a67d4face6f624ddc30952c5542c918b219be974bf380383ed2c` |
| Aday `red-back` | repo kökünde `MECHEN_M30-community-v1.292-red-back.HEX` (`.gitignore` dışında) | `f78bdf3bb9c2b29f3a9162150cf028aeef3d3f693a9230dc0fc7ee13d90b736c` |
| Actions SDK kaynağı | `<local-workspace>/m30-inputs/ref/PD196` (`Suber/PD196_ATJ2127`, GBK kodlu; `iconv -f gbk -t utf-8 -c`) | - |

Not: Google Drive indirmesi ve GitHub release indirmesi bu oturumda
yapıldı; stock ve community dosyaları için yukarıdaki hash'ler README ve
`docs/community-integration.md` ile eşleşti.

## Docker imajı `m30-build`

İmaj amd64 (Fedora). Ana makine arm64 olduğu için emülasyonla çalışır:
`docker run` sırasında `--platform linux/amd64` verme ("imaj bulunamıyor"
hatası); parametresiz çalışır, yalnızca platform uyarısı basar. Aday HEX'i
ayrı bir `-v` ile değil, repo dizinini salt-okunur bağlayarak ver (iç içe
mount başarısız oluyor).

```dockerfile
FROM --platform=linux/amd64 fedora:latest
RUN dnf install -y gcc gcc-c++ make git python3 zlib-devel \
    gcc-mips64-linux-gnu binutils-mips64-linux-gnu qemu-user-static-mips \
    libusb1-devel libpng-devel && dnf clean all
RUN git clone --depth 1 --filter=blob:none https://github.com/Rockbox/rockbox.git /opt/rockbox \
    && make -C /opt/rockbox/utils/atj2137/atjboottool
ENV ATJBOOTTOOL=/opt/rockbox/utils/atj2137/atjboottool/atjboottool
WORKDIR /work

# Ghidra headless (tam JDK gerekir; headless JRE "no TTY" hatası verir)
RUN dnf install -y java-25-openjdk-devel unzip && dnf clean all
RUN curl -sL -o /tmp/ghidra.zip https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_12.2_build/ghidra_12.2_PUBLIC_20261016.zip \
    && unzip -q /tmp/ghidra.zip -d /opt && rm /tmp/ghidra.zip && ln -s /opt/ghidra_12.2_PUBLIC /opt/ghidra
ENV GHIDRA=/opt/ghidra/support/analyzeHeadless
```

Doğrulanan sürümler: `mips64-linux-gnu-gcc` 16.2.1 (README'deki test edilen
sürümle aynı), JDK 25.0.4.1, Ghidra 12.2. Kullanılan Dockerfile bu oturumda
`<local-workspace>/m30-docker/Dockerfile` altındaydı; yukarıdaki blok
onun içeriğidir.

## macOS ARM'da tam statik suite

Tam `tools/emu/run_static_suite.sh` akışı Ghidra 12.2, Java 25 ve Ghidra'nın
platforma özgü native decompiler bileşenini gerektirir. macOS ARM'da en kısa
kurulum yolu Homebrew'dür:

```sh
brew install ghidra
```

Ghidra'nın doğrudan indirilen dağıtımı bazı macOS ARM paketlerinde
`os/mac_arm_64/decompile` bileşenini içermeyebilir. Bu durumda Ghidra açılır,
fakat decompiler probe'ları `native decompiler does not exist` hatasıyla
başarısız olur. Homebrew kurulumu gerekli native bileşeni sağlar.

`tools/emu/run_static_suite.sh`, Homebrew kurulumunu ve Java 25 yolunu otomatik
keşfeder. Elle override etmek veya Homebrew dışı kurulum kullanmak gerekirse:

```sh
GHIDRA="$(brew --prefix ghidra)/libexec/support/analyzeHeadless"
JAVA_HOME="$(brew --prefix openjdk@25)/libexec/openjdk.jdk/Contents/Home"
GHIDRA_USER_HOME="${TMPDIR:-/private/tmp}/m30-ghidra-home"
mkdir -p "$GHIDRA_USER_HOME"

JAVA_TOOL_OPTIONS="-Duser.home=$GHIDRA_USER_HOME" \
  GHIDRA="$GHIDRA" \
  JAVA_HOME="$JAVA_HOME" \
  bash tools/emu/run_static_suite.sh
```

`JAVA_TOOL_OPTIONS` gereklidir: Ghidra ilk çalıştırmada Java yolunu
`$HOME/Library/ghidra` altına kaydeder; kısıtlı veya geçici çalışma ortamlarında
bu dizin açıkça yazılabilir bir yere alınmalıdır. Suite yalnızca offline
firmware analizidir ve cihazla USB iletişimi kurmaz.

### Analiz girdileri

Firmware üyeleri ve tüm corpus kopyaları `.gitignore` kapsamındadır; repoya
eklenmez. Suite'in beklediği düzen:

```text
analysis/{stock,community,first-pass-verify,v1.101.11,v1.101.12,v5}/fw/
```

Bu dosyalar hazır bir yerel unpack çalışma alanında bulunuyorsa, her corpus
altındaki `fw` dizini o çalışma alanına bağlanabilir. Bağlantıların mutlak
makine yolları içermesi nedeniyle bunlar yalnızca yerel fixture olarak kalmalı;
dokümantasyonda `<local-workspace>` yer tutucusu kullanılmalıdır.
Eksik historical corpus'ları community kopyasına bağlamak geçerli değildir:
`run_decoder_callback_probe.sh` gibi karşılaştırmalar gerçek
`v1.101.12`/community byte farklarına dayanır.

## Üyeleri açma

```sh
atjboottool -c --fwu -o dec.bin MECHEN_M30.HEX
atjboottool -c -o afi/ dec.bin
atjboottool -c --fw -o fw/ afi/FWIMAGE.FW
```

Her üç imajda sonuç: AFI 19 ok / 0 hata, FWIMAGE.FW 201 ok / 0 hata, 99 üye.

## Ghidra ile `.ap` dekompilasyonu

Repodaki `tools/ghidra/LoadAP.java` ve `DumpC.java` Ghidra 12.2'de çalışıyor:

```sh
$GHIDRA PROJE_DIZINI ad -import X.ap -loader BinaryLoader -processor "MIPS:LE:32:default" -noanalysis \
  -scriptPath tools/ghidra -postScript LoadAP.java X.ap -postScript DumpC.java out.c
```

Üretilen dump'lar (fonksiyon sayısı): `browser` 449, `music` 819, `playlist` 386,
`drv_ui` 119 (düz haritalama, aşağıya bak); `config`, `setting`, `mengine`,
`udisk`, `manager`, `usound`, `mainmenu` de üretildi. Fonksiyon adları
`FUN_<adres>`; bankalar arası çağrılar `(*_UNK_xxxx)(...)` fonksiyon
işaretçisi olduğundan çağrı grafiği eksik.

### `.drv` dosyaları (düz haritalama)

`drv_ui.drv` aynı `yqhx` başlığını taşır ama banka tablosu farklıdır. `0x80`,
`0x100` ve `0x180` bölgeleri, üç overlay grubunun byte-order `u16` başlangıç/
bitiş çiftlerini taşır; grup dosya başlangıçları başlıktaki `0x48/0x4c/0x50`
alanlarından gelir. Bu yapı artık `tools/inspect_drv.py` ile raporlanıyor.
Bank yükleme adreslerinin M30 loader tarafındaki son eşlemesi yine çözülmediği
için dosya düz haritalanıyor: adres = `0x30000000` + dosya ofseti,
0x200'den itibaren. PC-göreli literal yüklemeleri doğru çözülür; işaretçi
üzerinden bankalar arası çağrılar çözülmez.

```java
// FlatLoad.java: Ghidra headless postScript. Arguments: file, base, startOffset.
// The maintained copy is tools/ghidra/FlatLoad.java.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.lang.Register;
import ghidra.program.model.mem.*;
import java.io.ByteArrayInputStream;
import java.math.BigInteger;
import java.nio.file.*;
import java.util.Arrays;

public class FlatLoad extends GhidraScript {
    @Override
    public void run() throws Exception {
        byte[] d = Files.readAllBytes(Paths.get(getScriptArgs()[0]));
        long base = Long.decode(getScriptArgs()[1]);
        int from = Integer.decode(getScriptArgs()[2]);
        Memory mem = currentProgram.getMemory();
        for (MemoryBlock b : mem.getBlocks()) mem.removeBlock(b, monitor);
        AddressSpace sp = currentProgram.getAddressFactory().getDefaultAddressSpace();
        Register isa = currentProgram.getRegister("ISA_MODE");
        Address start = sp.getAddress(base + from);
        int s = d.length - from;
        byte[] chunk = Arrays.copyOfRange(d, from, d.length);
        MemoryBlock blk = mem.createInitializedBlock("flat", start, new ByteArrayInputStream(chunk), s, monitor, false);
        blk.setRead(true); blk.setExecute(true);
        currentProgram.getProgramContext().setValue(isa, start, start.add(s - 1), BigInteger.ONE);
        int n = 0;
        for (int i = 0; i + 1 < chunk.length; i += 2) {
            int hw = (chunk[i] & 0xff) | ((chunk[i + 1] & 0xff) << 8);
            if ((hw & 0xff80) != 0x6480) continue;
            int fs = i;
            if (i >= 2) {
                int prev = (chunk[i - 2] & 0xff) | ((chunk[i - 1] & 0xff) << 8);
                if ((prev & 0xf800) == 0xf000) fs = i - 2;
            }
            Address fa = start.add(fs);
            if (getFunctionAt(fa) == null && disassemble(fa) && createFunction(fa, null) != null) n++;
        }
        println("FlatLoad: functions=" + n);
    }
}
```

Çağrı: `-postScript FlatLoad.java drv_ui.drv 0x30000000 0x200`.

### `drv_ui.drv` fonksiyon eşlemesi

| Fonksiyon | Anlamı |
|---|---|
| `FUN_30000200` | Dize kimliği önbelleği (kimliğe göre son erişilen girişleri tutar) |
| `FUN_300002f0` | Dize kimliği ile kaynak okuma; kayıt uzunluğundan 2 bayt (terminator) düşer |
| `FUN_300007c4` | UTF-16 karakter sınıflandırıcı: `0x0000` EOF, `0xfeff` Unicode bayrağı, `0x000a` / `0x000d` / `0x000d 0x000a` satır sonu |
| `FUN_3000083c` | 8-bit karakter sınıflandırıcı |
| `FUN_30008600` | Çok satırlı `put_string` (hizalama `x` hesabı) |
| `FUN_30009070` | Kayan yazı başlatma: ilk 0x66 bayt içinde sonlandırıcı arar, iki boşluk ekler, BOM'u atlar |
| `FUN_30009674` | Kayan yazı adımı (`scroll_desc` 0x7c bayt) |

## Banka düzeni için yapılan ve sonuç vermeyen girişimler

- `drv_ui.drv` içinde JAL/JALX hedef histogramı (kayıtlarda yeterli yoğunluk
  yok; çağrılar `lw` ile literal havuzundan işaretçi yüklenip `jalr` ile yapılıyor).
- 32 bit kelime histogramı: yalnızca `0x9fc0b000` (RAM verisi), `0xbfc09000`
  ve `0xbfc0a000` (resident kod) bölgeleri belirgin; kod yarım kelimeleri
  gürültü ürettiği için banka yükleme adresleri çıkarılamadı.
- `tools/apinfo.py` `.drv` için anlamsız çıktı verir (başlık farklı).

## Komut dili notu

Kabukta `echo =====` gibi satırlar zsh'de komut sanılabilir; ayırıcı için
`printf` kullan.
