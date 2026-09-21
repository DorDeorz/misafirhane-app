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

### 1.0.4.4 (laptopta, ev masaüstü DIŞINDA bir makinede Claude ile yapıldı, push edildi)

Bu bölüm **başka bir Claude Code oturumu** (Claude Sonnet 5, laptop/ev masaüstü
dışındaki bir makine) tarafından yapıldı. Kullanıcı önce "projeyi baştan aşağı
oku, anla, hataları/eksikleri bul" dedi (bu makinedeki eski/senkronsuz yerel
kopya `git reset --hard origin/main` ile 1.0.4.3'e eşitlendi, commit'siz iki
değişiklik — `guncelleme_olustur.py`/`guncelle.py` TAM paket denemesi — bu
oturumun kendi bulgusuyla çakıştığı için atıldı, GitHub'ın 1.0.4.3 çözümü
esas alındı). main.py/repository.py/detay_dialog.py iki paralel ajanla
incelendi, bulunanların TAMAMI kullanıcı onayıyla düzeltildi, ardından
kullanıcı iki ek özellik + tasarım denemesi istedi (tasarım kullanıcı
tarafından reddedilip **eski haline geri alındı** — bkz. aşağıda).

**Düzeltilen hatalar (özet):**
1. **İptal engeli**: `repository.rezervasyon_iptal` artık check-in yapılmış
   (fiilen içeride, `cikis_tarihi IS NULL`) bir oda varsa `ValueError` fırlatıp
   iptali reddediyor — önceden böyle bir rezervasyon iptal edilince odası
   `iptal=0` filtresi yüzünden tüm sorgularda "boş" görünüp ikinci kez
   satılabiliyordu.
2. **CheckinDialog "Sil" butonu** hiç çalışmıyordu (`_kisi_sil` yanlışlıkla
   `satir[6]` yani `bilgi_btn` ile karşılaştırıyordu, `satir[4]`=`sil_btn`
   olmalıydı) — düzeltildi.
3. **Aynı gün check-in kilidi**: `rezervasyon_odasi_tarih_degistir` ve
   `OdaTarihDialog` "konaklama başladı mı" kontrolünü `giris_tarihi < bugun`
   yerine `checkin_yapildi` bayrağına göre yapıyor artık — bugün check-in
   yapılmış bir misafirin giriş tarihi eskiden hâlâ değiştirilebiliyordu.
4. **Kişi bazlı fiyat / gece uzatma**: `rezervasyon_odasi_tarih_degistir`,
   `_odemeleri_yeniden_kur`'dan sonra `_odeme_tutarlarini_yeniden_hesapla`'yı
   da çağırıyor — gece uzat/kısalt sonrası "Özel" kişi bazlı fiyatlar artık
   doğru uygulanıyor (öncesinde ro-seviyesi varsayılan tutara dönüyordu).
5. **Erken çıkış / oda durumu**: `odasi_cikis_yap` artık (a) odayı `temiz`
   değil doğru şekilde `temizlikte` yapıyor (housekeeping adımı atlanıyordu),
   (b) `cikis_tarihi_str`'den sonraki HENÜZ ÖDENMEMİŞ gece kayıtlarını siliyor
   (İstatistik'teki "beklenen gelir" artık hiç kalınmayacak geceleri
   saymıyor), (c) önceden ÖDENMİŞ ama artık kapsam dışı kalan geceleri
   silmeden döndürüyor (UI bilgilendiriyor). Yeni `odasi_odenmemis_tutar()`
   ile "borç" hesaplanıyor.
6. **`oda_degistir`** artık hedef oda mevcut odayla aynıysa engelleniyor.
7. **CheckinDialog artık tek transaction'da**: yeni
   `odasi_misafirleri_kaydet_ve_checkin()` (eski ayrı
   `odasi_misafirleri_kaydet` + `odasi_checkin_yap` çağrısının yerini aldı).
8. **Telefon doğrulama** (`main.py` `_telefon_gecerli_mi`) artık `+90 5xx...`
   formatını doğru kabul ediyor (eskiden "90" kesilince kalan hane hiç "0"
   ile başlamadığından her zaman reddediliyordu).
9. **KBS Excel "Bildirim Geçmişi"** artık kaydedilen tur/misafir/TC/oda/tarih
   bilgisini gösteriyor (1.0.4.3'te kolonlar eklenmişti ama rapor hâlâ eski
   4 kolonu yazıyordu). **`export.py`**'nin 3 raporuna da (rezervasyon,
   günlük durum, tarih aralığı) `kbs.py`'deki formül enjeksiyonu koruması
   taşındı.
10. **Güncelleme aracı** (`guncelle.py`): `onceki_surum` kontrolü artık
    `mevcut` (kurulu sürüm) okunamadığında/boş olduğunda da devreye giriyor
    (öncesinde bu durumda kontrol tamamen atlanıyordu).
11. Yeni kullanıcı eklerken şifre uzunluğu (min 4) artık kontrol ediliyor;
    `main.py`'de 8 yerde sadece `ValueError` yakalanıyordu, artık `Exception`;
    tutar 0 TL iken hücre boş görünüyordu (`is not None` kontrolü); oda
    değiştir seçim listesi artık sıra numarasıyla benzersiz.
12. **Kurulum Aracı**: `_islem_bitti`'deki "Uğurlu olsun: ... tamamlandı"
    mesajı kaldırıldı, yerine işleme göre "Uygulama başarıyla
    yüklendi/güncellendi/onarıldı" geldi.
13. README'deki "bu depo gizli/private" ifadesi düzeltildi (repo gerçekte
    **public**, `gh repo view` ile doğrulandı).

**Yeni özellikler (kullanıcı isteğiyle):**
- **Erken Çıkışlar**: `CikisTab`'a, planlı çıkış günü seçili tarih OLMAYAN
  ama hâlâ check-in'li/çıkışsız olan oda satırlarını listeleyen yeni bir
  bölüm eklendi (`repository.erken_cikis_adaylari()`). Hem bu listede hem
  normal "Çıkış Yap" akışında artık ödenmemiş borç (`odasi_odenmemis_tutar`)
  gösteriliyor ve onay diyaloğunda soruluyor.
- **Gece +1/-1 butonları artık RezervasyonDetayDialog'u kapatmıyor**:
  `_yenile()` (layout'u `QWidget().setLayout(...)` hilesiyle temizleyip
  `_arayuzu_kur()`'u yeniden çağırıyor, seçili oda satırını koruyor) — art
  arda birden fazla kez tıklanabiliyor. Ayrıca sadece UZATMA (delta>0) için,
  hemen ertesi günde çakışan bir rezervasyon varsa artık anlamsız bir "gece
  sayısını N'e düşür" önerisi (N zaten mevcut sayıya eşit oluyordu) yerine
  net bir "Gece Eklenemiyor: ... rezervasyonu var" uyarısı çıkıyor.

**Denenip geri alınan tasarım değişikliği:** Kullanıcı "genel tasarımı tamamen
değiştir, modern yap, butonlar biraz büyük olsun, hiçbir yerde kaydırma
gerekmesin" dedi. `tema.py` (indigo/mor renk paleti, degrade üst bar, büyük
yuvarlak butonlar/sekmeler), pencere `showMaximized()`, tablo satır
yükseklikleri büyütüldü. Kullanıcı butonların çok büyük olduğunu söyleyince
boyutlar küçültüldü (orijinale yakın); ardından **tasarımın tamamını
beğenmedi ve eski hâline geri döndürülmesini istedi**. `tema.py` şu an
**origin/main ile birebir aynı** (tek fark: dosya sonu yeni satırı). Pencere
`showMaximized()` olarak KALDI (kullanıcı bunu ayrıca istedi, sadece bunu).
Satır yükseklikleri ve `#tehlikeli` obje adları da orijinaline döndürüldü
(iptal/sil butonları yine `setStyleSheet("color: #c0392b;")` kullanıyor).
**Sonraki oturum tasarım konusunda temkinli olsun**: kullanıcı büyük/modern
bir redesign istemiyor, mevcut kompakt görünümden memnun.

**Test:** `py_compile` tüm değişen dosyalarda geçti. Mevcut
`kbs_test.py`, `oda_degistir_kbs_test.py` (repo) geçti (kbs_test.py'nin son
satırındaki `✔` karakteri bu makinenin konsol kod sayfasında (cp1254)
`UnicodeEncodeError` veriyor — TEST BAŞARISIZLIĞI DEĞİL, tüm assertion'lar
zaten geçmişti, sadece dekoratif son `print()` çöküyor, ortamla ilgili, koddan
kaynaklanmıyor). Bu oturumda ayrıca özel smoke testler yazıldı (repository
seviyesinde iptal engeli/borç/erken-çıkış/aynı-gün-kilit/aynı-oda-engeli,
Qt seviyesinde gece butonlarının pencereyi kapatmaması ve Sil butonu) — hepsi
geçti, kalıcı repoya eklenmedi (scratchpad'te kaldı, gerekirse tekrar
yazılabilir). Uygulama bu makinede gerçek arayüzde kullanıcı tarafından
birkaç kez elle denendi ("bi sıkıntı yaşanmadı").

**Sürüm/release**: `versiyon.py` → 1.0.4.4 + YENILIKLER; README güncellendi.
`python guncelleme_olustur.py --tam` + Kurulum Aracı + Standalone derlemeleri
CLAUDE.md madde 6'daki adımlarla üretildi; `Misafirhane_Kurulumu_1.0.4.4.exe`
kullanıcının Masaüstü'ne kopyalandı. **DÜZELTME (21 Eylül 2026, ev
masaüstünde):** bu oturumun kendi notu "GitHub Release AÇILMADI" diyordu, ama
`gh release list` ile kontrol edildiğinde **Release GERÇEKTEN YAYINDA**
olduğu görüldü — `v1.0.4.4` / "Misafirhane 1.0.4.4", published
2026-09-20T22:29:01Z, `Latest` etiketli, 3 asset (`Misafirhane_1.0.4.4.exe`,
`Misafirhane_Guncelleme_1.0.4.4.exe`, `Misafirhane_Kurulumu_1.0.4.4.exe`).
Release oluşturulma zamanı push zamanıyla saniyesi saniyesine eşleşiyor; yani
laptop oturumunda ya kullanıcı ya da o oturum release'i fiilen açmış, ama
kendi dokümanına yanlış yazmış. **Ders:** release durumunu doğrularken bu
dosyaya değil `gh release list --repo DorDeorz/misafirhane-app` çıktısına
güven.

### 1.0.4.5 (commit `f45882b`, ev masaüstünde Claude Code ile yapıldı, push
edildi — **Release v1.0.4.5 GERÇEKTEN AÇILDI ve 3 exe yüklendi**)

Kullanıcı önce iş kuralı değişikliği istedi: **"Fatura" bir ödeme yöntemi
değil** — ödeme her zaman Kredi Kartı ya da Havale/IBAN ile yapılıyor,
misafir isterse ayrıca fatura kesiliyor (ödemeden SONRA, misafirin isteği
üzerine). Bunun üzerine:

- **Nakit kaldırıldı, Fatura ödeme yöntemi listesinden çıkarıldı:**
  `database.ODEME_SEKILLERI` artık yalnızca `["Kredi Karti", "Havale/IBAN"]`.
- **Yeni fatura takibi (ödeme yönteminden bağımsız):** `rezervasyon_odalar`'a
  `fatura_istiyor`/`fatura_alindi` kolonları eklendi (eski DB'ler için
  otomatik migrasyon, `onceki_ro_id` ile aynı desen). Check-in'de "🧾 Misafir
  fatura istiyor" işaretlenebiliyor (`detay_dialog.py` `CheckinDialog`); Oda
  Durumu'nun ödeme hücresinde ve rezervasyon detayındaki oda tablosunda
  "Fatura alınmalı/alındı" gösteriliyor; ödeme "ödendi" işaretlenirken (oda
  fatura istiyorsa ve henüz verilmediyse) "Fatura da verildi mi?" diye
  ayrıca soruluyor (`main.py` `OdaDurumuTab.odeme_isle`); rezervasyon
  detayındaki aksiyon çubuğunda tek tıkla "🧾 Fatura Alındı" işaretlenebiliyor
  (`repository.fatura_durumu_guncelle`).
- **Kendi hatam, kendim buldum ve düzelttim:** oda_degistir'in kalış-ortası
  bölme INSERT'i yeni fatura kolonlarını kopyalamıyordu — tam olarak daha
  önce (1.0.4.3'te) yabancı misafir KBS alanlarında yaptığım hatanın aynısı,
  bu kez kendi yeni kolonlarımda tekrarlamışım. Kullanıcı "push'tan önce
  tekrar baştan aşağı bak" deyince 2 paralel ajanla hem bu yeni özelliği hem
  de 1.0.4.4'ün (laptop) hiç incelenmemiş kodunu taradım; ajanlardan biri bu
  hatayı buldu, `oda_degistir`'in INSERT'ine `fatura_istiyor, fatura_alindi`
  eklenip test edilerek düzeltildi.
- **Laptop oturumunun (1.0.4.4) daha önce hiç incelenmemiş kodunda bulunan
  gerçek hata:** `main.py` `CikisTab._cikisi_uygula`, çıkış tarihini yalnızca
  borç ÖNİZLEMESİ için kullanıyordu; gerçek `repository.odasi_cikis_yap(ro_id)`
  çağrısı hiç tarih almadan yapılıyordu, yani her zaman BUGÜNÜ yazıyordu.
  Sonuç: Çıkış sekmesinde geçmiş bir güne gidip o günün çıkışını (unutulmuş
  bir çıkışı) işlemeye çalışırsan, sistem çıkışı bugün olmuş gibi kaydediyor
  VE bugünden itibaren "ödenmemiş gece" kayıtlarını (aslında meşru,
  faturalanmamış tutarlar) sessizce siliyordu. Düzeltildi: artık sekmede
  seçili tarih gerçekten kullanılıyor; aynı yerde `except ValueError` da
  `except Exception`'a genişletildi (kod tabanının geri kalanıyla tutarlı).
- **Kullanıcının ek istekleriyle bulunan/düzeltilen 3 küçük sorun:**
  (1) çıkış yapmış bir oda için Gece +1/-1, Tarih/Gece, Oda Değiştir hem
  arayüzde (`detay_dialog.py` `_oda_secim_degisti`) hem repository
  katmanında (`rezervasyon_odasi_tarih_degistir`, `oda_degistir` artık
  `cikis_tarihi` doluysa `ValueError` fırlatıyor — savunma iki katmanda da)
  engellendi; (2) "Erken Çıkışlar" listesindeki borç/gecikmiş göstergesi
  "bugün" yerine sekmede seçili tarihi kullanacak şekilde düzeltildi;
  (3) telefon doğrulama artık ülke kodu/başında 0 olmadan girilen 10 haneli
  numaraları da (`532 123 45 67` gibi) kabul ediyor.
- **Kullanıcının sorduğu (kod değişikliği gerektirmeyen) bir soru:** oda
  çıkış yaptıktan sonra, çıkıştan ÖNCEKİ günler takvim/tablo görünümünde
  siliniyor mu? Hayır — `repository.doluluk_haritasi` yalnızca
  `gun >= cikis_tarihi` olan geceleri atlıyor, çıkıştan önceki geceler
  olduğu gibi kalıyor (davranış doğrulandı, kod değiştirilmedi).
- **Derleme + Release:** `versiyon.py` → 1.0.4.5 + YENILIKLER; README
  güncellendi. `python guncelleme_olustur.py --tam` + Kurulum Aracı +
  Standalone derlemeleri madde 6'daki adımlarla üretildi (PyInstaller
  6.20.0, Inno Setup 6 — `%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe`).
  Üç exe de kısaca açılıp (login/kurulum penceresi göründü) kapatılarak
  duman testinden geçirildi. **GitHub Release `v1.0.4.5` GERÇEKTEN
  oluşturuldu** (`gh release create`, 3 asset: Kurulumu/Guncelleme/
  standalone) — bkz. madde 5.
  **ÖNEMLİ KISIT:** bu makinedeki `dagitim/son_manifest.json` (Güncelleme
  exe'sinin fark/baseline referansı) hâlâ **1.0.4.2**'den kalma — 1.0.4.3 bu
  makinede hiç derlenmedi, 1.0.4.4 laptopta derlendi (o dagitim/ buraya hiç
  senkronlanmadı, gitignore'lu). Yani `Misafirhane_Guncelleme_1.0.4.5.exe`
  "1.0.4.2 → 1.0.4.5" farkı olarak üretildi (`guncelle.json`
  `onceki_surum: "1.0.4.2"`). Kurulu sürüm gerçekten 1.0.4.2 ise sorunsuz
  çalışır; 1.0.4.4 (ya da başka bir sürüm) kuruluysa, 1.0.4.3'te eklenen
  `onceki_surum` kontrolü bunu GÜVENLİ şekilde reddedip kullanıcıyı Kurulum
  Aracı'ndaki "Tamir Et"e yönlendirir (veri kaybı riski yok, sadece
  Güncelleme exe'si o kurulumda işe yaramaz) — sonraki bir oturum, hangi
  sürüm kuruluysa ona göre ya "Tamir Et" önersin ya da önce o sürümün gerçek
  dist/Misafirhane çıktısından yeni bir baseline manifest üretsin.
- Test: `py_compile` tüm dosyalarda; `kbs_test.py`, `oda_degistir_kbs_test.py`
  (repo), ayrıca yeni scratchpad testleri (fatura/nakit akışı, çıkış-sonrası
  düzenleme engeli, telefon doğrulama vakaları) yazılıp geçti; `buton_test.py`,
  `coklu_test.py` (Temp\opencode) tekrar tekrar çalıştırıldı, hepsi geçti.

---

## 5. GitHub yapısı ve kuralları

- Repo: `https://github.com/DorDeorz/misafirhane-app` — ana dal `main`,
  **public** (private değil). Push eden kimlik: `DorDeorz` (PAT, git credential
  manager'da).
- Release'ler: **v1.0.1, v1.0.3, v1.0.4, v1.0.4.2, v1.0.4.4, v1.0.4.5**.
  Tag → commit:
  - v1.0.4 → `44f7f75`
  - v1.0.4.2 → `424d927`
  - v1.0.4.4 → `fd52c5d` (3 asset: Kurulum Aracı + Güncelleme + Standalone;
    `Latest` etiketli, published 2026-09-20T22:29:01Z).
  - v1.0.4.5 → `f45882b` (3 asset: Kurulum Aracı + Güncelleme + Standalone;
    bu makinede (ev masaüstü) derlendi ve `gh release create` ile açıldı,
    `Latest` etiketli).
  - v1.0.1 / v1.0.3 → kendi sürüm commit'leri.
  - **1.0.4.3 için release YOK** (kullanıcı özellikle istemedi — sadece kod
    push edildi, `Misafirhane_Kurulumu_1.0.4.3.exe` vb. üretilmedi/yüklenmedi).
    Bu hâlâ doğru — 1.0.4.3 hiç release edilmedi, sadece 1.0.4.4 edildi.
  - **1.0.4.4 için GitHub Release VAR** (bkz. yukarı). Önceki bir not burada
    "release yok" diyordu, bu 21 Eylül 2026'da `gh release list` ile
    doğrulanıp düzeltildi — ayrıntı için madde 4'teki "1.0.4.4" bölümünün
    sonundaki düzeltme notuna bakın. Bir sonraki sürüm için kullanıcı
    açıkça istemedikçe release'in zaten var olduğunu varsayıp tekrar
    oluşturmaya kalkma; önce `gh release list` ile kontrol et.
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

- Git HEAD: `f45882b` (main) + hemen ardından bir docs commit'i (bu dosya ve
  DEVAM.md'yi günceller), çalışma ağacı temiz. En yeni sürüm: **1.0.4.5**
  — **GitHub Release VAR** (`v1.0.4.5`, `Latest`, 3 asset — bkz. madde 5),
  bu sefer gerçekten bu oturumda `gh release create` ile açıldı (önceki
  1.0.4.4 release'i gibi belirsizlik yok). Ders (tekrar): bir sürüm
  eklerken madde 4, 5 VE 8'in hepsi güncellenmeli — bu oturum bu üçünü de
  güncelledi.
- Bu `CLAUDE.md` dosyası 1.0.4.3'e kadar (yani epeyce geç) **git'e hiç
  commit'lenmemişti** (yerelde vardı, push edilmemişti) — 1.0.4.3 docs
  commit'iyle ilk kez repoya girdi. Artık her `git clone`/`pull` ile gelir.
- **Bilinen eksikler:**
  1. Kurulum Aracı ve standalone derleme adımları `guncelleme_olustur.py`'de
     değil (manuel komutlar, yukarıda 6. maddede). Öneri: betiğe A2 adımı
     (Kurulum Aracı + standalone) eklenip tek komutta tüm release üretmek.
  2. Ev makinesinde daha önce bilinen `guncelleme_olustur.py` A+B (TAM paket)
     ve `guncelle_araci/guncelle.py` sürüm kapısı değişiklikleri hâlâ bu
     repoya taşınmadı (laptop oturumu bunu ele almadı).
  3. KBS excel/rapor ve islem geçmişi üzerinde otomatik test kapsamı dar
     (sok testleri manuel/komut bazlı), ama artık `oda_degistir_kbs_test.py`
     ile oda değiştirme + KBS zinciri repoya işlenmiş durumda. 1.0.4.4'te
     yazılan smoke testler (iptal engeli/borç/erken-çıkış/aynı-gün-kilit/
     Sil butonu) kalıcı repoya EKLENMEDİ (scratchpad'te kaldı) — istenirse
     bunlar da `oda_degistir_kbs_test.py` gibi kalıcı hale getirilebilir.
  4. 1.0.4.5 exe'leri (`dist/Misafirhane_Kurulumu_1.0.4.5.exe`,
     `dagitim/Misafirhane_Guncelleme_1.0.4.5.exe`,
     `dist/Misafirhane_1.0.4.5.exe`) yerelde (bu makinede) ve GitHub
     Release'inde mevcut; kullanıcının Masaüstü'ne bu sefer kopyalanmadı
     (istenmedi) — istenirse kopyalanabilir.
  5. **Güncelleme exe'si baseline kısıtı:** `Misafirhane_Guncelleme_1.0.4.5.exe`
     bu makinedeki eski (1.0.4.2) `dagitim/son_manifest.json` baseline'ına
     göre üretildi — bkz. madde 4 "1.0.4.5" bölümündeki "ÖNEMLİ KISIT" notu.
     Kurulu gerçek sürüm 1.0.4.2 değilse bu exe kendini güvenle reddeder
     (veri kaybı yok), kullanıcı "Tamir Et" kullanmalı. Bir sonraki
     derlemede bu makinenin `dagitim/son_manifest.json`'ı güncel olacağından
     (bu build onu tazeledi) aynı sorun tekrar YAŞANMAZ.

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
- Evdeki commit'siz değişiklikleri (`guncelleme_olustur.py` A+B TAM paket,
  `guncelle.py` sürüm kapısı) bu repoya aktarmak — hâlâ bekliyor, laptop
  oturumu da bunu ele almadı.
- Bir sonraki sürüm(ler) için özellik/eksik önceliklendirmesi. **Not:**
  kullanıcı büyük/modern bir arayüz yeniden tasarımını 1.0.4.4'te denedi ve
  beğenmedi, geri aldırdı — tekrar önerilmemeli.
- **Herhangi bir makineden devam ederken:** `git pull` sonrası bu dosyayı ve
  `DEVAM.md`'yi oku (madde 4'teki en son sürüm bölümü ve DEVAM.md'nin en
  üstü) — ama release durumu için bu dosyaya değil `gh release list` çıktısına
  güven (bkz. madde 8'deki not: laptop oturumu bu dosyaya yanlış "release
  yok" yazmıştı). `misafirhane_deneme.db`/`misafirhane.db`/`kbs_takip.db`
  gitignore'lu — yeni bir makinede YOKTUR, test için gerekiyorsa yeniden
  oluşturulmalı ya da elle taşınmalı.