# -*- coding: utf-8 -*-
"""
5 AYLIK TAM TEST VERİSİ OLUŞTURUCU (~5 ay geçmiş + ~5 ay gelecek)
=================================================================
Uygulamanın bütün ekranlarını uzun dönemli test etmek için kapsamlı bir
veritabanı üretir. Tarihler çalıştırıldığı GÜNE göre görecelidir:

  ✅ Geçmiş (~5 ay / 150 gün) : raporlar, gelir, eski misafirler, iptal,
                                no-show, ödenmiş/ödenmemiş geceler
  ✅ Bugün GİRİŞ / BUGÜN ÇIKIŞ / BUGÜN İÇERİDE senaryoları
  ✅ Gelecek (~5 ay / 150 gün): takvim doluluğu, Sabit/Üye/Özel fiyatlar
  ✅ Grup rezervasyonu (3 oda), ekstra yatak, oda değişikliği
  ✅ Arızalı / Temizlikte oda örnekleri
  ✅ 4 test kullanıcısı (+ admin/1234)

ÇALIŞTIRMA (aynı klasörde):
    python test_verisi_5ay.py

GÜVENLİK: Çalışmadan önce mevcut misafirhane.db 'yedekler' klasörüne
kopyalanır, ardından sıfırdan temiz bir veritabanı kurulur.
"""

import random
import shutil
import os
from datetime import date, timedelta

import database
import repository
import auth

random.seed(20260918)  # tekrarlanabilir test senaryoları

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
    "Can Yücel", "Deniz Ata", "Ceren Yavuz", "Efe Doğru", "Aylin Güneş",
]

ORNEK_REFERANSLAR = [
    "Başkan Ahmet Bey", "Üye Mehmet Yılmaz", "Üye Ayşe Kaya", "Sayman Hüseyin Bey",
    "", "", "", "",  # çoğunlukla referanssız (gerçekçi oran)
]

ORNEK_TC_HAVUZU = [str(random.randint(10000000000, 99999999999)) for _ in range(400)]
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
    return random.choice([1, 1, 2, 2, 2, 3, 3, 4, 5, 7, 10])


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
    ro = tek_ro(rez_id)
    isimler = [rastgele_isim() for _ in range(kisi + (1 if ekstra_yatak else 0))]
    tcler = [yeni_tc() for _ in range(len(isimler))]
    repository.odasi_misafirleri_kaydet(ro["id"], list(zip(isimler, tcler)), ekstra_yatak=ekstra_yatak)
    repository.odasi_checkin_yap(ro["id"])


def gecmis_geceleri_ode(rez_id, oran=0.8):
    bugun = date.today().isoformat()
    for ro in repository.rezervasyon_odalar_listele(rez_id):
        for o in repository.odasi_odemeler(ro["id"]):
            if o["tarih"] <= bugun and random.random() < oran:
                repository.odeme_guncelle(o["id"], True, random.choice(database.ODEME_SEKILLERI))


def simdiki_dosyayi_yedekle():
    if not os.path.exists(database.DB_PATH):
        return
    klasor = database.yedek_klasoru()
    os.makedirs(klasor, exist_ok=True)
    hedef = os.path.join(klasor, "misafirhane_yedek_TEST_ONCESI.db")
    shutil.copy2(database.DB_PATH, hedef)
    print(f"  Mevcut veritabanı yedeklendi: {hedef}")


def kullanicilari_olustur():
    auth.kullanici_ekle("admin", "1234", "Yönetici")
    for kullanici_adi, sifre, ad_soyad in TEST_KULLANICILAR:
        try:
            auth.kullanici_ekle(kullanici_adi, sifre, ad_soyad)
        except ValueError:
            pass
    return ["admin"] + [k[0] for k in TEST_KULLANICILAR]


def dolgu_gecmis(odalar, bugun, geri_gun, doluluk=0.6):
    """Bugünden `geri_gun` kadar geriye, her odaya rastgele bloklar yerleştirir.
    Gerçekçi oranlar: %10 no-show, %8 iptal, %80 ödenmiş gece."""
    toplam_rez, toplam_iptal = 0, 0
    baslangic = bugun - timedelta(days=geri_gun)
    for oda in odalar:
        isaretci = baslangic
        while isaretci < bugun:
            if random.random() < doluluk:
                gece = gece_sayisi()
                kisi = kisi_sayisi(oda["kapasite"])
                fiyat = random.choice(["Sabit", "Sabit", "Sabit", "Uye"])
                try:
                    r = rezervasyon_olustur(oda, kisi, isaretci, gece, fiyat_tipi=fiyat)
                except ValueError:
                    isaretci += timedelta(days=1)
                    continue
                toplam_rez += 1
                if random.random() < 0.10:
                    pass  # kasti no-show (check-in yapılmadı)
                else:
                    checkin_yap_full(r, kisi)
                    gecmis_geceleri_ode(r, oran=0.8)
                if random.random() < 0.08:
                    repository.rezervasyon_iptal(r)
                    toplam_iptal += 1
                isaretci += timedelta(days=gece)
            else:
                isaretci += timedelta(days=random.choice([1, 2]))
    return toplam_rez, toplam_iptal


def dolgu_gelecek(odalar, bugun, ileri_gun, doluluk=0.6):
    """Bugünden `ileri_gun` kadar ileriye rastgele bloklar yerleştirir.
    Küçük oranda Özel fiyat içerir."""
    toplam_rez = 0
    bitis = bugun + timedelta(days=ileri_gun)
    for oda in odalar:
        isaretci = bugun + timedelta(days=1)
        while isaretci < bitis:
            if random.random() < doluluk:
                gece = gece_sayisi()
                kisi = kisi_sayisi(oda["kapasite"])
                fiyat = random.choice(["Sabit", "Sabit", "Uye", "Sabit", "Uye", "Ozel"])
                ozel = random.choice([750, 850, 900, 1000, 1100, 1200]) if fiyat == "Ozel" else None
                try:
                    rezervasyon_olustur(oda, kisi, isaretci, gece, fiyat, ozel_ucret=ozel)
                except ValueError:
                    isaretci += timedelta(days=1)
                    continue
                toplam_rez += 1
                isaretci += timedelta(days=gece)
            else:
                isaretci += timedelta(days=random.choice([1, 2]))
    return toplam_rez


def main():
    print("5 AYLIK TAM TEST VERİSİ oluşturuluyor...")
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
    # A) BUGÜN GİRİŞ YAPACAKLAR (2 check-in olmuş, 2 "Bekleniyor")
    # ============================================================
    if len(odalar) >= 8:
        o0, o1, o2, o3 = odalar[0], odalar[1], odalar[2], odalar[3]

        # A1) Sabah geldi, check-in yapıldı (ekstra yatak da var)
        r = rezervasyon_olustur(o0, kisi=1, giris=bugun, gece=2, fiyat_tipi="Sabit",
                                referans="Üye Mehmet Yılmaz")
        checkin_yap_full(r, 1, ekstra_yatak=True)
        toplam_rez += 1
        print("  [BUGÜN GİRİŞ] Oda {0}: çocuk yataklı + check-in oldu".format(o0["oda_no"]))

        # A2) 2 kişi farklı fiyat (1 Üye + 1 Sabit), bugünkü gece ödendi
        r = rezervasyon_olustur(o1, kisi=2, giris=bugun, gece=3, fiyat_tipi="Uye")
        ro1 = tek_ro(r)
        repository.odasi_misafirleri_kaydet(ro1["id"], [("Ebru Demirtaş", "10000000011", "Uye", 600),
                                                       ("Cihan Demirtaş", "10000000022", "Sabit", 1300)])
        repository.odasi_checkin_yap(ro1["id"])
        repository.odeme_guncelle(repository.odasi_odemeler(ro1["id"])[0]["id"], True, "Nakit")
        toplam_rez += 1
        print("  [BUGÜN GİRİŞ] Oda {0}: 2 kişi, KARIŞIK FİYAT, ödendi, İÇERİDE".format(o1["oda_no"]))

        # A3) Özel fiyat, henüz gelmedi (Bekleniyor örneği)
        r = rezervasyon_olustur(o2, kisi=1, giris=bugun, gece=2, fiyat_tipi="Ozel", ozel_ucret=900,
                                referans="Üye Ayşe Kaya")
        toplam_rez += 1
        print("  [BUGÜN GİRİŞ] Oda {0}: ÖZEL 900 TL, bekleniyor".format(o2["oda_no"]))

        # A4) Bugün giriş, henüz gelmedi
        r = rezervasyon_olustur(o3, kisi=2, giris=bugun, gece=4, fiyat_tipi="Sabit")
        toplam_rez += 1
        print("  [BUGÜN GİRİŞ] Oda {0}: 2 kişi, bekleniyor".format(o3["oda_no"]))

    # ============================================================
    # B) BUGÜN ÇIKIŞ YAPACAKLAR (4 oda; 1'i çoktan çıkış -> temizlikte)
    # ============================================================
    bugun_cikis_rezleri = []
    if len(odalar) >= 12:
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

        ilk_cikan_ro = tek_ro(bugun_cikis_rezleri[0][0])
        repository.odasi_cikis_yap(ilk_cikan_ro["id"])
        print("  [BUGÜN ÇIKIŞ] Oda {0}: {1} çıkış yaptı, oda TEMİZ".format(
            bugun_cikis_rezleri[0][2], bugun_cikis_rezleri[0][1]))
        print("  [BUGÜN ÇIKIŞ] Diğer 3 oda Çıkış ekranında bekliyor")

    # ============================================================
    # C) BUGÜN İÇERİDE OLANLAR (devam eden konaklamalar)
    # ============================================================
    if len(odalar) >= 15:
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
        grup_odalar.append(dict(
            oda_id=oda["id"], giris_tarihi=grup_tarih.isoformat(), gece_sayisi=2,
            kisi_sayisi=kisi_sayisi(oda["kapasite"]), fiyat_tipi="Sabit",
        ))
        if len(grup_odalar) >= 3:
            break
    if grup_odalar:
        repository.rezervasyon_olustur(
            grup_odalar, ad_soyad="Eyüp Korkmaz", tc_no=yeni_tc(),
            telefon=yeni_telefon(), referans="Başkan Ahmet Bey",
            olusturan_kullanici=rastgele_kullanici(),
        )
        toplam_rez += 1
    print(f"  [GRUP] {len(grup_odalar)} oda -> {grup_tarih} (tek rezervasyon)")

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
    # F) GENEL DOLGU: ~5 ay geçmiş + ~5 ay gelecek
    # ============================================================
    past_gun = 150
    future_gun = 150
    print(f"  Genel dolgu: {past_gun} gün geçmiş + {future_gun} gün gelecek ...")

    p_rez, p_iptal = dolgu_gecmis(odalar, bugun, past_gun, doluluk=0.6)
    toplam_rez += p_rez
    toplam_iptal += p_iptal
    print(f"  Geçmiş dolgusu tamam: {p_rez} rezervasyon, {p_iptal} iptal")

    f_rez = dolgu_gelecek(odalar, bugun, future_gun, doluluk=0.6)
    toplam_rez += f_rez
    print(f"  Gelecek dolgusu tamam: {f_rez} rezervasyon")

    # ============================================================
    # G) GEÇMİŞE EK İPTAL + GEÇMİŞTE GRUP ÖRNEĞİ
    # ============================================================
    gecmis_rezler = [r for r in repository.rezervasyon_listesi("hepsi")
                     if r["giris_tarihi"] < (bugun - timedelta(days=30)).isoformat()
                     and not r["iptal"] and r["oda_sayisi"] >= 2]
    if gecmis_rezler:
        repository.rezervasyon_iptal(gecmis_rezler[0]["id"])
        toplam_iptal += 1

    # ============================================================
    # H) ODA DURUMU: bugün boş bir odayı 3 gün arızalı yap
    # ============================================================
    bugun_str = bugun.isoformat()
    gundeki = repository.gunun_checkin_durumu(bugun_str)
    bos = [s for s in gundeki if s["rez_id"] is None]
    for satir in bos:
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
    print(f"Kapsam               : {past_gun} gün geçmiş + {future_gun} gün gelecek (~{round((past_gun+future_gun)/30)} ay)")
    print(f"Toplam rezervasyon   : {len(repository.rezervasyon_listesi('hepsi'))}")
    print(f"  -> bu oturumda     : {toplam_rez}")
    print(f"İptal edilen         : {toplam_iptal}")
    gelmeyen = sum(1 for r in repository.rezervasyon_listesi("aktif")
                   if (r["gelmedi_odasi"] or 0) > 0)
    print(f"Gelmeyen (No-Show)   : {gelmeyen}")
    print(f"Veritabanı boyutu    : {os.path.getsize(database.DB_PATH)/1024:.0f} KB")

    print("\n--- BUGÜN ---")
    print(f"Bugün giriş yapacak  : {len(repository.gunun_girisleri(bugun_str))}")
    print(f"Bugün çıkış yapacak  : {len(repository.bugun_cikacaklar(bugun_str))}")
    iceride = sum(1 for s in gundeki if s["checkin_yapildi"])
    print(f"Bugün içeride (check-in): {iceride}")

    print("\n--- KULLANICILAR (şifre: test1234) ---")
    for k in auth.kullanici_listesi():
        print(f"  {k['kullanici_adi']:<12s} {k['ad_soyad']}")
    print("\nNot: admin/1234 de geçerlidir. Uygulamayı açıp giriş yapın.")
    print("Test verisini sıfırlamak için yine: python test_verisi_5ay.py")


if __name__ == "__main__":
    main()
