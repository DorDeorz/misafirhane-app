# -*- coding: utf-8 -*-
"""
İş mantığı / veri erişim katmanı.
GUI bu fonksiyonları çağırır; SQL burada saklı kalır.

ÇOK ODALI MODEL:
  rezervasyonlar      -> rezervasyon başına TEK satır (ad, telefon, referans, notlar, iptal)
  rezervasyon_odalar  -> rezervasyonun HER ODASI için bir satır (oda, giriş, gece, kişi,
                         fiyat tipi, gecelik ucret, checkin_yapildi, cikis_tarihi)
  misafirler          -> ODA bazlı (rezervasyon_oda_id) kalan kişilerin listesi
  odemeler            -> ODA bazlı (rezervasyon_oda_id) her gece için ayrı satır

Oda bazlı check-in/çıkış, oda bazlı tarih/oda değişikliği.
Grup = aynı rezervasyona birden fazla oda satırı eklemek demektir (tek satırda görünür).
"""

import re
from datetime import date, datetime, timedelta
from database import get_connection, gecelik_fiyat, ODA_TIPI_KAPASITE
import loglama


# ---------------- ODALAR ----------------

def _odanin_efektif_durumu(durum, ariza_bitis, bugun_str=None):
    """Depolanan durumdan gecerli (efektif) durumu hesaplar.
    Suresi dolmus arizalar 'temiz' sayilir. Donduren: 'temiz'/'temizlikte'/'arizali'."""
    if bugun_str is None:
        bugun_str = date.today().isoformat()
    if durum == "arizali" and ariza_bitis:
        if ariza_bitis <= bugun_str:  # ilk musait gun gelmis
            return "temiz"
    return durum or "temiz"


def oda_listesi():
    """Tum aktif odalar. Her satir dict olarak dondurulur ve 'aktif_durum'
    alani (temiz/temizlikte/arizali) eklenmis olur. Suresi dolmus arizalar
    otomatik temizlenir."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        bugun = date.today().isoformat()
        # suresi dolmus arizalari kalici olarak temizle
        cur.execute(
            "UPDATE odalar SET durum='temiz', ariza_bitis=NULL "
            "WHERE durum='arizali' AND ariza_bitis IS NOT NULL AND ariza_bitis <= ?",
            (bugun,),
        )
        conn.commit()
        rows = cur.execute(
            "SELECT * FROM odalar WHERE aktif=1 ORDER BY kat_no, oda_no"
        ).fetchall()
        sonuc = []
        for r in rows:
            d = dict(r)
            d["aktif_durum"] = _odanin_efektif_durumu(d.get("durum"), d.get("ariza_bitis"), bugun)
            sonuc.append(d)
        return sonuc
    finally:
        conn.close()


def _oda_durumu_sorgula(cur, oda_id):
    """Oda satirini dondurur; bulunamaz veya rezervasyona kapatilmis
    (temizlikte/arizali) ise ValueError firlatir."""
    oda = cur.execute("SELECT * FROM odalar WHERE id=? AND aktif=1", (oda_id,)).fetchone()
    if oda is None:
        raise ValueError("Oda bulunamadı veya pasif durumda.")
    bugun = date.today().isoformat()
    durum = _odanin_efektif_durumu(oda["durum"], oda["ariza_bitis"], bugun)
    if durum == "temizlikte":
        raise ValueError(f"Oda {oda['oda_no']} şu an 'Temizlikte' durumda, rezervasyon verilemez. Temiz yapılmadan oda verilmez.")
    if durum == "arizali":
        bitis = oda["ariza_bitis"] or "belirsiz"
        raise ValueError(f"Oda {oda['oda_no']} arızalı ({bitis} tarihine kadar kapalı), rezervasyon verilemez.")
    return oda


def _oda_no_cakisma_var_mi(cur, kat_no, oda_no, haric_id=None):
    q = "SELECT id FROM odalar WHERE aktif=1 AND kat_no=? AND oda_no=?"
    params = [kat_no, oda_no]
    if haric_id:
        q += " AND id != ?"
        params.append(haric_id)
    return cur.execute(q, params).fetchone() is not None


def oda_ekle(kat_no, kat_adi, oda_no, oda_tipi, eski_no=None, kapasite=None):
    if kapasite is None:
        kapasite = ODA_TIPI_KAPASITE.get(oda_tipi, 1)
    conn = get_connection()
    try:
        cur = conn.cursor()
        if _oda_no_cakisma_var_mi(cur, kat_no, oda_no):
            raise ValueError(f"Bu kat ve oda numarasında ({oda_no}) aktif bir oda zaten var.")
        cur.execute(
            "INSERT INTO odalar (eski_no, kat_no, kat_adi, oda_no, oda_tipi, kapasite) VALUES (?,?,?,?,?,?)",
            (eski_no, kat_no, kat_adi, oda_no, oda_tipi, kapasite),
        )
        conn.commit()
        loglama.islem_yaz("oda", f"Yeni oda eklendi: {kat_adi} - Oda {oda_no} ({oda_tipi}, {kapasite} kişi)")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def oda_sil(oda_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        oda = cur.execute("SELECT * FROM odalar WHERE id=?", (oda_id,)).fetchone()
        # aktif rezervasyon satiri olan oda silinemez
        aktif_rez = cur.execute(
            "SELECT COUNT(*) as c FROM rezervasyon_odalar ro "
            "JOIN rezervasyonlar r ON r.id = ro.rezervasyon_id "
            "WHERE ro.oda_id=? AND r.iptal=0 "
            "AND date(COALESCE(NULLIF(ro.cikis_tarihi, ''), "
            "              date(ro.giris_tarihi, '+' || ro.gece_sayisi || ' day'))) > date('now')",
            (oda_id,),
        ).fetchone()["c"]
        if aktif_rez:
            raise ValueError("Bu odada devam eden/ileri tarihli rezervasyon var, oda silinemez.")
        cur.execute("UPDATE odalar SET aktif=0 WHERE id=?", (oda_id,))
        conn.commit()
        if oda:
            loglama.islem_yaz("oda", f"Oda silindi: {oda['kat_adi']} - Oda {oda['oda_no']}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def oda_guncelle(oda_id, kat_no, kat_adi, oda_no, oda_tipi, eski_no, kapasite=None):
    if kapasite is None:
        kapasite = ODA_TIPI_KAPASITE.get(oda_tipi, 1)
    conn = get_connection()
    try:
        cur = conn.cursor()
        if _oda_no_cakisma_var_mi(cur, kat_no, oda_no, haric_id=oda_id):
            raise ValueError(f"Bu kat ve oda numarasında ({oda_no}) başka bir aktif oda var.")
        # kapasite dusurulurse, o odadaki aktif rezervasyon satirlarini asmamali
        max_kisi = cur.execute(
            "SELECT MAX(ro.kisi_sayisi) as m FROM rezervasyon_odalar ro "
            "JOIN rezervasyonlar r ON r.id = ro.rezervasyon_id "
            "WHERE ro.oda_id=? AND r.iptal=0 "
            "AND date(COALESCE(NULLIF(ro.cikis_tarihi, ''), "
            "              date(ro.giris_tarihi, '+' || ro.gece_sayisi || ' day'))) > date('now')",
            (oda_id,),
        ).fetchone()["m"]
        if max_kisi and kapasite < max_kisi:
            raise ValueError(
                f"Bu odadaki aktif rezervasyon en fazla {max_kisi} kişi; "
                f"kapasite {kapasite}'ye düşürülemez."
            )
        cur.execute("""
            UPDATE odalar SET kat_no=?, kat_adi=?, oda_no=?, oda_tipi=?, eski_no=?, kapasite=?
            WHERE id=?
        """, (kat_no, kat_adi, oda_no, oda_tipi, eski_no, kapasite, oda_id))
        conn.commit()
        loglama.islem_yaz("oda", f"Oda güncellendi: {kat_adi} - Oda {oda_no} ({oda_tipi}, {kapasite} kişi)")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def oda_durum_ayarla(oda_id, durum, ariza_gun=0):
    """Oda durumunu degistirir. durum: 'temiz'/'temizlikte'/'arizali'.
    'arizali' icin ariza_gun (kac gun kapali kalacagi) verilebilir;
    bitis tarihi = bugun + ariza_gun olur."""
    bugun = date.today().isoformat()
    conn = get_connection()
    try:
        cur = conn.cursor()
        oda = cur.execute("SELECT * FROM odalar WHERE id=? AND aktif=1", (oda_id,)).fetchone()
        if oda is None:
            raise ValueError("Oda bulunamadı.")

        # SImdi konaklayan misafir varsa durum degistirilemez
        odede_mi = cur.execute(
            "SELECT COUNT(*) as c FROM rezervasyon_odalar ro "
            "JOIN rezervasyonlar r ON r.id = ro.rezervasyon_id "
            "WHERE ro.oda_id=? AND r.iptal=0 AND ro.checkin_yapildi=1 AND ro.giris_tarihi <= ? "
            "AND date(COALESCE(NULLIF(ro.cikis_tarihi, ''), "
            "              date(ro.giris_tarihi, '+' || ro.gece_sayisi || ' day'))) > ?",
            (oda_id, bugun, bugun),
        ).fetchone()["c"]
        if odede_mi:
            raise ValueError(f"Oda {oda['oda_no']}'de şu an misafir kalıyor, durumu değiştirilemez.")

        if durum == "temizlikte":
            # bugun giris yapacak / yasiyor olabilecek rezervasyon satiri olan
            # odaya temizlikte denilemez
            cakisma = cur.execute(
                "SELECT r.ad_soyad FROM rezervasyon_odalar ro "
                "JOIN rezervasyonlar r ON r.id = ro.rezervasyon_id "
                "WHERE ro.oda_id=? AND r.iptal=0 AND ro.giris_tarihi <= ? "
                "AND date(COALESCE(NULLIF(ro.cikis_tarihi, ''), "
                "              date(ro.giris_tarihi, '+' || ro.gece_sayisi || ' day'))) > ?",
                (oda_id, bugun, bugun),
            ).fetchall()
            if cakisma:
                isimler = ", ".join(c["ad_soyad"] for c in cakisma)
                raise ValueError(f"Oda {oda['oda_no']} bugün için rezervasyonlu ({isimler}), temizlikte işaretlenemez.")
            cur.execute("UPDATE odalar SET durum='temizlikte', ariza_bitis=NULL WHERE id=?", (oda_id,))
            loglama.islem_yaz("oda_durum", f"Oda {oda['oda_no']} temizlikte işaretlendi.")
        elif durum == "arizali":
            gun = max(int(ariza_gun or 0), 0)
            if gun <= 0:
                gun = 1
            bitis = (datetime.strptime(bugun, "%Y-%m-%d").date() + timedelta(days=gun)).isoformat()
            # ariza araligina denk gelen aktif rezervasyon satiri varsa engelle
            cakisma = cur.execute(
                "SELECT r.ad_soyad FROM rezervasyon_odalar ro "
                "JOIN rezervasyonlar r ON r.id = ro.rezervasyon_id "
                "WHERE ro.oda_id=? AND r.iptal=0 AND date(ro.giris_tarihi) < date(?) "
                "AND date(COALESCE(NULLIF(ro.cikis_tarihi, ''), "
                "              date(ro.giris_tarihi, '+' || ro.gece_sayisi || ' day'))) > date(?)",
                (oda_id, bitis, bugun),
            ).fetchall()
            if cakisma:
                isimler = ", ".join(c["ad_soyad"] for c in cakisma)
                raise ValueError(
                    f"Oda {oda['oda_no']} arıza aralığında rezervasyonlu ({isimler}), arızalı işaretlenemez."
                )
            cur.execute("UPDATE odalar SET durum='arizali', ariza_bitis=? WHERE id=?", (bitis, oda_id))
            loglama.islem_yaz("oda_durum", f"Oda {oda['oda_no']} arızalı işaretlendi ({gun} gün, {bitis} tarihine kadar kapalı).")
        else:
            cur.execute("UPDATE odalar SET durum='temiz', ariza_bitis=NULL WHERE id=?", (oda_id,))
            loglama.islem_yaz("oda_durum", f"Oda {oda['oda_no']} temiz/Temizlik bitti işaretlendi.")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------- ORTAK YARDIMCILAR ----------------

def _tarih_araligi(giris_tarihi_str, gece_sayisi):
    baslangic = datetime.strptime(giris_tarihi_str, "%Y-%m-%d").date()
    return [baslangic + timedelta(days=i) for i in range(gece_sayisi)]


def cikis_tarihi_hesapla(giris_tarihi_str, gece_sayisi):
    baslangic = datetime.strptime(giris_tarihi_str, "%Y-%m-%d").date()
    return (baslangic + timedelta(days=gece_sayisi)).isoformat()


def _ro_efektif_cikis(ro):
    """Oda satirinin odadan ciktigi tarih: gercek cikis yapildiysa cikis_tarihi,
    yoksa giris + gece."""
    if "cikis_tarihi" in ro and ro["cikis_tarihi"]:
        return ro["cikis_tarihi"]
    return cikis_tarihi_hesapla(ro["giris_tarihi"], ro["gece_sayisi"])


def _oda_ozeti(odalar):
    """Kat adi - oda no dizisini insan okur metne cevirir: 'Lobi-1 + 1.KAT-3'."""
    return " + ".join(odalar) if odalar else "-"


def _musaitlik_sorgusu(cur, oda_id, giris_tarihi, gece_sayisi, haric_rez_id=None, haric_ro_id=None):
    """Ayni baglanti/cursor uzerinden cakisma kontrolu (ayri baglanti acmadan).
    rezervasyon_odalar uzerinden bakilir; iptal edilmis ve cikis yapilmis
    satirlar odada yer tutmaz. Cikis yapildigi gun yeni giris alinabilir."""
    q = """
        SELECT ro.id as ro_id, ro.rezervasyon_id, r.ad_soyad, ro.giris_tarihi, ro.gece_sayisi,
               o.oda_no, o.kat_adi
        FROM rezervasyon_odalar ro
        JOIN rezervasyonlar r ON ro.rezervasyon_id = r.id
        JOIN odalar o ON ro.oda_id = o.id
        WHERE ro.oda_id = ? AND r.iptal = 0
          AND date(ro.giris_tarihi) < date(?, '+' || ? || ' day')
          AND date(COALESCE(NULLIF(ro.cikis_tarihi, ''),
                            date(ro.giris_tarihi, '+' || ro.gece_sayisi || ' day'))) > date(?)
    """
    params = [oda_id, giris_tarihi, gece_sayisi, giris_tarihi]
    if haric_rez_id:
        q += " AND ro.rezervasyon_id != ?"
        params.append(haric_rez_id)
    if haric_ro_id:
        q += " AND ro.id != ?"
        params.append(haric_ro_id)
    return cur.execute(q, params).fetchall()


def musaitlik_kontrol(oda_id, giris_tarihi, gece_sayisi, haric_rez_id=None, haric_ro_id=None):
    """Seçilen oda, tarih aralığında dolu mu diye kontrol eder."""
    conn = get_connection()
    try:
        return _musaitlik_sorgusu(conn.cursor(), oda_id, giris_tarihi, gece_sayisi,
                                  haric_rez_id=haric_rez_id, haric_ro_id=haric_ro_id)
    finally:
        conn.close()


# ---------------- REZERVASYON (UST TABLO) ----------------

def rezervasyon_olustur(odalar, ad_soyad, tc_no="", telefon="", referans="", notlar="",
                        olusturan_kullanici=None, gecmis_kontrol=True):
    """ÇOK ODALI rezervasyon oluşturur.

    odalar: her biri bir oda satirini temsil eden dict (veya dict destekli) listesi:
        {oda_id, giris_tarihi, gece_sayisi, kisi_sayisi, fiyat_tipi, ozel_ucret}
    Tek elemanli liste tek odali rezervasyon demektir.

    GÜVENLİK: Kapasite, tarih çakışması, oda durumu (temizlikte/arızalı) ve geçmiş
    tarih burada da kontrol edilir (tek savunma hattı UI değil, DB katmanı da reddeder).

    Döner: rez_id"""
    if not odalar:
        raise ValueError("En az bir oda seçilmelidir.")
    bugun = date.today().isoformat()
    for r in odalar:
        if gecmis_kontrol and r["giris_tarihi"] < bugun:
            raise ValueError("Geçmiş tarihe rezervasyon alınamaz.")

    conn = get_connection()
    try:
        cur = conn.cursor()

        # 1) Ust tablo
        cur.execute("""
            INSERT INTO rezervasyonlar (ad_soyad, tc_no, telefon, referans, notlar, olusturan_kullanici)
            VALUES (?,?,?,?,?,?)
        """, (ad_soyad, tc_no, telefon, referans, notlar, olusturan_kullanici))
        rez_id = cur.lastrowid

        # 2) Her oda satiri + odemeler
        for r in odalar:
            oda = _oda_durumu_sorgula(cur, r["oda_id"])
            kapasite = oda["kapasite"] or 1
            if r["kisi_sayisi"] > kapasite:
                raise ValueError(f"Oda {oda['oda_no']} en fazla {kapasite} kişi alabilir, {r['kisi_sayisi']} kişi girildi.")

            cakisma = _musaitlik_sorgusu(cur, r["oda_id"], r["giris_tarihi"], r["gece_sayisi"])
            if cakisma:
                isimler = ", ".join(c["ad_soyad"] for c in cakisma)
                raise ValueError(f"Oda {oda['oda_no']} bu tarihlerde dolu: {isimler}.")

            ucret = gecelik_fiyat(r["fiyat_tipi"], r.get("ozel_ucret"))
            if r["fiyat_tipi"] == "Ozel" and ucret <= 0:
                raise ValueError("Özel fiyat için geçerli bir tutar girilmelidir.")

            cur.execute("""
                INSERT INTO rezervasyon_odalar
                (rezervasyon_id, oda_id, giris_tarihi, gece_sayisi, kisi_sayisi, fiyat_tipi, gecelik_ucret)
                VALUES (?,?,?,?,?,?,?)
            """, (rez_id, r["oda_id"], r["giris_tarihi"], r["gece_sayisi"],
                  r["kisi_sayisi"], r["fiyat_tipi"], ucret))
            ro_id = cur.lastrowid

            gecelik_toplam = ucret * r["kisi_sayisi"]
            for gun in _tarih_araligi(r["giris_tarihi"], r["gece_sayisi"]):
                cur.execute("""
                    INSERT INTO odemeler (rezervasyon_oda_id, tarih, tutar, odendi)
                    VALUES (?,?,?,0)
                """, (ro_id, gun.isoformat(), gecelik_toplam))

        conn.commit()
        odalar_metni = _oda_ozeti([
            f"{oda_getir_ozet_adi(r['oda_id'])}" for r in odalar
        ])
        loglama.islem_yaz(
            "rezervasyon_olustur",
            f"{ad_soyad} - {len(odalar)} oda ({odalar_metni}) rezervasyonu oluşturuldu.",
            kullanici=olusturan_kullanici,
        )
        return rez_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def oda_getir_ozet_adi(oda_id):
    """Tek oda icin 'Kat - Oda X' etiketi (loglama/ozet icin)."""
    conn = get_connection()
    try:
        o = conn.execute("SELECT kat_adi, oda_no FROM odalar WHERE id=?", (oda_id,)).fetchone()
        return f"{o['kat_adi']} - Oda {o['oda_no']}" if o else f"Oda ID {oda_id}"
    finally:
        conn.close()


def rezervasyon_getir(rez_id):
    """Rezervasyon (ust) satirini dondurur. Iptal durumu dahil tüm üst alanlar."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM rezervasyonlar WHERE id=?", (rez_id,)
        ).fetchone()
        return row
    finally:
        conn.close()


def rezervasyon_guncelle(rez_id, ad_soyad, tc_no, telefon, referans, notlar):
    """Üst tablodaki iletişim bilgilerini günceller (oda satirlari etkilenmez)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        row = cur.execute("SELECT id FROM rezervasyonlar WHERE id=?", (rez_id,)).fetchone()
        if not row:
            raise ValueError("Rezervasyon bulunamadı.")
        cur.execute("""
            UPDATE rezervasyonlar
            SET ad_soyad=?, tc_no=?, telefon=?, referans=?, notlar=?
            WHERE id=?
        """, (ad_soyad, tc_no, telefon, referans, notlar, rez_id))
        conn.commit()
        loglama.islem_yaz("rezervasyon_guncelle", f"Rezervasyon #{rez_id} bilgileri güncellendi: {ad_soyad}.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def rezervasyon_iptal(rez_id):
    """Müşteri tarafından iptal edilen rezervasyonu işaretler (tüm odalarıyla).

    GÜVENLİK: içeride hâlâ check-in yapılmış (fiilen konaklayan) bir oda varsa
    iptal reddedilir. Aksi halde iptal edilen rezervasyonun odaları
    _musaitlik_sorgusu/gunun_oda_durumu gibi tüm sorgularda 'iptal=0' filtresi
    yüzünden BOŞ görünür ve fiziksel olarak dolu bir oda ikinci kez satılabilir."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        rez = cur.execute("SELECT * FROM rezervasyonlar WHERE id=?", (rez_id,)).fetchone()
        if not rez:
            return
        icerde = cur.execute(
            "SELECT COUNT(*) as c FROM rezervasyon_odalar "
            "WHERE rezervasyon_id=? AND checkin_yapildi=1 AND cikis_tarihi IS NULL",
            (rez_id,),
        ).fetchone()["c"]
        if icerde:
            raise ValueError(
                "Bu rezervasyonda hâlâ check-in yapılmış ve çıkışı yapılmamış misafir var; "
                "iptal edilemez. Önce misafiri çıkış yaptır, sonra iptal et."
            )
        cur.execute("UPDATE rezervasyonlar SET iptal=1 WHERE id=?", (rez_id,))
        conn.commit()
        loglama.islem_yaz("rezervasyon_iptal", f"{rez['ad_soyad']} rezervasyonu (#{rez_id}) iptal edildi.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def rezervasyon_iptal_geri_al(rez_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        rez = cur.execute("SELECT * FROM rezervasyonlar WHERE id=?", (rez_id,)).fetchone()
        if rez:
            cur.execute("UPDATE rezervasyonlar SET iptal=0 WHERE id=?", (rez_id,))
            conn.commit()
            loglama.islem_yaz("rezervasyon_iptal", f"{rez['ad_soyad']} rezervasyonunun (#{rez_id}) iptali geri alındı.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------- REZERVASYON ODALARI (ALBERIM) ----------------

def rezervasyon_odalar_listele(rez_id):
    """Bir rezervasyonun tüm oda satirlarini oda ve üst rezervasyon bilgileriyle döndürür."""
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT ro.*, o.oda_no, o.kat_adi, o.oda_tipi, o.kapasite, o.eski_no,
                   r.id as rez_id, r.ad_soyad, r.telefon, r.tc_no, r.referans,
                   r.notlar, r.iptal, r.olusturan_kullanici
            FROM rezervasyon_odalar ro
            JOIN odalar o ON ro.oda_id = o.id
            JOIN rezervasyonlar r ON r.id = ro.rezervasyon_id
            WHERE ro.rezervasyon_id = ?
            ORDER BY o.kat_no, o.oda_no
        """, (rez_id,)).fetchall()
        return rows
    finally:
        conn.close()


def rezervasyon_odasi_getir(ro_id):
    """Tek oda satiri + oda ve üst rezervasyon bilgileri."""
    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT ro.*, o.oda_no, o.kat_adi, o.oda_tipi, o.kapasite, o.eski_no,
                   r.ad_soyad, r.tc_no, r.telefon, r.referans, r.notlar, r.iptal,
                   r.olusturan_kullanici, r.olusturma_tarihi, r.id as rez_id
            FROM rezervasyon_odalar ro
            JOIN odalar o ON ro.oda_id = o.id
            JOIN rezervasyonlar r ON ro.rezervasyon_id = r.id
            WHERE ro.id = ?
        """, (ro_id,)).fetchone()
        return row
    finally:
        conn.close()


def rezervasyon_listesi(durum="aktif"):
    """durum: 'aktif', 'iptal', 'gecmis' veya 'hepsi'.
    ANA SAYFA ICIN: her rezervasyon TEK SATIR olarak, odalari ozetlenmis halde.
    'gecmis' = iptal edilmemiş ve tüm odaları çıkış yapmış (eski misafirler)."""
    conn = get_connection()
    try:
        q = """
            SELECT r.id, r.ad_soyad, r.tc_no, r.telefon, r.referans, r.notlar,
                   r.olusturan_kullanici, r.iptal,
                   substr(r.olusturma_tarihi, 1, 16) as olusturma_tarihi,
                   COUNT(ro.id) as oda_sayisi,
                   COALESCE(SUM(ro.kisi_sayisi), 0) as toplam_kisi,
                   COALESCE(SUM(ro.gece_sayisi), 0) as toplam_gece,
                   MIN(ro.giris_tarihi) as giris_tarihi,
                   MAX(COALESCE(NULLIF(ro.cikis_tarihi, ''),
                                date(ro.giris_tarihi, '+' || ro.gece_sayisi || ' day'))) as cikis_tarihi,
                   GROUP_CONCAT(o.kat_adi || '-' || o.oda_no, ' + ') as oda_ozeti,
                   SUM(CASE WHEN ro.checkin_yapildi=1 THEN 1 ELSE 0 END) as checkin_odasi,
                   SUM(CASE WHEN ro.checkin_yapildi=0 AND ro.giris_tarihi < date('now') THEN 1 ELSE 0 END) as gelmedi_odasi,
                   SUM(CASE WHEN ro.cikis_tarihi IS NULL OR ro.cikis_tarihi='' THEN 1 ELSE 0 END) as acik_odasi,
                   SUM(CASE WHEN ro.gece_sayisi = 0 THEN 1 ELSE 0 END) as sifir_gece
            FROM rezervasyonlar r
            LEFT JOIN rezervasyon_odalar ro ON ro.rezervasyon_id = r.id
            LEFT JOIN odalar o ON o.id = ro.oda_id
        """
        if durum == "aktif":
            q += " WHERE r.iptal = 0"
        elif durum == "iptal":
            q += " WHERE r.iptal = 1"
        elif durum == "gecmis":
            q += " WHERE r.iptal = 0"
        q += " GROUP BY r.id"
        if durum == "gecmis":
            q += " HAVING acik_odasi = 0 AND oda_sayisi > 0"
        q += " ORDER BY giris_tarihi DESC"
        rows = conn.execute(q).fetchall()
        sonuc = []
        bugun = date.today().isoformat()
        for r in rows:
            d = dict(r)
            d["oda_ozeti"] = _oda_ozeti([x.strip() for x in (r["oda_ozeti"] or "").split("+")])
            d["durum_etiket"] = rezervasyon_durum_etiketi(d, bugun)
            sonuc.append(d)
        return sonuc
    finally:
        conn.close()


def rezervasyon_durum_etiketi(d, bugun_str=None):
    """Rezervasyon satirinin durum etiketini hesaplar (inceleme için):
    iptal / no-show (tüm odalar gelmedi) / kısmen gelmedi / bekleniyor / aktif."""
    if bugun_str is None:
        bugun_str = date.today().isoformat()
    if d["iptal"]:
        return "İptal Edildi"
    oda_sayisi = d["oda_sayisi"] or 0
    if oda_sayisi == 0:
        return "Odasız"
    checkin = d["checkin_odasi"] or 0
    gelmedi = d["gelmedi_odasi"] or 0
    if checkin == oda_sayisi:
        return "Check-in Oldu"
    if checkin > 0:
        return f"Kısmen ({checkin}/{oda_sayisi})"
    # hicbir oda check-in degil
    if gelmedi == oda_sayisi:
        return "Gelmedi (No-Show)"
    if d["giris_tarihi"] and d["giris_tarihi"] <= bugun_str:
        return "Bekleniyor"
    return "İleri Tarih"


def tum_rezervasyonlar():
    """Geriye uyumluluk için: sadece aktif rezervasyonlar."""
    return rezervasyon_listesi("aktif")


def rezervasyon_toplami(rez_id):
    """Rezervasyonun tüm odalarının, tüm gecelerin toplam tutarı."""
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT ro.*, o.oda_no, o.kat_adi
            FROM rezervasyon_odalar ro JOIN odalar o ON o.id = ro.oda_id
            WHERE ro.rezervasyon_id = ?
        """, (rez_id,)).fetchall()
        toplam = 0
        for ro in rows:
            toplam += odasi_gecelik_toplami(ro) * (ro["gece_sayisi"] or 1)
        return toplam
    finally:
        conn.close()


def rezervasyonlari_toplam_ozeti(rez_ids):
    """Birden çok rezervasyon için TEK sorguda fiyat tipi kümeleri ve toplam tutarlar.
    Döndürür: {rez_id: {'fiyat_tipleri': {..}, 'toplam': int}}"""
    if not rez_ids:
        return {}
    conn = get_connection()
    try:
        yer = ",".join("?" * len(rez_ids))
        rows = conn.execute(f"""
            SELECT ro.rezervasyon_id as rez_id, ro.gece_sayisi,
                   ro.fiyat_tipi, ro.gecelik_ucret, ro.kisi_sayisi,
                   COALESCE((SELECT SUM(m.gecelik_ucret) FROM misafirler m
                             WHERE m.rezervasyon_oda_id = ro.id
                               AND m.gecelik_ucret IS NOT NULL), 0) as misafir_toplam
            FROM rezervasyon_odalar ro
            WHERE ro.rezervasyon_id IN ({yer})
        """, tuple(rez_ids)).fetchall()
        sonuc = {}
        for ro in rows:
            kayit = sonuc.setdefault(ro["rez_id"], {"fiyat_tipleri": set(), "toplam": 0})
            if ro["fiyat_tipi"]:
                kayit["fiyat_tipleri"].add(ro["fiyat_tipi"])
            tek_gece = ro["misafir_toplam"] or ((ro["gecelik_ucret"] or 0) * (ro["kisi_sayisi"] or 1))
            kayit["toplam"] += tek_gece * (ro["gece_sayisi"] or 1)
        return sonuc
    finally:
        conn.close()


# ---------------- ODA SATIRI: KİŞİ / FİYAT / ÖDEME ----------------

def oda_liman(kapasite, ekstra_yatak=False):
    """Bir odanin kabul edebilecegi maksimum kisi sayisi (kapasite + 2 sabit taban,
    en az 3; ekstra yatak secildiyse +1). Check-in ve oda degistirmede ayni kural
    kullanilir ki farkli yerlerde tutarsiz kapasite kontrolu olmasin."""
    return max((kapasite or 1) + 2, 3) + (1 if ekstra_yatak else 0)


def odasi_misafirler_listele(ro_id):
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM misafirler WHERE rezervasyon_oda_id=? ORDER BY sira_no, id", (ro_id,)
        ).fetchall()
        return rows
    finally:
        conn.close()


def rezervasyonlar_yabanci_sayilari(rez_ids):
    """Verilen rezervasyonların her birinde kaç YABANCI misafir kaydı olduğunu döner.
    Yabancı = TC No alanında 11 haneli rakam olmayan kayıt (pasaport/belge no)."""
    if not rez_ids:
        return {}
    conn = get_connection()
    try:
        yer = ",".join("?" * len(rez_ids))
        rows = conn.execute(
            "SELECT ro.rezervasyon_id AS rez_id, COUNT(*) AS n "
            "FROM misafirler m JOIN rezervasyon_odalar ro ON ro.id = m.rezervasyon_oda_id "
            f"WHERE ro.rezervasyon_id IN ({yer}) "
            "AND m.tc_no IS NOT NULL AND TRIM(m.tc_no) <> '' "
            "AND (LENGTH(m.tc_no) <> 11 OR m.tc_no NOT GLOB '*[0-9]*') "
            "GROUP BY ro.rezervasyon_id",
            list(rez_ids),
        ).fetchall()
        return {r["rez_id"]: r["n"] for r in rows}
    finally:
        conn.close()


def _misafirleri_kaydet_cur(cur, ro_id, misafir_listesi, ekstra_yatak=False):
    """odasi_misafirleri_kaydet'in cursor alan iç sürümü: çağıranın kendi
    transaction'ı içinde çalışır (bkz. odasi_misafirleri_kaydet ve
    odasi_misafirleri_kaydet_ve_checkin)."""
    ro = cur.execute(
        "SELECT ro.*, o.kapasite FROM rezervasyon_odalar ro "
        "JOIN odalar o ON o.id = ro.oda_id WHERE ro.id=?", (ro_id,)
    ).fetchone()
    if not ro:
        raise ValueError("Oda satırı bulunamadı.")
    liman = oda_liman(ro["kapasite"], ekstra_yatak)
    if len(misafir_listesi) > liman:
        raise ValueError(
            f"Bu oda için en fazla {liman} kişi kaydedilebilir"
            f"{' (ekstra yatak dahil)' if ekstra_yatak else ''}, {len(misafir_listesi)} girildi."
        )
    cur.execute("DELETE FROM misafirler WHERE rezervasyon_oda_id=?", (ro_id,))
    for i, satir in enumerate(misafir_listesi, start=1):
        if isinstance(satir, dict):
            ad_soyad = (satir.get("ad_soyad") or "").strip()
            if not ad_soyad:
                raise ValueError("Misafir adı boş olamaz.")
            tc_no = (satir.get("tc_no") or "").strip()
            fiyat_tipi = satir.get("fiyat_tipi")
            ucret = satir.get("gecelik_ucret")
            cur.execute(
                "INSERT INTO misafirler (rezervasyon_oda_id, ad_soyad, tc_no, sira_no, "
                "fiyat_tipi, gecelik_ucret, uyruk, dogum_tarihi, cinsiyet, dogum_yeri, belge_turu) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (ro_id, ad_soyad, tc_no, i, fiyat_tipi, ucret,
                 (satir.get("uyruk") or "").strip(),
                 (satir.get("dogum_tarihi") or "").strip(),
                 (satir.get("cinsiyet") or "").strip(),
                 (satir.get("dogum_yeri") or "").strip(),
                 (satir.get("belge_turu") or "").strip())
            )
        else:
            ad_soyad = satir[0].strip()
            if not ad_soyad:
                raise ValueError("Misafir adı boş olamaz.")
            tc_no = satir[1] if len(satir) > 1 else ""
            fiyat_tipi = satir[2] if len(satir) > 2 else None
            ucret = satir[3] if len(satir) > 3 else None
            cur.execute(
                "INSERT INTO misafirler (rezervasyon_oda_id, ad_soyad, tc_no, sira_no, fiyat_tipi, gecelik_ucret) "
                "VALUES (?,?,?,?,?,?)",
                (ro_id, ad_soyad, tc_no, i, fiyat_tipi, ucret)
            )
    yeni_kisi = max(len(misafir_listesi), 1)
    cur.execute("UPDATE rezervasyon_odalar SET kisi_sayisi=? WHERE id=?", (yeni_kisi, ro_id))


def odasi_misafirleri_kaydet(ro_id, misafir_listesi, ekstra_yatak=False):
    """misafir_listesi: [(ad_soyad, tc_no), ...]
    veya 4 elemanli gelsede kişi başı fiyat bilgisi de saklanır:
        [(ad_soyad, tc_no, fiyat_tipi, gecelik_ucret), ...]
    Ya da her öğe sözlük olabilir (check-in penceresi yabancı bilgilerini de
    böyle aktarır):
        {ad_soyad, tc_no, fiyat_tipi, gecelik_ucret, uyruk, dogum_tarihi,
         cinsiyet, dogum_yeri, belge_turu}
    Mevcut listeyi tamamen değiştirir, oda satirinin kisi_sayisi'nini senkronlar
    ve henüz ödenmemiş gecelerin tutarini yeniden hesaplar."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        _misafirleri_kaydet_cur(cur, ro_id, misafir_listesi, ekstra_yatak)
        _odeme_tutarlarini_yeniden_hesapla(cur, ro_id)
        conn.commit()
        loglama.islem_yaz("misafir", f"Oda satırı #{ro_id} misafirleri kaydedildi ({len(misafir_listesi)} kişi).")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def odasi_misafirleri_kaydet_ve_checkin(ro_id, misafir_listesi, ekstra_yatak=False):
    """odasi_misafirleri_kaydet + odasi_checkin_yap TEK transaction'da: aradaki bir
    kesintide 'misafirler kaydedildi ama checkin_yapildi hâlâ 0' gibi tutarsız
    bir ara durumda kalınmaz (önceden CheckinDialog.kaydet() bu ikisini ayrı ayrı
    çağırıyordu)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        _misafirleri_kaydet_cur(cur, ro_id, misafir_listesi, ekstra_yatak)
        cur.execute("UPDATE rezervasyon_odalar SET checkin_yapildi=1 WHERE id=?", (ro_id,))
        _odeme_tutarlarini_yeniden_hesapla(cur, ro_id)
        ro = cur.execute(
            "SELECT o.oda_no, o.kat_adi FROM rezervasyon_odalar ro "
            "JOIN odalar o ON o.id = ro.oda_id WHERE ro.id=?", (ro_id,)
        ).fetchone()
        conn.commit()
        loglama.islem_yaz(
            "checkin",
            f"{ro['kat_adi']} Oda {ro['oda_no']} (satır #{ro_id}) check-in yapıldı ({len(misafir_listesi)} kişi)."
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def odasi_gecelik_toplami(ro_row):
    """Bir oda satirinin SİNGLE GECELİK toplamını verir: kayıtlı kişilerin bireysel
    fiyatları varsa onların toplamı, yoksa (kisi_sayisi * gecelik_ucret)."""
    ro_id = ro_row["id"]
    conn = get_connection()
    try:
        misafirler = conn.execute(
            "SELECT gecelik_ucret FROM misafirler WHERE rezervasyon_oda_id=? ORDER BY sira_no, id",
            (ro_id,),
        ).fetchall()
        ucretler = [m["gecelik_ucret"] for m in misafirler if m["gecelik_ucret"]]
        if ucretler:
            return sum(ucretler)
    finally:
        conn.close()
    return (ro_row["gecelik_ucret"] or 0) * (ro_row["kisi_sayisi"] or 1)


def _odeme_tutarlarini_yeniden_hesapla(cur, ro_id):
    """odasi_odeme_tutarlari_guncelle'nin cursor alan iç sürümü: çağıran fonksiyonun
    KENDİ transaction'ı içinde çalışır. Böylece misafir/kişi sayısı güncellemesiyle
    ödeme tutarı yeniden hesaplaması aynı commit ile birlikte gerçekleşir; aradaki
    çökme/kesinti durumunda tutarsız (eski tutar + yeni misafir listesi) bir ara
    durumda kalınmaz."""
    ro = cur.execute(
        "SELECT kisi_sayisi, gecelik_ucret FROM rezervasyon_odalar WHERE id=?", (ro_id,)
    ).fetchone()
    if not ro:
        return
    misafirler = cur.execute(
        "SELECT gecelik_ucret FROM misafirler WHERE rezervasyon_oda_id=? ORDER BY sira_no, id",
        (ro_id,),
    ).fetchall()
    gercek_sayilar = [m["gecelik_ucret"] for m in misafirler if m["gecelik_ucret"]]
    if gercek_sayilar:
        gecelik_toplam = sum(gercek_sayilar)
    else:
        gecelik_toplam = (ro["gecelik_ucret"] or 0) * (ro["kisi_sayisi"] or 1)
    cur.execute(
        "UPDATE odemeler SET tutar=? WHERE rezervasyon_oda_id=? AND odendi=0",
        (gecelik_toplam, ro_id),
    )


def odasi_odeme_tutarlari_guncelle(ro_id):
    """Kişi bazlı fiyatları topluca HENÜZ ÖDENMEMİŞ gecelere işler."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        _odeme_tutarlarini_yeniden_hesapla(cur, ro_id)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def odasi_odemeler(ro_id):
    """Oda satirinin gece gece ödeme listesi (tarih sirali)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM odemeler WHERE rezervasyon_oda_id=? ORDER BY tarih", (ro_id,)
        ).fetchall()
        return rows
    finally:
        conn.close()


def odeme_guncelle(odeme_id, odendi, odeme_sekli=None, odeme_notu=None):
    conn = get_connection()
    try:
        cur = conn.cursor()
        o = cur.execute(
            "SELECT od.*, o2.oda_no, o2.kat_adi FROM odemeler od "
            "JOIN rezervasyon_odalar ro ON od.rezervasyon_oda_id = ro.id "
            "JOIN odalar o2 ON ro.oda_id = o2.id WHERE od.id=?",
            (odeme_id,),
        ).fetchone()
        cur.execute("""
            UPDATE odemeler SET odendi=?, odeme_sekli=?, odeme_notu=? WHERE id=?
        """, (1 if odendi else 0, odeme_sekli, odeme_notu, odeme_id))
        conn.commit()
        if o:
            durum = "ödendi" if odendi else "ödendi değil"
            loglama.islem_yaz("odeme", f"{o['kat_adi']} Oda {o['oda_no']}, {o['tarih']} gecesi {o['tutar']} TL: {durum}. Sekli: {odeme_sekli or 'Yok'}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------- CHECK-IN / ÇIKIS (ODA BAZLI) ----------------

def odasi_checkin_yap(ro_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        ro = cur.execute(
            "SELECT ro.*, o.oda_no, o.kat_adi FROM rezervasyon_odalar ro "
            "JOIN odalar o ON ro.oda_id=o.id WHERE ro.id=?",
            (ro_id,),
        ).fetchone()
        if not ro:
            raise ValueError("Oda satırı bulunamadı.")
        cur.execute("UPDATE rezervasyon_odalar SET checkin_yapildi=1 WHERE id=?", (ro_id,))
        conn.commit()
        loglama.islem_yaz("checkin", f"Oda {ro['kat_adi']} Oda {ro['oda_no']} (satır #{ro_id}) check-in yapıldı.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def odasi_checkin_geri_al(ro_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        ro = cur.execute(
            "SELECT ro.*, o.oda_no, o.kat_adi FROM rezervasyon_odalar ro "
            "JOIN odalar o ON ro.oda_id=o.id WHERE ro.id=?",
            (ro_id,),
        ).fetchone()
        if not ro:
            raise ValueError("Oda satırı bulunamadı.")
        cur.execute("UPDATE rezervasyon_odalar SET checkin_yapildi=0 WHERE id=?", (ro_id,))
        conn.commit()
        loglama.islem_yaz("checkin", f"Oda {ro['kat_adi']} Oda {ro['oda_no']} (satır #{ro_id}) check-in iptal edildi.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def odasi_cikis_yap(ro_id, cikis_tarihi_str=None):
    """Oda bazlı check-out: satirin cikis_tarihi'ni isaretler, odanin durumunu
    'temizlikte' yapar (housekeeping temizleyene kadar tekrar rezervasyona
    açılmaz — bkz. database.py ODA_DURUMLARI). Diger odalari etkilemez (cok
    odali rezervasyonun tek odasi cikis yapabilir).

    ERKEN ÇIKIŞ: cikis_tarihi_str, satırın planlanan bitişinden ÖNCEyse, artık
    gerçekleşmeyecek gelecek gecelerin HENÜZ ÖDENMEMİŞ kayıtları silinir (aksi
    halde İstatistik'teki 'beklenen gelir' hiç kalınmayacak geceleri de sayardı).
    Önceden ÖDENMİŞ ama artık kapsam dışı kalan geceler silinmez (para zaten
    alınmış); bu tür geceler döndürülür ki arayüz kullanıcıyı bilgilendirsin."""
    tarih = cikis_tarihi_str or date.today().isoformat()
    conn = get_connection()
    try:
        cur = conn.cursor()
        ro = cur.execute(
            "SELECT ro.*, o.oda_no, o.kat_adi, o.durum FROM rezervasyon_odalar ro "
            "JOIN odalar o ON ro.oda_id=o.id WHERE ro.id=? AND ro.rezervasyon_id IN "
            "(SELECT id FROM rezervasyonlar WHERE iptal=0)",
            (ro_id,),
        ).fetchone()
        if not ro:
            raise ValueError("Çıkış yapılacak oda satırı bulunamadı.")
        if not ro["checkin_yapildi"]:
            raise ValueError("Bu oda check-in yapılmamış, çıkış işlemi uygulanamaz.")
        cur.execute(
            "UPDATE rezervasyon_odalar SET cikis_tarihi=? WHERE id=?",
            (tarih, ro_id),
        )
        cur.execute(
            "UPDATE odalar SET durum='temizlikte', ariza_bitis=NULL WHERE id=?",
            (ro["oda_id"],),
        )
        cur.execute(
            "DELETE FROM odemeler WHERE rezervasyon_oda_id=? AND tarih>=? AND odendi=0",
            (ro_id, tarih),
        )
        dusen_odenmis = cur.execute(
            "SELECT tarih FROM odemeler WHERE rezervasyon_oda_id=? AND tarih>=? AND odendi=1 ORDER BY tarih",
            (ro_id, tarih),
        ).fetchall()
        conn.commit()
        loglama.islem_yaz(
            "cikis",
            f"Oda {ro['kat_adi']} Oda {ro['oda_no']} (satır #{ro_id}) çıkış yaptı ({tarih}). "
            "Oda temizlikte olarak işaretlendi.",
        )
        return [o["tarih"] for o in dusen_odenmis]
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def odasi_odenmemis_tutar(ro_id, kesim_tarihi=None):
    """Bir oda satırının, kesim_tarihi'nden ÖNCEki (gerçekten kalınan) gecelerinden
    HENÜZ ÖDENMEMİŞ olanların toplam tutarı — çıkış yaparken 'borç var mı' göstermek
    için. kesim_tarihi verilmezse tüm ödenmemiş geceler sayılır."""
    conn = get_connection()
    try:
        q = "SELECT COALESCE(SUM(tutar), 0) as borc FROM odemeler WHERE rezervasyon_oda_id=? AND odendi=0"
        params = [ro_id]
        if kesim_tarihi:
            q += " AND tarih < ?"
            params.append(kesim_tarihi)
        return conn.execute(q, params).fetchone()["borc"]
    finally:
        conn.close()


def erken_cikis_adaylari(tarih_str=None):
    """Şu an fiilen konaklayan (check-in yapılmış, henüz çıkışı yapılmamış) ama
    planlanan çıkış günü tarih_str OLMAYAN oda satırları — yani 'bugün_cikacaklar'
    listesinde zaten görünenler HARİÇ, erken (ya da gecikmiş) çıkış adayları."""
    tarih_str = tarih_str or date.today().isoformat()
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT ro.*, o.oda_no, o.kat_adi, r.ad_soyad, r.telefon, r.referans,
                   r.id as rez_id, r.tc_no,
                   date(ro.giris_tarihi, '+' || ro.gece_sayisi || ' day') as planli_cikis
            FROM rezervasyon_odalar ro
            JOIN odalar o ON ro.oda_id = o.id
            JOIN rezervasyonlar r ON r.id = ro.rezervasyon_id
            WHERE r.iptal = 0 AND ro.checkin_yapildi = 1
              AND ro.cikis_tarihi IS NULL
              AND ro.giris_tarihi <= ?
              AND date(ro.giris_tarihi, '+' || ro.gece_sayisi || ' day') != date(?)
            ORDER BY planli_cikis, o.kat_no, o.oda_no
        """, (tarih_str, tarih_str)).fetchall()
        return rows
    finally:
        conn.close()


def odasi_gelmedi_mi(ro_row, bugun_str=None):
    """Oda satiri 'gelmedi' (no-show) sayilir mi?"""
    if bugun_str is None:
        bugun_str = date.today().isoformat()
    iptal = ("iptal" in ro_row and ro_row["iptal"]) or 0
    return (not iptal) and (not ro_row["checkin_yapildi"]) and (ro_row["giris_tarihi"] < bugun_str)


def gelmedi_mi(rez_row, bugun_str=None):
    """Geriye uyumluluk: ust rezervasyon no-show sayilir mi?
    (tum odalari gelmedigi, yani hic oda check-in degil ve giris gecmisse)"""
    if "checkin_yapildi" in rez_row and "giris_tarihi" in rez_row and "iptal" in rez_row:
        if bugun_str is None:
            bugun_str = date.today().isoformat()
        return (not rez_row["iptal"]) and (not rez_row["checkin_yapildi"]) and (rez_row["giris_tarihi"] < bugun_str)
    return False


# ---------------- GÜNLÜK GÖRÜNÜMLER ----------------

def gunun_checkin_durumu(tarih_str):
    """Check-in ekranı için: her odanın o günkü durumu + o gün odayı tutan
    rezervasyon_odalar satiri (varsa)."""
    conn = get_connection()
    try:
        bugun = date.today().isoformat()
        rows = conn.execute("""
            SELECT o.id as oda_id, o.oda_no, o.kat_adi, o.kat_no, o.oda_tipi, o.kapasite,
                   o.durum as oda_durum, o.ariza_bitis,
                   ro.id as ro_id, r.id as rez_id, r.ad_soyad, r.telefon,
                   ro.kisi_sayisi, ro.checkin_yapildi, ro.giris_tarihi, ro.gece_sayisi,
                   r.referans, ro.fiyat_tipi
            FROM odalar o
            LEFT JOIN rezervasyon_odalar ro ON ro.oda_id = o.id
                   AND ro.giris_tarihi <= ?
                   AND date(COALESCE(NULLIF(ro.cikis_tarihi, ''),
                                     date(ro.giris_tarihi, '+' || ro.gece_sayisi || ' day'))) > ?
            LEFT JOIN rezervasyonlar r ON r.id = ro.rezervasyon_id AND r.iptal = 0
            WHERE o.aktif = 1
            ORDER BY o.kat_no, o.oda_no
        """, (tarih_str, tarih_str)).fetchall()
        sonuc = []
        for r in rows:
            d = dict(r)
            d["aktif_durum"] = _odanin_efektif_durumu(d.get("oda_durum"), d.get("ariza_bitis"), bugun)
            sonuc.append(d)
        return sonuc
    finally:
        conn.close()


def bugun_cikacaklar(tarih_str):
    """O gün çıkış yapacak oda satirlari — sadece gerçekten check-in yapılmış olanlar."""
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT ro.*, o.oda_no, o.kat_adi, r.ad_soyad, r.telefon, r.referans,
                   r.id as rez_id, r.tc_no
            FROM rezervasyon_odalar ro
            JOIN odalar o ON ro.oda_id = o.id
            JOIN rezervasyonlar r ON r.id = ro.rezervasyon_id
            WHERE r.iptal = 0 AND ro.checkin_yapildi = 1
              AND ro.cikis_tarihi IS NULL
              AND date(ro.giris_tarihi, '+' || ro.gece_sayisi || ' day') = date(?)
            ORDER BY o.kat_no, o.oda_no
        """, (tarih_str,)).fetchall()
        return rows
    finally:
        conn.close()


def gunun_girisleri(tarih_str):
    """O gün check-in yapacak (ilk gecesi bu tarih olan) ODA SATIRLARI."""
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT ro.*, o.oda_no, o.kat_adi, r.ad_soyad, r.telefon, r.referans, r.tc_no,
                   r.id as rez_id, r.olusturan_kullanici
            FROM rezervasyon_odalar ro
            JOIN odalar o ON ro.oda_id = o.id
            JOIN rezervasyonlar r ON r.id = ro.rezervasyon_id
            WHERE ro.giris_tarihi = ? AND r.iptal = 0
            ORDER BY o.kat_no, o.oda_no
        """, (tarih_str,)).fetchall()
        return rows
    finally:
        conn.close()


def gunun_oda_durumu(tarih_str):
    """Tüm odaların o günkü durumu: o gün kalan oda satiri + o geceki ödeme durumu.
    Cok odali rezervasyonlarda her oda KENDI satiriyla gorunur."""
    conn = get_connection()
    try:
        bugun = date.today().isoformat()
        rows = conn.execute("""
            SELECT o.id as oda_id, o.oda_no, o.kat_adi, o.kat_no, o.oda_tipi, o.kapasite,
                   o.durum as oda_durum, o.ariza_bitis,
                   ro.id as ro_id, r.id as rez_id, r.ad_soyad, r.tc_no, r.telefon,
                   ro.kisi_sayisi, ro.fiyat_tipi, ro.gecelik_ucret, ro.checkin_yapildi,
                   ro.giris_tarihi, ro.gece_sayisi,
                   od.id as odeme_id, od.tutar, od.odendi, od.odeme_sekli, od.odeme_notu,
                   CASE WHEN ro.id IS NOT NULL THEN
                       CAST(julianday(date(ro.giris_tarihi, '+' || ro.gece_sayisi || ' day')) - julianday(?) AS INTEGER)
                   ELSE NULL END as kalan_gece
            FROM odalar o
            LEFT JOIN rezervasyon_odalar ro ON ro.oda_id = o.id
                   AND ro.giris_tarihi <= ?
                   AND date(COALESCE(NULLIF(ro.cikis_tarihi, ''),
                                     date(ro.giris_tarihi, '+' || ro.gece_sayisi || ' day'))) > ?
            LEFT JOIN rezervasyonlar r ON r.id = ro.rezervasyon_id AND r.iptal = 0
            LEFT JOIN odemeler od ON od.rezervasyon_oda_id = ro.id AND od.tarih = ?
            WHERE o.aktif = 1
            ORDER BY o.kat_no, o.oda_no
        """, (tarih_str, tarih_str, tarih_str, tarih_str)).fetchall()
        sonuc = []
        for r in rows:
            d = dict(r)
            d["aktif_durum"] = _odanin_efektif_durumu(d.get("oda_durum"), d.get("ariza_bitis"), bugun)
            sonuc.append(d)
        return sonuc
    finally:
        conn.close()


# ---------------- ODA DEĞİŞTİRME (ODA BAZLI) ----------------

def oda_degistir(ro_id, yeni_oda_id, degisim_tarihi):
    """Bir rezervasyonun TEK ODA SATIRINI başka bir odaya taşır.

    - degisim_tarihi, giris tarihinden önce veya eşitse: tüm gece yeni odaya taşınır.
    - degisim_tarihi girişin ortasindaysa: satır İKİYE ayrılır (aynı rezervasyon içinde):
        eski satir kesime kadar kalir, ayni rezervasyona YENİ bir oda satiri eklenir.
      Böylece rezervasyon yönetim sayfasında hâlâ tek satır görünür.
    Döner: (ro_id, yeni_ro_id_veya_None)
    """
    if not degisim_tarihi:
        degisim_tarihi = date.today().isoformat()
    conn = get_connection()
    try:
        cur = conn.cursor()
        eski = cur.execute(
            "SELECT ro.*, o.oda_no, o.kat_adi FROM rezervasyon_odalar ro "
            "JOIN odalar o ON ro.oda_id=o.id WHERE ro.id=?", (ro_id,)
        ).fetchone()
        if not eski:
            raise ValueError("Oda satırı bulunamadı.")
        ust = cur.execute(
            "SELECT * FROM rezervasyonlar WHERE id=? AND iptal=0", (eski["rezervasyon_id"],)
        ).fetchone()
        if not ust:
            raise ValueError("Rezervasyon bulunamadı veya iptal edilmiş.")

        if yeni_oda_id == eski["oda_id"]:
            raise ValueError("Hedef oda, mevcut odayla aynı; oda değişikliği için farklı bir oda seçmelisin.")

        # Ayni rezervasyonun zaten bu hedef odada bir satiri varsa engelle
        zaten_var = cur.execute(
            "SELECT id FROM rezervasyon_odalar WHERE rezervasyon_id=? AND oda_id=? AND id != ?",
            (eski["rezervasyon_id"], yeni_oda_id, ro_id),
        ).fetchone()
        if zaten_var:
            raise ValueError("Bu rezervasyonun hedef odada zaten bir satırı var.")

        yeni_oda = _oda_durumu_sorgula(cur, yeni_oda_id)
        liman = oda_liman(yeni_oda["kapasite"])
        if eski["kisi_sayisi"] > liman:
            raise ValueError(f"Hedef oda en fazla {liman} kişi alabilir (ekstra yatak dahil), satır {eski['kisi_sayisi']} kişi.")

        giris = datetime.strptime(eski["giris_tarihi"], "%Y-%m-%d").date()
        degisim = datetime.strptime(degisim_tarihi, "%Y-%m-%d").date()
        gecirilen_gece = (degisim - giris).days

        # Tam taşınma
        if gecirilen_gece <= 0:
            cakisma = _musaitlik_sorgusu(cur, yeni_oda_id, eski["giris_tarihi"],
                                         eski["gece_sayisi"], haric_ro_id=ro_id)
            if cakisma:
                isimler = ", ".join(c["ad_soyad"] for c in cakisma)
                raise ValueError(f"Hedef oda istenen tarihlerde dolu: {isimler}.")
            cur.execute("UPDATE rezervasyon_odalar SET oda_id=? WHERE id=?", (yeni_oda_id, ro_id))
            conn.commit()
            loglama.islem_yaz("oda_degistir", f"{ust['ad_soyad']} rezervasyonu oda satırı (ro#{ro_id}) {yeni_oda['kat_adi']} Oda {yeni_oda['oda_no']} odasına taşındı (tüm gece).")
            return ro_id, None

        if gecirilen_gece >= eski["gece_sayisi"]:
            raise ValueError("Bu tarihte misafirin zaten çıkışı var, oda değişikliğine gerek yok.")

        # Kısmi taşınma: eski satır kesime kadar, yeni satır kesimden itibaren
        kalan_gece = eski["gece_sayisi"] - gecirilen_gece
        cakisma = _musaitlik_sorgusu(cur, yeni_oda_id, degisim_tarihi, kalan_gece,
                                     haric_rez_id=eski["rezervasyon_id"])
        if cakisma:
            isimler = ", ".join(c["ad_soyad"] for c in cakisma)
            raise ValueError(f"Hedef oda bu tarihten sonra dolu: {isimler}.")

        tasinacaklar = cur.execute(
            "SELECT * FROM odemeler WHERE rezervasyon_oda_id=? AND tarih>=?",
            (ro_id, degisim_tarihi)
        ).fetchall()
        odeme_haritasi = {o["tarih"]: o for o in tasinacaklar}

        # Eski satır kesim tarihinde KAPANIR (cikis_tarihi = degisim_tarihi): misafir
        # otelden ayrılmadı, sadece bu satırın temsil ettiği oda-dönemi burada bitti.
        # Bu olmadan eski satır sonsuza dek "checkin_yapildi=1, cikis_tarihi=NULL"
        # kalır ve (a) rezervasyon_listesi'nde "acik_odasi" hep >0 sayıldığından bu
        # rezervasyon hiçbir zaman Geçmiş Kayıtlar'a düşmez, (b) hesaplanan bitiş
        # tarihi tam olarak degisim_tarihi'ne denk geldiğinden bugun_cikacaklar()
        # bu satırı o gün gerçekten çıkış yapılacakmış gibi (yanlışlıkla) listeler.
        cur.execute(
            "UPDATE rezervasyon_odalar SET gece_sayisi=?, cikis_tarihi=? WHERE id=?",
            (gecirilen_gece, degisim_tarihi, ro_id),
        )
        cur.execute("DELETE FROM odemeler WHERE rezervasyon_oda_id=? AND tarih>=?", (ro_id, degisim_tarihi))

        # Yeni oda satiri (aynı rezervasyonun devamı). onceki_ro_id ile eski satıra
        # bağlanır: KBS bu bağı, aynı misafir için mükerrer "giriş" bildirimi
        # üretmemek amacıyla kullanır (bkz. kbs.py kbs_bekleyenler).
        cur.execute("""
            INSERT INTO rezervasyon_odalar
            (rezervasyon_id, oda_id, giris_tarihi, gece_sayisi, kisi_sayisi, fiyat_tipi, gecelik_ucret, checkin_yapildi, onceki_ro_id)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (eski["rezervasyon_id"], yeni_oda_id, degisim_tarihi, kalan_gece,
              eski["kisi_sayisi"], eski["fiyat_tipi"], eski["gecelik_ucret"], eski["checkin_yapildi"], ro_id))
        yeni_ro_id = cur.lastrowid

        # Misafirleri de tasi (KBS'nin yabancı misafir alanları dahil - aksi halde
        # zaten tamamlanmış bir yabancı misafir kaydı oda değişince yeniden "eksik
        # bilgi" gibi görünür).
        misafirler = cur.execute(
            "SELECT ad_soyad, tc_no, sira_no, fiyat_tipi, gecelik_ucret, "
            "uyruk, dogum_tarihi, cinsiyet, dogum_yeri, belge_turu "
            "FROM misafirler WHERE rezervasyon_oda_id=?",
            (ro_id,),
        ).fetchall()
        for m in misafirler:
            cur.execute(
                "INSERT INTO misafirler (rezervasyon_oda_id, ad_soyad, tc_no, sira_no, fiyat_tipi, gecelik_ucret, "
                "uyruk, dogum_tarihi, cinsiyet, dogum_yeri, belge_turu) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (yeni_ro_id, m["ad_soyad"], m["tc_no"], m["sira_no"], m["fiyat_tipi"], m["gecelik_ucret"],
                 m["uyruk"], m["dogum_tarihi"], m["cinsiyet"], m["dogum_yeri"], m["belge_turu"])
            )

        varsayilan_gecelik_toplam = eski["gecelik_ucret"] * eski["kisi_sayisi"]
        for i in range(kalan_gece):
            gun = (degisim + timedelta(days=i)).isoformat()
            eski_odeme = odeme_haritasi.get(gun)
            if eski_odeme:
                odendi = eski_odeme["odendi"]
                sekli = eski_odeme["odeme_sekli"]
                notu = eski_odeme["odeme_notu"]
                tutar = eski_odeme["tutar"]
            else:
                odendi = 0
                sekli = None
                notu = None
                tutar = varsayilan_gecelik_toplam
            cur.execute("""
                INSERT INTO odemeler (rezervasyon_oda_id, tarih, tutar, odendi, odeme_sekli, odeme_notu)
                VALUES (?,?,?,?,?,?)
            """, (yeni_ro_id, gun, tutar, odendi, sekli, notu))

        _odeme_tutarlarini_yeniden_hesapla(cur, yeni_ro_id)
        conn.commit()
        loglama.islem_yaz("oda_degistir", f"{ust['ad_soyad']} rezervasyonu {degisim_tarihi} itibariyle {yeni_oda['kat_adi']} Oda {yeni_oda['oda_no']} odasına taşındı (eski satır #{ro_id} kesime kadar, yeni satır #{yeni_ro_id}).")
        return ro_id, yeni_ro_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------- REZERVASYON ODA SATIRI: TARİH DEĞİŞTİRME ----------------

def _odemeleri_yeniden_kur(cur, ro, yeni_giris_tarihi, yeni_gece_sayisi):
    """Bir oda satirinin ödemelerini yeni tarih aralığına göre yeniden kurar.
    Aynı tarihli eski ödemenin ödendi/şekli/notu korunur; kapsam dışı kalan
    ÖDENMİŞ gecelerin tarihleri döndürülür (UI bu listeyi kullanıcıya gösterir)."""
    mevcut = cur.execute(
        "SELECT * FROM odemeler WHERE rezervasyon_oda_id=? ORDER BY tarih", (ro["id"],)
    ).fetchall()
    yeni_set = set(g.isoformat() for g in _tarih_araligi(yeni_giris_tarihi, yeni_gece_sayisi))
    dusen_odenmis = []
    for o in mevcut:
        if o["odendi"] and o["tarih"] not in yeni_set:
            dusen_odenmis.append(o["tarih"])
    dusen_odenmis.sort()

    cur.execute("DELETE FROM odemeler WHERE rezervasyon_oda_id=?", (ro["id"],))
    toplam = (ro["gecelik_ucret"] or 0) * (ro["kisi_sayisi"] or 1)
    for gun in _tarih_araligi(yeni_giris_tarihi, yeni_gece_sayisi):
        gun_str = gun.isoformat()
        eski = next((o for o in mevcut if o["tarih"] == gun_str), None)
        if eski is not None:
            cur.execute(
                "INSERT INTO odemeler (rezervasyon_oda_id, tarih, tutar, odendi, odeme_sekli, odeme_notu) "
                "VALUES (?,?,?,?,?,?)",
                (ro["id"], gun_str, eski["tutar"] or toplam,
                 eski["odendi"], eski["odeme_sekli"], eski["odeme_notu"]),
            )
        else:
            cur.execute(
                "INSERT INTO odemeler (rezervasyon_oda_id, tarih, tutar, odendi) VALUES (?,?,?,0)",
                (ro["id"], gun_str, toplam),
            )
    return dusen_odenmis


def _odasi_max_gece_cur(cur, oda_id, haric_ro_id, yeni_giris_tarihi):
    """Bir oda satırının girişi yeni_giris_tarihi'ne alınırsa, odadaki diğer
    rezervasyonlarla çakışmadan sığabilecek EN FAZLA gece sayısı.
    0 = o tarihte hiç gece sığmaz. Aynı cursor üzerinden çalışır.
    Kural: başka bir satır giriş gününü İŞGAL ediyorsa (başladı ve henüz çıkmadı) 0;
    ileride başlayan satır varsa yeni giriş ile başlangıcı arasına sınırlanır."""
    satirlar = cur.execute("""
        SELECT ro.giris_tarihi, ro.gece_sayisi,
               COALESCE(NULLIF(ro.cikis_tarihi, ''),
                        date(ro.giris_tarihi, '+' || ro.gece_sayisi || ' day')) as ef_cikis
        FROM rezervasyon_odalar ro
        JOIN rezervasyonlar r ON ro.rezervasyon_id = r.id
        WHERE ro.oda_id=? AND r.iptal=0 AND ro.id!=?
    """, (oda_id, haric_ro_id)).fetchall()
    g = datetime.strptime(yeni_giris_tarihi, "%Y-%m-%d").date()
    limit = 365
    for s in satirlar:
        sect = datetime.strptime(s["giris_tarihi"], "%Y-%m-%d").date()
        ecik = datetime.strptime(s["ef_cikis"], "%Y-%m-%d").date()
        if ecik > g:
            if sect > g:
                limit = min(limit, (sect - g).days)
            else:
                return 0
    return max(limit, 0)


def odasi_max_gece(ro_id, yeni_giris_tarihi):
    """UI için: giriş yeni_giris_tarihi'ne alınırsa sığabilecek en fazla gece."""
    conn = get_connection()
    try:
        ro = conn.execute("SELECT oda_id FROM rezervasyon_odalar WHERE id=?", (ro_id,)).fetchone()
        if not ro:
            raise ValueError("Oda satırı bulunamadı.")
        return _odasi_max_gece_cur(conn.cursor(), ro["oda_id"], ro_id, yeni_giris_tarihi)
    finally:
        conn.close()


def rezervasyon_odasi_tarih_degistir(ro_id, yeni_giris_tarihi, yeni_gece_sayisi):
    """Bir oda satirinin tarih/gece sayısını değiştirir (ODA BAZLI).
    Yeni aralıkta o odada çakışan başka rezervasyon engellenir. Ödemeler yeniden
    kurulur; ödenmiş geceler tarih eşleşmesine göre korunur. Düşen ödenmiş
    gecelerin tarihleri döndürülür.

    BAŞLAMIŞ KONAKLAMA: giriş tarihi geçmişte olan satırda giriş SABİTTİR;
    yalnızca gece sayısı uzatılabilir/kısaltılabilir (misafir zaten içeride).

    NOT: Eski modeldeki 'oda değişikliği dengesi' (iki rezervasyonu birbirine
    bağlama) mantığı kaldirildi: artık her oda satiri tamamen bağımsız."""
    bugun = date.today().isoformat()
    conn = get_connection()
    try:
        cur = conn.cursor()
        ro = cur.execute(
            "SELECT ro.*, o.oda_no, o.kat_adi FROM rezervasyon_odalar ro "
            "JOIN odalar o ON ro.oda_id=o.id WHERE ro.id=?", (ro_id,)
        ).fetchone()
        if not ro:
            raise ValueError("Oda satırı bulunamadı.")
        ust = cur.execute(
            "SELECT * FROM rezervasyonlar WHERE id=? AND iptal=0", (ro["rezervasyon_id"],)
        ).fetchone()
        if not ust:
            raise ValueError("Rezervasyon bulunamadı veya iptal edilmiş.")

        if yeni_giris_tarihi < bugun:
            if yeni_giris_tarihi != ro["giris_tarihi"]:
                raise ValueError("Geçmiş tarihe rezervasyon taşınamaz.")
        elif ro["checkin_yapildi"]:
            # Check-in yapılmış (misafir fiilen içeride, giriş bugün de olsa): giriş
            # tarihi bozulmadan sadece gece uzat/kısalt. NOT: eskiden bu kontrol
            # "giris_tarihi < bugun" ile yapılıyordu; bugün check-in yapılmış bir
            # misafirde bu koşul yanlışlıkla False kalıp giriş tarihinin hâlâ
            # değiştirilebilmesine izin veriyordu.
            if yeni_giris_tarihi != ro["giris_tarihi"]:
                raise ValueError("Check-in yapılmış; giriş tarihi değiştirilemez, "
                                 "yalnızca gece sayısı uzatılabilir/kısaltılabilir.")

        cakisma = _musaitlik_sorgusu(cur, ro["oda_id"], yeni_giris_tarihi, yeni_gece_sayisi,
                                     haric_ro_id=ro_id)
        if cakisma:
            isimler = ", ".join(c["ad_soyad"] for c in cakisma)
            max_gece = _odasi_max_gece_cur(cur, ro["oda_id"], ro_id, yeni_giris_tarihi)
            mesaj = f"Bu tarihler odada dolu: {isimler}."
            if max_gece > 0:
                mesaj += (f" Bu girişte çakışmadan en fazla {max_gece} gece sığar; "
                          f"gece sayısını azaltıp tekrar deneyebilirsin.")
            raise ValueError(mesaj)

        dusen_odenmis = _odemeleri_yeniden_kur(cur, ro, yeni_giris_tarihi, yeni_gece_sayisi)
        cur.execute(
            "UPDATE rezervasyon_odalar SET giris_tarihi=?, gece_sayisi=? WHERE id=?",
            (yeni_giris_tarihi, yeni_gece_sayisi, ro_id),
        )
        # _odemeleri_yeniden_kur() yeni eklenen (eşleşmeyen) geceleri ro seviyesi
        # varsayılan tutarla (gecelik_ucret * kisi_sayisi) kaydeder; oda kişi bazlı
        # (Özel) fiyatlarla check-in yapılmışsa bu yanlış olur. Henüz ödenmemiş
        # geceleri kişi bazlı gerçek toplamla düzelt (bkz. _odeme_tutarlarini_yeniden_hesapla).
        _odeme_tutarlarini_yeniden_hesapla(cur, ro_id)
        conn.commit()
        loglama.islem_yaz("rezervasyon_tarih", f"{ust['ad_soyad']} rezervasyonu oda satırı (ro#{ro_id}) tarihi değiştirildi: {ro['giris_tarihi']}+{ro['gece_sayisi']} -> {yeni_giris_tarihi}+{yeni_gece_sayisi}.")
        dusen_odenmis.sort()
        return dusen_odenmis
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------- TAKVİM IZGARASI ----------------

def doluluk_haritasi(baslangic_str, gun_sayisi):
    """Belirtilen tarih aralığındaki dolu oda satirlarını tek sorguda getirir.
    Çıkış yapılmış satirlar cikis_tarihi'ne kadar dolu sayılır."""
    baslangic = datetime.strptime(baslangic_str, "%Y-%m-%d").date()
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT ro.oda_id, ro.giris_tarihi, ro.gece_sayisi, ro.cikis_tarihi,
                   ro.kisi_sayisi, ro.fiyat_tipi, ro.rezervasyon_id,
                   r.ad_soyad, r.referans, r.iptal, r.id as rez_id
            FROM rezervasyon_odalar ro
            JOIN rezervasyonlar r ON ro.rezervasyon_id = r.id
            WHERE r.iptal = 0
              AND date(ro.giris_tarihi) < date(?, '+' || ? || ' day')
              AND date(COALESCE(NULLIF(ro.cikis_tarihi, ''),
                                date(ro.giris_tarihi, '+' || ro.gece_sayisi || ' day'))) > date(?)
        """, (baslangic_str, gun_sayisi, baslangic_str)).fetchall()
    finally:
        conn.close()

    harita = {}
    bitis = baslangic + timedelta(days=gun_sayisi)
    for r in rows:
        giris = datetime.strptime(r["giris_tarihi"], "%Y-%m-%d").date()
        cikis = datetime.strptime(r["cikis_tarihi"], "%Y-%m-%d").date() if r["cikis_tarihi"] else None
        for i in range(r["gece_sayisi"]):
            gun = giris + timedelta(days=i)
            if baslangic <= gun < bitis:
                if cikis is not None and gun >= cikis:
                    continue
                harita[(r["oda_id"], gun.isoformat())] = r
    return harita


# ---------------- İSTATİSTİK ----------------

def aylik_istatistik(ay, yil):
    """Belirli ay/yıl için istatistik: pazarlanan gece, gelir, iptaller, kayıp gece."""
    conn = get_connection()
    try:
        ay_bas = f"{yil:04d}-{ay:02d}-01"
        nxt = (datetime(yil, ay, 1) + timedelta(days=32)).replace(day=1)
        ay_son = (nxt - timedelta(days=1)).isoformat()
        ay_ilk_yedi = f"{yil:04d}-{ay:02d}"

        # Satilan geceler + gelir: oda satirlarinin ilgili ay icindeki geceleri
        reklar = conn.execute("""
            SELECT od.*, r.ad_soyad FROM odemeler od
            JOIN rezervasyon_odalar ro ON od.rezervasyon_oda_id = ro.id
            JOIN rezervasyonlar r ON ro.rezervasyon_id = r.id
            WHERE r.iptal = 0 AND od.tarih >= ? AND od.tarih <= ?
        """, (ay_bas, ay_son)).fetchall()
        satilan_gece = len(reklar)
        gelir = sum(o["tutar"] or 0 for o in reklar)
        tahsilat = sum(o["tutar"] or 0 for o in reklar if o["odendi"])

        # Iptal edilmis rezervasyonlarin (o ay olusturulmus) toplam geceleri
        iptal_rez = conn.execute("""
            SELECT COALESCE(SUM(ro.gece_sayisi), 0) as geceler
            FROM rezervasyonlar r
            LEFT JOIN rezervasyon_odalar ro ON ro.rezervasyon_id = r.id
            WHERE r.iptal = 1
              AND substr(r.olusturma_tarihi, 1, 10) >= ? AND substr(r.olusturma_tarihi, 1, 10) <= ?
        """, (ay_bas, ay_son)).fetchone()["geceler"]

        # Gelmemis (no-show) oda satirlari
        noshow_rez = conn.execute("""
            SELECT COALESCE(SUM(ro.gece_sayisi), 0) as geceler
            FROM rezervasyon_odalar ro
            JOIN rezervasyonlar r ON ro.rezervasyon_id = r.id
            WHERE r.iptal = 0 AND ro.checkin_yapildi = 0
              AND substr(ro.giris_tarihi, 1, 7) = ? AND substr(ro.giris_tarihi, 1, 10) <= date('now')
        """, (ay_ilk_yedi,)).fetchone()["geceler"]

        # Aktif rezervasyon sayisi (o ay girisli)
        rez_adedi = conn.execute("""
            SELECT COUNT(DISTINCT r.id) as c FROM rezervasyonlar r
            JOIN rezervasyon_odalar ro ON ro.rezervasyon_id = r.id
            WHERE r.iptal = 0 AND substr(ro.giris_tarihi, 1, 7) = ?
        """, (ay_ilk_yedi,)).fetchone()["c"]

        return {
            "ay": ay_ilk_yedi,
            "satilan_gece": satilan_gece,
            "gelir": gelir,
            "tahsilat": tahsilat,
            "iptal_gece": iptal_rez,
            "noshow_gece": noshow_rez,
            "rez_adedi": rez_adedi,
        }
    finally:
        conn.close()