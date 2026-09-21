# -*- coding: utf-8 -*-
"""
TAM TEST VERİSİ OLUŞTURUCU (2-3 aylık)
=======================================
Uygulamanın BÜTÜN ekranlarını uçtan uca deneyebilmek için gerçekçi bir
veritabanı üretir. Çalıştırıldığı GÜNE göre tarihler üretilir; ne zaman
çalıştırırsan çalıştır, bugün için aşağıdaki senaryolar hazır olur:

  ✅ Geçmiş (~70 gün)   : eski misafirler, ödenmiş/ödenmemiş, iptaller, no-show'lar
  ✅ Bugün GİRİŞ        : bazıları sabah check-in olmuş, bazıları "Bekleniyor"
  ✅ Bugün ÇIKIŞ        : bugün çıkış yapacakları Çıkış ekranında listeler
  ✅ Bugün İÇERİDE      : devam eden konaklamalar (check-in yapılmış)
  ✅ Gelecek (~75 gün)  : ileri tarihli rezervasyonlar (Sabit/Üye/Özel fiyat)
  ✅ Grup rezervasyonu  : aynı gün 3 oda
  ✅ Ekstra yatak       : kapasite +1 misafir
  ✅ Oda değişikliği    : kalan bir misafir yarın başka odaya taşınır
  ✅ Arızalı / Temizlikte oda örnekleri
  ✅ 4 test kullanıcısı (+ admin/1234 korunur)

ÇALIŞTIRMA (aynı klasörde):
    python test_verisi_tam.py

GÜVENLİK: Çalışmadan önce mevcut misafirhane.db dosyasını 'yedekler'
klasörüne kopyalar, sonra sıfırdan temiz bir test veritabanı kurar.
"""

import random
import shutil
import os
from datetime import date, timedelta

import database
import repository
import auth

random.seed(20260917)  # tekrarlanabilir test senaryoları

TEST_KULLANICILAR = [
    ("ayse", "test1234", "Ayşe Yılmaz"),
    ("mehmet", "test1234", "Mehmet Kaya"),
    ("fatma", "test1234", "Fatma Demir"),
    ("ali", "test1234", "Ali Çelik"),
]

ORNEK_ISIMLER = [
    "Ahmet Yılmaz", "Mehmet Demir", "Ayşe Kaya", "Fatma Şahin", "Mustafa Çelik",
    "Emine Yıldız", "Hüseyin Aydın", "Zeynep Öztürk", "Ali Arslan", "Hatice Doğan",
    "İbrahim Kılıç", "Elif Aslan", "Hasan Çetin", "Sultan Kurt", "Osman Koç",
    "Fatih Şen", "Merve Aksoy", "Ramazan Türk", "Büşra Yalçın", "Kemal Öz",
    "Selin Acar", "Yusuf Polat", "Gül Erdoğan", "Murat Bulut", "Esra Güneş",
]

ORNEK_REFERANSLAR = [
    "Başkan Ahmet Bey", "Üye Mehmet Yılmaz", "Üye Ayşe Kaya", "Sayman Hüseyin Bey",
    "", "", "", "",  # çoğunlukla referanssız (gerçekçi oran)
]

ORNEK_TC_HAVUZU = [str(random.randint(10000000000, 99999999999)) for _ in range(300)]
_tc_index = 0


def yeni_tc():
    global _tc_index
    tc = ORNEK_TC_HAVUZU[_tc_index % len(ORNEK_TC_HAVUZU)]
    _tc_index += 1
    return tc


def yeni_telefon():
    return f"05{random.randint(30, 59)}{random.randint(1000000, 9999999)}"


def rastgele_kullanici():
    return random.choice([k[0] for k in TEST_KULLANICILAR])


def rastgele_isim():
    return random.choice(ORNEK_ISIMLER)


def rastgele_referans():
    return random.choice(ORNEK_REFERANSLAR)


def kisi_sayisi(kapasite):
    return random.randint(1, kapasite)


def gece_sayisi():
    return random.choice([1, 1, 2, 2, 2, 3, 3, 4, 5, 7])


def rezervasyon_olustur(oda, kisi, giris, gece, fiyat_tipi="Sabit", ozel_ucret=None,
                        referans=None, kullanici=None):
    gecmis_mi = giris.isoformat() < date.today().isoformat()
    return repository.rezervasyon_olustur(
        odalar=[dict(
            oda_id=oda["id"], giris_tarihi=giris.isoformat(), gece_sayisi=gece,
            kisi_sayisi=kisi, fiyat_tipi=fiyat_tipi,
            ozel_ucret=ozel_ucret if fiyat_tipi == "Ozel" else None,
        )],
        ad_soyad=rastgele_isim(),
        tc_no=yeni_tc(),
        telefon=yeni_telefon(),
        referans=referans if referans is not None else rastgele_referans(),
        olusturan_kullanici=kullanici or rastgele_kullanici(),
        gecmis_kontrol=not gecmis_mi,
    )


def tek_ro(rez_id):
    """Tek odalı bir rezervasyonun ilk (tek) oda satırını verir."""
    return repository.rezervasyon_odalar_listele(rez_id)[0]


def checkin_yap_full(rez_id, kisi, ekstra_yatak=False):
    """Misafirleri girip check-in yapar ve dönüş yapar."""
    ro = tek_ro(rez_id)
    isimler = [rastgele_isim() for _ in range(kisi + (1 if ekstra_yatak else 0))]
    tcler = [yeni_tc() for _ in range(len(isimler))]
    repository.odasi_misafirleri_kaydet(ro["id"], list(zip(isimler, tcler)), ekstra_yatak=ekstra_yatak)
    repository.odasi_checkin_yap(ro["id"])


def gecmis_geceleri_ode(rez_id, oran=0.8):
    """Bugüne kadarki gecelerin bir kısmını ödendi yapar."""
    bugun = date.today().isoformat()
    for ro in repository.rezervasyon_odalar_listele(rez_id):
        for o in repository.odasi_odemeler(ro["id"]):
            if o["tarih"] <= bugun and random.random() < oran:
                repository.odeme_guncelle(o["id"], True, random.choice(database.ODEME_SEKILLERI))


def simdiki_dosyayi_yedekle():
    """Mevcut DB'yi yedekler klasörüne kopyala (güvenlik)."""
    if not os.path.exists(database.DB_PATH):
        return
    klasor = database.yedek_klasoru()
    os.makedirs(klasor, exist_ok=True)
    hedef = os.path.join(klasor, "misafirhane_yedek_TEST_ONCESI.db")
    shutil.copy2(database.DB_PATH, hedef)
    print(f"  Mevcut veritabanı yedeklendi: {hedef}")


def kullanicilari_olustur():
    auth.kullanici_ekle("admin", "1234", "Yönetici")  # ilk admin (varsa atlanmaz; silinmiş DB'de yeni)
    for kullanici_adi, sifre, ad_soyad in TEST_KULLANICILAR:
        try:
            auth.kullanici_ekle(kullanici_adi, sifre, ad_soyad)
        except ValueError:
            pass
    return ["admin"] + [k[0] for k in TEST_KULLANICILAR]


def main():
    print("TAM TEST VERİSİ oluşturuluyor...")
    print(f"  Referans tarih (bugün): {date.today().isoformat()}")

    # 1) Güvenlik: mevcut DB'yi yedekle, sonra sıfırdan kur
    simdiki_dosyayi_yedekle()
    if os.path.exists(database.DB_PATH):
        os.remove(database.DB_PATH)
    database.init_db()
    if repository.oda_listesi() == []:
        database.varsayilan_odalari_yukle()
    odalar = repository.oda_listesi()
    kullanicilar = kullanicilari_olustur()
    print(f"  Temiz DB kuruldu: {len(odalar)} oda, {len(kullanicilar)} kullanıcı")

    bugun = date.today()
    toplam_rez = 0
    toplam_iptal = 0

    # ============================================================
    # A) BUGÜN GİRİŞ YAPACAKLAR (2'si check-in olmuş, 2'si "Bekleniyor")
    # ============================================================
    o0, o1, o2, o3 = odalar[0], odalar[1], odalar[2], odalar[3]

    # A1) Sabah geldi, check-in yapıldı (ekstra yatak da var)
    r = rezervasyon_olustur(o0, kisi=1, giris=bugun, gece=2, fiyat_tipi="Sabit",
                            referans="Üye Mehmet Yılmaz")
    checkin_yap_full(r, 1, ekstra_yatak=True)
    toplam_rez += 1
    print("  [BUGÜN GİRİŞ] Oda {0}: çocuk yataklı + check-in oldu".format(o0["oda_no"]))

    # A2) Sabah geldi, check-in yapıldı, bugünkü gece ödendi (yeşil örnek).
    #     ANCAK 2 kişi FARKLI FİYAT ödüyor: 1'i Üye, 1'i Sabit (kişi başı fiyat örneği).
    r = rezervasyon_olustur(o1, kisi=2, giris=bugun, gece=3, fiyat_tipi="Uye")
    ro1 = tek_ro(r)
    repository.odasi_misafirleri_kaydet(ro1["id"], [("Ebru Demirtaş", "10000000011", "Uye", 600),
                                                   ("Cihan Demirtaş", "10000000022", "Sabit", 1300)])
    repository.odasi_checkin_yap(ro1["id"])
    repository.odeme_guncelle(repository.odasi_odemeler(ro1["id"])[0]["id"], True, "Kredi Karti")
    toplam_rez += 1
    print("  [BUGÜN GİRİŞ] Oda {0}: 2 kişi, KARIŞIK FİYAT (1 Üye + 1 Sabit), ödendi, İÇERİDE".format(o1["oda_no"]))

    # A3) Özel fiyatla bugün giriş ama HENÜZ GELMEDİ (Best Bekleniyor örneği)
    r = rezervasyon_olustur(o2, kisi=1, giris=bugun, gece=2, fiyat_tipi="Ozel", ozel_ucret=900,
                            referans="Üye Ayşe Kaya")
    toplam_rez += 1
    print("  [BUGÜN GİRİŞ] Oda {0}: ÖZEL 900 TL, bekleniyor (check-in değil)".format(o2["oda_no"]))

    # A4) Bugün giriş ama HENÜZ GELMEDİ
    r = rezervasyon_olustur(o3, kisi=2, giris=bugun, gece=4, fiyat_tipi="Sabit")
    toplam_rez += 1
    print("  [BUGÜN GİRİŞ] Oda {0}: 2 kişi, bekleniyor".format(o3["oda_no"]))

    # ============================================================
    # B) BUGÜN ÇIKIŞ YAPACAKLAR (4 oda; 1'i çoktan çıkış yaptı -> temizlikte)
    # ============================================================
    bugun_cikis_rezleri = []
    for i in range(4, 8):
        oda = odalar[i]
        giris = bugun - timedelta(days=2)
        kisi = kisi_sayisi(oda["kapasite"])
        r = rezervasyon_olustur(oda, kisi, giris, gece=2, fiyat_tipi="Sabit")
        checkin_yap_full(r, kisi)
        toplam_rez += 1
        gecmis_geceleri_ode(r, oran=0.95)
        ad = repository.rezervasyon_getir(r)["ad_soyad"]
        bugun_cikis_rezleri.append((r, ad, oda["oda_no"]))

    # B1) Bir misafir sabah çıkışını tamamladı (oda aynı gün temizlenip yeni girişe hazır)
    repository.odasi_cikis_yap(tek_ro(bugun_cikis_rezleri[0][0])["id"])
    print("  [BUGÜN ÇIKIŞ] Oda {0}: {1} çoktan çıkış yaptı, oda TEMİZ (aynı gece yeni misafir alabilir)".format(
        bugun_cikis_rezleri[0][2], bugun_cikis_rezleri[0][1]))
    print("  [BUGÜN ÇIKIŞ] Diğer 3 oda Çıkış ekranında bekliyor (çıkış butonu hazır)")

    # ============================================================
    # C) BUGÜN İÇERİDE OLANLAR (devam eden konaklamalar)
    # ============================================================
    for i, (gun_once, gece, fiyat, kisi_kap) in enumerate(
            [(3, 8, "Sabit", 2), (5, 12, "Uye", 1), (1, 5, "Sabit", 2)]):
        oda = odalar[8 + i]
        giris = bugun - timedelta(days=gun_once)
        if repository.musaitlik_kontrol(oda["id"], giris.isoformat(), gece):
            print("  ! Oda {0} C senaryosu için dolu, atlandı".format(oda["oda_no"]))
            continue
        r = rezervasyon_olustur(oda, kisi=kisi_kap, giris=giris, gece=gece, fiyat_tipi=fiyat)
        checkin_yap_full(r, kisi_kap)
        gecmis_geceleri_ode(r, oran=0.5)  # yarım ödenmiş örnek
        toplam_rez += 1
        print("  [BUGÜN İÇERİDE] Oda {0}: {1} kişi, {2} gece aktif".format(oda["oda_no"], kisi_kap, gece))

    # ============================================================
    # D) GRUP REZERVASYONU (gelecek +10 gün, 3 oda, 2 gece, tek üst kayıt)
    # ============================================================
    grup_tarih = bugun + timedelta(days=10)
    grup_odalar = []
    for oda in odalar:
        if repository.musaitlik_kontrol(oda["id"], grup_tarih.isoformat(), 2):
            continue
        grup_kisi = kisi_sayisi(oda["kapasite"])
        grup_odalar.append(dict(
            oda_id=oda["id"], giris_tarihi=grup_tarih.isoformat(), gece_sayisi=2,
            kisi_sayisi=grup_kisi, fiyat_tipi="Sabit",
        ))
        print("  [GRUP] Oda {0} ({1} kişi) -> {2}".format(oda["oda_no"], grup_kisi, grup_tarih))
        if len(grup_odalar) >= 3:
            break
    if grup_odalar:
        repository.rezervasyon_olustur(
            grup_odalar, ad_soyad="Eyüp Korkmaz", tc_no=yeni_tc(),
            telefon=yeni_telefon(), referans="Başkan Ahmet Bey",
            olusturan_kullanici=rastgele_kullanici(),
        )
        toplam_rez += 1
    print("  -> Grup rezervasyonu: {0} oda".format(len(grup_odalar)))

    # ============================================================
    # E) ODA DEĞİŞİKLİĞİ: devam eden bir misafiri yarın başka odaya taşı
    # ============================================================
    degisiklik_yapildi = False
    for r in repository.rezervasyon_listesi("aktif"):
        if degisiklik_yapildi:
            break
        for ro_satir in repository.rezervasyon_odalar_listele(r["id"]):
            if ro_satir["giris_tarihi"] > bugun.isoformat():
                continue
            if repository.cikis_tarihi_hesapla(ro_satir["giris_tarihi"], ro_satir["gece_sayisi"]) \
                    <= (bugun + timedelta(days=2)).isoformat():
                continue
            deg_tarih = (bugun + timedelta(days=1)).isoformat()
            for oda in odalar:
                if oda["id"] == ro_satir["oda_id"]:
                    continue
                if repository.musaitlik_kontrol(oda["id"], deg_tarih, 1):
                    continue
                try:
                    repository.oda_degistir(ro_satir["id"], oda["id"], deg_tarih)
                    degisiklik_yapildi = True
                    print("  [ODA DEĞİŞİKLİĞİ] '{0}' yarın Oda {1}'e taşınıyor".format(
                        r["ad_soyad"], oda["oda_no"]))
                    break
                except ValueError:
                    continue
    if not degisiklik_yapildi:
        print("  [ODA DEĞİŞİKLİĞİ] atlandı (uygun oda bulunamadı)")

    # ============================================================
    # F) GENEL DOLGU: geçmiş ~70 gün + gelecek ~75 gün rastgele bloklar
    # ============================================================
    gecmis_baslangic = bugun - timedelta(days=70)
    gelecek_bitis = bugun + timedelta(days=75)

    for oda in odalar:
        isaretci = gecmis_baslangic

        # Geçmiş: %55 doluluk, %8 no-show, %6 iptal
        while isaretci < bugun:
            if random.random() < 0.55:
                gece = gece_sayisi()
                kisi = kisi_sayisi(oda["kapasite"])
                fiyat = random.choice(["Sabit", "Sabit", "Sabit", "Uye"])
                if repository.musaitlik_kontrol(oda["id"], isaretci.isoformat(), gece):
                    isaretci += timedelta(days=1)
                    continue
                try:
                    r = rezervasyon_olustur(oda, kisi, isaretci, gece, fiyat_tipi=fiyat)
                except ValueError:
                    isaretci += timedelta(days=1)
                    continue
                toplam_rez += 1
                if random.random() < 0.08:
                    pass  # kasti no-show (check-in yapılmadı)
                else:
                    checkin_yap_full(r, kisi)
                    gecmis_geceleri_ode(r, oran=0.8)
                if random.random() < 0.06:
                    repository.rezervasyon_iptal(r)
                    toplam_iptal += 1
                isaretci += timedelta(days=gece)
            else:
                isaretci += timedelta(days=random.choice([1, 2]))

        # Gelecek: %55 doluluk, küçük oranda Özel fiyat
        isaretci = bugun + timedelta(days=1)
        while isaretci < gelecek_bitis:
            if random.random() < 0.55:
                gece = gece_sayisi()
                kisi = kisi_sayisi(oda["kapasite"])
                fiyat = random.choice(["Sabit", "Sabit", "Uye", "Sabit", "Uye", "Ozel"])
                if repository.musaitlik_kontrol(oda["id"], isaretci.isoformat(), gece):
                    isaretci += timedelta(days=1)
                    continue
                ozel = random.choice([750, 900, 1100]) if fiyat == "Ozel" else None
                try:
                    rezervasyon_olustur(oda, kisi, isaretci, gece, fiyat, ozel_ucret=ozel)
                except ValueError:
                    isaretci += timedelta(days=1)
                    continue
                toplam_rez += 1
                isaretci += timedelta(days=gece)
            else:
                isaretci += timedelta(days=random.choice([1, 2]))

    # ============================================================
    # G) DETERMİNİSTİK İPTAL ÖRNEĞİ (ileri tarihli, işlem geçmişine düşer)
    # ============================================================
    gelecek_rezler = [r for r in repository.rezervasyon_listesi("hepsi")
                      if r["giris_tarihi"] > bugun.isoformat() and not r["iptal"]]
    if gelecek_rezler:
        repository.rezervasyon_iptal(gelecek_rezler[0]["id"])
        toplam_iptal += 1
        print("  [İPTAL] '{0}' iptal edildi (İşlem Geçmişi'nde görünür)".format(gelecek_rezler[0]["ad_soyad"]))

    # ============================================================
    # H) ODA DURUMU: bugün boş bir odayı 3 gün arızalı yap
    #    (4 numaralı çıkış yapan oda zaten 'temizlikte')
    # ============================================================
    bugun_str = bugun.isoformat()
    gundeki = repository.gunun_checkin_durumu(bugun_str)
    bos = [s for s in gundeki if s["rez_id"] is None]
    for satir in bos:
        if satir.get("aktif_durum") in ("temizlikte", "arizali"):
            continue
        try:
            repository.oda_durum_ayarla(satir["oda_id"], "arizali", ariza_gun=3)
            print("  [ODA DURUMU] Oda {0} 3 gün ARIZALI yapıldı".format(satir["oda_no"]))
            break
        except ValueError:
            continue

    # ============================================================
    # ÖZET
    # ============================================================
    print("\n==================== ÖZET ====================")
    print(f"Toplam rezervasyon          : {len(repository.rezervasyon_listesi('hepsi'))}")
    print(f"  -> bu oturumda oluşan     : {toplam_rez}")
    print(f"İptal edilen                : {toplam_iptal}")
    gelmeyen = sum(1 for r in repository.rezervasyon_listesi("aktif")
                   if (r["gelmedi_odasi"] or 0) > 0)
    print(f"Gelmeyen (No-Show)          : {gelmeyen}")

    print("\n--- BUGÜNÜKÜ SENARYOLAR ---")
    bugun_giren = repository.gunun_girisleri(bugun_str)
    print(f"Bugün giriş yapacak         : {len(bugun_giren)}")
    print(f"Bugün çıkış yapacak         : {len(repository.bugun_cikacaklar(bugun_str))}")
    iceride = sum(1 for s in gundeki if s["checkin_yapildi"])
    print(f"Bugün içeride (check-in)    : {iceride}")

    print("\n--- KULLANICILAR ---")
    for k in auth.kullanici_listesi():
        print(f"  {k['kullanici_adi']:<12s} {k['ad_soyad']}")
    print("\nNot: admin/1234 de geçerlidir. Uygulamayı açıp giriş yapın.")
    print("Test verisini sıfırlamak için yine: python test_verisi_tam.py")


if __name__ == "__main__":
    main()
