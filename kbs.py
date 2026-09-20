# -*- coding: utf-8 -*-
"""
KBS (Kimlik Bildirim Sistemi) modülü - izole test sürümü.

Bu dosya ana uygulamadan tamamen bağımsızdır:
- Veritabanını YALNIZCA okur (misafir / oda / rezervasyon bilgileri).
- "Gönderildi" takibi ayrı bir dosyada (kbs_takip.db) tutulur.
- Bildirim listesi Excel (.xlsx) olarak çıkarılır (openpyxl).
- Uygulama verisine ASLA yazmaz; silindiğinde sistemden iz kalmaz.

Yasal çerçeve (1774 sayılı Kimlik Bildirme Kanunu):
- Yerli misafir  : KBS yalnızca T.C. kimlik no + oda numarası ister
                   (kimlik bilgileri ulusal veri tabanından otomatik tamlanır).
- Yabancı misafir: belge no, ad-soyad, uyruk, doğum tarihi, cinsiyet,
                   doğum yeri gibi tam bilgi zorunludur.
- API entegrasyonlu tesisler günlük, manuel kullananlar aylık bildirim
  (takip eden ayın 10'una kadar) yapar; gecikme cezai risk doğurur.
"""

import os
import sqlite3
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

TAKIP_DOSYASI = "kbs_takip.db"


# --------------------------------------------------------------------------
# Yardımcılar
# --------------------------------------------------------------------------

def tc_dogrula(tc):
    """T.C. kimlik numarası sağlamasını doğrular (yalnızca biçim/algoritma)."""
    tc = (tc or "").strip()
    if not tc.isdigit() or len(tc) != 11 or tc[0] == "0":
        return False
    haneler = [int(h) for h in tc]
    tek = sum(haneler[0::2][:5])
    cift = sum(haneler[1:9:2])
    onuncu = (tek * 7 - cift) % 10
    onbirinci = (tek + cift + onuncu) % 10
    return onuncu == haneler[9] and onbirinci == haneler[10]


def tanitim_kodu_gecerli_mi(tc):
    """11 haneli sayı ise T.C. no; değil ise yabancı/muhtemel belge no.
    NOT: yalnızca numaranın BİÇİMİNE bakar. Türkiye'de yabancılara verilen
    Yabancı Kimlik Numarası (YKN) da 11 haneli rakamdır; bu yüzden bir misafirin
    gerçekten yabancı olup olmadığını kesin olarak ayırt etmek için misafir_tipi()
    tercih edilmelidir (check-in'de zaten toplanan uyruk/doğum yeri gibi KBS
    alanlarının varlığına bakar)."""
    value = (tc or "").strip()
    if value.isdigit() and len(value) == 11:
        return "yerli"
    if value:
        return "yabanci"
    return "eksik"


def _alan_degeri(satir, alan):
    """satir bir sqlite3.Row ya da dict olabilir; alan yoksa/boşsa '' döner."""
    try:
        deger = satir[alan]
    except (KeyError, IndexError, TypeError):
        return ""
    return (deger or "").strip() if isinstance(deger, str) else (deger or "")


def misafir_tipi(tc_no, satir=None):
    """Misafirin yerli/yabancı/eksik durumunu belirler.

    Öncelik, check-in'de toplanan KBS'ye özgü yabancı alanlarından (uyruk,
    doğum tarihi, cinsiyet, doğum yeri, belge türü) biri doluysa "yabanci"
    döner: bu, 11 haneli Yabancı Kimlik Numarası (YKN) taşıyan, bilgileri tam
    girilmiş bir yabancı misafirin yalnızca numara biçimine bakılarak yanlışlıkla
    "yerli" sayılmasını önler (bkz. tanitim_kodu_gecerli_mi notu).
    `satir` verilmezse (ör. henüz kaydedilmemiş, elle girilen bir numara) yalnızca
    numara biçiminden tahmin eder."""
    if satir is not None:
        for alan, _ in YABANCI_ALANLAR:
            if _alan_degeri(satir, alan):
                return "yabanci"
    return tanitim_kodu_gecerli_mi(tc_no)


def varsayilan_veri_yolu():
    apdata = os.path.join(
        os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"),
        "Misafirhane", "misafirhane.db")
    if os.path.exists(apdata):
        return apdata
    kendi = os.path.join(os.path.dirname(os.path.abspath(__file__)), "misafirhane.db")
    if os.path.exists(kendi):
        return kendi
    return apdata


def _baglan(db_yolu):
    conn = sqlite3.connect(db_yolu)
    conn.row_factory = sqlite3.Row
    return conn


def _takip_baglan(takip_yolu):
    conn = sqlite3.connect(takip_yolu)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bildirimler (
            kesit      TEXT PRIMARY KEY,
            tur        TEXT,
            durum      TEXT DEFAULT 'bekliyor',
            misafir_ad TEXT,
            tc_no      TEXT,
            oda        TEXT,
            tarih      TEXT,
            zaman      TEXT
        )
    """)
    return conn


# --------------------------------------------------------------------------
# Veri toplama
# --------------------------------------------------------------------------

YABANCI_ALANLAR = [
    ("uyruk", "UYRUK"), ("dogum_tarihi", "DOĞUM TARİHİ"), ("cinsiyet", "CİNSİYET"),
    ("dogum_yeri", "DOĞUM YERİ"), ("belge_turu", "BELGE TÜRÜ"),
]


def kbs_veri_topla(db_yolu=None):
    """Check-in yapılmış odalardaki tüm misafirleri oda bilgileriyle getirir.

    Dönüş: her biri misafir satırı olan sözlük listesi. Odaya misafir kaydı
    girilmemişse, rezervasyon üst bilgisinden tek sanal misafir üretilir.
    Yabancı misafir alanları (uyruk, doğum tarihi, ...) eski veritabanında
    yoksa boş döner (PRAGMA ile yoklama yapılır).
    """
    if db_yolu is None:
        db_yolu = varsayilan_veri_yolu()
    conn = _baglan(db_yolu)
    try:
        _misafir_kolonlari = [
            r[1] for r in conn.execute("PRAGMA table_info(misafirler)").fetchall()
        ]
        gercek_kolonlar = ", ".join(
            "m.%s AS %s" % (a, a) if a in _misafir_kolonlari else "NULL AS %s" % a
            for a, _ in YABANCI_ALANLAR
        )
        sanal_kolonlar = ", ".join("NULL AS %s" % a for a, _ in YABANCI_ALANLAR)

        # Eski veritabanlarında (1.0.4.2 ve öncesi) onceki_ro_id kolonu yoktu; PRAGMA
        # ile yoklanır, yoksa oda değiştirme zinciri yokmuş gibi davranılır (NULL/0).
        _ro_kolonlari = [
            r[1] for r in conn.execute("PRAGMA table_info(rezervasyon_odalar)").fetchall()
        ]
        if "onceki_ro_id" in _ro_kolonlari:
            onceki_ifade = "ro.onceki_ro_id"
            devam_ifade = "EXISTS (SELECT 1 FROM rezervasyon_odalar r2 WHERE r2.onceki_ro_id = ro.id)"
        else:
            onceki_ifade = "NULL"
            devam_ifade = "0"

        sorgu = """
            SELECT
                m.id AS misafir_id, m.rezervasyon_oda_id AS ro_id,
                m.ad_soyad AS misafir_ad, m.tc_no, m.sira_no,
                m.fiyat_tipi,
                ro.giris_tarihi, ro.gece_sayisi, ro.cikis_tarihi, ro.checkin_yapildi,
                %s AS onceki_ro_id, %s AS devam_var_mi,
                o.kat_adi, o.oda_no, o.oda_tipi,
                r.id AS rez_id, r.telefon, r.ad_soyad AS rez_ad, r.referans,
                %s
            FROM misafirler m
            JOIN rezervasyon_odalar ro ON ro.id = m.rezervasyon_oda_id
            JOIN odalar o ON o.id = ro.oda_id
            JOIN rezervasyonlar r ON r.id = ro.rezervasyon_id
            WHERE r.iptal = 0 AND ro.checkin_yapildi = 1
            UNION ALL
            SELECT
                0 AS misafir_id, ro.id AS ro_id,
                r.ad_soyad AS misafir_ad, r.tc_no, 1 AS sira_no,
                ro.fiyat_tipi,
                ro.giris_tarihi, ro.gece_sayisi, ro.cikis_tarihi, ro.checkin_yapildi,
                %s AS onceki_ro_id, %s AS devam_var_mi,
                o.kat_adi, o.oda_no, o.oda_tipi,
                r.id AS rez_id, r.telefon, r.ad_soyad AS rez_ad, r.referans,
                %s
            FROM rezervasyon_odalar ro
            JOIN odalar o ON o.id = ro.oda_id
            JOIN rezervasyonlar r ON r.id = ro.rezervasyon_id
            WHERE r.iptal = 0 AND ro.checkin_yapildi = 1
              AND NOT EXISTS (
                  SELECT 1 FROM misafirler m WHERE m.rezervasyon_oda_id = ro.id
              )
            ORDER BY giris_tarihi, kat_adi, oda_no, sira_no
        """ % (onceki_ifade, devam_ifade, gercek_kolonlar,
               onceki_ifade, devam_ifade, sanal_kolonlar)
        rows = conn.execute(sorgu).fetchall()
    finally:
        conn.close()

    sonuc = []
    for r in rows:
        yabanci_bilgi = {alan: (r[alan] or "").strip() for alan, _ in YABANCI_ALANLAR}
        tip = misafir_tipi(r["tc_no"], yabanci_bilgi)
        satir = {
            "misafir_id": r["misafir_id"],
            "ro_id": r["ro_id"],
            "misafir_ad": r["misafir_ad"],
            "tc_no": (r["tc_no"] or "").strip(),
            "sira_no": r["sira_no"],
            "telefon": (r["telefon"] or "").strip(),
            "oda": "%s Oda %d" % (r["kat_adi"], r["oda_no"]) if r["kat_adi"] else "Oda %d" % r["oda_no"],
            "giris_tarihi": r["giris_tarihi"],
            "cikis_tarihi": r["cikis_tarihi"],
            "checkin_yapildi": r["checkin_yapildi"],
            # Oda değiştirmede bölünen satırları birbirine bağlar (bkz. kbs_bekleyenler):
            "onceki_ro_id": r["onceki_ro_id"],
            "devam_var_mi": bool(r["devam_var_mi"]),
            "rez_id": r["rez_id"],
            "tip": tip,  # yerli / yabanci / eksik
            "referans": (r["referans"] or ""),
        }
        satir.update(yabanci_bilgi)
        sonuc.append(satir)
    return sonuc


def kbs_bekleyenler(db_yolu=None, takip_yolu=None):
    """Giriş/çıkış bildirimi henüz yapılmamış satırları döner.

    Dönüş: (giris_listesi, cikis_listesi). Her liste öğesi:
    {subject alanları..., tur, tarih, kesit, not}
    """
    if takip_yolu is None:
        takip_yolu = TAKIP_DOSYASI
    veriler = kbs_veri_topla(db_yolu)
    takip = _takip_baglan(takip_yolu)
    try:
        izlenenler = {
            row["kesit"] for row in takip.execute(
                "SELECT kesit FROM bildirimler WHERE durum IN ('gonderildi', 'atlandi')")
        }
    finally:
        takip.close()

    giris, cikis = [], []
    for v in veriler:
        # onceki_ro_id doluysa bu satır bir oda değiştirmeyle oluşan DEVAM satırıdır:
        # misafir zaten (eski satırdan) bildirilmiş sayılır, yeni bir "giriş" değildir.
        if v["checkin_yapildi"] and not v["onceki_ro_id"]:
            g = dict(v, tur="GİRİŞ", tarih=v["giris_tarihi"],
                     kesit="%s:%s:giris" % (v["ro_id"], v["misafir_id"]))
            g["not"] = _satir_notu(v)
            if g["kesit"] not in izlenenler:
                giris.append(g)
        # devam_var_mi True ise bu satırın cikis_tarihi'si gerçek bir otelden ayrılış
        # değil, oda değiştirme sırasında satırın kapatılmasından kaynaklanır.
        if v["cikis_tarihi"] and not v["devam_var_mi"]:
            c = dict(v, tur="ÇIKIŞ", tarih=v["cikis_tarihi"],
                     kesit="%s:%s:cikis" % (v["ro_id"], v["misafir_id"]))
            c["not"] = _satir_notu(v)
            if c["kesit"] not in izlenenler:
                cikis.append(c)
    return giris, cikis


def _satir_notu(v):
    if v["tip"] == "yerli":
        dogru = tc_dogrula(v["tc_no"])
        return "TC doğrulama: %s" % ("TAMAM" if dogru else "SAĞLAMA HATASI")
    if v["tip"] == "yabanci":
        eksikler = [etiket for alan, etiket in YABANCI_ALANLAR
                    if not (v.get(alan) or "").strip()]
        if eksikler:
            return "YABANCI — tam bilgi zorunlu (" + ", ".join(eksikler) + ")"
        return "YABANCI — bilgi tam"
    return "TC NO EKSİK — elle girilecek"


def kbs_durum_ozet(db_yolu=None, takip_yolu=None):
    """Yasal yükümlülük özeti: bekleyen / gönderilen / atlanan sayıları."""
    giris, cikis = kbs_bekleyenler(db_yolu, takip_yolu)
    takip = _takip_baglan(takip_yolu or TAKIP_DOSYASI)
    try:
        gonderilen = takip.execute(
            "SELECT COUNT(*) c FROM bildirimler WHERE durum='gonderildi'").fetchone()["c"]
        atlanan = takip.execute(
            "SELECT COUNT(*) c FROM bildirimler WHERE durum='atlandi'").fetchone()["c"]
    finally:
        takip.close()
    return {
        "giris_bekleyen": len(giris),
        "cikis_bekleyen": len(cikis),
        "toplam_bekleyen": len(giris) + len(cikis),
        "gonderilen": gonderilen,
        "atlanan": atlanan,
    }


# --------------------------------------------------------------------------
# Gönderildi / atlandı işaretleme
# --------------------------------------------------------------------------

def kbs_markala(kayitlar, durum="gonderildi", takip_yolu=None):
    """Verilen kayıtları 'gonderildi' ya da 'atlandi' olarak işaretler.

    kayitlar: kesit (str) listesi OLABİLİR (geriye uyumlu, sadece kesit yazılır)
    VEYA kbs_bekleyenler()'in döndürdüğü satır sözlüklerinin listesi olabilir —
    bu durumda tur/misafir_ad/tc_no/oda/tarih de denetim izine (BİLDİRİM GEÇMİŞİ)
    kaydedilir."""
    if takip_yolu is None:
        takip_yolu = TAKIP_DOSYASI
    takip = _takip_baglan(takip_yolu)
    try:
        zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for kayit in kayitlar:
            if isinstance(kayit, dict):
                kesit = kayit["kesit"]
                tur = kayit.get("tur")
                misafir_ad = kayit.get("misafir_ad")
                tc_no = kayit.get("tc_no")
                oda = kayit.get("oda")
                tarih = kayit.get("tarih")
            else:
                kesit = kayit
                tur = misafir_ad = tc_no = oda = tarih = None
            takip.execute(
                "INSERT OR IGNORE INTO bildirimler (kesit, durum) VALUES (?, ?)",
                (kesit, durum))
            takip.execute(
                "UPDATE bildirimler SET durum=?, tur=COALESCE(?, tur), "
                "misafir_ad=COALESCE(?, misafir_ad), tc_no=COALESCE(?, tc_no), "
                "oda=COALESCE(?, oda), tarih=COALESCE(?, tarih), zaman=? WHERE kesit=?",
                (durum, tur, misafir_ad, tc_no, oda, tarih, zaman, kesit))
        takip.commit()
    finally:
        takip.close()


# --------------------------------------------------------------------------
# Excel çıktısı
# --------------------------------------------------------------------------

def _baslik_satiri(ws, basliklar):
    ws.append(basliklar)
    for col in range(1, len(basliklar) + 1):
        hucre = ws.cell(row=1, column=col)
        hucre.font = Font(bold=True, color="FFFFFF")
        hucre.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        hucre.alignment = Alignment(horizontal="center")


def _genislik(ws, genislikler):
    for harf, g in genislikler:
        ws.column_dimensions[harf].width = g


_TEHLIKELI_ON_EK = ("=", "+", "-", "@", "\t", "\r")


def _guvenli_hucre(deger):
    """Excel/CSV formül enjeksiyonuna karşı: '=', '+', '-', '@' ile başlayan
    (misafir adı, TC/belge no, referans gibi elle girilen) hücre değerlerinin
    başına tek tırnak ekler ki Excel bunu formül olarak yorumlamasın."""
    if deger is None:
        return deger
    s = str(deger)
    if s.startswith(_TEHLIKELI_ON_EK):
        return "'" + s
    return s


def kbs_excel_ure(cikti_yolu, db_yolu=None, takip_yolu=None):
    """Bildirim listesini Excel dosyasına yazar. Kaç satır yazıldığını döner."""
    giris, cikis = kbs_bekleyenler(db_yolu, takip_yolu)

    wb = Workbook()

    ws = wb.active
    ws.title = "GİRİŞ BİLDİRİMLERİ"
    _baslik_satiri(ws, ["No", "T.C. Kimlik / Belge No", "Ad Soyad", "Telefon", "Kat / Oda",
                        "Giriş Tarihi", "Kişi Tipi", "Uyruk", "Doğum Tarihi", "Cinsiyet",
                        "Doğum Yeri", "Belge Türü", "Not"])
    for i, s in enumerate(giris, start=1):
        ws.append([i, _guvenli_hucre(s["tc_no"]), _guvenli_hucre(s["misafir_ad"]),
                   _guvenli_hucre(s["telefon"]), s["oda"], s["tarih"],
                   s["tip"].upper(), _guvenli_hucre(s["uyruk"]), _guvenli_hucre(s["dogum_tarihi"]),
                   _guvenli_hucre(s["cinsiyet"]), _guvenli_hucre(s["dogum_yeri"]),
                   _guvenli_hucre(s["belge_turu"]), s["not"]])
    _genislik(ws, [("A", 5), ("B", 20), ("C", 24), ("D", 14), ("E", 16), ("F", 12),
                   ("G", 10), ("H", 12), ("I", 12), ("J", 10), ("K", 12), ("L", 12), ("M", 34)])

    ws2 = wb.create_sheet("ÇIKIŞ BİLDİRİMLERİ")
    _baslik_satiri(ws2, ["No", "T.C. Kimlik / Belge No", "Ad Soyad", "Kat / Oda",
                         "Çıkış Tarihi", "Kişi Tipi", "Not"])
    for i, s in enumerate(cikis, start=1):
        ws2.append([i, _guvenli_hucre(s["tc_no"]), _guvenli_hucre(s["misafir_ad"]),
                    s["oda"], s["tarih"], s["tip"].upper(), s["not"]])
    _genislik(ws2, [("A", 5), ("B", 20), ("C", 24), ("D", 16), ("E", 12),
                    ("F", 10), ("G", 34)])

    ws3 = wb.create_sheet("ÖZET")
    ozet = kbs_durum_ozet(db_yolu, takip_yolu)
    _baslik_satiri(ws3, ["Alan", "Değer"])
    for anahtar, etiket in [
        ("giris_bekleyen", "Giriş bildirimi bekleyen"),
        ("cikis_bekleyen", "Çıkış bildirimi bekleyen"),
        ("toplam_bekleyen", "Toplam bekleyen"),
        ("gonderilen", "Toplam gönderilen"),
        ("atlanan", "Atlana/atla"),
    ]:
        ws3.append([etiket, ozet.get(anahtar, 0)])
    ws3.append(["Rapor zamanı", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    ws3.append(["Uyarı", "Yerli misafir için T.C. no + oda yeterlidir; yabancı için tam bilgi zorunludur."])
    _genislik(ws3, [("A", 34), ("B", 28)])

    ws4 = wb.create_sheet("BİLDİRİM GEÇMİŞİ")
    _baslik_satiri(ws4, ["Tür", "Ad Soyad", "T.C. Kimlik / Belge No", "Kat / Oda", "Tarih", "Durum", "Zaman"])
    takip = _takip_baglan(takip_yolu or TAKIP_DOSYASI)
    try:
        for row in takip.execute(
                "SELECT tur, misafir_ad, tc_no, oda, tarih, durum, zaman FROM bildirimler "
                "WHERE durum='gonderildi' ORDER BY zaman DESC"):
            ws4.append([
                row["tur"], _guvenli_hucre(row["misafir_ad"]), _guvenli_hucre(row["tc_no"]),
                row["oda"], row["tarih"], row["durum"], row["zaman"],
            ])
    finally:
        takip.close()
    _genislik(ws4, [("A", 8), ("B", 24), ("C", 20), ("D", 16), ("E", 12), ("F", 12), ("G", 20)])

    wb.save(cikti_yolu)
    return len(giris), len(cikis)


if __name__ == "__main__":
    yol = varsayilan_veri_yolu()
    print("Veritabanı:", yol)
    g, c = kbs_bekleyenler(yol)
    print("Giriş bekleyen:", len(g), "| Çıkış bekleyen:", len(c))
    for s in g[:5]:
        print("  [GİRİŞ]", s["tarih"], s["tc_no"], s["misafir_ad"], "|", s["oda"], "|", s["not"])