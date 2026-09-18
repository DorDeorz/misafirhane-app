# Misafirhane Rezervasyon

Küçük işletmeler ve misafirhaneler için **internetsiz çalışan** masaüstü rezervasyon yönetim sistemi. Oda durumunu, giriş-çıkışları, misafir kayıtlarını, ödemeleri ve gelir raporlarını tek ekrandan takip eder.

> Bu depo **gizli (private)** bir projedir. Uygulama Python + Qt (PySide6) ile yazılmıştır ve Windows için derlenmiş (exe) olarak dağıtılır.

## Ne yapar?

- **Oda Durumu** — günün check-in/check-out listesi, oda durumları (temiz / temizlikte / arızalı)
- **Rezervasyon** — misafir ekleme/düzenleme, kişi başı fiyat tipleri (Sabit / Üye / Özel), ekstra yatak
- **Check-in / Check-out** — odadaki kişileri yönetme, gecelik ücret hesaplama
- **Takvim Görünümü** — odaların günlük doluluk tablosu
- **Raporlar & Excel** — günlük durum, rezervasyonlar ve tarih aralığı raporlarını `.xlsx` olarak dışa aktarma
- **Kullanıcı hesapları** — yönetici/çalışan girişi, şifre değiştirme
- **Yedekleme** — veritabanını tek tıkla yedekleme, yedekten geri yükleme, kapanışta otomatik yedek
- **Görünüm** — aydınlık / karanlık tema

## Sürümler ve Dağıtım

EXE dosyaları GitHub **Releases** sayfasında ayrı tutulur: https://github.com/DorDeorz/misafirhane-app/releases

- `Misafirhane_Kurulum_<sürüm>.exe` — **yeni bilgisayarlara** kurulum için (Program Files'a kurar, masaüstü + başlat menüsü kısayolu, kaldırıcı).
- `Misafirhane_Guncelleme_<sürüm>.exe` — **kurulu olan uygulamayı** yerinde günceller (yalnızca değişen dosyalar, verilere dokunmaz).

Veriler uygulama klasörüne değil, `%LOCALAPPDATA%\Misafirhane\` altına yazılır. Böylece güncelleme/kaldırma işlemleri kayıtlı verileri korur.

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
4. Yeni bilgisayar kurulumu gerekiyorsa `--tam` ile tam kurulum dosyası da üretilir.
5. Üretilen exe dosyalarını GitHub Releases'e yükle.

## Proje Yapısı

```
main.py                Uygulama girişi ve arayüz
database.py            Veritabanı (SQLite) ve yedekleme
repository.py          Sorgular ve iş kuralları
auth.py                Kullanıcı girişi / şifre
detay_dialog.py        Rezervasyon/misafir düzenleme pencereleri
takvim_widget.py       Takvim görünümü
export.py              Excel çıktıları
tema.py                Aydınlık/karanlık tema
loglama.py             İşlem geçmişi (denetim izi)
versiyon.py            Sürüm bilgisi
guncelleme_olustur.py  Güncelleme paketi/üretme aracı
guncelleme_araci/      Güncelleme uygulama aracı (exe kaynağı)
kurulum.iss            Inno Setup kurulum betiği
```

## Sürüm Notları

| Sürüm | Not |
|-------|-----|
| 1.0.1 | Ayarlar sekmesine sürüm bilgisi eklendi; güncelleme altyapısı |
| 1.0.0 | İlk yayın sürümü |