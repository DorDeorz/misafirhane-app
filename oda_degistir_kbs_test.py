# -*- coding: utf-8 -*-
"""
oda_degistir() + KBS zinciri icin izole regresyon testi.

1.0.4.3'te duzeltilen ucu-uca senaryoyu dogrular: bir misafir check-in
yapildiktan sonra BASKA BIR ODAYA tasinirsa (kalis ortasinda bolunme):
  - yeni odadaki misafir kaydinda yabanci KBS alanlari (uyruk vb.) kaybolmamali,
  - KBS'de aynı misafir icin MUKERRER "giris" bildirimi cikmamali,
  - misafir hala otelde oldugu icin o gun "bugun_cikacaklar" listesine
    YANLISLIKLA dusmemeli,
  - gercekten check-out yapildiginda KBS'de TEK bir "cikis" bildirimi cikmali.

Kendi GECICI veritabanini kurar (TEMP altinda); uygulamanin gercek
verisine (misafirhane.db / misafirhane_deneme.db) DOKUNMAZ.
"""
import os
import sys
import tempfile
import shutil
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TEST_KLASOR = os.path.join(tempfile.gettempdir(), "opencode", "oda_degistir_kbs_test")
if os.path.isdir(TEST_KLASOR):
    shutil.rmtree(TEST_KLASOR)
os.makedirs(TEST_KLASOR, exist_ok=True)

import database
import repository
import kbs

# database.py dev modunda __file__ konumunu (proje klasorunu) kullanir; gercek
# uygulama verisine DOKUNMAMAK icin burada TEMP'teki test klasorune yonlendiriyoruz.
database.VERI_KLASORU = TEST_KLASOR
database.DB_PATH = os.path.join(TEST_KLASOR, "misafirhane.db")
TAKIP_YOLU = os.path.join(TEST_KLASOR, "kbs_takip.db")

database.init_db()
database.varsayilan_odalari_yukle()

odalar = database.get_connection().execute("SELECT id, oda_no FROM odalar ORDER BY id").fetchall()
oda_a, oda_b = odalar[0]["id"], odalar[1]["id"]

bugun = date.today()
giris = (bugun - timedelta(days=2)).isoformat()

conn = database.get_connection()
cur = conn.cursor()
cur.execute("INSERT INTO rezervasyonlar (ad_soyad) VALUES ('Test Yabanci')")
rez_id = cur.lastrowid
cur.execute(
    "INSERT INTO rezervasyon_odalar (rezervasyon_id, oda_id, giris_tarihi, gece_sayisi, kisi_sayisi, checkin_yapildi) "
    "VALUES (?,?,?,?,1,1)",
    (rez_id, oda_a, giris, 4),
)
ro_id = cur.lastrowid
conn.commit()
conn.close()

# Yabanci misafir bilgilerini TAM olarak kaydet (gercek check-in akisindaki gibi)
repository.odasi_misafirleri_kaydet(ro_id, [{
    "ad_soyad": "Hans Muller", "tc_no": "A1234567", "fiyat_tipi": "Sabit", "gecelik_ucret": 1300,
    "uyruk": "Alman", "dogum_tarihi": "1980-01-01", "cinsiyet": "Erkek",
    "dogum_yeri": "Berlin", "belge_turu": "Pasaport",
}])

hatalar = []

giris_once, _ = kbs.kbs_bekleyenler(database.DB_PATH, TAKIP_YOLU)
if len(giris_once) != 1:
    hatalar.append(f"[ONCE] giris bekleyen 1 degil: {len(giris_once)}")

# BUGUN itibariyle oda degistir (kalis ortasinda bolunme)
eski_ro_id, yeni_ro_id = repository.oda_degistir(ro_id, oda_b, bugun.isoformat())
if yeni_ro_id is None:
    hatalar.append("oda_degistir tam tasima yapti, kismi bolme beklendi")

giris_sonra, cikis_sonra = kbs.kbs_bekleyenler(database.DB_PATH, TAKIP_YOLU)
if len(giris_sonra) != 1:
    hatalar.append(f"MUKERRER GIRIS: oda degisiminden sonra giris bekleyen 1 degil: {len(giris_sonra)}")

bugun_cikanlar = repository.bugun_cikacaklar(bugun.isoformat())
if len(bugun_cikanlar) != 0:
    hatalar.append(f"SAHTE CIKIS: oda degisimi bugun_cikacaklar'da yanlis satir uretti: {len(bugun_cikanlar)}")

yeni_misafirler = repository.odasi_misafirler_listele(yeni_ro_id)
if not yeni_misafirler or (yeni_misafirler[0]["uyruk"] or "") != "Alman":
    hatalar.append(f"YABANCI BILGISI KAYBOLDU: {[dict(m) for m in yeni_misafirler]}")

eski_satir = repository.rezervasyon_odasi_getir(eski_ro_id)
if not eski_satir["cikis_tarihi"]:
    hatalar.append("eski (bolunmus) satirin cikis_tarihi'si hala NULL (Gecmis Kayitlar'a hic dusmez)")

# Simdi GERCEK cikis yapilsin (yeni odadan) -> KBS'de TEK bir cikis bildirimi cikmali
repository.odasi_cikis_yap(yeni_ro_id, bugun.isoformat())
_, cikis_final = kbs.kbs_bekleyenler(database.DB_PATH, TAKIP_YOLU)
if len(cikis_final) != 1:
    hatalar.append(f"gercek cikis sonrasi cikis bekleyen 1 degil: {len(cikis_final)}")

print("Giris (once):", len(giris_once), "| Giris (oda degisimi sonrasi):", len(giris_sonra),
      "| bugun_cikacaklar:", len(bugun_cikanlar), "| Cikis (gercek cikis sonrasi):", len(cikis_final))

if hatalar:
    print("\nHATALAR:")
    for h in hatalar:
        print(" -", h)
    raise SystemExit(1)
print("\nTUM ODA DEGISTIRME/KBS DOGRULAMALARI GECTI")
