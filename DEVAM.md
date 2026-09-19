# DEVAM (18 Eylül 2026)

Bu dosya, evdeki masaüstü bilgisayardaki opencode oturumunun kaldığı yerden devam
edebilmesi için hazırlandı. İlk iş olarak okuyun.

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