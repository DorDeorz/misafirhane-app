# Misafirhane Rezervasyon — Proje Anlatımı (Claude Code için)

Bu belge, projenin geçmişini ve bugünkü durumunu hiçbir şeyi atlamadan anlatır.
GitHub push'ları, olan sürümler, yapılan güncellemeler, test ortamı ve çalışma
kuralları teker teker aşağıdadır. İlk iş olarak oku.

---

## 1. Proje nedir?

**Misafirhane Rezervasyon** — tek bilgisayarda (Windows) çalışan Türkçe bir
misafirhane/pansiyon yönetim uygulaması.

- **Teknoloji:** Python 3 + PySide6 (Qt) GUI · SQLite veritabanı · PyInstaller
  ile derleme (onedir + tek dosya) · Inno Setup (kurulum motoru) · Tkinter
  (Kurulum Aracı, ayrı araç).
- **Veri:** Tek kullanıcı (tek kurulum → tek yerel DB). Login kullanıcı adıyla
  açılır (varsayılan kullanıcı: `oğuz`).
- **Kullanım:** Rezervasyon kaydı (çok odalı: bir kayıtta birden çok oda),
  oda durumu/takvim, check-in / check-out (çıkış), günün girişleri, istatistikler,
  oda yönetimi, ayarlar, işlem geçmişi (denetim izi) ve **KBS Bildirimi**
  (1774 sayılı Kimlik Bildirme Kanunu) modülü.

---

## 2. Klasör yapısı ve dosyaların görevi

Proje kökü: `C:\Users\oguzh\Documents\misafirhane-app`

### Kaynak (Python)
- `main.py` — ana uygulama ve 11 sekme: Yeni Rezervasyon, Oda Durumu, Check-in,
  Günün Girişleri, Çıkış, Rezervasyon Yönetimi, İstatistik, Oda Yönetimi,
  Ayarlar, İşlem Geçmişi, Kullanıcılar.
- `database.py` — bağlantı, şema, `VERI_KLASORU`/`DB_PATH` mantığı, yardımcı
  sorgular, yedekleme.
- `repository.py` — iş katmanı: rezervasyon/oda/misafir CRUD, tarih/gece
  denetimi, çakışma kuralları, gece sayısı hesapları.
- `detay_dialog.py` — RezervasyonDetayDialog (splitter düzeni, kompakt başlık,
  misafirler tablosu, oda aksiyon çubuğu), CheckinDialog, OdaTarihDialog,
  YabanciBilgiDialog (KBS for yabancı misafir).
- `tema.py` — `rozet(metin, renk)`, kompakt QSS (aydınlık + karanlık), birincil
  buton stili.
- `kbs.py` — KBS ilgili izole yardımcılar (TC doğrulama, yabancı alan listesi).
- `kbs_pencere.py` — KBS Bildirimi penceresi (bekleyen giriş/çıkış, gönderildi
  işaretleme, Excel, özet).
- `versiyon.py` — `SURUM`, `YENILIKLER` sözlüğü, `gecmise_cevir()`.
- `guncelleme_olustur.py` — geliştirici aracı: uygulamayı derler, fark tespiti,
  güncelleme paketi + Güncelleme exe + Inno kurulum **motoru** üretir.
- `kurulum_araci.py` — **Kurulum Aracı** (Tkinter): Yükle / Güncelle / Tamir Et /
  Kaldır + veri silme seçeneği.
- `kurulum.iss` — Inno Setup betiği (hibrit: kurulum=kurulum=güncelleme=tamir tek exe).
- `loglama.py` — işlem geçmişi logu.
- `kbs_test.py` — KBS izole testi.
- `oda_degistir_kbs_test.py` — oda değiştirme + KBS zinciri izole regresyon
  testi (1.0.4.3; mükerrer giriş/sahte çıkış/yabancı bilgi kaybı senaryoları).

### Güncelleme altyapısı
- `guncelleme_araci/guncelle.py` + `main.py` — kurulu uygulamayı yerinde
  güncelleyen yardımcı (patch zip'i `_internal` üzerine yazar; veriler
  `%LOCALAPPDATA%`da korunur).
- `surum.txt` — mevcut sürüm (gitignore'lu, derlemede üretilir).

### Üretim (gitignore'lu — asla GitHub'a gitmez)
- `dist/` — PyInstaller çıktıları (Misafirhane onedir; kurulum motoru;
  tek dosya exe'ler).
- `dagitim/` — hazır paketler (guncelleme exe, güncelleme patch klasörleri,
  son_manifest.json).
- `build/`, `*.spec`, `*.db`, `surum.txt` — hepsi gitignore'lu.

### Veriler (özel — asla push edilmez)
- `misafirhane.db` — **geliştirme kopyası** (gerçek veri gibi, dev modunda DB
  yolu proje klasörü olduğu için burada görünür).
- `misafirhane_deneme.db` — test veritabanı (senaryolar).
- `kbs_takip.db` — KBS "gönderildi" takibi (dev).
- DONDURULMUŞ (exe) sürümde veriler `%LOCALAPPDATA%\Misafirhane\` altına yazılır;
  yedekler `%LOCALAPPDATA%\Misafirhane\yedekler\`.

---

## 3. Veri mimarisi (SQLite şeması)

Tablolar (`database.py` — `CREATE TABLE IF NOT EXISTS`):

- `odalar` — oda kayıtları (numara, tip, fiyat, aktif).
- `rezervasyonlar` — rezervasyon başlığı / ana kayıt.
- `rezervasyon_odalar` — rezervasyonun oda satırları **+ oda parçaları**
  (önceki/devam: oda değiştirme ve tarih değişikliği bu parçaları dengeler).
  `onceki_ro_id` (1.0.4.3) kalış ortasında oda değiştirmede oluşan satırı
  böldüğü eski satıra bağlar; KBS bu bağı kullanarak aynı misafir için
  mükerrer "giriş" bildirimi üretmez (bkz. `kbs.py` `kbs_bekleyenler`).
- `misafirler` — kişiler (ad soyad, TC, yabancı KBS bilgileri).
- `odemeler` — ödenen gece sayısı, toplam ücret, alınan ücret vb.
- `kullanicilar` — giriş kullanıcıları (iletki şifreli).
- `ayarlar` — uygulama ayarları.
- `islem_gecmisi` — denetim izi (işlem geçmişi).

`VERI_KLASORU` kuralı (`database.py`):
```
dondurulmus (exe)  -> %LOCALAPPDATA%\Misafirhane
gelistirme (python) -> proje klasörü (komut dosyasının bulunduğu dizin)
```
DB hiçbir zaman uygulama klasörüne (Program Files) yazılmaz; bu sayede
güncelleme/kaldırma veriye dokunmaz.

---

## 4. Sürüm geçmişi — adım adım, GitHub'a push'lar dahil

### İlk sürüm (commit `f2ac5b1`)
Temel rezervasyon sistemi: odalar, rezervasyon, odemeler, kullanicilar,
ayarlar, islem_gecmisi, takvim, rapor ve yedekleme. Sürüm 1.0.0.

### 1.0.1 (commit `9dd4bac`) → Release **v1.0.1**
- EXE paketleme başladı; veri dizini `%LOCALAPPDATA%\Misafirhane`'e alındı
  (Program Files'a yazılma sorunu çözüldü), pencere ikonu eklendi.
- Sürüm yönetimi (`versiyon.py`), güncelleme altyapısı
  (`guncelleme_olustur.py` + `guncelleme_araci/`) kuruldu.
- Ayarlar sekmesine sürüm bilgisi eklendi.
- **Release v1.0.1:** `Misafirhane_Kurulum_1.0.1.exe` (32,7 MB) +
  `Misafirhane_Guncelleme_1.0.1.exe` (12,4 MB).

### 1.0.2 / 1.0.2.1 (release yok, push edildi)
- 1.0.2: Oda Değiştir ekranı renk kodlu müsaitlik tablosuna geçti; takvimde
  misafir adı yalnızca giriş gününe, diğer gecelere `X` yazılır (aynı isimli
  rezervasyonlar ayırt edilebilir).
- 1.0.2.1: takvim ipuçlarında (referans) açılış hatası düzeltildi.

### 1.0.2.2 (commit `5546d02`) → push edildi
Oda değiştirme sonrası giriş tarihi değiştirilince aynı gece iki odada görünme
hatası çözüldü; oda parçaları (önceki/devam) otomatik dengelenir, ödemeler
yeniden kurulur.

### 1.0.3 (commit `565c14d`) → Release **v1.0.3**
- **Çok odalı rezervasyon:** tek kayıtta birden çok oda; oda satırı bazlı
  check-in/çıkış/oda değiştirme.
- **Geçmiş Kayıtlar** görünümü: çıkışı yapılmış eski misafirler, arama,
  sıralama, Excel dışa aktarma.
- Günün Girişleri'nde çok odalı rezervasyon tek satır + oda bazlı
  Geldi/Gelmedi/Bekleniyor durumu.
- Performans: arama yalnızca Ad Soyad'da anında filtreler, gecikmeli yenileme +
  toplu sorgular (büyük listelerde kasma giderildi).
- Düzeltmeler: Oda Değiştir / Tarih Değiştir pencerelerinin açılmama hatası,
  iptal listesinde satır renklendirme çökmesi.
- **Release v1.0.3:** `Misafirhane_Kurulum_1.0.3.exe` (36,1 MB) +
  `Misafirhane_Guncelleme_1.0.3.exe` (13,7 MB).

### 1.0.4 (commit `44f7f75`) → Release **v1.0.4**
- **KBS Bildirimi (1774 sayılı Kimlik Bildirme Kanunu):** ana pencerede
  "🛂 KBS Bildirimi" penceresi — bekleyen girişler (check-in'e alınan
  yabancılar) ve o gün çıkacaklar; şahıs TC doğrulaması; "Gönderildi"
  işaretleme (`kbs_takip.db` ile kalıcı); Excel (.xlsx) dışa aktarma; genel özet.
- **Yabancı misafir KBS alanları:** check-in'de uyruk, doğum tarihi
  (bilinmiyor dahil), cinsiyet, doğum yeri, belge türü toplanır; eksik bilgi
  kayıt engeli; geçersiz TC No engeli. Detay "Odada Kalan Misafirler" tablosu
  9 → 5 sütuna sadeleşti, Yerli/Yabancı + yabancı bilgi durumu gösterilir.
- **Arayüz yeniden tasarımı (laptop dostu):** kompakt tema + ortak durum
  rozetleri (`tema.py` `rozet()`), aydınlık/karanlık QSS; rezervasyon detayı
  tek satır kompakt başlık + splitter düzeni; oda işlemleri tablo içinden
  seçime dayalı **aksiyon çubuğuna** taşındı (buton sığmama sorunu çözüldü);
  CheckinDialog kompakt; birincil/ikincil buton stilleri; OdaDurumu çift özet
  düzeltmesi; "admin" sabit yazısı yerine gerçek kullanıcı adı; sekmelerde
  tutarlı `setSpacing(6)`.
- **Gece uzat/kısalt + çakışma yönetimi:** içerideki misafirde de gece sayısı
  uzatılıp kısaltılabilir (başlamış konaklamada giriş tarihi kilitli); tarih
  çakışmasında "gece sayısını azalt" önerisi + onay akışı; canlı çıkış/çakışma
  önizlemeli Tarih/Gece düzenleme penceresi; ödenmiş gece uyarısı.
- **Sürüm içeriği dosyaları:** `kbs.py`, `kbs_pencere.py`, `kbs_test.py` +
  `database.py`, `detay_dialog.py`, `main.py`, `repository.py`, `tema.py`,
  `versiyon.py`, README, DEVAM.
- **Release v1.0.4:** `Misafirhane_1.0.4.exe` (51,6 MB — standalone, ayrıca
  repo köküne commit'lendi) + `Misafirhane_Guncelleme_1.0.4.exe` (13,7 MB) +
  `Misafirhane_Kurulum_1.0.4.exe` (36,1 MB).

### 1.0.4.1 (commit `8d0a91a`, ev bilgisayarında yapıldı, push edildi)
- **Kurulum Aracı (`kurulum_araci.py`, yeni):** tek exe, Tkinter; kayıt
  defterinden kurulum durumu (HKLM uninstall anahtarı, `KEY_WOW64_64KEY`,
  `InstallLocation`, `Misafirhane.exe` varlığı, `surum.txt` ilk satırı) →
  **Yükle / Güncelle / Tamir Et / Uygulamayı Kaldır** butonları, duruma göre
  birincil/tehlikeli/kilitli stiller. Gömülü Inno kurulum motoru
  (`dist\kurulum\Misafirhane_Kurulum.exe`) `ShellExecuteEx runas` (UAC) ile
  çalıştırılıp beklenir (çıkış koduyla sonuç gösterilir). Kaldırma:
  `UninstallString` (unins000) + `taskkill`. Tema Windows koyu/açık modundan
  okunur (`AppsUseLightTheme`), `MISAFIRHANE_TEMA` ile zorlanabilir.
- **1.0.4.1 için release yapılmadı** (dağıtım evde bırakıldı; bu atölyede
  incumbent ile test edildi).
- DEVAM: `guncelleme_olustur.py` A+B (TAM paket) ve `guncelle.py` sürüm kapısı
  **push edilmeden bekliyor** (ev makinesinde kaldı, bu repoya gelmedi).

### 1.0.4.2 (commit `424d927`) → Release **v1.0.4.2**
- **Kurulum Aracı'nda Kaldırma geliştirmesi:** kaldırırken 3'lü seçim sorar —
  **Evet** → kaldırma başarılı olursa veri klasörü (`%LOCALAPPDATA%\Misafirhane`:
  misafirhane.db + kbs_takip.db + yedekler) kalıcı silinir (`shutil.rmtree`);
  **Hayır** → veriler korunur; **İptal** → kaldırma iptal. Veri silme yalnızca
  çıkış kodu 0 olunca yapılır; silme hatasında uyarı gösterilir.
- `versiyon.py` → 1.0.4.2 + YENILIKLER; README/DEVAM güncellendi.
- **Release v1.0.4.2** (güncel hâli): `Misafirhane_Kurulumu_1.0.4.2.exe`
  (45,6 MB — tek kurulum aracı) + `Misafirhane_Guncelleme_1.0.4.2.exe`
  (13,7 MB) + `Misafirhane_1.0.4.2.exe` (51,6 MB — standalone).
  İlk yüklenen `Misafirhane_Kurulum_1.0.4.2.exe` (Inno) asset'i **silindi**
  (tek kurulum aracı yeter).

### 93245ae (derleme aracı düzeltmesi, push edildi)
`guncelleme_olustur.py`: ayrı Inno `Misafirhane_Kurulum_<v>.exe` üretimi
**kapatıldı** — Inno motoru yalnızca Kurulum Aracı'na gömülmek için derlenir;
`dagitim/`'e kurulum exe kopyalanmaz.

### 1.0.4.3 (commit `8767217`, ev masaüstünde Claude Code kod incelemesiyle
yapıldı, push edildi — **release yok**, kullanıcı özellikle istemedi)

Kullanıcı "projeyi denetle" dedi; `main.py`, `repository.py`, `detay_dialog.py`,
`database.py`, `kbs.py`, `kbs_pencere.py`, `kurulum_araci.py`,
`guncelleme_olustur.py` dosyaları 4 paralel ajanla (repository+detay_dialog,
kbs+kbs_pencere, kurulum/güncelleme araçları, main.py) satır satır incelendi.
Bulunan hataların TAMAMI kullanıcı onayıyla düzeltildi:

- **KBS oda değiştirme hataları (en kritik bulgu):** `repository.oda_degistir`
  kalış ortasında bir oda satırını ikiye bölerken (eski satır kesime kadar
  kalır, yeni satır kesimden devam eder) üç ayrı hata vardı: (1) yabancı
  misafirin `uyruk`/`dogum_tarihi`/`cinsiyet`/`dogum_yeri`/`belge_turu`
  alanları yeni satıra kopyalanmıyordu → oda değiştiren yabancı misafir KBS'de
  yeniden "eksik bilgi" görünüyordu; (2) eski satırın `cikis_tarihi`'si hiç
  set edilmiyordu → hem `bugun_cikacaklar()` bu satırı kesim günü yanlışlıkla
  "bugün çıkıyor" olarak listeliyordu, hem de `rezervasyon_listesi`'nin
  `acik_odasi` sayacı bu rezervasyonun asla "Geçmiş Kayıtlar"a düşmemesine
  sebep oluyordu; (3) eski + yeni satırın ikisi de `checkin_yapildi=1` ve
  ayrı `misafirler` kopyalarıyla var olduğundan, `kbs.kbs_veri_topla` aynı
  fiziksel misafir için İKİ ayrı "giriş" bildirimi üretiyordu.
  **Çözüm:** `rezervasyon_odalar`'a `onceki_ro_id INTEGER` kolonu eklendi
  (database.py'de eski DB'ler için otomatik `ALTER TABLE` migrasyonu var,
  misafirler tablosundaki yabancı alan migrasyonuyla aynı desen). `oda_degistir`
  artık (a) tüm yabancı alanları kopyalıyor, (b) eski satırı kesim tarihinde
  `cikis_tarihi` ile kapatıyor, (c) yeni satırı `onceki_ro_id` ile eskiye
  bağlıyor. `kbs.kbs_bekleyenler` bu bağı kullanarak: `onceki_ro_id` dolu olan
  satırları "yeni giriş" saymıyor (misafir zaten bildirilmiş), ve bir satırın
  `onceki_ro_id` ile referans aldığı (yani üzerine devam satırı olan) satırları
  "çıkış" saymıyor (misafir otelden ayrılmadı, sadece oda değiştirdi).
- **KBS "gönderildi" takip anahtarı çakışması:** aynı odada 2+ misafir varsa
  hepsi aynı `"<ro_id>:giris"` anahtarını paylaşıyordu; birini "gönderildi"
  işaretlemek diğerlerini de sessizce düşürüyordu. Anahtar artık
  `"<ro_id>:<misafir_id>:giris"` / `:cikis` formatında.
- **Yerli/yabancı yanlış sınıflandırma:** `kbs.tanitim_kodu_gecerli_mi` sadece
  "11 haneli rakam mı" bakıyordu; Türkiye'nin yabancılara verdiği Yabancı
  Kimlik No (YKN) da 11 hanedir, bu yüzden bilgileri tam girilmiş bir yabancı
  misafir "yerli" sayılabiliyordu. Yeni `kbs.misafir_tipi(tc_no, satir)`
  önce check-in'de toplanan yabancı alanlarının (uyruk vb.) doluluğuna bakıyor,
  yoksa eski şekil-bazlı tahmine düşüyor. `detay_dialog.py`'deki iki çağrı
  yeri güncellendi.
- **T.C. Kimlik No doğrulaması hiç zorunlu değildi:** `detay_dialog.py` check-in
  kaydında yalnızca "11 haneli rakam mı" kontrol ediyordu; gerçek sağlama
  algoritması (`kbs.tc_dogrula`, zaten doğru yazılmıştı) sadece KBS Excel
  raporunda bilgilendirme notu olarak kullanılıyordu, kaydı engellemiyordu.
  Artık check-in kaydı `tc_dogrula()` ile zorunlu doğrulanıyor.
- **KBS Excel formül enjeksiyonu:** misafir adı/TC/telefon gibi elle girilen
  alanlar `=`/`+`/`-`/`@` ile başlıyorsa Excel'de formül olarak
  yorumlanabiliyordu; hücreler artık `kbs._guvenli_hucre()` ile korunuyor.
  Ayrıca "BİLDİRİM GEÇMİŞİ" sekmesi artık tur/misafir adı/TC/oda/tarih
  bilgisini de kaydediyor (öncesinde bu kolonlar hep boştu).
- **Çok odalı "Oda Değiştir" çökmesi:** `main.py`'de `QInputDialog` üst
  seviyede import edilmemişti (iki başka yerde yerel import vardı, burada
  yoktu); birden fazla odalı bir rezervasyonda "Oda Değiştir"e tıklamak
  `NameError` ile çöküyordu. Üst seviye import listesine eklendi; kullanılmayan
  `QCheckBox`/`QTextEdit`/`QScrollArea` importları da temizlendi.
- **Kapasite/transaction/hata-yönetimi iyileştirmeleri:** oda değiştirmede
  kapasite kontrolü artık check-in'deki gibi ekstra yatak hakkını da sayıyor
  (üç yerdeki tekrarlı formül `repository.oda_liman()`'da birleştirildi,
  ölü kod `_ro_liman` kaldırıldı); misafir kaydı + ödeme yeniden hesaplama
  artık tek transaction'da (`_odeme_tutarlarini_yeniden_hesapla`); İstatistik
  sekmesi hesaplama hatasını artık "0" değil açık bir uyarıyla gösteriyor.
- **Güncelleme aracı (`guncelleme_araci/guncelle.py`) sertleştirildi:** yama
  uygulama artık her hatayı yakalayıp gösteriyor (öncesinde sadece
  `RuntimeError` yakalanıyordu, `--windowed` exe başka hata türlerinde sessizce
  çöküyordu — artık ayrıca TEMP'e log da yazıyor); paketin `onceki_surum`'u
  kurulu sürümle eşleşmiyorsa güncelleme engelleniyor (yanlış/eski paket
  eksik dosya seti uygulayabilirdi); yedekleme başarısız olursa kullanıcı
  bilgilendiriliyor (öncesinde sessizce yutuluyordu).
- **Kurulum Aracı:** `calistir_bekle()`'de `WaitForSingleObject`/
  `GetExitCodeProcess` dönüş değerleri artık kontrol ediliyor — API çağrısı
  başarısız olursa çıkış kodu asla varsayılan `0` (başarılı) olarak
  dönmüyor (bu değer kaldırmada veri silme kararını etkiliyor).
- **Yeni test:** `oda_degistir_kbs_test.py` (repo köküne eklendi) — oda
  değiştirme + KBS zincirini uçtan uca doğrular (izole TEMP veritabanı,
  gerçek veriye dokunmaz).
- Bilinçli DEĞİŞTİRİLMEYEN noktalar: KBS "bekleyen çıkışlar" listesi hâlâ
  "bugün"le sınırlı değil (kasıtlı — bir güvenlik ağı, hiç bildirilmemiş eski
  kayıtları da gösteriyor); `main.py`'deki fiyat önizleme tekrarı; `CheckinDialog`
  içindeki index'li tuple yapısı; `repository.py`'de ~8 yerde tekrarlanan
  "etkin çıkış tarihi" SQL parçası. Bunlar kod kalitesi/bakım konuları, hata
  değil — değiştirmenin riski faydasından büyüktü.
- Test: `py_compile` tüm değişen dosyalarda; mevcut `kbs_test.py`,
  `buton_test.py`, `coklu_test.py` (Temp\opencode) geçti; yeni
  `oda_degistir_kbs_test.py` geçti. `gece_ui_test.py` (Temp\opencode, bu
  oturumda dokunulmayan bir alan — gece uzat/kısalt) bu makinede takıldı;
  ortamla ilgili önceden var olan bir sorun gibi görünüyor, düzeltmelerle
  ilgisi yok, araştırılmadı.
- Uygulama bu makinede `dev_canli_calistir.py` ile test DB'siyle açıldı,
  kullanıcı elle denedi, sorun bildirmedi.

---

## 5. GitHub yapısı ve kuralları

- Repo: `https://github.com/DorDeorz/misafirhane-app` — ana dal `main`,
  **public** (private değil). Push eden kimlik: `DorDeorz` (PAT, git credential
  manager'da).
- Release'ler: **v1.0.1, v1.0.3, v1.0.4, v1.0.4.2**. Tag → commit:
  - v1.0.4 → `44f7f75`
  - v1.0.4.2 → `424d927`
  - v1.0.1 / v1.0.3 → kendi sürüm commit'leri.
  - **1.0.4.3 için release YOK** (kullanıcı özellikle istemedi — sadece kod
    push edildi, `Misafirhane_Kurulumu_1.0.4.3.exe` vb. üretilmedi/yüklenmedi).
    Yeni bir laptoptan devam ederken bunu unutma: `dist/kurulum` çıktısı bu
    sürüm için yok, gerekirse 6. maddedeki adımlarla üretilmeli.
- Eski release'lerden (`v1.0.1/v1.0.3/v1.0.4`) Inno `Misafirhane_Kurulum_*.exe`
  **silinmedi** (geçmiş sürümlerin tek kurulum yolu — dokunulmadı).
- **Asla push edilmez:** `*.db` (gerçek/test verileri), `build/`, `dist/`,
  `dagitim/`, `*.spec`, `surum.txt`. `.gitignore` buna bakar.
- Commit mesajı stili: `1.0.x: <başlık>; alt maddeler`.

---

## 6. Derleme ve dağıtım akışı (geliştirici)

1. `versiyon.py`'de `SURUM` arttır + `YENILIKLER` girdisi.
2. `python guncelleme_olustur.py --tam` →
   - onedir uygulama (`dist\Misafirhane`),
   - fark/sha256 tespiti, `dagitim\guncelle_<SURUM>\guncelle_patch.zip` + `guncelle.json`,
   - `dagitim\Misafirhane_Guncelleme_<SURUM>.exe` (onefile, UAC),
   - Inno kurulum **motoru** `dist\kurulum\Misafirhane_Kurulum.exe`
     (artık dagitim'e kopyalanmaz).
3. **Kurulum Aracı** tek exe (manuel, repoya betik eklenmedi):
   ```
   pyinstaller --noconfirm --clean --onefile --windowed \
     --name Misafirhane_Kurulumu_<SURUM> \
     --icon assets\misafirhane.ico \
     --add-data "dist\kurulum\Misafirhane_Kurulum.exe;." \
     --add-data "versiyon.py;." \
     --add-data "assets\misafirhane.ico;assets" \
     kurulum_araci.py
   ```
   Çıktı: `dist\Misafirhane_Kurulumu_<SURUM>.exe`.
4. **Standalone** uygulama (manuel):
   ```
   pyinstaller --noconfirm --clean --onefile --windowed \
     --name Misafirhane_<SURUM> --icon assets\misafirhane.ico \
     --add-data "assets\misafirhane.ico;assets" main.py
   ```
5. Release oluştur + asset yükle (API / gh). Varsayılan asset seti:
   **Kurulum Aracı + Güncelleme + Standalone** (Inno Kurulum ayrıca çıkmaz).

---

## 7. Test ortamı ve senaryolar (yerel, push edilmez)

- **Test DB:** `misafirhane_deneme.db` — kullanıcı `oğuz` (canlıdan kopyalandı),
  18 oda; senaryolar: rez 1001–1008, oda ro 2001–2012 (bazıları içeride/
  bekleyen). Bugün bazlı ilerleyen tarih senaryoları üretilen DB'ye işlendi.
- **Geçerli TC'ler:** Ahmet `10000000146`, Ayşe `10000000528`, Hasan `10000000900`;
  bozuk (reddedilen): Veli `11111111111`.
- **Bekleyen KBS:** 6 giriş + 2 çıkış (test DB'de).
- **Test launcher:** `C:\Users\oguzh\AppData\Local\Temp\opencode\dev_canli_calistir.py`
  → uygulamayı test DB ile açar (canlı veriye dokunmaz).
- **Test araçları (Temp\opencode):** `kbs_musteri_db_olustur.py` (test DB
  üretir), `kbs_sok_test.py`, `ui_sok_test.py` (11 sekme + detay/checkin
  açılışı), `coklu_test.py` (çok odalı), `buton_test.py` (aksiyon çubuğu
  durumları), `gece_ui_test.py` (gece uzat/kısalt + çakışma).
- Bu makinede **uçtan uca kaldırma + veri silme testi** yapıldı: Kurulum
  Aracı ile "Evet" seçildi, uygulama kaldırıldı ve `%LOCALAPPDATA%\Misafirhane`
  silindi. Sonuç olarak bu bilgisayarda uygulama şu an **kaldırılmış** durumda
  (kayıt defterinde kurulum yok; `C:\Program Files\Misafirhane Rezervasyon\`
  içinde yalnızca `_eski` kalmış).

---

## 8. Mevcut durum + bilinen eksikler / öneriler

- Git HEAD: `8767217` (main) + hemen ardından bir docs commit'i (bu dosya ve
  DEVAM.md'yi günceller), çalışma ağacı temiz. En yeni sürüm: **1.0.4.3**
  (release YOK, sadece kod push edildi — bkz. madde 5).
- Bu `CLAUDE.md` dosyası daha önce (bu oturuma kadar) **git'e hiç
  commit'lenmemişti** (yerelde vardı, push edilmemişti) — 1.0.4.3 docs
  commit'iyle ilk kez repoya girdi. Yeni bir bilgisayarda `git clone`
  yapılırsa bu dosya artık gelir.
- **Bilinen eksikler:**
  1. Kurulum Aracı ve standalone derleme adımları `guncelleme_olustur.py`'de
     değil (manuel komutlar, yukarıda 6. maddede). Öneri: betiğe A2 adımı
     (Kurulum Aracı + standalone) eklenip tek komutta tüm release üretmek.
  2. Ev makinesinde `guncelleme_olustur.py` A+B (TAM paket) ve
     `guncelle_araci/guncelle.py` sürüm kapısı değişiklikleri commit'siz
     kaldı — bu repoya taşınmadı.
  3. KBS excel/rapor ve islem geçmişi üzerinde otomatik test kapsamı dar
     (sok testleri manuel/komut bazlı), ama artık `oda_degistir_kbs_test.py`
     ile oda değiştirme + KBS zinciri repoya işlenmiş durumda.
  4. 1.0.4.3 için henüz exe/kurulum paketi üretilmedi (kullanıcı istemedi).
     Bir sonraki sürüm çıkarılırken 1.0.4.3'ün düzeltmeleri de pakete girer.

## 9. Çalışma kuralları (bu projede)

- **Veri güvenliği:** `*.db` dosyaları hiçbir şekilde commit/push edilmez;
  üretim/dagitim klasörleri git'e girmez. Uygulama üzerinde deneme yaparken
  test DB kullan (`dev_canli_calistir.py`).
- **Dil/stil:** kod yorumları ve kullanıcı arayüzü Türkçe; ASCII olmayan
  karakterler kodda bozulmasın diye dikkat (dosyalar UTF-8). PySide6,
  mevcut dosyalardaki desenler korunur (repo'da hâlihazırda kullanılan
  fonksiyon/adlandırma alışkanlığına uy).
- **Akış:** değişiklik yapınca `py_compile` + sok testi; gerekirse uygulamayı
  test DB ile aç. Devam notları `DEVAM.md`'ye işlenir (oturumlar arası
  köprü), kullanıcıya onay almadan push/commit yapılmaz.
- **Sürüm:** yeni özellik → `SURUM` +1; yayınlanmış hatası → sona ek hane
  (1.0.4.2 gibi). Yeni sürümde `YENILIKLER` girdisi zorunlu.
- **Release:** tek kurulum aracı (Kurulumu) + Güncelleme + Standalone; Inno
  Kurulum exe'si ayrıca yayınlanmaz.

## 10. Sıradaki adım önerisi (kullanıcıya sorulur)

- Kurulum Aracı + standalone derlemeyi `guncelleme_olustur.py`'ye taşımak
  (tek komutla tam release üretimi).
- Evdeki commit'siz değişiklikleri bu repoya aktarmak.
- Bir sonraki sürüm(ler) için özellik/eksik önceliklendirmesi.
- **Laptoptan devam ederken:** `git clone`/`git pull` sonrası bu dosyayı ve
  `DEVAM.md`'yi oku (madde 4'teki "1.0.4.3" bölümü ve DEVAM.md'nin en üstü).
  1.0.4.3 için henüz exe/release üretilmedi; istenirse 6. maddedeki adımlarla
  üretilebilir. `misafirhane_deneme.db`/`misafirhane.db`/`kbs_takip.db`
  gitignore'lu olduğu için laptopta YOKTUR — test için gerekiyorsa yeniden
  oluşturulmalı ya da ev bilgisayarından elle taşınmalı.