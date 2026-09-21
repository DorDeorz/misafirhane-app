# Misafirhane Rezervasyon

Küçük işletmeler ve misafirhaneler için **internetsiz çalışan** masaüstü rezervasyon yönetim sistemi. Oda durumunu, giriş-çıkışları, misafir kayıtlarını, ödemeleri, gelir raporlarını ve **KBS bildirimlerini** tek ekrandan takip eder.

> Bu depo **açık (public)** bir projedir; gerçek kullanıcı verisi (`*.db`, yedekler) `.gitignore` ile hariç tutulur ve asla push edilmez. Uygulama Python + Qt (PySide6) ile yazılmıştır ve Windows için derlenmiş (exe) olarak dağıtılır.

## Ne yapar?

Uygulamanın tüm özellikleri, kullanıldıkları ekranlarla birlikte aşağıda **teker teker** listelenir.

### Rezervasyon

- **Çok odalı rezervasyon** — tek kayıtta birden çok oda alınır. Her oda, kendi giriş/çıkış tarihi, gece sayısı, kişi sayısı, fiyat tipi ve gecelik ücretiyle **ayrı bir oda satırı** olarak tutulur; check-in / çıkış / oda değiştirme / tarih işlemleri her oda için bağımsız yapılır.
- **Kişi başı fiyat tipleri** — aynı odada kalan kişiler farklı fiyat ödeyebilir: **Sabit / Üye / Özel**. Özel fiyatta tutarı elle girersin.
- **Gece sayısı uzatma / kısaltma** — hem gelecek rezervasyonlarda hem de **hâlihazırda içeride olan misafirde** gece sayısı artırılıp azaltılabilir. Konaklama başladıysa giriş tarihi kilitlenir (misafir zaten içeride), yalnızca gece sayısı değişir. Değişiklik sırasında yeni çıkış tarihi canlı önizlenir; önceden ödenmiş ama yeni planın dışında kalan geceler ayrıca uyarılır (tutarları kesinlikle iade edilmez, ödendi bilgisi korunur).
- **Tarih değişikliğinde çakışma yönetimi** — yeni tarih odada başka bir rezervasyonla çakışırsa işlem körü körüne engellenmez. Sistem çakışan rezervasyonu ve bu giriş tarihine sığabilecek **en fazla gece sayısını** gösterir; "gece sayısını N'e düşürmen gerekir, onaylıyor musun?" diye sorar. Onaylarsan gece otomatik N'e düşürülüp uygulanır, onaylamazsan hiçbir şey değişmez.
- **Ekstra yatak** — odanın kapasitesini o kalış için geçici olarak bir kişi artırır.
- **Oda Değiştir** — bir oda satırı başka bir odaya taşınır. Taşıma giriş gününde (tüm gece) ya da kalış ortasında (satır iki parçaya bölünerek) yapılabilir. Hedef odanın müsaitliği renk kodlu tabloda gösterilir (yeşil boş / kırmızı dolu / gri seçilemez).

### Oda Durumu ve Günlük Görünümler

- **Oda Durumu** — seçilen günün doluluk listesi: odada kalan misafir, kalan gece, günlük ödeme durumu (ödendi/ödenmedi). Ödeme sütununa çift tık ile ödendi/ödenmedi işaretlenir; isim/TC gibi alanlara çift tık misafir düzenlemesini açar.
- **Oda durumları** — temiz / temizlikte / arızalı. Arızalı odada bitiş tarihi tutulur ve o aralıktaki rezervasyonlar engellenir. **Temizlikte/arızalı** bir odanın durum kolonuna (veya takvimdeki bloğuna ya da Rezervasyon Yönetimi'ndeki "Oda" sütununa) **çift tıklamak** "Oda temizlendi mi?" diye sorar, evetse odayı temiz durumuna alır.
- **Check-in** — günün girişleri, misafir kaydı ve check-in tamamlama.
- **Günün Girişleri** — çok odalı rezervasyonlar tek satırda görünür; her oda için **Geldi / Gelmedi (No-Show) / Bekleniyor** durumu ayrıca gösterilir.
- **Çıkış** — check-in yapılmış odalar çıkış yapar, oda otomatik "temizlikte" durumuna alınır. Aynı gün girip aynı gün çıkan misafirde bugünkü gece de ücrete girer: ödenmemişse "Tahsil edilsin mi?", ödenmişse "İade yapıldı mı?" diye sorularak hesap netleştirilir.
- **Takvim Görünümü** — odaların günlük doluluk ızgarası; ad yalnızca giriş gününde yazılır, diğer geceler X olur; ipucunda isim, giriş-çıkış, rezervasyon no, fiyat ve referans bilgisi. Temizlikte/arızalı bir bloğa çift tık odayı temiz yapar (ana pencere de otomatik yenilenir).

### Rezervasyon Yönetimi ve Geçmiş

- **Rezervasyon Yönetimi** — tüm rezervasyonları filtrele (Bugünkü / Beklenen / İçerideki / Çıkış Yapmış / Gelmedi (No-Show) / İptal), ara (yalnızca Ad Soyad'da anında filtreler), sırala ve Excel'e aktar. Uzun listelerde işlem butonları gizlenir, detay isme çift tık ile açılır — büyük veri setlerinde performans korunur.
- **Geçmiş Kayıtlar** — çıkışı yapılmış eski misafirlerin kayıtları isimle aranıp bulunabilir ve Excel'e aktarılabilir.
- **İşlem Geçmişi** — yapılan tüm işlemlerin denetim izi (kim, ne zaman, ne yaptı).

### KBS Bildirimi (1774 sayılı Kanun / Kimlik Bildirme Sistemi)

- Ana pencerede **"🛂 KBS Bildirimi"** butonu: bekleyen **giriş bildirimleri** (check-in yapılmış yabancı misafirler) ve **çıkış bildirimleri** (o gün çıkacaklar) ayrı ayrı listelenir.
- **Şahıs kontrolü** — bildirilmeden önce TC/belge numarasının doğru biçimde girilip girilmediği kontrol edilir; hatalı/eksik kayıtlar engellenir ve listede işaretlenir.
- **Gönderildi işaretleme** — her satır için bildirimin yapıldığı işaretlenebilir; durum bir takip veritabanında (`kbs_takip.db`) saklanır, uygulama yeniden açılsa bile korunur.
- **Excel dışa aktarma** — bekleyen bildirimler `.xlsx` olarak dışa aktarılabilir.
- **Genel özet** — ne kadar giriş/çıkış beklediği, kaçının gönderildiği tek ekranda.

### Yabancı Misafir Bilgileri (check-in)

- Check-in sırasında yabancı misafir için KBS'nin zorunlu tuttuğu alanlar toplanır: **Uyruk, Doğum Tarihi (veya "bilinmiyor"), Cinsiyet, Doğum Yeri, Belge Türü**.
- Eksik bilgi varsa check-in kaydedilmez; satırdaki buton üzerinden **"Yabancı Bilg… (n eksik)"** olarak gösterilir.
- Rezervasyon detayındaki **"Odada Kalan Misafirler"** tablosu, her misafir için yerli/yabancı ayrımını ve yabancı bilgisinin tam/eksik durumunu gösterir.
- **TC doğrulama** — yerli misafir için TC No 11 haneli rakamlardan oluşmuyorsa check-in engellenir.

### Raporlar, Yedekleme, Diğer

- **Raporlar & Excel** — günlük durum, rezervasyonlar ve tarih aralığı raporları `.xlsx` olarak dışa aktarılır.
- **İstatistik** — aylık pazarlanan gece, gelir, tahsilat, iptal kayıp geceler ve no-show istatistikleri.
- **Kullanıcı hesapları** — yönetici/çalışan girişi, şifre değiştirme, kullanıcı ekleme (kimin aldığı denetim izinde görünür).
- **Yedekleme** — veritabanını tek tıkla yedekleme, yedekten geri yükleme, kapanışta otomatik yedek.
- **Görünüm** — aydınlık / karanlık tema; ikisinde de ortak bileşen ve kompakt düzen.

### Arayüz (1.0.4 yeniden tasarımı)

Uygulama 1366×768 gibi laptop ekranlarında rahat kullanılacak şekilde yeniden düzenlendi; tüm ekranlarda tutarlı görünüm:

- **Ortak rozetler** — durumlar renkli rozetlerle gösterilir (ör. "✓ Tüm odalar içeride", "Kısmen check-in", "⚠ GELMEDİ (No-Show)", "İptal Edildi").
- **Kompakt tema** — sıkışık sekmeler, grup başlıkları, butonlar ve giriş alanları; aydınlık ve karanlık temalara aynı oranda uygulanır.
- **Rezervasyon detayı** — tek satır kompakt başlık (isim + durum rozeti + oda özeti + tarih/gece + alınma bilgisi); **QSplitter** düzeni (sol: misafir bilgileri formu, sağ: odalar + odada kalan misafirler); en altta her zaman görünür **aksiyon çubuğu** (toplam tutar, iptal, kapat, kaydet).
- **Oda işlemleri artık tablo içinde değil** — odalar tablosu saf bilgi tablosudur; bir satır seçilir ve işlemler **tablonun altındaki aksiyon çubuğundan** yapılır: 👥 Kişiler / Check-in · 🛏 +1 Gece · 🛏 −1 Gece · 🗓 Tarih / Gece · 🔁 Oda Değiştir · 🚪 Çıkış Yap. Böylece buton yazıları asla sığmama sorunu yaşamaz.
- **Birincil/ikincil buton stilleri** — önemli eylemler (Check-in'i Tamamla, Bilgileri Kaydet, Çıkış Yap, Yeni Oda Ekle, Fiyatları Kaydet) vurgulu stilde, zararsız eylemler sade.

## Sürümler ve Dağıtım

EXE dosyaları GitHub **Releases** sayfasında ayrı tutulur: https://github.com/DorDeorz/misafirhane-app/releases

- `Misafirhane_Kurulumu_<sürüm>.exe` — **çok amaçlı Kurulum Aracı**: yeni bilgisayara kurar, kurulu sürümü yerinde **Günceller** (verilere dokunmaz), bozuk kurulumu **Tamir Eder** ve programı **Kaldırır**. Programın durumunu otomatik algılar; arayüz Windows'un koyu/açık mod ayarıyla otomatik eşleşir. 1.0.4'teki tek amaçlı `Misafirhane_Kurulum` exe'sinin yerini alır.
- `Misafirhane_Guncelleme_<sürüm>.exe` — **kurulu olan uygulamayı** yerinde günceller (yalnızca değişen dosyalar, verilere dokunmaz).
- `Misafirhane_<sürüm>.exe` — sürümün tek dosyalık (standalone) derlenmiş uygulaması; reponun kökünde de tutulur.

Veriler uygulama klasörüne değil, `%LOCALAPPDATA%\Misafirhane\` altına yazılır. Böylece güncelleme/kaldırma işlemleri kayıtlı verileri korur.

### Kurulum Aracı (`Misafirhane_Kurulumu.exe`)

Araç, `Misafirhane Rezervasyon` klasörünü ve kayıt defterini tarayarak programın durumunu gösterir:

| Buton | Ne yapar? |
|-------|-----------|
| **Yükle** | Bilgisayarda kurulum yoksa kurar (UAC onayı açılır). |
| **Güncelle** | Kurulu sürümü yerinde günceller; veriler korunur. |
| **Tamir Et** | Dosyaları yeniden yazarak bozuk kurulumu onarır. |
| **Uygulamayı Kaldır** | Programı kaldırır; kaldırma sırasında **veritabanının da silinip silinmeyeceğini sorar** (Evet → veriler de silinir, Hayır → veriler `%LOCALAPPDATA%\Misafirhane` altında korunur, İptal → kaldırma iptal edilir). |

Varsayılan tema Windows'un koyu/açık mod ayarından okunur. Uygulama açıkken güncelleme/tamir/kaldırma yapılırsa `Misafirhane.exe` önce otomatik kapatılır. 1.0.4.1 sürümünün SHA256'sı: `2D72A5BEC08BA70A6D0945B0FF82AB537D4B8737E6A8E579BB1D93C33724BD18`.

> **Geliştirme veritabanı** (`misafirhane.db`) ve **test veritabanı** (`misafirhane_deneme.db`) gizli veriler içerdiği için **asla GitHub'a yüklenmez** (`.gitignore` engeller). Test/senaryo verisi yalnızca yerel makinede tutulur.

## Test Senaryoları (yerel)

KBS ve arayüz testleri için yerelde bir test veritabanı (`misafirhane_deneme.db`) üretildi. Kullanıcılar canlı veritabanından aynen kopyalandı (`oğuz` kullanıcısı korundu); 18 oda ve müşteri senaryoları (rezervasyonlar `1001–1008`, oda satırları `2001–2012`) yazıldı.

Deneme için geçerli TC numaraları:

| Kişi   | TC / Belge No  |
|--------|----------------|
| Ahmet  | `10000000146`  |
| Ayşe   | `10000000528`  |
| Hasan  | `10000000900`  |

- Geçersiz örnek: `11111111111` (Veli — "bozuk TC" senaryosu).
- Senaryolar: içeride olan misafir, çıkış yapmış misafir, iptal edilmiş rezervasyon, check-in yapılmadan geçen (no-show) rezervasyon, iki odalı kalış. Bekleyen KBS: 6 giriş + 2 çıkış.

## Geliştirme

Gereksinimler: Python 3.12+

```bash
python -m pip install -r requirements.txt
python main.py
```

İlk açılışta veritabanı otomatik oluşturulur; boş olduğunda varsayılan odalar yüklenir ve ilk yönetici hesabını sen oluşturursun.

## Yeni sürüm çıkarma

1. `versiyon.py` içinde `SURUM` değerini artır, `YENILIKLER` sözlüğüne sürüm notu ekle.
2. Kod değişikliklerini yap.
3. `python guncelleme_olustur.py` çalıştır → `dagitim/` altında güncelleme exe'si üretilir.
4. Yeni bilgisayar kurulumu gerekiyorsa `--tam` ile tam kurulum dosyası da üretilir (Inno Setup gerektirir).
5. Üretilen exe dosyalarını GitHub Releases'e yükle; dilediğinde tek dosyalık exe'yi depoya da ekle.

## Proje Yapısı

```
main.py                Uygulama girişi ve arayüz (tüm sekmeler)
database.py            Veritabanı (SQLite) ve yedekleme
repository.py          Sorgular ve iş kuralları (tarih/gece, çakışma, KBS sorguları)
kbs.py                 KBS (1774 sayılı Kanun) doğrulama mantığı
kbs_pencere.py         KBS Bildirimi penceresi
detay_dialog.py        Rezervasyon/misafir düzenleme pencereleri (çok odalı)
takvim_widget.py       Takvim görünümü
export.py              Excel çıktıları
tema.py                Aydınlık/karanlık tema, rozetler, kompakt stiller
auth.py                Kullanıcı girişi / şifre
loglama.py             İşlem geçmişi (denetim izi)
versiyon.py            Sürüm bilgisi ve sürüm notları
guncelleme_olustur.py  Güncelleme paketi/üretme aracı
guncelleme_araci/      Güncelleme uygulama aracı (exe kaynağı)
kurulum_araci.py       Kurulum Aracı (Yükle/Güncelle/Tamir/Kaldır) — Tkinter launcher
kurulum.iss            Inno Setup kurulum betiği
```

## Sürüm Notları

| Sürüm | Not |
|-------|-----|
| 1.0.4.6 | **Temizlik/arıza çift tıklamayla temize çekme + aynı gün giriş-çıkış hesabı**: "Temizlikte"/"Arızalı" bir oda artık Oda Durumu durum kolonuna, takvim bloğuna ve Rezervasyon Yönetimi "Oda" sütununa çift tıklanarak "Oda temizlendi mi?" onayıyla temiz yapılabiliyor (arızalıda bitiş tarihi de sıfırlanır; dolu odalarda engellenir). Aynı gün girip aynı gün çıkan misafirin bugünkü gecesi artık ücrete giriyor: ödenmemişse "Tahsil edilsin mi?" (ödeme alınıp kaydedilir) ve ödenmişse "İade yapıldı mı?" (kayıt iptal edilir) akışı; çıkış listelerindeki borç sütunu bu geceyi gösterir. Bağımsız Takvim Görünümü'nden yapılan temizlik artık ana penceredeki diğer sekmeleri de otomatik yeniler. |
| 1.0.4.5 | **Nakit kaldırıldı, Fatura takibi eklendi + hata düzeltmeleri**: Ödeme yöntemleri artık yalnızca Kredi Kartı / Havale-IBAN (Nakit ve ayrı bir "Fatura" seçeneği kaldırıldı). Check-in'de "Fatura İstiyor" işaretlenebiliyor; ödeme ekranlarında "Fatura alınmalı/alındı" gösteriliyor, ödeme alınırken fatura verildi mi diye sorulup tek tıkla işaretlenebiliyor. Düzeltmeler: "Çıkış Yap" artık bugünü değil Çıkış sekmesinde seçili tarihi kaydediyor (geriye dönük çıkış işlemede yanlış tarih ve silinen faturalanmamış tutar sorunu giderildi); oda değiştirmede fatura durumu artık kayboluyor; çıkış yapmış bir odada gece/tarih/oda değiştirme işlemleri artık engelleniyor (hem arayüz hem veritabanı katmanında); "Erken Çıkışlar" listesi artık seçili tarihe göre tutarlı; telefon doğrulama ülke kodsuz 10 haneli numaraları da kabul ediyor. |
| 1.0.4.4 | **Erken Çıkış + hata düzeltmeleri**: Çıkış sekmesine, planlı çıkışı bugün olmayan ama hâlâ konaklayan misafirleri listeleyen "Erken Çıkışlar" bölümü eklendi (ödenmemiş borç gösterimiyle). Rezervasyon detayında "+1/-1 Gece" butonları artık pencereyi kapatmıyor ve çakışma durumunda net uyarı veriyor. Kurulum Aracı mesajı sadeleşti. Düzeltmeler: içerideki misafirin rezervasyonu iptal edilemiyor, check-in ekranında "Sil" butonu, aynı gün check-in kilidi, gece uzatmada kişi bazlı fiyat, erken çıkışta gelecek ödemelerin temizlenmesi, çıkış sonrası oda durumunun "temizlikte" olması, telefon +90 doğrulama, KBS ve diğer Excel raporlarında formül enjeksiyonu koruması, güncelleme aracı sürüm kontrolü ve daha fazlası. |
| 1.0.4.3 | **Kod incelemesi ve hata düzeltmeleri**: Oda değiştirmede KBS'ye özgü hatalar giderildi — yabancı misafir bilgileri artık kaybolmuyor, aynı misafir için mükerrer KBS giriş bildirimi ve yanlış "bugün çıkıyor" görünümü düzeldi; KBS "gönderildi" takibi artık misafir bazlı; yerli/yabancı sınıflandırması ve T.C. Kimlik No doğrulaması güçlendirildi (gerçek sağlama algoritması); KBS Excel çıktısına formül enjeksiyonu koruması eklendi. Çok odalı rezervasyonda "Oda Değiştir" çökmesi düzeltildi. Güncelleme aracı hataları artık sessizce yutmuyor. |
| 1.0.4.2 | **Kurulum Aracı — veri silme seçeneği**: Kaldırma sırasında "veritabanını ve verileri de silmek ister misiniz?" sorulur (Evet → `%LOCALAPPDATA%\Misafirhane` kalıcı silinir, Hayır → veriler korunur, İptal → kaldırma iptal). Veri silme yalnızca kaldırma başarıyla bitince yapılır. |
| 1.0.4.1 | **Kurulum Aracı** (tek exe): Yükle / Güncelle / Tamir Et / Kaldır; programın durumu otomatik algılanır, gömülü kurulum UAC ile çalışır; arayüz Windows'un koyu/açık mod ayarına göre otomatik tema seçer; kaldırma sırasında veriler korunur. Eski hibrit `Misafirhane_Kurulum` exe'sinin yerine geçer. |
| 1.0.4 | **KBS Bildirimi**: bekleyen giriş/çıkışlar, şahıs TC doğrulaması, gönderildi işaretleme, `kbs_takip.db`, Excel çıktısı. **Yabancı misafir KBS alanları** check-in'de toplanır ve eksik bilgi engellenir; **TC doğrulama**. **Arayüz yeniden tasarımı**: kompakt tema + rozetler, rezervasyon detayı splitter düzeni, oda işlemlerinin tablo altı aksiyon çubuğuna taşınması (buton sığmama sorunu çözüldü), birincil/ikincil buton stilleri, Oda Durumu çift özet düzeltmesi, gerçek kullanıcı adı gösterimi. **Gece uzat/kısalt** içerideki misafirde de çalışır; **çakışmada gece azaltma önerisi + onay** akışı; canlı çıkış/çakışma önizlemesi. |
| 1.0.3 | Çok odalı rezervasyon (tek kayıtta birden çok oda, oda satırı bazlı check-in/çıkış/oda değiştirme); **Geçmiş Kayıtlar** görünümü (çıkışı yapılmış eski misafirler, arama/sıralama/Excel); Günün Girişleri'nde çok odalı rezervasyon tek satır + oda bazlı Geldi/Gelmedi/Bekleniyor durumu; performans (arama yalnızca Ad Soyad'da anında filtrelenir, gecikmeli yenileme + toplu sorgular — büyük listelerde kasma yok); düzeltmeler: Oda Değiştir / Tarih Değiştir pencerelerinin açılmama hatası, iptal listesinde satır renklendirme çökmesi |
| 1.0.2.2 | Hata düzeltmesi: oda değiştirme sonrası giriş tarihi değiştirilince aynı gece iki odada görünme sorunu; oda parçaları (önceki/devam) artık tarih değişikliğinde otomatik dengelenir, ödemeler yeniden kurulur |
| 1.0.2.1 | Hata düzeltmesi: takvim ipuçlarında (referans bilgisi) açılış hatası |
| 1.0.2 | Oda Değiştir ekranı tablo haline getirildi (renk kodlu müsaitlik); takvimde ad yalnızca giriş gününe yazılır, diğer geceler X olur |
| 1.0.1 | Ayarlar sekmesine sürüm bilgisi eklendi; güncelleme altyapısı |
| 1.0.0 | İlk yayın sürümü |