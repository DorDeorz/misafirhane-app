# -*- coding: utf-8 -*-
"""
1.0.5 TEST VERİTABANI OLUŞTURUCU
================================
Uygulamanın bütün ekranlarını ve 1.0.5 özelliklerini (Kasa / Borçlar, tekrar
gelen misafir, misafir kartı, hesap dökümü, günün özeti, istatistik
karşılaştırması) deneyebilmek için örnek verili AYRI bir veritabanı üretir.
Tarihler çalıştırıldığı güne göre kurulur.

GÜVENLİK: GERÇEK VERİYE DOKUNMAZ. Veritabanı yalnızca verilen hedef klasöre
yazılır; hedef, proje klasörü ya da %LOCALAPPDATA%\\Misafirhane ise çalışmaz.

ÇALIŞTIRMA:
    python test_verisi_105.py <hedef_klasör>          (veritabanını üretir)
    python test_verisi_105.py <hedef_klasör> --ac     (üretir ve uygulamayı o veriyle açar)
Hedef verilmezse TEMP\\misafirhane_test_105 kullanılır. Klasördeki eski
misafirhane.db / kbs_takip.db silinip yeniden kurulur.

Giriş: oğuz / 1234   (ayrıca ayse, mehmet / test1234)
"""

import os
import random
import sys
import tempfile
from datetime import date, datetime, timedelta

PROJE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJE)

import database

random.seed(20260927)

KULLANICILAR = [("oğuz", "1234", "Oğuz"), ("ayse", "test1234", "Ayşe Yılmaz"),
                ("mehmet", "test1234", "Mehmet Kaya")]

ISIMLER = [
    "Ahmet Yıldırım", "Mehmet Demir", "Ayşe Kaya", "Fatma Şahin", "Mustafa Çelik",
    "Emine Yıldız", "Hüseyin Aydın", "Zeynep Öztürk", "Ali Arslan", "Hatice Doğan",
    "İbrahim Kılıç", "Elif Aslan", "Hasan Çetin", "Sultan Kurt", "Osman Koç",
    "Fatih Şen", "Merve Aksoy", "Ramazan Türk", "Büşra Yalçın", "Kemal Öz",
    "Selin Acar", "Yusuf Polat", "Gül Erdoğan", "Murat Bulut", "Esra Güneş",
    "Cem Özkan", "Deniz Uçar", "Burak Tekin", "Sevgi Ateş", "Onur Karaca",
]
REFERANSLAR = ["Başkan Ahmet Bey", "Üye Mehmet Yılmaz", "Üye Ayşe Kaya", "Sayman Hüseyin Bey",
               "", "", "", "", ""]

# Tekrar gelen misafirler: aynı telefon/TC ile birden çok konaklama.
SADIK = {
    "hakan": dict(ad="Hakan Yurt", tel="0532 400 10 01"),
    "serkan": dict(ad="Serkan Tunç", tel="0533 400 10 02"),
    "derya": dict(ad="Derya Kılınç", tel="0544 400 10 03"),
}


def gecerli_tc():
    """T.C. Kimlik No sağlama algoritmasına uyan rastgele numara."""
    d = [random.randint(1, 9)] + [random.randint(0, 9) for _ in range(8)]
    d10 = ((d[0] + d[2] + d[4] + d[6] + d[8]) * 7 - (d[1] + d[3] + d[5] + d[7])) % 10
    d.append(d10)
    d.append(sum(d) % 10)
    return "".join(map(str, d))


for _s in SADIK.values():
    _s["tc"] = gecerli_tc()


def telefon():
    return f"05{random.choice(['32', '33', '35', '42', '44', '52', '55'])} " \
           f"{random.randint(100, 999)} {random.randint(10, 99)} {random.randint(10, 99)}"


def hedef_klasoru_hazirla(klasor):
    klasor = os.path.abspath(klasor)
    yasak = {os.path.abspath(PROJE)}
    if os.environ.get("LOCALAPPDATA"):
        yasak.add(os.path.abspath(os.path.join(os.environ["LOCALAPPDATA"], "Misafirhane")))
    if klasor in yasak:
        sys.exit(f"HATA: {klasor} gerçek veri klasörü, test verisi buraya yazılmaz.")
    os.makedirs(klasor, exist_ok=True)
    for ad in ("misafirhane.db", "kbs_takip.db"):
        yol = os.path.join(klasor, ad)
        if os.path.exists(yol):
            os.remove(yol)
    database.VERI_KLASORU = klasor
    database.DB_PATH = os.path.join(klasor, "misafirhane.db")
    return klasor


# Aşağıdaki modüller DB yolunu çağrı anında database'den okur; yol ayarlandıktan
# sonra kullanılırlar.
import repository as R  # noqa: E402
import loglama  # noqa: E402
import auth  # noqa: E402

B = date.today()


def g(n):
    return (B + timedelta(days=n)).isoformat()


def rez(oda, giris_ofs, gece, kisi=1, ad=None, tel=None, fiyat="Sabit", ozel=None,
        referans=None, kullanici=None, odalar=None):
    """Tek (ya da odalar verilirse çok) odalı rezervasyon; oda satırlarını döndürür."""
    satirlar = odalar or [dict(oda_id=oda["id"], giris_tarihi=g(giris_ofs), gece_sayisi=gece,
                               kisi_sayisi=kisi, fiyat_tipi=fiyat, ozel_ucret=ozel)]
    rid = R.rezervasyon_olustur(
        satirlar, ad_soyad=ad or random.choice(ISIMLER), telefon=tel or telefon(),
        referans=random.choice(REFERANSLAR) if referans is None else referans,
        olusturan_kullanici=kullanici or random.choice(KULLANICILAR)[0], gecmis_kontrol=False)
    return rid, [dict(r) for r in R.rezervasyon_odalar_listele(rid)]


def checkin(ro, ilk_ad=None, ilk_tc=None, fatura=False, yabanci=False):
    kisiler = []
    for i in range(ro["kisi_sayisi"]):
        if i == 0 and ilk_ad:
            kisiler.append({"ad_soyad": ilk_ad, "tc_no": ilk_tc or gecerli_tc()})
        elif yabanci and i == 0:
            kisiler.append({"ad_soyad": "John Smith", "tc_no": "P" + str(random.randint(1000000, 9999999)),
                            "uyruk": "GBR", "dogum_tarihi": "1985-04-12", "cinsiyet": "Erkek",
                            "dogum_yeri": "London", "belge_turu": "Pasaport"})
        else:
            kisiler.append({"ad_soyad": random.choice(ISIMLER), "tc_no": gecerli_tc()})
    for k in kisiler:
        k.setdefault("fiyat_tipi", ro["fiyat_tipi"])
        k.setdefault("gecelik_ucret", ro["gecelik_ucret"])
    R.odasi_misafirleri_kaydet_ve_checkin(ro["id"], kisiler, fatura_istiyor=fatura)


def ode(odeme, sekil=None, zaman=None, kullanici=None):
    """Bir geceyi ödendi yapar; zaman verilirse tahsil zamanını o ana çeker
    (geçmiş günlerin kasa raporu dolsun diye)."""
    kullanici = kullanici or random.choice(KULLANICILAR)[0]
    loglama.set_aktif_kullanici(kullanici)
    R.odeme_guncelle(odeme["id"], True, sekil or random.choice(database.ODEME_SEKILLERI))
    if zaman:
        c = database.get_connection()
        c.execute("UPDATE odemeler SET tahsil_zamani=? WHERE id=?", (zaman, odeme["id"]))
        c.commit()
        c.close()


def saat(gun_str):
    return f"{gun_str} {random.randint(9, 21):02d}:{random.randint(0, 59):02d}:00"


def gecmis_odemeleri(ro, borc_birak=0):
    """Kalınmış geceleri öder (tahsil günü = çıkış ya da giriş günü);
    borc_birak kadar son geceyi ödenmemiş bırakır (açık borç)."""
    odemeler = [o for o in R.odasi_odemeler(ro["id"]) if o["tarih"] < g(0)]
    if borc_birak:
        odemeler = odemeler[:-borc_birak] if len(odemeler) > borc_birak else []
    cikis = R.cikis_tarihi_hesapla(ro["giris_tarihi"], ro["gece_sayisi"])
    tahsil_gunu = min(cikis, g(0)) if random.random() < 0.7 else ro["giris_tarihi"]
    sekil = random.choice(database.ODEME_SEKILLERI)
    kisi = random.choice(KULLANICILAR)[0]
    for o in odemeler:
        ode(o, sekil, saat(tahsil_gunu) if tahsil_gunu < g(0) else None, kisi)


def dolgu(odalar, bas_ofs, bit_ofs, doluluk, gecmis):
    """[bas_ofs, bit_ofs) aralığına her odaya rastgele kalışlar yerleştirir."""
    sayi = 0
    for oda in odalar:
        gun = bas_ofs
        while gun < bit_ofs:
            if random.random() > doluluk:
                gun += random.choice([1, 2, 3])
                continue
            gece = random.choice([1, 2, 2, 3, 3, 4, 5, 7])
            if gecmis:
                gece = min(gece, max(1, -gun))  # geçmiş kalış bugünden önce biter
            kisi = random.randint(1, oda["kapasite"])
            fiyat = random.choice(["Sabit", "Sabit", "Sabit", "Uye", "Ozel"])
            ozel = random.choice([900, 1000, 1100]) if fiyat == "Ozel" else None
            if R.musaitlik_kontrol(oda["id"], g(gun), gece):
                gun += 1
                continue
            try:
                rid, ros = rez(oda, gun, gece, kisi, fiyat=fiyat, ozel=ozel)
            except ValueError:
                gun += 1
                continue
            sayi += 1
            if gecmis:
                zar = random.random()
                if zar < 0.06:
                    R.rezervasyon_iptal(rid)
                elif zar < 0.14:
                    R.gelmeyenleri_iptal_et([rid])  # eski no-show: zaten 'Gelmedi' işaretli
                else:
                    fatura = random.random() < 0.15
                    checkin(ros[0], fatura=fatura)
                    gecmis_odemeleri(ros[0], borc_birak=1 if random.random() < 0.03 else 0)
                    if fatura and random.random() < 0.85:
                        R.fatura_durumu_guncelle(ros[0]["id"], True)
            gun += gece + random.choice([0, 0, 1])
    return sayi


def main():
    arg = [a for a in sys.argv[1:] if not a.startswith("--")]
    klasor = hedef_klasoru_hazirla(arg[0] if arg else os.path.join(tempfile.gettempdir(), "misafirhane_test_105"))
    print(f"Test veritabanı kuruluyor: {database.DB_PATH}")
    print(f"Referans gün (bugün): {g(0)}")

    database.init_db()
    database.varsayilan_odalari_yukle()
    for k, s, a in KULLANICILAR:
        auth.kullanici_ekle(k, s, a)
    database.set_ayar("tesis_adi", "Misafirhane (TEST)")
    O = R.oda_listesi()
    oda = {o["oda_no"]: o for o in O}

    # ---- BUGÜN: içeride, çıkacak, gelecek ----
    # Oda 1-3: bugün çıkacaklar (biri çıkış yaptı -> temizlikte)
    cikacaklar = []
    for no in (1, 2, 3):
        _, ros = rez(oda[no], -2, 2, kisi=1)
        checkin(ros[0])
        cikacaklar.append(ros[0])
    gecmis_odemeleri(cikacaklar[0])
    gecmis_odemeleri(cikacaklar[1], borc_birak=1)          # çıkarken borcu var
    R.odasi_cikis_yap(cikacaklar[0]["id"], g(0))            # çıktı, oda temizlikte

    # Oda 4: Derya (tekrar gelen) içeride, 1 gece borçlu, fatura istiyor (alınmadı)
    d = SADIK["derya"]
    _, ros = rez(oda[4], -3, 5, kisi=2, ad=d["ad"], tel=d["tel"], referans="Üye Ayşe Kaya")
    checkin(ros[0], d["ad"], d["tc"], fatura=True)
    gecmis_odemeleri(ros[0], borc_birak=1)

    # Oda 5: yabancı misafir içeride (KBS giriş bekleyen)
    _, ros = rez(oda[5], -1, 3, kisi=1, ad="John Smith")
    checkin(ros[0], yabanci=True)

    # Oda 6: uzun kalış, kalış ortasında Oda 7'ye taşındı; ödemeler bugün alındı
    _, ros = rez(oda[6], -4, 8, kisi=2, referans="Başkan Ahmet Bey")
    checkin(ros[0])
    for o in R.odasi_odemeler(ros[0]["id"]):
        if o["tarih"] <= g(0):
            ode(o, "Havale/IBAN", kullanici="oğuz")          # bugün tahsil -> kasada görünür
    R.oda_degistir(ros[0]["id"], oda[7]["id"], g(-1))

    # Oda 8: bugün giriş, check-in yapıldı, bugünkü gece ödendi (kasada)
    _, ros = rez(oda[8], 0, 2, kisi=1, fiyat="Uye")
    checkin(ros[0])
    ode(R.odasi_odemeler(ros[0]["id"])[0], "Kredi Karti", kullanici="ayse")

    # Oda 9-10: bugün giriş, bekleniyor
    rez(oda[9], 0, 3, kisi=2)
    rez(oda[10], 0, 1, kisi=1, fiyat="Ozel", ozel=950, referans="Üye Mehmet Yılmaz")

    # Oda 11: dün girmesi gerekiyordu, gelmedi (açılışta sorulur)
    rez(oda[11], -1, 2, kisi=1)

    # Oda 12: arızalı (3 gün)
    R.oda_durum_ayarla(oda[12]["id"], "arizali", ariza_gun=3)

    # ---- TEKRAR GELEN MİSAFİRLERİN GEÇMİŞİ ----
    gecmis_kalislar = [("hakan", 13, -95, 2), ("hakan", 14, -60, 3), ("hakan", 13, -20, 2),
                       ("serkan", 15, -80, 2), ("serkan", 16, -40, 4),
                       ("derya", 17, -70, 3), ("derya", 17, -30, 2)]
    for anahtar, no, ofs, gece in gecmis_kalislar:
        s = SADIK[anahtar]
        _, ros = rez(oda[no], ofs, gece, kisi=1, ad=s["ad"], tel=s["tel"])
        checkin(ros[0], s["ad"], s["tc"])
        gecmis_odemeleri(ros[0], borc_birak=1 if anahtar == "serkan" and ofs == -40 else 0)
    R.misafir_karti_kaydet(SADIK["hakan"]["tel"], SADIK["hakan"]["tc"], SADIK["hakan"]["ad"],
                           "Sessiz oda ister, üst katları tercih ediyor.", False)
    R.misafir_karti_kaydet(SADIK["serkan"]["tel"], SADIK["serkan"]["tc"], SADIK["serkan"]["ad"],
                           "Odada hasar bıraktı, ödemeyi geciktirdi.", True)
    # Serkan ileri tarihli rezervasyon (detayda kırmızı uyarı görünür)
    rez(oda[15], 12, 2, kisi=1, ad=SADIK["serkan"]["ad"], tel=SADIK["serkan"]["tel"])

    # ---- İLERİ TARİH: grup rezervasyonu ----
    grup = [dict(oda_id=oda[no]["id"], giris_tarihi=g(8), gece_sayisi=2, kisi_sayisi=2,
                 fiyat_tipi="Sabit") for no in (2, 3, 5)]
    rez(None, 0, 0, ad="Eyüp Korkmaz", referans="Başkan Ahmet Bey", odalar=grup)

    # ---- GENEL DOLGU ----
    n_gecmis = dolgu(O, -120, -3, 0.55, gecmis=True)
    n_gecen_yil = dolgu(O, -365 - 20, -365 + 20, 0.4, gecmis=True)
    n_gelecek = dolgu(O, 1, 60, 0.45, gecmis=False)

    # Eski konaklamaları kapat (uygulamanın açılıştaki günlük bakımıyla aynı iş)
    R.gunluk_bakim()
    loglama.set_aktif_kullanici(None)

    # ---- ÖZET ----
    oz = R.gunun_ozeti()
    kasa = R.gun_sonu_kasa(g(0))
    borc = R.acik_borclar()
    print(f"\nRezervasyon: {len(R.rezervasyon_listesi('hepsi'))} "
          f"(dolgu: {n_gecmis} geçmiş, {n_gecen_yil} geçen yıl, {n_gelecek} ileri)")
    print(f"Bugün: {oz['giris_toplam']} giriş ({oz['giris_bekleyen']} bekleniyor), "
          f"{oz['cikis_bekleyen']} çıkacak, {oz['dolu_oda']} dolu oda")
    print(f"Kasa (bugün): {kasa['toplam']:,} TL / {len(kasa['satirlar'])} gece")
    print(f"Açık borç: {sum(b['borc'] for b in borc):,} TL / {len(borc)} oda")
    print(f"Gelmeyen (açılışta sorulacak): {len(R.gelmeyen_rezervasyonlar())}")
    print("Tekrar gelen misafir telefonları (Yeni Rezervasyon'da deneyin):")
    for s in SADIK.values():
        print(f"  {s['tel']}  {s['ad']}")
    print("Giriş: oğuz / 1234")

    if "--ac" in sys.argv:
        os.chdir(PROJE)
        import main as uygulama
        uygulama.main()


if __name__ == "__main__":
    main()
