# DEVAM (18 Eylül 2026)

Bu dosya, evdeki masaüstü bilgisayardaki opencode oturumunun kaldığı yerden devam
edebilmesi için hazırlandı. İlk iş olarak okuyun.

## DEVAM (21 Eylül 2026) — Fatura takibi + Nakit kaldırma, hata düzeltmeleri, derleme + Release (1.0.4.5)

Bu bölüm **ev masaüstünde**, aynı Claude Code oturumunda (1.0.4.3'ü yapan
oturumun devamı) yapıldı. Ayrıntı için `CLAUDE.md` madde 4 "1.0.4.5"
bölümüne bakın — özet:

### İstenen iş kuralı değişikliği
Kullanıcı: ödeme her zaman Kredi Kartı ya da Havale/IBAN ile yapılıyor;
"Fatura" bir ödeme yöntemi değil, ödemeden SONRA misafirin isteği üzerine
ayrıca kesilen bir belge. Bunun üzerine:
- `database.ODEME_SEKILLERI` → yalnızca `["Kredi Karti", "Havale/IBAN"]`
  (Nakit VE Fatura kaldırıldı — ilk denemede sadece Nakit kaldırılmış,
  kullanıcı "Fatura da bir ödeme yöntemi değil" diye düzeltti).
- Yeni, ödeme yönteminden bağımsız fatura takibi: `rezervasyon_odalar`'a
  `fatura_istiyor`/`fatura_alindi` kolonları (otomatik migrasyon). Check-in'de
  "Fatura İstiyor" işaretlenir; Oda Durumu'nda ve rezervasyon detayında
  "Fatura alınmalı/alındı" gösterilir; ödeme alınırken sorulur; detayda tek
  tıkla işaretlenebilir.

### Push öncesi "baştan aşağı bak" turu (kullanıcı istedi)
Kullanıcı commit/push'tan önce projeyi yeniden gözden geçirmemi istedi. 2
paralel ajanla hem yeni fatura özelliğini hem de **1.0.4.4'ün (laptop
oturumu) daha önce hiç incelenmemiş kodunu** taradım. İki gerçek hata
bulundu ve düzeltildi:
1. **Kendi hatam:** `oda_degistir`'in kalış-ortası bölme INSERT'i yeni
   fatura kolonlarını kopyalamıyordu (1.0.4.3'teki yabancı-misafir-alanı
   hatasının aynısı, bu kez kendi yeni kolonlarımda).
2. **Laptop oturumunun hatası:** `CikisTab._cikisi_uygula` çıkışı her zaman
   BUGÜN olarak kaydediyordu (seçili tarihi yalnızca borç önizlemesinde
   kullanıyordu) — geçmiş bir günün çıkışını işlerken hem yanlış tarih
   kaydediliyor hem de aradaki günlerin meşru, faturalanmamış tutarları
   sessizce siliniyordu.

Kullanıcı ayrıca 3 küçük ek sorun sordu/buldurdu, hepsi düzeltildi: çıkış
yapmış bir odada tarih/gece/oda değiştirme artık hem UI hem repository
katmanında engelleniyor; "Erken Çıkışlar" borç/gecikmiş göstergesi artık
sekmedeki tarihi kullanıyor; telefon doğrulama ülke kodsuz 10 haneli
numaraları kabul ediyor. Ayrıca kullanıcı bir soru sordu (kod değişikliği
gerektirmedi): çıkış sonrası, çıkıştan ÖNCEKİ günler takvimde siliniyor mu?
Hayır, `doluluk_haritasi` yalnızca `cikis_tarihi`'nden sonraki geceleri
atlıyor — geçmiş kayıt korunuyor.

### Derleme + Release (kullanıcı özellikle istedi)
`versiyon.py` → 1.0.4.5. Bu makinede ilk kez `python guncelleme_olustur.py
--tam` + Kurulum Aracı + Standalone derlemeleri CLAUDE.md madde 6'daki
adımlarla üretildi (PyInstaller 6.20.0, Inno Setup 6 kuruluymuş —
`%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe`). Üç exe de açılıp
(pencere göründü) kapatılarak duman testinden geçirildi.
**GitHub Release `v1.0.4.5` gerçekten `gh release create` ile açıldı**, 3
asset yüklendi (`Misafirhane_Kurulumu_1.0.4.5.exe`,
`Misafirhane_Guncelleme_1.0.4.5.exe`, `Misafirhane_1.0.4.5.exe`) —
`gh release view v1.0.4.5` ile doğrulandı.

**Bilinmesi gereken kısıt:** bu makinenin `dagitim/son_manifest.json`'ı bu
build'e kadar 1.0.4.2'den kalmaydı (1.0.4.3 bu makinede hiç derlenmedi,
1.0.4.4 laptopta derlendi ve o dagitim/ buraya senkronlanmadı — gitignore'lu).
`Misafirhane_Guncelleme_1.0.4.5.exe` bu yüzden "1.0.4.2 → 1.0.4.5" farkı
olarak üretildi. Kurulu sürüm gerçekten 1.0.4.2 ise sorunsuz çalışır; başka
bir sürümse, 1.0.4.3'te eklenen `onceki_surum` kontrolü bunu güvenle
reddeder (veri kaybı yok), kullanıcı Kurulum Aracı'ndaki "Tamir Et"i
kullanmalı. Bu build sonunda `dagitim/son_manifest.json` artık 1.0.4.5'i
yansıtıyor (doğrulandı) — bir SONRAKİ güncelleme exe'si bu sorunu
yaşamayacak, baseline artık güncel.

### Commit'ler
- `f45882b` — fonksiyonel değişiklikler (fatura/nakit + tüm hata
  düzeltmeleri + `versiyon.py` 1.0.4.5 + `README.md`).
- Bu commit'in hemen ardından bir docs commit'i — `CLAUDE.md`/`DEVAM.md`.

### Test
`py_compile` tüm değişen dosyalarda; `kbs_test.py`, `oda_degistir_kbs_test.py`
(repo) geçti; yeni scratchpad testleri yazıldı (fatura/nakit akışı uçtan uca,
çıkış-sonrası düzenleme engeli, telefon doğrulama vakaları) — hepsi geçti;
`buton_test.py`/`coklu_test.py` (Temp\opencode) birden fazla kez tekrar
çalıştırıldı, hepsi geçti.

## DEVAM (21 Eylül 2026) — laptop oturumu: hata düzeltmeleri + Erken Çıkış (1.0.4.4, GitHub Release VAR)

**DÜZELTME (21 Eylül 2026, ev masaüstünde):** bu bölümün aşağıdaki son
satırı "GitHub Release açılmadı" diyordu — bu YANLIŞTI. `gh release list`
ile kontrol edildi: **`v1.0.4.4` release'i gerçekten yayında**, `Latest`
etiketli, 3 asset'i de yüklü (`Misafirhane_1.0.4.4.exe`,
`Misafirhane_Guncelleme_1.0.4.4.exe`, `Misafirhane_Kurulumu_1.0.4.4.exe`),
published 2026-09-20T22:29:01Z — push zamanıyla saniyesi saniyesine
eşleşiyor. Yani release fiilen açılmış ama laptop oturumu kendi notuna
yanlış yazmış. Bundan sonra release durumu bu dosyaya değil
`gh release list --repo DorDeorz/misafirhane-app` çıktısına göre kontrol
edilmeli.

Bu bölüm **başka bir Claude Code oturumu** (Claude Sonnet 5), ev masaüstü
DIŞINDA bir makinede (laptop) yapıldı. Ayrıntılı liste için `CLAUDE.md`
madde 4 "1.0.4.4" bölümüne bakın — burada özet:

- Oturum başında bu makinedeki eski/senkronsuz yerel kopya
  `git reset --hard origin/main` ile GitHub'ın güncel hâline (1.0.4.3)
  eşitlendi; test veritabanları/yedekler ve derleme klasörleri temizlendi.
- Kullanıcı "projeyi incele, hata bul" dedi; iki paralel ajanla
  main.py/repository.py/detay_dialog.py tarandı, bulunanlar onayla düzeltildi:
  içerideki misafirin rezervasyonu iptal edilememesi, check-in "Sil" butonu,
  aynı gün check-in kilidi, gece uzatmada kişi bazlı fiyat, erken çıkışta
  gelecek ödemelerin temizlenmesi + oda durumunun doğru "temizlikte" olması,
  telefon +90 doğrulama, KBS/export Excel formül enjeksiyonu koruması,
  güncelleme aracı sürüm kontrolü boşluğu, şifre uzunluğu kontrolü, aynı
  odaya taşımanın engellenmesi, check-in'in tek transaction'da olması, ve
  daha fazlası.
- Kullanıcı iki özellik istedi: **Erken Çıkışlar** bölümü (Çıkış sekmesi,
  ödenmemiş borç gösterimiyle) ve **+1/-1 Gece butonlarının artık pencereyi
  kapatmaması** (+ çakışmada net "gece eklenemiyor" uyarısı). İkisi de
  eklendi.
- Kullanıcı ayrıca **tam bir arayüz yeniden tasarımı** istedi; yapıldı, ama
  beğenilmedi (önce "butonlar çok büyük", sonra "tasarımı hiç beğenmedim, eski
  hâline döndür" dendi). **`tema.py` şu an origin/main ile birebir aynı**
  (tasarım tamamen geri alındı). Tek kalıcı istisna: pencere açılışta
  `showMaximized()` kullanıyor (kullanıcı bunu ayrıca, tasarımdan bağımsız
  olarak istedi). **Sonraki oturum: kullanıcı büyük/modern bir redesign
  istemiyor, mevcut kompakt görünümden memnun — tekrar önermeyin.**
- `versiyon.py` → 1.0.4.4 + YENILIKLER; README güncellendi. Kod GitHub'a push
  edildi. `guncelleme_olustur.py --tam` + Kurulum Aracı + Standalone
  derlemeleri üretildi; `Misafirhane_Kurulumu_1.0.4.4.exe` kullanıcının
  Masaüstü'ne kopyalandı. ~~GitHub Release açılmadı (kullanıcı istemedi).~~
  **YANLIŞ NOT — bkz. bu bölümün başındaki düzeltme: release fiilen açılmış
  ve yayında.**

## DEVAM (20 Eylül 2026) — Claude Code kod incelemesi + hata düzeltmeleri (1.0.4.3, release YOK)

Bu bölüm **Claude Code** (Claude Sonnet 5) ile bu makinede (ev masaüstü)
yapıldı; laptoptan devam edilecekse bu bölümü baştan sona okuyun — sonraki
oturumun bilmesi gereken her şey burada.

### Ne istendi, ne yapıldı
Kullanıcı "projeyi denetle" dedi (CLAUDE.md, DEVAM.md, README.md okunduktan
sonra `main.py`, `repository.py`, `detay_dialog.py`, `database.py`, `kbs.py`,
`kbs_pencere.py`, `kurulum_araci.py`, `guncelleme_olustur.py` incelendi — 4
paralel ajanla, her biri ~1300-2500 satırlık dosyaları uçtan uca okudu).
Bulunan TÜM hatalar kullanıcı onayıyla düzeltildi (aşağıda), uygulama test
DB'siyle (`misafirhane_deneme.db`) açılıp kullanıcı tarafından elle denendi,
sonra **GitHub'a push edildi** (release/exe ÜRETİLMEDİ — kullanıcı özellikle
istemedi, "sadece push, release gerek yok" dedi).

**Commit'ler (main dalı):**
- `8767217` — fonksiyonel düzeltmeler (kod + `versiyon.py` 1.0.4.3 +
  `README.md` sürüm notu + yeni `oda_degistir_kbs_test.py`).
- Bu commit'in hemen ardından bir docs commit'i — `CLAUDE.md` (bu oturuma
  kadar git'e hiç commit'lenmemişti, ilk kez eklendi) ve bu `DEVAM.md` bölümü.

### Düzeltilen hatalar (özet — ayrıntı için CLAUDE.md madde 4 "1.0.4.3")
1. **[EN KRİTİK] KBS oda değiştirme hataları** — `repository.oda_degistir`
   kalış ortasında oda değiştirirken satırı ikiye bölüyor (eski satır kesime
   kadar, yeni satır kesimden devam). Üç hata vardı ve hepsi tek bir kök
   nedene bağlıydı: eski ve yeni satır arasında hiçbir bağlantı yoktu.
   - Yabancı misafirin KBS alanları (uyruk, doğum tarihi, cinsiyet, doğum
     yeri, belge türü) yeni satıra kopyalanmıyordu.
   - Eski satırın `cikis_tarihi`'si hiç set edilmiyordu → hem
     `bugun_cikacaklar()` yanlışlıkla "bugün çıkıyor" gösteriyordu, hem de
     `rezervasyon_listesi`'nin `acik_odasi` sayacı yüzünden bu rezervasyon
     ASLA "Geçmiş Kayıtlar"a düşmüyordu (oda değiştirmiş her rezervasyon
     sonsuza dek "açık" sayılıyordu — bunu ben (Claude) incelerken buldum,
     orijinal bulgu listesinde yoktu).
   - Aynı fiziksel misafir için KBS'de İKİ ayrı "giriş" bildirimi çıkıyordu
     (eski + yeni satır, ikisi de `checkin_yapildi=1` ve kendi `misafirler`
     kopyasıyla).
   - **Çözüm:** `rezervasyon_odalar`'a `onceki_ro_id INTEGER` kolonu eklendi
     (database.py, eski DB'ler için otomatik migrasyon var — `misafirler`
     tablosundaki yabancı alan migrasyonuyla AYNI desen, test edildi: hem
     sıfırdan DB hem eski şemalı DB üzerinde çalıştı, veri kaybı yok).
     `oda_degistir` artık tüm yabancı alanları kopyalıyor, eski satırı kesim
     tarihinde kapatıyor (`cikis_tarihi`), yeni satırı `onceki_ro_id` ile
     eskiye bağlıyor. `kbs.kbs_bekleyenler` bu bağı kullanıyor.
2. **KBS "gönderildi" takip anahtarı çakışması** — aynı odada 2+ misafir
   varsa hepsi `"<ro_id>:giris"` anahtarını paylaşıyordu; birini işaretlemek
   diğerlerini sessizce düşürüyordu. Anahtar artık misafir ID'sini de
   içeriyor: `"<ro_id>:<misafir_id>:giris"`.
3. **Yerli/yabancı yanlış sınıflandırma** — 11 haneli Yabancı Kimlik No
   (YKN) taşıyan, bilgileri tam yabancı misafirler TC şekli yüzünden "yerli"
   sayılabiliyordu. Yeni `kbs.misafir_tipi()` önce check-in'de toplanan
   yabancı alanlarının doluluğuna bakıyor.
4. **T.C. Kimlik No doğrulaması check-in'de zorunlu değildi** — sadece "11
   haneli rakam" kontrol ediliyordu; gerçek sağlama algoritması
   (`kbs.tc_dogrula`, zaten doğru yazılmıştı) yalnızca KBS Excel raporunda
   bilgi notuydu, kaydı engellemiyordu. Artık check-in `tc_dogrula()` ile
   zorunlu doğruluyor.
5. **KBS Excel formül enjeksiyonu** — elle girilen alanlar (`=`/`+`/`-`/`@`
   ile başlarsa) Excel'de formül sanılabiliyordu; artık `_guvenli_hucre()`
   ile korunuyor. "BİLDİRİM GEÇMİŞİ" sekmesi artık tur/ad/TC/oda/tarih
   bilgisini de kaydediyor (öncesinde hep boştu — kolonlar tanımlıydı ama
   hiç yazılmıyordu).
6. **Çok odalı "Oda Değiştir" çökmesi** — `main.py`'de `QInputDialog` üst
   seviyede import edilmemişti; birden fazla odalı rezervasyonda "Oda
   Değiştir"e tıklamak `NameError` ile çöküyordu. Düzeltildi + kullanılmayan
   3 import temizlendi.
7. **Kapasite/transaction/hata yönetimi** — oda değiştirmede kapasite
   kontrolü artık ekstra yatak hakkını da sayıyor (`repository.oda_liman()`
   ile üç yerdeki tekrar birleştirildi); misafir kaydı + ödeme yeniden
   hesaplama artık tek transaction'da; İstatistik sekmesi hata olduğunda
   "0" değil açık uyarı gösteriyor.
8. **Güncelleme aracı** (`guncelleme_araci/guncelle.py`) — artık her hatayı
   yakalayıp gösteriyor (öncesinde `--windowed` exe sessizce çökebiliyordu);
   yanlış/eski sürümden gelen paket engelleniyor (`onceki_surum` kontrolü);
   yedekleme başarısız olursa kullanıcı bilgilendiriliyor.
9. **Kurulum Aracı** — `calistir_bekle()`'de WinAPI dönüş değerleri artık
   kontrol ediliyor (veri silme kararını etkileyen `kod==0` asla varsayılan
   olarak dönmüyor).

### Bilinçli DEĞİŞTİRİLMEYEN noktalar (bug değil, tasarım/kalite kararı)
- KBS "bekleyen çıkışlar" listesi hâlâ "bugün"le sınırlı değil — kasıtlı,
  güvenlik ağı (hiç bildirilmemiş eski kayıtları da göstermeli).
- `main.py`'deki fiyat önizleme tekrarı, `CheckinDialog`'daki index'li tuple
  yapısı, `repository.py`'de ~8 yerde tekrarlanan "etkin çıkış tarihi" SQL
  parçası: kod kalitesi/bakım konusu, değiştirmenin riski faydasından büyük.

### Test
`py_compile` tüm değişen dosyalarda geçti. Mevcut testler: `kbs_test.py`
(repoda), `buton_test.py`, `coklu_test.py` (Temp\opencode) geçti. Yeni
`oda_degistir_kbs_test.py` (repo köküne eklendi, izole TEMP DB kullanır,
gerçek veriye dokunmaz) yazıldı ve geçti — oda değiştirme + KBS zincirini
uçtan uca doğruluyor (mükerrer giriş yok, sahte çıkış yok, yabancı bilgisi
korunuyor, gerçek çıkışta doğru tek bildirim). `gece_ui_test.py`
(Temp\opencode, bu oturumda dokunulmamış bir alan) bu makinede takılıp kaldı
— ortamla ilgili önceden var olan bir sorun gibi duruyor, araştırılmadı,
düzeltmelerle ilgisi yok. Uygulama `dev_canli_calistir.py` ile test DB'siyle
açıldı, kullanıcı elle denedi, sorun bildirmedi.

### Laptopta devam ederken bilinmesi gerekenler
- `git pull` sonrası kod 1.0.4.3 düzeltmelerini içerir ama **exe/kurulum
  paketi ÜRETİLMEDİ** (release yok). Gerekirse CLAUDE.md madde 6'daki
  adımlarla üretilebilir.
- `misafirhane_deneme.db` / `misafirhane.db` / `kbs_takip.db` gitignore'lu —
  laptopta YOK. Test için gerekiyorsa yeniden oluşturulmalı (bkz.
  Temp\opencode'daki `kbs_musteri_db_olustur.py` gibi araçlar, onlar da
  gitignore'lu/yerel — laptopta yoksa sıfırdan yazılmalı) ya da ev
  bilgisayarından elle taşınmalı.
- `CLAUDE.md` bu oturuma kadar git'e hiç girmemişti; artık girdi — laptopta
  `git clone`/`pull` sonrası mevcut olacak.
- Ev makinesinde daha önceden bilinen commit'siz iş hâlâ geçerli:
  `guncelleme_olustur.py` A+B (TAM paket) ve `guncelle.py` sürüm kapısı
  değişiklikleri bu repoya hiç taşınmadı (bkz. aşağıdaki "1.0.4.1" bölümü).

## DEVAM (20 Eylül 2026) — Kurulum Aracı: veri silme seçeneği (1.0.4.2)

`kurulum_araci.py` güncellendi ve sürüm **1.0.4.2** olarak release edildi:
- **Kaldırmada 3'lü seçim**: `askyesnocancel` ile "Veritabanını ve verileri de
  silmek ister misiniz?" sorar. Evet → kaldırma başarılı olursa
  `%LOCALAPPDATA%\Misafirhane` (`veri_klasoru()`, `database.py` ile aynı kural)
  `shutil.rmtree` ile silinir; Hayır → veriler korunur; İptal → kaldırma iptal.
- Veri silme yalnızca uninstaller çıkış kodu 0 olunca yapılır; silme hatasında
  "el ile silmeniz gerekebilir" uyarısı gösterilir. `import shutil` eklendi.
- README'deki "Uygulamayı Kaldır" satırı güncellendi. Durum bitti mesajı seçime
  göre değişir ("veriler de silindi" / "verileriniz korundu").
- Bu bilgisayarda uçtan uca test edildi (kaldırma + veri silme akışı çalıştı);
  sonrasında 1.0.4.2 paketi (Kurulum Aracı + Kurulum + Guncelleme + standalone)
  derlenip GitHub Releases'e yüklendi ve kod push edildi.

## DEVAM (20 Eylül 2026) — 1.0.4.1 (push edildi)

Bu oturumda yapıldı:

### Kurulum Aracı (tek exe) — `kurulum_araci.py` (YENİ)
- Tkinter launcher: kurulum durumu kayıt defterinden (`HKLM\...\Uninstall\{AppId}_is1`, KEY_WOW64_64KEY)
  ve `surum.txt`'ten okunur; **Yükle / Güncelle / Tamir Et / Uygulamayı Kaldır** butonları.
- Gömülü `dist\kurulum\Misafirhane_Kurulum.exe` (temiz hibrit: `UsePreviousAppDir=yes`,
  `DirExistsWarning=no`, `[Code] InitializeSetup` taskkill) ShellExecuteEx `runas` (UAC) ile
  çalıştırılıp beklenir (SEE_MASK_NOCLOSEPROCESS).
- Kaldırma: `UninstallString` (unins000.exe) + `taskkill /F /T /IM Misafirhane.exe`;
  veriler `%LOCALAPPDATA%\Misafirhane` korunur; 4. buton kırmızı (tehlike) stil.
- Tema **Windows koyu/açık moduna bağlandı**: `HKCU\...\Themes\Personalize\AppsUseLightTheme`
  (0=karanlık). `MISAFIRHANE_TEMA=acik|karanlik` ile zorlanabilir. Ayrı
  `kurulum_araci_karanlik.py` kaldırıldı; tek exe: `dagitim\Misafirhane_Kurulumu_1.0.4.1.exe`
  (SHA256 `2D72A5BE...`).
- Sürüm 1.0.4 → 1.0.4.1 (`versiyon.py` + `surum.txt`); Kurulum exe'si `/DMyAppVersion=1.0.4.1`.
  Launcher "Paket sürümü" için `--add-data versiyon.py;.` ile `versiyon.py`'yi gömer.
- README güncellendi (Kurulum Aracı bölümü + 1.0.4.1 sürüm notu).
- Commit kapsamı: `kurulum_araci.py`, `kurulum.iss`, `versiyon.py`, `README.md`, `DEVAM.md`.

### Push edilmedi (bekliyor)
- `guncelleme_olustur.py` A+B (TAM paket) + `guncelleme_araci/guncelle.py` sürüm kapısı — commit'siz.
- GitHub Releases'e asset yükleme — kullanıcı onayı bekleniyor.

## DEVAM (19 Eylül 2026) — 1.0.4

Bir sonraki oturum şunları bilir (hepsi commit/push edildi):

### KBS (1774 sayılı Kanun) — `kbs.py`, `kbs_pencere.py` (YENİ dosyalar, git'e eklendi)
- `kbs.py`: `tanitim_kodu_gecerli_mi` (11 hane + rakam -> "yerli", yabancı -> "yabanci"),
  `YABANCI_ALANLAR` (uyruk, dogum_tarihi, cinsiyet, dogum_yeri, belge_turu).
- `kbs_pencere.py`: `KbsPencere(db_yolu=None, parent=None, takip_yolu=None)` —
  bekleyen giriş (check-in'li yabancı) ve çıkış (o gün çıkacak) bildirimleri,
  şahıs TC doğrulaması, "Gönderildi" işaretleme, Excel çıktısı, genel özet.
  Takip `kbs_takip.db` (VERI_KLASORU) içinde; uygulama yeniden açılınca korunur.
- `main.py`: üst barda `kbs_btn = "🛂 KBS Bildirimi"` -> `kbs_penceresini_ac()`
  (takip_yolu=os.path.join(database.VERI_KLASORU, "kbs_takip.db")). `database.py`
  değişti (kullanıcı/odalar özetleri, excel kullanımı).
- Yabancı alan toplama: `YabanciBilgiDialog` (detay_dialog.py); check-in'de eksik
  bilgi girilirse kayıt engellenir; detay "Odada Kalan Misafirler" tablosu 9->5
  sütuna sadeleşti (Oda, Ad Soyad, Belge No, Yerli/Yabancı, Yabancı Bilgisi).
- TC doğrulama: yerli 11 hane rakam; yabancı belge no max 32 karakter.

### Test veritabanı (yerel, gitignore'lu — asla push EDİLMEZ)
- `misafirhane_deneme.db`: kullanıcılar canlıdan kopyalandı (`oğuz` korundu),
  18 oda, senaryolar rez 1001-1008 / ro 2001-2012. Geçerli TC'ler: Ahmet
  `10000000146`, Ayşe `10000000528`, Hasan `10000000900`; bozuk: `11111111111` (Veli).
  Bekleyen KBS: 6 giriş + 2 çıkış. Araçlar temp'te: `kbs_musteri_db_olustur.py`,
  `kbs_sok_test.py`, `ui_sok_test.py`, `coklu_test.py`, `buton_test.py`,
  `gece_ui_test.py`.
- Canlı DB `%LOCALAPPDATA%\Misafirhane\misafirhane.db`'e dokunulmadı. Launcher:
  `Temp\opencode\dev_canli_calistir.py` (test DB'ye yönlü).

### Arayüz yeniden tasarımı (laptop dostu / tutarlı)
- `tema.py`: `rozet(metin, renk)` ortak rozet + kompakt QSS (aydınlık+karanlık):
  sekme 6px 10px, QGroupBox margin-top 9/padding 6 8, buton min-height 24,
  giriş padding 3 7.
- `detay_dialog.py` RezervasyonDetayDialog: tek satır kompakt başlık (ad + durum
  rozeti + oda + tarih/gece + alınma), QSplitter (sol: misafir formu max 360,
  sağ: odalar + odada kalanlar), alt aksiyon çubuğu (İptal / Kapat / 💾 Kaydet birincil).
- Oda işlemleri tablodan çıkarıldı -> satır seçimi + tablo ALTI aksiyon çubuğu:
  👥 Kişiler/Check-in · 🛏 +1 Gece · 🛏 −1 Gece · 🗓 Tarih / Gece · 🔁 Oda Değiştir ·
  🚪 Çıkış Yap (birincil). `_oda_secim_degisti` / `_secili_oda` / `_oda_gece_degistir`.
- CheckinDialog kompakt (720x480), "Check-in'i Tamamla" birincil; satır yüksekliği 34.
- `main.py`: Checkin/Çıkış/Yeni Oda/Fiyat Kaydet butonları `birincil`; OdaDurumu
  çift `ozet_label` hatası giderildi; "Şu an: admin" sabit yazısı -> gerçek
  kullanıcı; tüm sekmelere tutarlı `layout.setSpacing(6)`; RezervasyonYonetimi
  bilgi metni netleştirildi.

### Gece uzat / kısalt + çakışmada gece azaltma önerisi
- `repository.py` `rezervasyon_odasi_tarih_degistir`: başlamış konaklamada (giriş
  geçmişte) giriş SABİT, yalnızca gece değişebilir; eski "Geçmiş tarihe taşınamaz"
  bloğu buna göre gevşetildi. Çakışma hatası artık "en fazla N gece sığar" önerisi
  verir. Yeni: `_odasi_max_gece_cur` / `odasi_max_gece(ro_id, yeni_giris)`.
- `detay_dialog.py`: `_tarih_degistir_akisi(ebeveyn, ro, giris, gece)` ortak akış —
  çakışırsa "gece sayısını N'e düşürmen gerekir, onaylıyor musun?" -> Evet -> N ile
  uygulanır; düşen ödenmiş geceler uyarısı korunur. `OdaTarihDialog` ("Tarih / Gece
  Düzenle"): canlı önizleme (yeni çıkış, çakışma, en fazla sığan gece), başlamış
  konaklamada giriş kilitli. Detayda 🛏 +1 / −1 Gece hızlı düğmeleri.
- Test kanıtı: 2001 (içeride) gece 3->4->3; 2010 giriş +1 gün, 2 gece istenince
  Ahmet ile çakışma -> önerilen 1 gece onayla uygulandı.

### Sürüm ve dağıtım
- `versiyon.py` `SURUM = "1.0.4"` + YENILIKLER girdisi. README.md baştan yazıldı
  (her şey teker teker). DEVAM.md bu bölüm. `Misafirhane_1.0.4.exe` (tek dosyalık
  derleme) repoya eklendi. Güncelleme/kurulum exe'leri Releases içindir
  (makinede `gh` ve ISCC yoktu; tek dosya exe repo kökünde).

## Sürüm şeması (kullanıcı kararı)
- Büyük/belirgin özellik güncellemesi: 1.0.2 -> 1.0.3
- Yayınlanmış sürümde hata düzeltmesi: sona bir sayı eklenir: 1.0.2 -> 1.0.2.1 -> 1.0.2.2
- `versiyon.py` `gecmise_cevir` 4 parçalı sürümleri destekler (1.0.2.1 > 1.0.2).

## İş akışı (yeni kural, kullanıcı kararı)
1. Güncelleme/patch üretmeden ÖNCE uygulama cmd'den (dev mod) açılıp test edilir:
   `python main.py` (klasör: misafirhane_app).
2. Testi KULLANICI yapar; çalışıp çalışmadığını ve gereken değişiklikleri bildirir.
3. Kullanıcı onayı verince exe üretilir: `python guncelleme_olustur.py`
   -> `dagitim\Misafirhane_Guncelleme_<surum>.exe` -> Masaüstüne kopyalanır.

## Bugün yapılanlar (1.0.3)
- **Çok odalı rezervasyon**: tek rezervasyona birden çok oda; `database.py` rezervasyonlar/
  rezervasyon_odalar şeması; `repository.rezervasyon_olustur(odalar_list, ...)`; Yeni
  Rezervasyon çok odalı giriş, detay ekranı (`detay_dialog.py`), oda değiştirme ve
  check-in/çıkış oda satırı bazlı.
- **Geçmiş Kayıtlar**: Rezervasyon Yönetimi'nde yeni "Göster" filtresi
  (`rezervasyon_listesi("gecmis")`, `acik_odasi=0 HAVING`) — çıkışı yapılmış eski
  misafirler aranabilir/sıralanabilir/Excel'e aktarılabilir.
- **Günün Girişleri**: çok odalı rezervasyon tek satır; "Oda Durumları" sütununda her
  oda için Geldi/Gelmedi/Bekleniyor; Durum sütunu Kısmen Geldi (n/m).
- **Performans**: arama yalnızca Ad Soyad; 250 ms debounce (`QTimer`); N+1 fiyat/tutar
  sorgusu yerine `rezervasyonlari_toplam_ozeti` (tek sorgu, export da kullanır);
  `setRowCount` + `setUpdatesEnabled(False)`; 250+ satırda işlem butonları gizlenir
  (çift tık -> detay). Ölçüm: 1168 satır ~140 ms, arama ~35 ms.
- **Düzeltmeler**: `rezervasyon_odalar_listele` artık `ad_soyad` vb. içerir (Oda Değiştir /
  Tarih Değiştir açılmıyordu); `tema.renklendir` `setForeground`'a string geçiyordu
  (iptal listesinde çökme) -> QColor.

## Bugün yapılanlar (1.0.2 -> 1.0.2.2)
- **Oda Değiştir dialogu** tabloya çevrildi (`main.py`, `OdaDegistirDialog`): sütunlar
  Oda / Tip / Kapasite / Oda Durumu / Bu Aralıkta Müsaitlik; renk: yeşil=boş,
  kırmızı=aralıkta dolu (isimleriyle), gri=seçilemez; çift tık ile seçim.
- **Takvim**: ad yalnızca giriş gününde (kalın) yazılır, diğer geceler X olur;
  tooltip'te isim, giriş-çıkış, rezervasyon #, fiyat, referans
  (`takvim_widget.py`, `_hucreyi_ciz`). Hem "Yeni Rezervasyon" hem "Takvim Görünümü".
- **Takvim ipucu hatası** (1.0.2.1): `sqlite3.Row`'da `.get()` yok, `[]` kullanılır.
- **ÖNEMLİ HATA DÜZELTMESİ (1.0.2.2)**: Oda Değiştir rezervasyonu iki parçaya böler;
  ilk parçanın giriş tarihi değiştirilince aynı gece iki odada görünme oluyordu.
  `repository.py` `rezervasyon_tarih_degistir` artık:
  - `_oda_degistirme_devami()` / `_oda_degistirme_oncesi()` parçaları `notlar`'daki
    `[Oda değişikliği: önceki oda ID X]` işaretiyle (regex) bağlar;
  - ilk parça düzenlenirse kesim tarihi sabit tutulur, toplam gece iki parçaya paylaşılır;
  - devam/önceki parça otomatik dengelenir; çakışma olursa `ValueError`;
  - `_odemeleri_yeniden_kur()` ödemeleri tarih eşleşmesiyle yeniden kurar,
    düşen ödenmiş gecelerin listesini döndürür (UI gösterir).
  - Test kanıtı: temp'te `tarih_degistir_test.py` (senaryo: giriş 18, 3 gece,
    20'sinde oda değiştir, girişi 19'a al -> çakışma yok, toplam gece korunur).

## Mevcut durum / SIRADAKİ
- `versiyon.py` `SURUM = "1.0.3"`; YENILIKLER güncel; README'ye 1.0.2 / 1.0.2.1 / 1.0.2.2 / 1.0.3
  satırları da eklendi.
- 1.0.3 exe'leri ÜRETİLDİ ve Masaüstüne kopyalandı: `Misafirhane_Guncelleme_1.0.3.exe`,
  `Misafirhane_Kurulum_1.0.3.exe` (SHA256 yukarıda adımlarda; `Get-FileHash`).
- Uygulama kullanıcı tarafından dev modda test edildi ve onaylandı. Kod 1.0.3 olarak
  commit/push edildi. Sıradaki adım (istenirse): exe'leri GitHub Releases'e yükle
  (makinede `gh` CLI yok, elle/`gh` ile yapılır).

## Teknik ortam
- Repo kökü: `misafirhane_app` (git bu klasörde). Uzak: `github.com/DorDeorz/misafirhane-app`,
  dal `main`. Tarihçe: `f2ac5b1` (ilk), `9dd4bac` (1.0.1). Release: `v1.0.1` (iki exe).
- Python: `C:\Users\oguzh\AppData\Local\Programs\Python\Python312\python.exe`
- Geliştirme DB: proje klasöründeki `misafirhane.db` (gitignore'lu). Frozen (exe) veri:
  `%LOCALAPPDATA%\Misafirhane\`.
- Güncelleme üretimi: `python guncelleme_olustur.py` -> `dagitim\Misafirhane_Guncelleme_<surum>.exe`
  (SHA256 için `Get-FileHash`).
- Windows PowerShell'de `git -C <repos> ...` ve `gh --repo DorDeorz/misafirhane-app ...`
  kullanın (workdir güvenilmez). Türkçe karakterli satır bozulabiliyor: komut argümanlarında
  ASCII tercih edin.
- PyInstaller üretimleri (`build/`, `dist/`, `*.spec`, `dagitim/`, `*.db`) gitignore'lu,
  repo'ya gitmez.