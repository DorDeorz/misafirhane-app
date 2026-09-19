# -*- coding: utf-8 -*-
"""
Misafirhane Rezervasyon Sistemi - Veritabanı Katmanı
SQLite kullanarak yerel, internetsiz çalışan veri yönetimi.
"""

import sqlite3
import os
import sys
import shutil
from datetime import datetime


def _veri_klasoru():
    """Kullaniciya ait verilerin (DB, yedekler) saklanacagi klasor.

    Dondurulmus (PyInstaller) surumde program dosyalari okuma-yazma
    korumali olabileceginden veri %LOCALAPPDATA%\\Misafirhane altina alinir.
    Gelistirme modunda betigin bulundugu klasor kullanilir.
    """
    if getattr(sys, "frozen", False):
        taban = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(taban, "Misafirhane")
    return os.path.dirname(os.path.abspath(__file__))


VERI_KLASORU = _veri_klasoru()
os.makedirs(VERI_KLASORU, exist_ok=True)

DB_PATH = os.path.join(VERI_KLASORU, "misafirhane.db")

ODA_TIPLERI = ["Tek", "Double", "Aile", "Tek+Tek"]
# "Sabit" ve "Uye" fiyati admin panelinden degistirilebilir; "Ozel" rezervasyon
# sirasinda elle girilen kisi basi fiyat icindir.
FIYAT_TIPLERI = ["Sabit", "Uye", "Ozel"]  # Sabit ilk sirada -> formlarda varsayilan secim
FIYAT_UYE = 600      # KİŞİ BAŞI, gecelik (varsayilan; ayarlardan degistirilir)
FIYAT_SABIT = 1300   # KİŞİ BAŞI, gecelik (varsayilan; ayarlardan degistirilir)
ODEME_SEKILLERI = ["Nakit", "Kredi Karti", "Havale/IBAN", "Fatura"]

# Oda durumlari (odalar.durum):
#   temiz      -> normal, rezervasyona acik
#   temizlikte -> cikis yapildi, housekeeping temizligi bekliyor
#   arizali    -> bakim/ariza nedeniyle kapali (ariza_bitis'e kadar)
ODA_DURUMLARI = ["temiz", "temizlikte", "arizali"]


def fiyat_tipi_goster(tip):
    """Veritabanindaki fiyat kodu -> ekranda gosterilecek etiket."""
    return {"Uye": "Üye", "Ozel": "Özel", "Sabit": "Sabit"}.get(tip, tip)

# Oda tipine göre varsayılan maksimum kapasite (ekstra yatak ile)
ODA_TIPI_KAPASITE = {"Tek": 1, "Double": 2, "Tek+Tek": 3, "Aile": 4}


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS odalar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                eski_no INTEGER,
                kat_no INTEGER,
                kat_adi TEXT,
                oda_no INTEGER,
                oda_tipi TEXT,
                kapasite INTEGER DEFAULT 1,
                aktif INTEGER DEFAULT 1,
                durum TEXT DEFAULT 'temiz',
                ariza_bitis TEXT
            )
        """)

        # Rezervasyon basina TEK satir: bir rezervasyon birden fazla odaya
        # (rezervasyon_odalar) yayilabilir. Oda/kisi/giris bilgileri burada degil.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rezervasyonlar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ad_soyad TEXT NOT NULL,
                tc_no TEXT,
                telefon TEXT,
                referans TEXT,
                notlar TEXT DEFAULT '',
                olusturan_kullanici TEXT,
                iptal INTEGER DEFAULT 0,
                olusturma_tarihi TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Bir rezervasyondaki her oda icin ayri satir. Oda bazli giris/cikis,
        # kisi, fiyat ve check-in burada tutulur. Ayni oda bir rezervasyonda
        # yalnizca bir kez gecebilir (oda degisikliginde ayni rezervasyona
        # SECOND bir satir eklenmez; eski satir yeni odaya tasinir / bolunur).
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rezervasyon_odalar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rezervasyon_id INTEGER NOT NULL,
                oda_id INTEGER NOT NULL,
                giris_tarihi TEXT NOT NULL,
                gece_sayisi INTEGER NOT NULL DEFAULT 1,
                cikis_tarihi TEXT,
                kisi_sayisi INTEGER NOT NULL DEFAULT 1,
                fiyat_tipi TEXT DEFAULT 'Sabit',
                gecelik_ucret INTEGER DEFAULT 1300,
                checkin_yapildi INTEGER DEFAULT 0,
                FOREIGN KEY (rezervasyon_id) REFERENCES rezervasyonlar(id),
                FOREIGN KEY (oda_id) REFERENCES odalar(id)
            )
        """)
        cur.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uk_rez_oda "
            "ON rezervasyon_odalar (rezervasyon_id, oda_id)"
        )

        # Oda bazli check-in ile doldurulan kisi listesi (her misafirin fiyati).
        cur.execute("""
            CREATE TABLE IF NOT EXISTS misafirler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rezervasyon_oda_id INTEGER NOT NULL,
                ad_soyad TEXT,
                tc_no TEXT,
                sira_no INTEGER DEFAULT 1,
                fiyat_tipi TEXT,
                gecelik_ucret INTEGER,
                FOREIGN KEY (rezervasyon_oda_id) REFERENCES rezervasyon_odalar(id)
            )
        """)

        # Her gece icin oda bazli ayri odeme kaydi (defterdeki + isareti mantigi)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS odemeler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rezervasyon_oda_id INTEGER NOT NULL,
                tarih TEXT NOT NULL,
                tutar INTEGER NOT NULL,
                odendi INTEGER DEFAULT 0,
                odeme_sekli TEXT,
                odeme_notu TEXT,
                FOREIGN KEY (rezervasyon_oda_id) REFERENCES rezervasyon_odalar(id)
            )
        """)

        # Resepsiyon calisanlari - hangi rezervasyonu kimin aldigini takip etmek icin
        cur.execute("""
            CREATE TABLE IF NOT EXISTS kullanicilar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kullanici_adi TEXT UNIQUE NOT NULL,
                sifre_hash TEXT NOT NULL,
                tuz TEXT NOT NULL,
                ad_soyad TEXT,
                aktif INTEGER DEFAULT 1,
                olusturma_tarihi TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Sistem ayarlari (fiyatlar vb.)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ayarlar (
                anahtar TEXT PRIMARY KEY,
                deger TEXT
            )
        """)
        cur.execute(
            "INSERT OR IGNORE INTO ayarlar (anahtar, deger) VALUES ('sabit_fiyat', ?), ('uye_fiyat', ?)",
            (str(FIYAT_SABIT), str(FIYAT_UYE)),
        )

        # Islem gecmisi (denetim izi): kim, ne zaman, ne yapti
        cur.execute("""
            CREATE TABLE IF NOT EXISTS islem_gecmisi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zaman TEXT DEFAULT CURRENT_TIMESTAMP,
                kullanici TEXT,
                tur TEXT,
                detay TEXT
            )
        """)

        # Eskiden olusturulmus (tek odali model) veritabani geri yüklenmişse
        # hizli bir sekilde fark edip net bir hata mesaji verelim ki bilinçsizce
        # yeni model uzerinde bozuk veri calismasin.
        _rez_kolonlari = [r[1] for r in cur.execute("PRAGMA table_info(rezervasyonlar)").fetchall()]
        if _rez_kolonlari and "oda_id" in _rez_kolonlari:
            raise RuntimeError(
                "Bu veritabani eski (tek odali) modele ait. Yeni model "
                "misafirhane.db olusturulmadan once mevcut dosya silinmelidir. "
                "Yedeginiz korunur; geri yuklemek isterseniz yedek dosyasini acmayin."
            )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def odalar_bos_mu():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as c FROM odalar")
        c = cur.fetchone()["c"]
        return c == 0
    finally:
        conn.close()


def varsayilan_odalari_yukle():
    """Misafirhanenin gerçek 18 odalık yapısı.
    eski_no: Defterdeki eski oda numarası, oda telefonuna ulaşmak için kullanılıyor
    (arama kodu = '1' + eski_no iki haneli, örn. eski no 14 -> 114 çevrilir).
    kapasite: oda tipine göre otomatik atanır (Tek=1, Double=2, Tek+Tek=3, Aile=4)."""
    # (kat_no, kat_adi, [(oda_no, oda_tipi, eski_no), ...])
    kat_yapisi = [
        (0, "Lobi", [(1, "Tek", 1), (2, "Double", 2)]),
        (1, "1.KAT", [(3, "Aile", 3), (4, "Tek+Tek", 5), (5, "Double", 6)]),
        (2, "2.KAT", [(6, "Aile", 7), (7, "Tek+Tek", 8), (8, "Double", 10)]),
        (3, "3.KAT", [(9, "Aile", 11), (10, "Tek+Tek", 13), (11, "Double", 14)]),
        (4, "4.KAT", [(12, "Aile", 15), (13, "Tek+Tek", 17), (14, "Double", 18)]),
        (5, "5.KAT", [(15, "Aile", 19), (16, "Tek+Tek", 21), (17, "Double", 22)]),
        (6, "6.KAT", [(18, "Aile", 24)]),
    ]
    conn = get_connection()
    try:
        cur = conn.cursor()
        for kat_no, kat_adi, odalar in kat_yapisi:
            for oda_no, oda_tipi, eski_no in odalar:
                kapasite = ODA_TIPI_KAPASITE.get(oda_tipi, 1)
                cur.execute(
                    "INSERT INTO odalar (eski_no, kat_no, kat_adi, oda_no, oda_tipi, kapasite) VALUES (?, ?, ?, ?, ?, ?)",
                    (eski_no, kat_no, kat_adi, oda_no, oda_tipi, kapasite),
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_ayar(anahtar, varsayilan=None):
    """Ayar degerini dondurur (yoksa varsayilan)."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT deger FROM ayarlar WHERE anahtar=?", (anahtar,)).fetchone()
        if row is None:
            return varsayilan
        return row["deger"]
    finally:
        conn.close()


def set_ayar(anahtar, deger):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO ayarlar (anahtar, deger) VALUES (?,?) "
            "ON CONFLICT(anahtar) DO UPDATE SET deger=excluded.deger",
            (anahtar, str(deger)),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def gecelik_fiyat(fiyat_tipi, ozel_ucret=None):
    """Fiyat tipinden kisi basi gecelik ucreti dondurur.
    Sabit/Uye fiyatlari ayarlar tablosundan okunur (admin panelinden
    degistirilebilir); 'Ozel' secildiyse rezervasyon sirasinda girilen
    ozel_ucret kullanilir."""
    if fiyat_tipi == "Uye":
        try:
            return int(get_ayar("uye_fiyat", str(FIYAT_UYE)))
        except (ValueError, TypeError):
            return FIYAT_UYE
    if fiyat_tipi == "Ozel":
        try:
            return int(ozel_ucret) if ozel_ucret else 0
        except (ValueError, TypeError):
            return 0
    try:
        return int(get_ayar("sabit_fiyat", str(FIYAT_SABIT)))
    except (ValueError, TypeError):
        return FIYAT_SABIT


# ---------------- YEDEKLEME ----------------

def yedek_klasoru():
    return os.path.join(VERI_KLASORU, "yedekler")


def yedek_al():
    """misafirhane.db dosyasinin zaman damgali bir kopyasini yedekler klasorune alir."""
    os.makedirs(yedek_klasoru(), exist_ok=True)
    ad = f"misafirhane_yedek_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    hedef = os.path.join(yedek_klasoru(), ad)
    shutil.copy2(DB_PATH, hedef)
    return hedef


def yedek_listele():
    """Yedek klasorundeki .db dosyalarini (yeni -> eski) liste olarak dondurur."""
    klasor = yedek_klasoru()
    if not os.path.isdir(klasor):
        return []
    dosyalar = [f for f in os.listdir(klasor) if f.endswith(".db")]
    dosyalar.sort(reverse=True)
    return dosyalar


def yedek_otomatik(adet=10):
    """Uygulama kapanisinda cagrilir.

    - Veritabani son yedekten bu yana degismediyse yeni yedek ALMAZ (gereksiz yigma onlenir).
    - Degistiyse zaman damgali bir kopya alir ve klasordeki yedek sayisini 'adet' ile sinirlar.
    - Hatalari sessizce yutar: yedekleme asla kapanmayi engellememeli.
    """
    try:
        if not os.path.exists(DB_PATH):
            return None
        mevcut = yedek_listele()
        if mevcut:
            en_yeni = os.path.join(yedek_klasoru(), mevcut[0])
            if os.path.getmtime(en_yeni) >= os.path.getmtime(DB_PATH):
                return None
        hedef = yedek_al()
        for eski in mevcut[adet:]:
            try:
                os.remove(os.path.join(yedek_klasoru(), eski))
            except OSError:
                pass
        return hedef
    except Exception:
        return None


def yedek_geri_yukle(dosya_adi):
    """Yedek klasorundeki bir dosyayi ana veritabani olarak geri yukler."""
    kaynak = os.path.join(yedek_klasoru(), dosya_adi)
    if not os.path.isfile(kaynak):
        raise FileNotFoundError("Seçilen yedek dosyası bulunamadı: " + dosya_adi)
    shutil.copy2(kaynak, DB_PATH)
    return DB_PATH


def telefon_kodu(eski_no):
    """Oda telefonunu aramak için resepsiyonda çevrilecek kod. Örn: eski no 14 -> '114'."""
    if eski_no is None or eski_no == "":
        return "-"
    try:
        return "1" + str(int(eski_no)).zfill(2)
    except (ValueError, TypeError):
        return "-"


# NOT: gecelik_fiyat artik ayarlar tablosundan okunur (yukarida).

if __name__ == "__main__":
    init_db()
    if odalar_bos_mu():
        varsayilan_odalari_yukle()
        print("Veritabani olusturuldu ve varsayilan odalar yuklendi.")
    else:
        print("Veritabani zaten mevcut.")