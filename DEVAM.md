# DEVAM (18 Eylül 2026)

Bu dosya, evdeki masaüstü bilgisayardaki opencode oturumunun kaldığı yerden devam
edebilmesi için hazırlandı. İlk iş olarak okuyun.

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
- `versiyon.py` `SURUM = "1.0.2.2"`; `YENILIKLER` güncel.
- 1.0.2.2 güncelleme exe'i önceden ÜRETİLDİ ve Masaüstüne kopyalandı, AMA yeni iş akışı
  gereği KULLANICI TESTİ VE ONAYI OLMADAN uygulanmayacak / yeniden üretilmeyecek.
- Kullanıcı dev modu testini evdeki bilgisayarda yapacak. Test sonucunu ve istediği
  değişiklikleri bildirdiğinde: kodu güncelle (gerekirse sürümü yama artır), sonra
  exe üret ve Masaüstüne kopyala. GitHub push/release için kullanıcı onayı alın.

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