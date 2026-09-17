# -*- coding: utf-8 -*-
"""
TEST/DEMO VERİSİ OLUŞTURUCU
Sistemi baştan sona denemek için ~2 aylık gerçekçi rezervasyon verisi üretir:
geçmiş/güncel/gelecek rezervasyonlar, check-in yapılmış ve yapılmamış odalar,
ödenmiş/ödenmemiş geceler, iptal edilen rezervasyonlar, çok odalı grup
rezervasyonu, oda değişikliği örneği, ekstra yatak örneği, ve 4 test kullanıcısı.

ÇALIŞTIRMAK İÇİN (aynı klasörde):
    python test_verisi_olustur.py

NOT: Bu betik SADECE test/demo amaçlıdır. Gerçek rezervasyon verisi olan bir
veritabanında çalıştırma — mevcut kayıtları silmez ama üzerine yüzlerce sahte
kayıt ekler, karışıklık yaratır. Temiz bir test için önce misafirhane.db
dosyasını silip betiği öyle çalıştır.

Tarihler, betiğin çalıştırıldığı GÜNE göre göreceli üretilir (geçmişten
geleceğe ~2 aylık bir pencere), böylece ne zaman çalıştırırsan çalıştır
güncel bir görünüm elde edersin.
"""

import random
from datetime import date, timedelta

import database
import repository
import auth

random.seed(42)  # tekrarlanabilir sonuclar icin sabit tohum

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
    "", "", "", "",  # cogunlukla referanssiz olsun (gercekci oran)
]

ORNEK_TC_HAVUZU = [str(random.randint(10000000000, 99999999999)) for _ in range(200)]
_tc_index = 0


def yeni_tc():
    global _tc_index
    tc = ORNEK_TC_HAVUZU[_tc_index % len(ORNEK_TC_HAVUZU)]
    _tc_index += 1
    return tc


def yeni_telefon():
    return f"05{random.randint(30,59)}{random.randint(1000000,9999999)}"


def kullanicilari_olustur():
    olusturulanlar = []
    for kullanici_adi, sifre, ad_soyad in TEST_KULLANICILAR:
        try:
            auth.kullanici_ekle(kullanici_adi, sifre, ad_soyad)
            olusturulanlar.append(kullanici_adi)
        except ValueError:
            pass  # zaten var, atla
    return [k[0] for k in TEST_KULLANICILAR]


def rastgele_kullanici():
    return random.choice([k[0] for k in TEST_KULLANICILAR])


def rastgele_isim():
    return random.choice(ORNEK_ISIMLER)


def rastgele_referans():
    return random.choice(ORNEK_REFERANSLAR)


def kapasiteye_uygun_kisi(kapasite):
    return random.randint(1, kapasite)


def gecmis_gecelerini_ode(rez_id, oran=0.75):
    """Bir rezervasyonun BUGÜNE KADAR (bugün dahil) olan gecelerinin bir kısmını
    'ödendi' yapar (gerçekçi bir ödeme oranı, gelecek geceler hep ödenmemiş kalır)."""
    bugun = date.today().isoformat()
    odemeler = repository.rezervasyon_odemeleri(rez_id)
    for o in odemeler:
        if o["tarih"] <= bugun and random.random() < oran:
            sekil = random.choice(database.ODEME_SEKILLERI)
            repository.odeme_guncelle(o["id"], True, sekil)


def main():
    database.init_db()
    if repository.oda_listesi() == []:
        database.varsayilan_odalari_yukle()

    kullanicilar = kullanicilari_olustur()
    odalar = repository.oda_listesi()

    bugun = date.today()
    olusturulan_rez_sayisi = 0
    olusturulan_iptal_sayisi = 0

    print(f"Test verisi oluşturuluyor (referans tarih: {bugun.isoformat()})...")
    print(f"Kullanılan odalar: {len(odalar)}")

    # ---------------------------------------------------------------
    # 1) GENEL DOLGU: son 30 gün ile önümüzdeki 30 gün arasında,
    #    her oda için birkaç rastgele rezervasyon bloğu oluştur.
    # ---------------------------------------------------------------
    pencere_baslangic = bugun - timedelta(days=30)
    pencere_bitis = bugun + timedelta(days=35)

    for oda in odalar:
        gunluk_isaretci = pencere_baslangic
        # her odada, pencere boyunca dolu/bos karisik bloklar olustur
        while gunluk_isaretci < pencere_bitis:
            # %55 ihtimalle bu bloktan bir rezervasyon olustur, degilse bosluk birak
            if random.random() < 0.55:
                gece = random.choice([1, 1, 2, 2, 3, 4, 5])
                kisi = kapasiteye_uygun_kisi(oda["kapasite"])
                fiyat_tipi = random.choice(["Sabit", "Sabit", "Sabit", "Uye"])  # cogunlukla Sabit
                giris_str = gunluk_isaretci.isoformat()

                cakisma = repository.musaitlik_kontrol(oda["id"], giris_str, gece)
                if not cakisma:
                    try:
                        # Gecmis tarihe rezervasyon olusturuluyorsa gecmis engeli kapali gonder
                        gecmis_kontrol = giris_str >= bugun.isoformat()
                        rez_id = repository.rezervasyon_olustur(
                            oda_id=oda["id"],
                            ad_soyad=rastgele_isim(),
                            tc_no=yeni_tc(),
                            telefon=yeni_telefon(),
                            kisi_sayisi=kisi,
                            giris_tarihi=giris_str,
                            gece_sayisi=gece,
                            fiyat_tipi=fiyat_tipi,
                            referans=rastgele_referans(),
                            olusturan_kullanici=rastgele_kullanici(),
                            gecmis_kontrol=gecmis_kontrol,
                        )
                        olusturulan_rez_sayisi += 1

                        cikis = gunluk_isaretci + timedelta(days=gece)
                        # Eger konaklama bugune kadar basladiysa check-in yapilmis olsun.
                        # Tam BUGUN baslayanlarin bir kismi ("Bekleniyor" ornegi icin) kasti
                        # olarak check-in YAPILMAMIS birakilir. GECMISTE baslayip hala check-in
                        # yapilmamis olanlarin kucuk bir kismi de kasti olarak "Gelmedi/No-Show"
                        # ornegi olarak birakilir (gercekci oran ~%8).
                        bugun_str = bugun.isoformat()
                        if giris_str < bugun_str:
                            if random.random() < 0.08:
                                pass  # kasti olarak check-in yapilmadan birakiliyor -> No-Show ornegi
                            else:
                                isimler = [rastgele_isim() for _ in range(kisi)]
                                tcler = [yeni_tc() for _ in range(kisi)]
                                repository.misafirleri_kaydet(rez_id, list(zip(isimler, tcler)))
                                repository.checkin_yap(rez_id)
                                gecmis_gecelerini_ode(rez_id, oran=0.75)
                        elif giris_str == bugun_str and random.random() < 0.6:
                            isimler = [rastgele_isim() for _ in range(kisi)]
                            tcler = [yeni_tc() for _ in range(kisi)]
                            repository.misafirleri_kaydet(rez_id, list(zip(isimler, tcler)))
                            repository.checkin_yap(rez_id)
                            gecmis_gecelerini_ode(rez_id, oran=0.75)

                        # nadiren iptal edilmis rezervasyon ornegi
                        if random.random() < 0.06:
                            repository.rezervasyon_iptal(rez_id)
                            olusturulan_iptal_sayisi += 1

                        gunluk_isaretci = cikis
                    except ValueError:
                        gunluk_isaretci += timedelta(days=1)
                else:
                    gunluk_isaretci += timedelta(days=1)
            else:
                gunluk_isaretci += timedelta(days=random.choice([1, 2]))

    # ---------------------------------------------------------------
    # 2) ÇOK ODALI GRUP REZERVASYONU ÖRNEĞİ (aynı gün, 3 farklı oda)
    # ---------------------------------------------------------------
    bos_odalar_orta_vade = []
    grup_tarih = (bugun + timedelta(days=10)).isoformat()
    for oda in odalar:
        if not repository.musaitlik_kontrol(oda["id"], grup_tarih, 2):
            bos_odalar_orta_vade.append(oda)
        if len(bos_odalar_orta_vade) >= 3:
            break

    if len(bos_odalar_orta_vade) >= 3:
        grup_id = repository.yeni_grup_id()
        grup_ad = "Kemal Öztürk (Grup Rezervasyonu)"
        grup_tc = yeni_tc()
        grup_tel = yeni_telefon()
        for oda in bos_odalar_orta_vade[:3]:
            repository.rezervasyon_olustur(
                oda_id=oda["id"], ad_soyad=grup_ad, tc_no=grup_tc, telefon=grup_tel,
                kisi_sayisi=kapasiteye_uygun_kisi(oda["kapasite"]),
                giris_tarihi=grup_tarih, gece_sayisi=2, fiyat_tipi="Sabit",
                referans="Başkan Ahmet Bey", grup_id=grup_id,
                olusturan_kullanici=rastgele_kullanici(),
            )
            olusturulan_rez_sayisi += 1
        print(f"Grup rezervasyonu örneği eklendi: {grup_ad} ({grup_tarih}, 3 oda)")

    # ---------------------------------------------------------------
    # 3) EKSTRA YATAK ÖRNEĞİ (Aile odasında kapasite üstü, +1 ekstra yatakla)
    # ---------------------------------------------------------------
    aile_odalari = [o for o in odalar if o["oda_tipi"] == "Aile"]
    if aile_odalari:
        oda = aile_odalari[0]
        tarih = (bugun + timedelta(days=3)).isoformat()
        if not repository.musaitlik_kontrol(oda["id"], tarih, 2):
            rez_id = repository.rezervasyon_olustur(
                oda_id=oda["id"], ad_soyad="Ekstra Yataklı Aile", tc_no=yeni_tc(),
                telefon=yeni_telefon(), kisi_sayisi=oda["kapasite"],
                giris_tarihi=tarih, gece_sayisi=2, fiyat_tipi="Sabit",
                olusturan_kullanici=rastgele_kullanici(),
            )
            # check-in yapip ekstra yatakla 1 kisi daha ekleyelim
            isimler = [rastgele_isim() for _ in range(oda["kapasite"] + 1)]
            tcler = [yeni_tc() for _ in range(oda["kapasite"] + 1)]
            repository.misafirleri_kaydet(rez_id, list(zip(isimler, tcler)), ekstra_yatak=True)
            repository.checkin_yap(rez_id)
            olusturulan_rez_sayisi += 1
            print(f"Ekstra yatak örneği eklendi: Oda {oda['oda_no']} ({oda['kapasite']}+1 kişi)")

    # ---------------------------------------------------------------
    # 4) ODA DEĞİŞİKLİĞİ ÖRNEĞİ (halihazırda kalan birini başka odaya taşı)
    # ---------------------------------------------------------------
    tum_rez = repository.rezervasyon_listesi("aktif")
    devam_eden = [
        r for r in tum_rez
        if r["giris_tarihi"] <= bugun.isoformat()
        and repository.cikis_tarihi_hesapla(r["giris_tarihi"], r["gece_sayisi"]) > (bugun + timedelta(days=1)).isoformat()
    ]
    if devam_eden:
        secilen = devam_eden[0]
        eski_oda_id = secilen["oda_id"]
        for oda in odalar:
            if oda["id"] == eski_oda_id:
                continue
            degisim_tarihi = (bugun + timedelta(days=1)).isoformat()
            if not repository.musaitlik_kontrol(oda["id"], degisim_tarihi, 1):
                try:
                    repository.oda_degistir(secilen["id"], oda["id"], degisim_tarihi)
                    print(f"Oda değişikliği örneği: '{secilen['ad_soyad']}' başka odaya taşındı.")
                    break
                except ValueError:
                    continue

    # ---------------------------------------------------------------
    # 5) ODA DURUMU ÖRNEKLERİ (arızalı + temizlikte)
    #    Bugün boş olan (rezervasyonsuz) odalardan birini arızalı, birini
    #    temizlikte işaretle ki takvimde ve Oda Yönetimi ekranında görünsün.
    # ---------------------------------------------------------------
    bugun_str = bugun.isoformat()
    gundeki_odalar = repository.gunun_checkin_durumu(bugun_str)
    bos_odalar = [satir for satir in gundeki_odalar if satir["rez_id"] is None]
    if len(bos_odalar) >= 2:
        try:
            repository.oda_durum_ayarla(bos_odalar[0]["oda_id"], "arizali", ariza_gun=3)
            print("Arızalı oda örneği eklendi (bugün, 3 gün kapalı).")
        except ValueError:
            pass
        try:
            repository.oda_durum_ayarla(bos_odalar[1]["oda_id"], "temizlikte")
            print("Temizlikte oda örneği eklendi.")
        except ValueError:
            pass

    print(f"\nToplam oluşturulan rezervasyon: {olusturulan_rez_sayisi}")
    print(f"Toplam iptal edilen: {olusturulan_iptal_sayisi}")
    gelmeyen_sayisi = sum(1 for r in repository.rezervasyon_listesi("aktif") if repository.gelmedi_mi(r))
    print(f"Toplam gelmeyen (No-Show): {gelmeyen_sayisi}")
    print("\n--- TEST KULLANICILARI (hepsinin şifresi: test1234) ---")
    for kullanici_adi, sifre, ad_soyad in TEST_KULLANICILAR:
        print(f"  Kullanıcı adı: {kullanici_adi:10s}  Ad Soyad: {ad_soyad}")
    print("\nUygulamayı açıp yukarıdaki kullanıcılardan biriyle giriş yapabilirsin.")
    print("Test verisini temizlemek istersen, sadece misafirhane.db dosyasını sil.")


if __name__ == "__main__":
    main()
