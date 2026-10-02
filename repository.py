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


def _oda_durumu_sorgula(cur, oda_id, baslangic_tarihi=None):
    """Oda satirini dondurur; bulunamaz veya baslangic_tarihi'nde rezervasyona
    kapali (temizlikte/arizali) ise ValueError firlatir.

    baslangic_tarihi: odada kalisin baslayacagi gun (verilmezse bugun).
    'Temizlikte' yalnizca BUGUN baslayan kalislari engeller (ileri bir tarihe
    kadar zaten temizlenmis olur); 'Arizali' ise yalnizca ariza bitisinden once
    baslayan kalislari engeller. Takvim izgarasi (takvim_widget._hucre_blok_nedeni)
    ayni kurali kullanir; eskiden burada tarih hic dikkate alinmadigi icin takvimde
    secilebilen ileri tarihli bir hucre kaydederken reddediliyordu."""
    oda = cur.execute("SELECT * FROM odalar WHERE id=? AND aktif=1", (oda_id,)).fetchone()
    if oda is None:
        raise ValueError("Oda bulunamadı veya pasif durumda.")
    bugun = date.today().isoformat()
    baslangic = baslangic_tarihi or bugun
    durum = _odanin_efektif_durumu(oda["durum"], oda["ariza_bitis"], bugun)
    if durum == "temizlikte" and baslangic <= bugun:
        raise ValueError(f"Oda {oda['oda_no']} şu an 'Temizlikte' durumda, rezervasyon verilemez. Temiz yapılmadan oda verilmez.")
    if durum == "arizali" and (not oda["ariza_bitis"] or baslangic < oda["ariza_bitis"]):
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
            "              date(ro.giris_tarihi, '+' || ro.gece_sayisi || ' day'))) > date('now', 'localtime')",
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
            "              date(ro.giris_tarihi, '+' || ro.gece_sayisi || ' day'))) > date('now', 'localtime')",
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
            log_mesaji = f"Oda {oda['oda_no']} temizlikte işaretlendi."
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
            log_mesaji = f"Oda {oda['oda_no']} arızalı işaretlendi ({gun} gün, {bitis} tarihine kadar kapalı)."
        else:
            cur.execute("UPDATE odalar SET durum='temiz', ariza_bitis=NULL WHERE id=?", (oda_id,))
            log_mesaji = f"Oda {oda['oda_no']} temiz/Temizlik bitti işaretlendi."
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    # Log, işlem kapandıktan SONRA yazılır: açık yazma işlemi varken ayrı
    # bağlantıyla yazmaya çalışmak veritabanı kilidinde ~5 sn bekletip
    # (arayüz donuyordu) sonunda log kaydını sessizce kaybediyordu.
    loglama.islem_yaz("oda_durum", log_mesaji)


# ---------------- ORTAK YARDIMCILAR ----------------

def _tarih_araligi(giris_tarihi_str, gece_sayisi):
    baslangic = datetime.strptime(giris_tarihi_str, "%Y-%m-%d").date()
    return [baslangic + timedelta(days=i) for i in range(gece_sayisi)]


def _tarih_dogrula(tarih_str):
    """'YYYY-AA-GG' bicimini dogrular; bozuksa anlasilir ValueError firlatir."""
    try:
        datetime.strptime(tarih_str or "", "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Geçersiz tarih: {tarih_str!r} (YYYY-AA-GG olmalı).")


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
                        olusturan_kullanici=None, gecmis_kontrol=True, geldigi_yer=""):
    """ÇOK ODALI rezervasyon oluşturur.

    odalar: her biri bir oda satirini temsil eden dict (veya dict destekli) listesi:
        {oda_id, giris_tarihi, gece_sayisi, kisi_sayisi, fiyat_tipi, ozel_ucret}
    Tek elemanli liste tek odali rezervasyon demektir.

    GÜVENLİK: Kapasite, tarih çakışması, oda durumu (temizlikte/arızalı) ve geçmiş
    tarih burada da kontrol edilir (tek savunma hattı UI değil, DB katmanı da reddeder).

    Döner: rez_id"""
    if not odalar:
        raise ValueError("En az bir oda seçilmelidir.")
    ad_soyad = (ad_soyad or "").strip()
    if not ad_soyad:
        raise ValueError("Ad Soyad boş bırakılamaz.")
    bugun = date.today().isoformat()
    for r in odalar:
        _tarih_dogrula(r["giris_tarihi"])
        if int(r["gece_sayisi"] or 0) < 1:
            raise ValueError("Gece sayısı en az 1 olmalıdır.")
        if int(r["kisi_sayisi"] or 0) < 1:
            raise ValueError("Kişi sayısı en az 1 olmalıdır.")
        if gecmis_kontrol and r["giris_tarihi"] < bugun:
            raise ValueError("Geçmiş tarihe rezervasyon alınamaz.")

    conn = get_connection()
    try:
        cur = conn.cursor()

        # 1) Ust tablo
        cur.execute("""
            INSERT INTO rezervasyonlar (ad_soyad, tc_no, telefon, referans, notlar, olusturan_kullanici,
                                        geldigi_yer)
            VALUES (?,?,?,?,?,?,?)
        """, (ad_soyad, tc_no, telefon, referans, notlar, olusturan_kullanici,
              (geldigi_yer or "").strip()))
        rez_id = cur.lastrowid
        # 1.0.6: rezervasyon alınırken yazılan not, not geçmişine ilk not olarak
        # (rezervasyonu alan kullanıcı adıyla) girer.
        if (notlar or "").strip():
            _not_ekle_cur(cur, "rezervasyon", rez_id, notlar,
                          olusturan_kullanici or loglama.AKTIF_KULLANICI)

        # 2) Her oda satiri + odemeler
        for r in odalar:
            oda = _oda_durumu_sorgula(cur, r["oda_id"], r["giris_tarihi"])
            kapasite = oda["kapasite"] or 1
            if r["kisi_sayisi"] > kapasite:
                raise ValueError(f"Oda {oda['oda_no']} en fazla {kapasite} kişi alabilir, {r['kisi_sayisi']} kişi girildi.")

            # Ayni cursor, bu istekte az once eklenen satirlari da gorur: ayni oda
            # ayni istekte iki kez ve cakisan tarihlerle secildiyse burada yakalanir
            # (cakismayan iki ayri donem ise serbest).
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


def rezervasyon_guncelle(rez_id, ad_soyad, tc_no, telefon, referans, notlar=None, geldigi_yer=None):
    """Üst tablodaki iletişim bilgilerini günceller (oda satirlari etkilenmez).
    notlar / geldigi_yer None verilirse mevcut değer korunur (1.0.6'dan beri
    notlar not geçmişinde tutulur, bkz. not_ekle)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        row = cur.execute("SELECT id, notlar, geldigi_yer FROM rezervasyonlar WHERE id=?", (rez_id,)).fetchone()
        if not row:
            raise ValueError("Rezervasyon bulunamadı.")
        if notlar is None:
            notlar = row["notlar"]
        if geldigi_yer is None:
            geldigi_yer = row["geldigi_yer"]
        cur.execute("""
            UPDATE rezervasyonlar
            SET ad_soyad=?, tc_no=?, telefon=?, referans=?, notlar=?, geldigi_yer=?
            WHERE id=?
        """, (ad_soyad, tc_no, telefon, referans, notlar, (geldigi_yer or "").strip(), rez_id))
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
        # Konaklamasi fiilen gerceklesmis (check-in + cikis yapilmis) bir oda
        # varsa da iptal edilemez: iptal edilirse KBS'deki cikis bildirimi
        # listeden kaybolur (giris bildirilmis, cikis hic bildirilmemis kalir)
        # ve o gecelerin geliri istatistikten duser.
        konaklamis = cur.execute(
            "SELECT COUNT(*) as c FROM rezervasyon_odalar "
            "WHERE rezervasyon_id=? AND checkin_yapildi=1",
            (rez_id,),
        ).fetchone()["c"]
        if konaklamis:
            raise ValueError(
                "Bu rezervasyonda konaklama gerçekleşmiş (check-in yapılmış oda var); "
                "iptal edilemez. Kayıt yanlışlıkla check-in yapıldıysa önce check-in'i geri al."
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
            # Iptal edildigi surede oda(lar) baskasina satilmis olabilir: geri
            # almadan once her oda satirinin (fiilen kaplayacagi) araligi icin
            # cakisma kontrolu yapilir, aksi halde ayni oda ayni gece iki
            # rezervasyonda gorunur (cifte satis).
            satirlar = cur.execute(
                "SELECT ro.*, o.oda_no, o.kat_adi FROM rezervasyon_odalar ro "
                "JOIN odalar o ON o.id = ro.oda_id WHERE ro.rezervasyon_id=?", (rez_id,)
            ).fetchall()
            for ro in satirlar:
                gece = ro["gece_sayisi"] or 0
                if ro["cikis_tarihi"]:
                    gece = (datetime.strptime(ro["cikis_tarihi"], "%Y-%m-%d").date()
                            - datetime.strptime(ro["giris_tarihi"], "%Y-%m-%d").date()).days
                if gece <= 0:
                    continue
                cakisma = _musaitlik_sorgusu(cur, ro["oda_id"], ro["giris_tarihi"], gece,
                                             haric_rez_id=rez_id)
                if cakisma:
                    isimler = ", ".join(c["ad_soyad"] for c in cakisma)
                    raise ValueError(
                        f"İptal geri alınamaz: {ro['kat_adi']} Oda {ro['oda_no']} bu tarihlerde "
                        f"artık başka bir rezervasyona ait ({isimler})."
                    )
            # Otomatik "gelmedi" iptali elle geri alındıysa bir daha otomatik
            # iptal edilmesin (misafir gelmiş ama check-in unutulmuş olabilir).
            yeni_neden = "geri_alindi" if rez["iptal_nedeni"] == "gelmedi" else None
            cur.execute("UPDATE rezervasyonlar SET iptal=0, iptal_nedeni=? WHERE id=?",
                        (yeni_neden, rez_id))
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
            SELECT ro.*, o.oda_no, o.kat_adi, o.oda_tipi, o.kapasite, o.eski_no, o.durum, o.ariza_bitis,
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
                   r.olusturan_kullanici, r.iptal, r.iptal_nedeni,
                   substr(r.olusturma_tarihi, 1, 16) as olusturma_tarihi,
                   COUNT(ro.id) as oda_sayisi,
                   COALESCE(SUM(ro.kisi_sayisi), 0) as toplam_kisi,
                   COALESCE(SUM(ro.gece_sayisi), 0) as toplam_gece,
                   MIN(ro.giris_tarihi) as giris_tarihi,
                   MAX(COALESCE(NULLIF(ro.cikis_tarihi, ''),
                                date(ro.giris_tarihi, '+' || ro.gece_sayisi || ' day'))) as cikis_tarihi,
                   GROUP_CONCAT(o.kat_adi || '-' || o.oda_no, ' + ') as oda_ozeti,
                   SUM(CASE WHEN ro.checkin_yapildi=1 THEN 1 ELSE 0 END) as checkin_odasi,
                   SUM(CASE WHEN ro.checkin_yapildi=0 AND ro.giris_tarihi < date('now', 'localtime') THEN 1 ELSE 0 END) as gelmedi_odasi,
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
        if d.get("iptal_nedeni") == "gelmedi":
            return "Gelmedi (İptal)"
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
    Sınıflandırma KBS ile aynıdır (kbs.misafir_tipi): check-in'de yabancı alanları
    (uyruk vb.) doluysa ya da belge no 11 haneli rakam değilse yabancı sayılır.
    Oda değiştirmede kopyalanan (onceki_ro_id dolu) satırlardaki misafirler aynı
    kişiler olduğu için tekrar sayılmaz.
    (Eskiden SQL'deki GLOB '*[0-9]*' ifadesi 'hiç rakam içermeyen' anlamına
    geldiğinden rakam içeren pasaport numaraları ve 11 haneli YKN'ler sayılmıyordu.)"""
    if not rez_ids:
        return {}
    import kbs
    conn = get_connection()
    try:
        yer = ",".join("?" * len(rez_ids))
        rows = conn.execute(
            "SELECT ro.rezervasyon_id AS rez_id, m.tc_no, m.uyruk, m.dogum_tarihi, "
            "m.cinsiyet, m.dogum_yeri, m.belge_turu "
            "FROM misafirler m JOIN rezervasyon_odalar ro ON ro.id = m.rezervasyon_oda_id "
            f"WHERE ro.rezervasyon_id IN ({yer}) AND ro.onceki_ro_id IS NULL",
            list(rez_ids),
        ).fetchall()
        sonuc = {}
        for r in rows:
            if kbs.misafir_tipi(r["tc_no"], r) == "yabanci":
                sonuc[r["rez_id"]] = sonuc.get(r["rez_id"], 0) + 1
        return sonuc
    finally:
        conn.close()


def _kimlik_adi(ad_soyad):
    """Ad soyadı karşılaştırma için sadeleştirir (boşluk/büyük-küçük harf farkı yok)."""
    return " ".join((ad_soyad or "").replace("İ", "i").replace("I", "ı").lower().split())


def _misafirleri_kaydet_cur(cur, ro_id, misafir_listesi, ekstra_yatak=False, fatura_istiyor=None):
    """odasi_misafirleri_kaydet'in cursor alan iç sürümü: çağıranın kendi
    transaction'ı içinde çalışır (bkz. odasi_misafirleri_kaydet ve
    odasi_misafirleri_kaydet_ve_checkin).
    fatura_istiyor=None ise dokunulmaz (mevcut değer korunur); True/False
    verilirse oda satırının fatura_istiyor alanı güncellenir (check-in'de
    misafirin fatura isteyip istemediği burada kaydedilir)."""
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
    # Misafir kayitlari silinip yeniden EKLENMEZ: ayni kisi (ayni TC/belge no,
    # yoksa ayni ad) mevcut kaydini (misafir id'sini) korur. KBS "gonderildi"
    # takibi misafir id'sine baglidir (bkz. kbs.kbs_bekleyenler); eskiden tek bir
    # bilgi duzeltmesi bile tum misafirlere yeni id verip daha once bildirilmis
    # herkesi yeniden "giris bekleyen" listesine dusuruyordu.
    mevcutlar = cur.execute(
        "SELECT id, ad_soyad, tc_no FROM misafirler WHERE rezervasyon_oda_id=? ORDER BY sira_no, id",
        (ro_id,),
    ).fetchall()
    kullanilan = set()

    def _eslesen_id(ad_soyad, tc_no):
        tc = (tc_no or "").strip()
        ad = _kimlik_adi(ad_soyad)
        for m in mevcutlar:
            if m["id"] not in kullanilan and tc and (m["tc_no"] or "").strip() == tc:
                return m["id"]
        for m in mevcutlar:
            if (m["id"] not in kullanilan and ad and _kimlik_adi(m["ad_soyad"]) == ad
                    and (not tc or not (m["tc_no"] or "").strip())):
                return m["id"]
        return None

    for i, satir in enumerate(misafir_listesi, start=1):
        if isinstance(satir, dict):
            ad_soyad = (satir.get("ad_soyad") or "").strip()
            if not ad_soyad:
                raise ValueError("Misafir adı boş olamaz.")
            tc_no = (satir.get("tc_no") or "").strip()
            fiyat_tipi = satir.get("fiyat_tipi")
            ucret = satir.get("gecelik_ucret")
            yabanci = tuple((satir.get(a) or "").strip() for a in
                            ("uyruk", "dogum_tarihi", "cinsiyet", "dogum_yeri", "belge_turu"))
        else:
            ad_soyad = satir[0].strip()
            if not ad_soyad:
                raise ValueError("Misafir adı boş olamaz.")
            tc_no = (satir[1] if len(satir) > 1 else "") or ""
            fiyat_tipi = satir[2] if len(satir) > 2 else None
            ucret = satir[3] if len(satir) > 3 else None
            yabanci = ("", "", "", "", "")
        mid = _eslesen_id(ad_soyad, tc_no)
        if mid is not None:
            kullanilan.add(mid)
            cur.execute(
                "UPDATE misafirler SET ad_soyad=?, tc_no=?, sira_no=?, fiyat_tipi=?, gecelik_ucret=?, "
                "uyruk=?, dogum_tarihi=?, cinsiyet=?, dogum_yeri=?, belge_turu=? WHERE id=?",
                (ad_soyad, tc_no, i, fiyat_tipi, ucret) + yabanci + (mid,),
            )
        else:
            cur.execute(
                "INSERT INTO misafirler (rezervasyon_oda_id, ad_soyad, tc_no, sira_no, "
                "fiyat_tipi, gecelik_ucret, uyruk, dogum_tarihi, cinsiyet, dogum_yeri, belge_turu) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (ro_id, ad_soyad, tc_no, i, fiyat_tipi, ucret) + yabanci,
            )
    for m in mevcutlar:
        if m["id"] not in kullanilan:
            cur.execute("DELETE FROM misafirler WHERE id=?", (m["id"],))
    yeni_kisi = max(len(misafir_listesi), 1)
    cur.execute("UPDATE rezervasyon_odalar SET kisi_sayisi=? WHERE id=?", (yeni_kisi, ro_id))
    if fatura_istiyor is not None:
        cur.execute(
            "UPDATE rezervasyon_odalar SET fatura_istiyor=? WHERE id=?",
            (1 if fatura_istiyor else 0, ro_id),
        )


def odasi_misafirleri_kaydet(ro_id, misafir_listesi, ekstra_yatak=False, fatura_istiyor=None):
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
        _misafirleri_kaydet_cur(cur, ro_id, misafir_listesi, ekstra_yatak, fatura_istiyor)
        _odeme_tutarlarini_yeniden_hesapla(cur, ro_id)
        conn.commit()
        loglama.islem_yaz("misafir", f"Oda satırı #{ro_id} misafirleri kaydedildi ({len(misafir_listesi)} kişi).")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _checkin_uygun_mu(cur, ro_id):
    """Check-in yapılabilir mi? Satır yoksa, rezervasyon iptalse veya giriş
    tarihi henüz gelmemişse ValueError. Zaten check-in yapılmış satırda (misafir
    düzenleme) kontrol yapılmaz."""
    ro = cur.execute(
        "SELECT ro.checkin_yapildi, ro.giris_tarihi, r.iptal FROM rezervasyon_odalar ro "
        "JOIN rezervasyonlar r ON r.id = ro.rezervasyon_id WHERE ro.id=?", (ro_id,)
    ).fetchone()
    if not ro:
        raise ValueError("Oda satırı bulunamadı.")
    if ro["checkin_yapildi"]:
        return
    if ro["iptal"]:
        raise ValueError("İptal edilmiş rezervasyona check-in yapılamaz.")
    if ro["giris_tarihi"] > date.today().isoformat():
        raise ValueError(
            f"Giriş tarihi ({ro['giris_tarihi']}) henüz gelmedi; check-in giriş günü yapılabilir. "
            "Misafir bilgilerini şimdiden kaydedebilirsin."
        )


def odasi_misafirleri_kaydet_ve_checkin(ro_id, misafir_listesi, ekstra_yatak=False, fatura_istiyor=None):
    """odasi_misafirleri_kaydet + odasi_checkin_yap TEK transaction'da: aradaki bir
    kesintide 'misafirler kaydedildi ama checkin_yapildi hâlâ 0' gibi tutarsız
    bir ara durumda kalınmaz (önceden CheckinDialog.kaydet() bu ikisini ayrı ayrı
    çağırıyordu)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        _checkin_uygun_mu(cur, ro_id)
        _misafirleri_kaydet_cur(cur, ro_id, misafir_listesi, ekstra_yatak, fatura_istiyor)
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
    """Döner: ödemenin ait olduğu oda satırının id'si (rezervasyon_oda_id),
    bulunamazsa None (çağıran taraf fatura durumu gibi oda bazlı takipleri
    bu id ile güncelleyebilir)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        o = cur.execute(
            "SELECT od.*, o2.oda_no, o2.kat_adi FROM odemeler od "
            "JOIN rezervasyon_odalar ro ON od.rezervasyon_oda_id = ro.id "
            "JOIN odalar o2 ON ro.oda_id = o2.id WHERE od.id=?",
            (odeme_id,),
        ).fetchone()
        # Kasa raporu için: yeni tahsil edilen gecenin zamanı ve tahsil eden
        # kaydedilir; zaten ödenmiş bir gecenin yalnızca şekli/notu
        # değiştiriliyorsa ilk tahsil zamanı korunur. Ödendi kaldırılırsa silinir.
        if odendi:
            if o is not None and o["odendi"] and o["tahsil_zamani"]:
                tahsil_zamani, tahsil_eden = o["tahsil_zamani"], o["tahsil_eden"]
            else:
                tahsil_zamani = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                tahsil_eden = loglama.AKTIF_KULLANICI
        else:
            tahsil_zamani = tahsil_eden = None
        cur.execute("""
            UPDATE odemeler SET odendi=?, odeme_sekli=?, odeme_notu=?, tahsil_zamani=?, tahsil_eden=?
            WHERE id=?
        """, (1 if odendi else 0, odeme_sekli, odeme_notu, tahsil_zamani, tahsil_eden, odeme_id))
        conn.commit()
        if o:
            durum = "ödendi" if odendi else "ödendi değil"
            loglama.islem_yaz("odeme", f"{o['kat_adi']} Oda {o['oda_no']}, {o['tarih']} gecesi {o['tutar']} TL: {durum}. Sekli: {odeme_sekli or 'Yok'}")
        return o["rezervasyon_oda_id"] if o else None
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def odeme_sil(odeme_id):
    """Bir gece ücreti kaydını tamamen siler — örn. aynı gün girip çıkan misafirin
    ücreti iade edildiğinde o gece artık 'satış' ve borç hesabına girmez."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        o = cur.execute(
            "SELECT od.*, o2.oda_no, o2.kat_adi FROM odemeler od "
            "JOIN rezervasyon_odalar ro ON od.rezervasyon_oda_id = ro.id "
            "JOIN odalar o2 ON ro.oda_id = o2.id WHERE od.id=?",
            (odeme_id,),
        ).fetchone()
        if o is None:
            return
        cur.execute("DELETE FROM odemeler WHERE id=?", (odeme_id,))
        conn.commit()
        loglama.islem_yaz(
            "odeme",
            f"{o['kat_adi']} Oda {o['oda_no']}, {o['tarih']} gecesi {o['tutar']} TL ödeme kaydı silindi (iade).",
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fatura_durumu_guncelle(ro_id, alindi):
    """Oda satırının fatura_alindi bayrağını günceller (fatura_istiyor
    check-in'de zaten işaretlenmiş olmalı, bkz. odasi_misafirleri_kaydet_ve_checkin)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        ro = cur.execute(
            "SELECT ro.*, o.oda_no, o.kat_adi FROM rezervasyon_odalar ro "
            "JOIN odalar o ON ro.oda_id=o.id WHERE ro.id=?", (ro_id,)
        ).fetchone()
        if not ro:
            raise ValueError("Oda satırı bulunamadı.")
        cur.execute(
            "UPDATE rezervasyon_odalar SET fatura_alindi=? WHERE id=?",
            (1 if alindi else 0, ro_id),
        )
        conn.commit()
        durum = "alındı" if alindi else "alınmadı (geri alındı)"
        loglama.islem_yaz("fatura", f"{ro['kat_adi']} Oda {ro['oda_no']} (satır #{ro_id}): fatura {durum}.")
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
        _checkin_uygun_mu(cur, ro_id)
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
        if ro["cikis_tarihi"]:
            raise ValueError("Bu odanın çıkışı yapılmış; check-in geri alınamaz.")
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
        if ro["cikis_tarihi"]:
            raise ValueError(f"Bu odanın çıkışı zaten yapılmış ({ro['cikis_tarihi']}).")
        _tarih_dogrula(tarih)
        if tarih > date.today().isoformat():
            raise ValueError(
                f"İleri bir tarihe ({tarih}) çıkış yapılamaz; çıkış, misafir fiilen "
                "ayrıldığı gün işlenmelidir (oda hemen 'temizlikte' olur)."
            )
        if tarih < ro["giris_tarihi"]:
            raise ValueError(f"Çıkış tarihi ({tarih}) giriş tarihinden ({ro['giris_tarihi']}) önce olamaz.")
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
    """tarih_str günü misafirhanede fiilen kalan (check-in yapılmış, çıkışı
    yapılmamış) ve planlı çıkışı o günden SONRA olan oda satırları — yani erken
    çıkış adayları. Planlı çıkışı o gün olanlar 'bugun_cikacaklar' listesinde;
    planlı çıkışı geçmiş (çıkışı unutulmuş) satırlar ise artık burada
    gösterilmez, günlük bakımda otomatik kapatılır (bkz.
    suresi_gecmis_konaklamalari_kapat)."""
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
              AND date(ro.giris_tarihi, '+' || ro.gece_sayisi || ' day') > date(?)
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


# ---------------- GÜNLÜK BAKIM (otomatik iptal / kapatma) ----------------

def gelmeyen_rezervasyonlar(bugun_str=None):
    """Giriş günü GEÇMİŞ (tüm odalarının giriş tarihi bugünden önce) ve hiçbir
    odasına check-in yapılmamış, iptal edilmemiş rezervasyonlar — yani gelmeyen
    misafirler. Uygulama bunları kullanıcıya gösterip iptal edilsin mi diye
    sorar (bkz. main.py GelmeyenlerDialog). Kullanıcı 'iptal edilmesin' dediyse
    (iptal_nedeni='iptal_edilmesin') ya da bir otomatik iptali geri aldıysa
    (iptal_nedeni='geri_alindi') o rezervasyon bir daha sorulmaz. Çok odalı
    rezervasyonda odalardan biri bile check-in yaptıysa ya da bir odanın giriş
    günü henüz gelmediyse listelenmez."""
    bugun = bugun_str or date.today().isoformat()
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT r.id, r.ad_soyad, r.telefon, MIN(ro.giris_tarihi) as giris_tarihi,
                   MAX(ro.gece_sayisi) as gece_sayisi,
                   GROUP_CONCAT(o.kat_adi || ' ' || o.oda_no, ', ') as odalar
            FROM rezervasyonlar r
            JOIN rezervasyon_odalar ro ON ro.rezervasyon_id = r.id
            JOIN odalar o ON o.id = ro.oda_id
            WHERE r.iptal = 0
              AND COALESCE(r.iptal_nedeni, '') NOT IN ('geri_alindi', 'iptal_edilmesin')
            GROUP BY r.id
            HAVING SUM(CASE WHEN ro.checkin_yapildi = 1 THEN 1 ELSE 0 END) = 0
               AND MAX(ro.giris_tarihi) < ?
            ORDER BY giris_tarihi, r.id
        """, (bugun,)).fetchall()
    finally:
        conn.close()


def gelmeyenleri_iptal_et(rez_idler):
    """Kullanıcının onayladığı gelmeyen rezervasyonları 'gelmedi' nedeniyle iptal
    eder (etiket: 'Gelmedi (İptal)'). Check-in yapılmış oda varsa atlar.
    Döner: iptal edilen sayı."""
    conn = get_connection()
    iptal_edilenler = []
    try:
        cur = conn.cursor()
        for rid in rez_idler:
            r = cur.execute("SELECT id, ad_soyad, iptal FROM rezervasyonlar WHERE id=?", (rid,)).fetchone()
            if r is None or r["iptal"]:
                continue
            icerde = cur.execute(
                "SELECT COUNT(*) FROM rezervasyon_odalar WHERE rezervasyon_id=? AND checkin_yapildi=1",
                (rid,)).fetchone()[0]
            if icerde:
                continue
            cur.execute("UPDATE rezervasyonlar SET iptal=1, iptal_nedeni='gelmedi' WHERE id=?", (rid,))
            iptal_edilenler.append(r)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    for r in iptal_edilenler:
        loglama.islem_yaz(
            "rezervasyon_iptal",
            f"{r['ad_soyad']} rezervasyonu (#{r['id']}) misafir giriş gününde gelmediği için iptal edildi.")
    return len(iptal_edilenler)


def gelmeyenleri_iptal_etme(rez_idler):
    """Kullanıcı 'iptal edilmesin' dediği gelmeyen rezervasyonları işaretler;
    bunlar bir daha sorulmaz (rezervasyon aktif kalır)."""
    if not rez_idler:
        return
    conn = get_connection()
    try:
        conn.executemany(
            "UPDATE rezervasyonlar SET iptal_nedeni='iptal_edilmesin' WHERE id=? AND iptal=0",
            [(rid,) for rid in rez_idler])
        conn.commit()
    finally:
        conn.close()


def suresi_gecmis_konaklamalari_kapat(bugun_str=None):
    """Check-in yapılmış ama planlı çıkış günü GEÇMİŞ olduğu halde çıkışı hiç
    işlenmemiş (unutulmuş) oda satırlarını planlı çıkış tarihiyle kapatır.
    Odanın doluluğu zaten planlı çıkışta bitiyordu (takvim/çakışma hesapları
    bunu kullanır); bu yalnızca kaydı resmîleştirir: satır Erken Çıkış
    listesinde 'hâlâ içeride' gibi görünmez, rezervasyon Geçmiş Kayıtlar'a
    düşer ve KBS'de çıkış bildirimi üretilir. Oda durumuna (temiz/temizlikte)
    dokunulmaz, ödeme kayıtları değişmez. Döner: kapatılan satır sayısı."""
    bugun = bugun_str or date.today().isoformat()
    conn = get_connection()
    try:
        cur = conn.cursor()
        satirlar = cur.execute("""
            SELECT ro.id, r.ad_soyad, o.kat_adi, o.oda_no,
                   date(ro.giris_tarihi, '+' || ro.gece_sayisi || ' day') as planli_cikis
            FROM rezervasyon_odalar ro
            JOIN rezervasyonlar r ON r.id = ro.rezervasyon_id
            JOIN odalar o ON o.id = ro.oda_id
            WHERE r.iptal = 0 AND ro.checkin_yapildi = 1
              AND (ro.cikis_tarihi IS NULL OR ro.cikis_tarihi = '')
              AND date(ro.giris_tarihi, '+' || ro.gece_sayisi || ' day') < date(?)
        """, (bugun,)).fetchall()
        for s in satirlar:
            cur.execute("UPDATE rezervasyon_odalar SET cikis_tarihi=? WHERE id=?",
                        (s["planli_cikis"], s["id"]))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    for s in satirlar:
        loglama.islem_yaz(
            "cikis",
            f"{s['kat_adi']} Oda {s['oda_no']} (satır #{s['id']}, {s['ad_soyad']}): çıkışı "
            f"işlenmemişti, planlı çıkış tarihiyle ({s['planli_cikis']}) otomatik kapatıldı.",
            kullanici="sistem",
        )
    return len(satirlar)


def gunluk_bakim():
    """Uygulama açılışında ve her genel yenilemede çağrılır. Gelmeyen
    rezervasyonlar burada iptal EDİLMEZ; kullanıcıya sorulur
    (gelmeyen_rezervasyonlar)."""
    return suresi_gecmis_konaklamalari_kapat()


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
                   AND ro.rezervasyon_id IN (SELECT id FROM rezervasyonlar WHERE iptal = 0)
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
                   ro.giris_tarihi, ro.gece_sayisi, ro.fatura_istiyor, ro.fatura_alindi,
                   od.id as odeme_id, od.tutar, od.odendi, od.odeme_sekli, od.odeme_notu,
                   CASE WHEN ro.id IS NOT NULL THEN
                       CAST(julianday(date(ro.giris_tarihi, '+' || ro.gece_sayisi || ' day')) - julianday(?) AS INTEGER)
                   ELSE NULL END as kalan_gece
            FROM odalar o
            LEFT JOIN rezervasyon_odalar ro ON ro.oda_id = o.id
                   AND ro.rezervasyon_id IN (SELECT id FROM rezervasyonlar WHERE iptal = 0)
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
        if eski["cikis_tarihi"]:
            raise ValueError("Bu oda zaten çıkış yapmış; oda değiştirilemez.")

        if yeni_oda_id == eski["oda_id"]:
            raise ValueError("Hedef oda, mevcut odayla aynı; oda değişikliği için farklı bir oda seçmelisin.")

        # NOT: Ayni rezervasyonun hedef odada ZATEN bir satiri olmasi artik
        # engellenmez (1.0.4.7): misafir A -> B -> A seklinde eski odasina geri
        # donebilir. Gercek engel yalnizca tarih cakismasidir; asagidaki
        # _musaitlik_sorgusu ayni rezervasyonun diger satirlarini da kontrol eder.

        giris = datetime.strptime(eski["giris_tarihi"], "%Y-%m-%d").date()
        _tarih_dogrula(degisim_tarihi)
        degisim = datetime.strptime(degisim_tarihi, "%Y-%m-%d").date()
        gecirilen_gece = (degisim - giris).days

        yeni_oda = _oda_durumu_sorgula(cur, yeni_oda_id, max(eski["giris_tarihi"], degisim_tarihi))
        liman = oda_liman(yeni_oda["kapasite"])
        if eski["kisi_sayisi"] > liman:
            raise ValueError(f"Hedef oda en fazla {liman} kişi alabilir (ekstra yatak dahil), satır {eski['kisi_sayisi']} kişi.")

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
                                     haric_ro_id=ro_id)
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
            (rezervasyon_id, oda_id, giris_tarihi, gece_sayisi, kisi_sayisi, fiyat_tipi, gecelik_ucret, checkin_yapildi, onceki_ro_id, fatura_istiyor, fatura_alindi)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (eski["rezervasyon_id"], yeni_oda_id, degisim_tarihi, kalan_gece,
              eski["kisi_sayisi"], eski["fiyat_tipi"], eski["gecelik_ucret"], eski["checkin_yapildi"], ro_id,
              eski["fatura_istiyor"], eski["fatura_alindi"]))
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
                tahsil_zamani = eski_odeme["tahsil_zamani"]
                tahsil_eden = eski_odeme["tahsil_eden"]
            else:
                odendi = 0
                sekli = None
                notu = None
                tutar = varsayilan_gecelik_toplam
                tahsil_zamani = tahsil_eden = None
            cur.execute("""
                INSERT INTO odemeler (rezervasyon_oda_id, tarih, tutar, odendi, odeme_sekli, odeme_notu,
                                      tahsil_zamani, tahsil_eden)
                VALUES (?,?,?,?,?,?,?,?)
            """, (yeni_ro_id, gun, tutar, odendi, sekli, notu, tahsil_zamani, tahsil_eden))

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
                "INSERT INTO odemeler (rezervasyon_oda_id, tarih, tutar, odendi, odeme_sekli, odeme_notu, "
                "tahsil_zamani, tahsil_eden) VALUES (?,?,?,?,?,?,?,?)",
                (ro["id"], gun_str, eski["tutar"] or toplam,
                 eski["odendi"], eski["odeme_sekli"], eski["odeme_notu"],
                 eski["tahsil_zamani"], eski["tahsil_eden"]),
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


def en_az_gece(giris_tarihi_str, bugun_str=None):
    """Check-in yapılmış (içerideki) bir satırın gece sayısının inebileceği en
    düşük değer: planlı çıkış bugünden önce olamaz (en az 1)."""
    bugun = datetime.strptime(bugun_str or date.today().isoformat(), "%Y-%m-%d").date()
    giris = datetime.strptime(giris_tarihi_str, "%Y-%m-%d").date()
    return max((bugun - giris).days, 1)


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
        if ro["cikis_tarihi"]:
            raise ValueError("Bu oda zaten çıkış yapmış; tarih/gece değiştirilemez.")
        _tarih_dogrula(yeni_giris_tarihi)
        yeni_gece_sayisi = int(yeni_gece_sayisi or 0)
        if yeni_gece_sayisi < 1:
            raise ValueError("Gece sayısı en az 1 olmalıdır.")
        if ro["checkin_yapildi"] and cikis_tarihi_hesapla(yeni_giris_tarihi, yeni_gece_sayisi) < bugun:
            # Misafir hâlâ içeride: planlı çıkış geçmişe çekilirse oda bugün
            # 'boş' görünüp yeniden satılabilir ve kalınan ama ödenmemiş geçmiş
            # geceler silinir. Erken ayrılan misafir için Çıkış işlemi kullanılır.
            raise ValueError(
                "Misafir hâlâ içeride; planlı çıkış bugünden önceye alınamaz "
                f"(en az {en_az_gece(yeni_giris_tarihi)} gece olmalı). "
                "Misafir ayrıldıysa Çıkış işlemini kullan."
            )

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
            WHERE r.iptal = 1 AND COALESCE(r.iptal_nedeni, '') != 'gelmedi'
              AND substr(r.olusturma_tarihi, 1, 10) >= ? AND substr(r.olusturma_tarihi, 1, 10) <= ?
        """, (ay_bas, ay_son)).fetchone()["geceler"]

        # Gelmemis (no-show) oda satirlari
        noshow_rez = conn.execute("""
            SELECT COALESCE(SUM(ro.gece_sayisi), 0) as geceler
            FROM rezervasyon_odalar ro
            JOIN rezervasyonlar r ON ro.rezervasyon_id = r.id
            WHERE (r.iptal = 0 OR r.iptal_nedeni = 'gelmedi') AND ro.checkin_yapildi = 0
              AND substr(ro.giris_tarihi, 1, 7) = ? AND substr(ro.giris_tarihi, 1, 10) <= date('now', 'localtime')
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

def _ay_araligi(ay, yil):
    ay_bas = f"{yil:04d}-{ay:02d}-01"
    nxt = (date(yil, ay, 1) + timedelta(days=32)).replace(day=1)
    ay_son = (nxt - timedelta(days=1)).isoformat()
    return ay_bas, ay_son


def aylik_detay_istatistik(ay, yil):
    """aylik_istatistik'e ek olarak (1.0.5): doluluk oranı, ortalama gecelik
    oda fiyatı, ortalama kalış, tahsilatın ödeme şekline göre dağılımı ve
    referansa göre dağılım. Doluluk, bugünkü aktif oda sayısı × ayın gün
    sayısı üzerinden hesaplanır."""
    s = aylik_istatistik(ay, yil)
    ay_bas, ay_son = _ay_araligi(ay, yil)
    gun_sayisi = int(ay_son[-2:])
    conn = get_connection()
    try:
        aktif_oda = conn.execute("SELECT COUNT(*) c FROM odalar WHERE aktif=1").fetchone()["c"]
        kapasite = aktif_oda * gun_sayisi
        s["aktif_oda"] = aktif_oda
        s["doluluk"] = round(100.0 * s["satilan_gece"] / kapasite, 1) if kapasite else 0.0
        s["ort_gecelik"] = round(s["gelir"] / s["satilan_gece"]) if s["satilan_gece"] else 0

        kalis = conn.execute("""
            SELECT AVG(ro.gece_sayisi) g FROM rezervasyon_odalar ro
            JOIN rezervasyonlar r ON r.id = ro.rezervasyon_id
            WHERE r.iptal = 0 AND ro.onceki_ro_id IS NULL
              AND ro.giris_tarihi >= ? AND ro.giris_tarihi <= ?
        """, (ay_bas, ay_son)).fetchone()["g"]
        s["ort_kalis"] = round(kalis, 1) if kalis else 0

        sekiller = conn.execute("""
            SELECT COALESCE(NULLIF(od.odeme_sekli, ''), 'Belirtilmemiş') sekil,
                   SUM(od.tutar) tutar
            FROM odemeler od
            JOIN rezervasyon_odalar ro ON od.rezervasyon_oda_id = ro.id
            JOIN rezervasyonlar r ON ro.rezervasyon_id = r.id
            WHERE r.iptal = 0 AND od.odendi = 1 AND od.tarih >= ? AND od.tarih <= ?
            GROUP BY sekil ORDER BY tutar DESC
        """, (ay_bas, ay_son)).fetchall()
        s["tahsilat_sekilleri"] = [(r["sekil"], r["tutar"] or 0) for r in sekiller]

        referanslar = conn.execute("""
            SELECT COALESCE(NULLIF(TRIM(r.referans), ''), '(Referanssız)') referans,
                   COUNT(DISTINCT r.id) rez, COUNT(od.id) gece, COALESCE(SUM(od.tutar), 0) tutar
            FROM odemeler od
            JOIN rezervasyon_odalar ro ON od.rezervasyon_oda_id = ro.id
            JOIN rezervasyonlar r ON ro.rezervasyon_id = r.id
            WHERE r.iptal = 0 AND od.tarih >= ? AND od.tarih <= ?
            GROUP BY referans ORDER BY gece DESC, referans
        """, (ay_bas, ay_son)).fetchall()
        s["referanslar"] = [dict(r) for r in referanslar]
        return s
    finally:
        conn.close()


# ---------------- KASA / BORÇ (1.0.5) ----------------

def gun_sonu_kasa(tarih_str):
    """tarih_str günü TAHSİL EDİLEN (ödendi işaretlenen) gece ücretleri.
    Gecenin kendisi başka bir gün olabilir; önemli olan tahsil günüdür.
    1.0.5'ten önce ödenmiş kayıtların tahsil zamanı bilinmediği için bu
    rapora girmez. Döner: {'satirlar': [...], 'toplam', 'sekiller', 'kullanicilar'}"""
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT od.id as odeme_id, od.tarih as gece, od.tutar, od.odeme_sekli, od.odeme_notu,
                   od.tahsil_zamani, od.tahsil_eden,
                   ro.id as ro_id, o.oda_no, o.kat_adi, r.id as rez_id, r.ad_soyad
            FROM odemeler od
            JOIN rezervasyon_odalar ro ON od.rezervasyon_oda_id = ro.id
            JOIN odalar o ON ro.oda_id = o.id
            JOIN rezervasyonlar r ON ro.rezervasyon_id = r.id
            WHERE od.odendi = 1 AND substr(od.tahsil_zamani, 1, 10) = ?
            ORDER BY od.tahsil_zamani, o.kat_no, o.oda_no, od.tarih
        """, (tarih_str,)).fetchall()
        satirlar = [dict(r) for r in rows]
        sekiller, kullanicilar = {}, {}
        for r in satirlar:
            sekil = r["odeme_sekli"] or "Belirtilmemiş"
            kisi = r["tahsil_eden"] or "Bilinmiyor"
            sekiller[sekil] = sekiller.get(sekil, 0) + (r["tutar"] or 0)
            kullanicilar[kisi] = kullanicilar.get(kisi, 0) + (r["tutar"] or 0)
        return {
            "satirlar": satirlar,
            "toplam": sum(r["tutar"] or 0 for r in satirlar),
            "sekiller": sekiller,
            "kullanicilar": kullanicilar,
        }
    finally:
        conn.close()


def acik_borclar(tarih_str=None):
    """Kalınmış ama henüz ödenmemiş geceler, oda satırı bazında gruplu.
    'Kalınmış gece' = check-in yapılmış satırın tarih_str'den (varsayılan
    bugün) ÖNCEKİ geceleri; bu gecenin kendisi henüz tamamlanmadığı için
    sayılmaz. İptal rezervasyonlar hariç."""
    tarih_str = tarih_str or date.today().isoformat()
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT ro.id as ro_id, r.id as rez_id, r.ad_soyad, r.telefon,
                   o.oda_no, o.kat_adi, ro.giris_tarihi, ro.gece_sayisi, ro.cikis_tarihi,
                   COUNT(od.id) as gece_adedi, SUM(od.tutar) as borc,
                   MIN(od.tarih) as ilk_gece, MAX(od.tarih) as son_gece
            FROM odemeler od
            JOIN rezervasyon_odalar ro ON od.rezervasyon_oda_id = ro.id
            JOIN odalar o ON ro.oda_id = o.id
            JOIN rezervasyonlar r ON ro.rezervasyon_id = r.id
            WHERE r.iptal = 0 AND ro.checkin_yapildi = 1 AND od.odendi = 0 AND od.tarih < ?
            GROUP BY ro.id
            ORDER BY MIN(od.tarih), o.kat_no, o.oda_no
        """, (tarih_str,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------- MİSAFİR KARTI / GEÇMİŞİ (1.0.5) ----------------

def telefon_anahtari(telefon):
    """Telefonu karşılaştırma için sadeleştirir: yalnız rakamlar, son 10 hane
    (0532..., +90 532..., 532... hepsi aynı anahtarı verir). 7 haneden kısa
    numaralar eşleşme için kullanılmaz ('' döner)."""
    rakamlar = "".join(c for c in (telefon or "") if c.isdigit())
    if len(rakamlar) < 7:
        return ""
    return rakamlar[-10:]


def misafir_gecmisi(telefon=None, tc_no=None, haric_rez_id=None):
    """Aynı telefon (son 10 hane) veya aynı TC/belge no ile daha önce yapılmış,
    iptal edilmemiş ve fiilen konaklanmış (en az bir odası check-in yapılmış)
    rezervasyonlar; en yeniden eskiye."""
    anahtar = telefon_anahtari(telefon)
    tc = (tc_no or "").strip()
    if not anahtar and not tc:
        return []
    conn = get_connection()
    try:
        adaylar = set()
        if anahtar:
            for r in conn.execute(
                    "SELECT id, telefon FROM rezervasyonlar WHERE COALESCE(telefon, '') != ''"):
                if telefon_anahtari(r["telefon"]) == anahtar:
                    adaylar.add(r["id"])
        if tc:
            for r in conn.execute("""
                SELECT id FROM rezervasyonlar WHERE tc_no = ?
                UNION
                SELECT ro.rezervasyon_id FROM misafirler m
                JOIN rezervasyon_odalar ro ON ro.id = m.rezervasyon_oda_id
                WHERE m.tc_no = ?
            """, (tc, tc)):
                adaylar.add(r[0])
        adaylar.discard(haric_rez_id)
        if not adaylar:
            return []
        yer = ",".join("?" * len(adaylar))
        rows = conn.execute(f"""
            SELECT r.id as rez_id, r.ad_soyad, r.telefon,
                   MIN(ro.giris_tarihi) as giris,
                   MAX(COALESCE(NULLIF(ro.cikis_tarihi, ''),
                                date(ro.giris_tarihi, '+' || ro.gece_sayisi || ' day'))) as cikis,
                   SUM(ro.gece_sayisi) as gece,
                   GROUP_CONCAT(DISTINCT o.oda_no) as odalar
            FROM rezervasyonlar r
            JOIN rezervasyon_odalar ro ON ro.rezervasyon_id = r.id
            JOIN odalar o ON o.id = ro.oda_id
            WHERE r.id IN ({yer}) AND r.iptal = 0
            GROUP BY r.id
            HAVING SUM(ro.checkin_yapildi) > 0
            ORDER BY giris DESC
        """, list(adaylar)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def misafir_karti_getir(telefon=None, tc_no=None):
    """Telefon (son 10 hane) veya TC/belge no ile eşleşen misafir kartı
    (not + sorunlu uyarısı). Yoksa None. TC eşleşmesi önceliklidir."""
    anahtar = telefon_anahtari(telefon)
    tc = (tc_no or "").strip()
    conn = get_connection()
    try:
        if tc:
            row = conn.execute(
                "SELECT * FROM misafir_kartlari WHERE tc_no = ? ORDER BY id DESC LIMIT 1", (tc,)
            ).fetchone()
            if row:
                return dict(row)
        if anahtar:
            row = conn.execute(
                "SELECT * FROM misafir_kartlari WHERE telefon_anahtar = ? ORDER BY id DESC LIMIT 1",
                (anahtar,),
            ).fetchone()
            if row:
                return dict(row)
        return None
    finally:
        conn.close()


def _kart_bul_cur(cur, anahtar, tc):
    if tc:
        row = cur.execute(
            "SELECT * FROM misafir_kartlari WHERE tc_no = ? ORDER BY id DESC LIMIT 1", (tc,)
        ).fetchone()
        if row:
            return row
    if anahtar:
        return cur.execute(
            "SELECT * FROM misafir_kartlari WHERE telefon_anahtar = ? ORDER BY id DESC LIMIT 1",
            (anahtar,),
        ).fetchone()
    return None


def misafir_karti_olustur(telefon, tc_no, ad_soyad):
    """Misafirin kartını döndürür; yoksa boş bir kart açar (misafir notu
    eklemek için kart gerekir). Telefon da TC de yoksa ValueError."""
    anahtar = telefon_anahtari(telefon)
    tc = (tc_no or "").strip()
    if not anahtar and not tc:
        raise ValueError("Misafir kartı için telefon ya da TC/belge no gerekli.")
    conn = get_connection()
    try:
        cur = conn.cursor()
        row = _kart_bul_cur(cur, anahtar, tc)
        if row is None:
            cur.execute("""
                INSERT INTO misafir_kartlari (telefon_anahtar, tc_no, ad_soyad, guncelleyen, guncelleme_zamani)
                VALUES (?,?,?,?,?)
            """, (anahtar, tc, ad_soyad or "", loglama.AKTIF_KULLANICI, _simdi()))
            row = cur.execute("SELECT * FROM misafir_kartlari WHERE id=?", (cur.lastrowid,)).fetchone()
            conn.commit()
        return dict(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def misafir_karti_kaydet(telefon, tc_no, ad_soyad, puan=0, sorunlu=False, sorunlu_nedeni=""):
    """Misafir kartının puanını (0 = puan yok, 1-5) ve 'sorunlu misafir'
    işaretini (nedeniyle) kaydeder. Sorunlu işaretlenirken ya da nedeni
    değiştirilirken işaretleyen kullanıcı ve zaman da yazılır.
    Puan yok, sorunlu değil ve misafir notu da yoksa kart silinir (gereksiz
    boş kart birikmesin). Telefon da TC de yoksa kaydedilemez (ValueError)."""
    anahtar = telefon_anahtari(telefon)
    tc = (tc_no or "").strip()
    if not anahtar and not tc:
        raise ValueError("Misafir kartı için telefon ya da TC/belge no gerekli.")
    puan = int(puan or 0)
    if not 0 <= puan <= 5:
        raise ValueError("Puan 1 ile 5 arasında olmalıdır.")
    sorunlu = bool(sorunlu)
    neden = (sorunlu_nedeni or "").strip() if sorunlu else ""
    conn = get_connection()
    degisiklik = None
    try:
        cur = conn.cursor()
        mevcut = _kart_bul_cur(cur, anahtar, tc)
        mevcut = dict(mevcut) if mevcut else None
        zaman = _simdi()
        kullanici = loglama.AKTIF_KULLANICI
        not_var = bool(mevcut) and cur.execute(
            "SELECT 1 FROM notlar WHERE tur='misafir' AND anahtar=? LIMIT 1", (str(mevcut["id"]),)
        ).fetchone() is not None
        if not puan and not sorunlu and not not_var:
            if mevcut:
                cur.execute("DELETE FROM misafir_kartlari WHERE id=?", (mevcut["id"],))
        else:
            eski = mevcut or {}
            if sorunlu and (not eski.get("sorunlu") or neden != (eski.get("sorunlu_nedeni") or "")):
                isaretleyen, isaret_zamani = kullanici, zaman
            elif sorunlu:
                isaretleyen, isaret_zamani = eski.get("sorunlu_isaretleyen"), eski.get("sorunlu_zamani")
            else:
                isaretleyen, isaret_zamani = None, None
            if mevcut:
                cur.execute("""
                    UPDATE misafir_kartlari
                    SET telefon_anahtar=?, tc_no=?, ad_soyad=?, puan=?, sorunlu=?, sorunlu_nedeni=?,
                        sorunlu_isaretleyen=?, sorunlu_zamani=?, guncelleyen=?, guncelleme_zamani=?
                    WHERE id=?
                """, (anahtar or mevcut["telefon_anahtar"], tc or mevcut["tc_no"],
                      ad_soyad or mevcut["ad_soyad"] or "", puan, 1 if sorunlu else 0, neden,
                      isaretleyen, isaret_zamani, kullanici, zaman, mevcut["id"]))
            else:
                cur.execute("""
                    INSERT INTO misafir_kartlari
                        (telefon_anahtar, tc_no, ad_soyad, puan, sorunlu, sorunlu_nedeni,
                         sorunlu_isaretleyen, sorunlu_zamani, guncelleyen, guncelleme_zamani)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                """, (anahtar, tc, ad_soyad or "", puan, 1 if sorunlu else 0, neden,
                      isaretleyen, isaret_zamani, kullanici, zaman))
        conn.commit()
        eski = mevcut or {}
        parcalar = []
        if int(eski.get("puan") or 0) != puan:
            parcalar.append(f"puan {puan}/5" if puan else "puan kaldırıldı")
        if bool(eski.get("sorunlu")) != sorunlu or (sorunlu and neden != (eski.get("sorunlu_nedeni") or "")):
            parcalar.append(f"sorunlu olarak işaretlendi: {neden or '(neden yazılmadı)'}" if sorunlu
                            else "sorunlu işareti kaldırıldı")
        if parcalar:
            degisiklik = f"{ad_soyad or eski.get('ad_soyad') or '-'} misafir kartı: " + "; ".join(parcalar)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    if degisiklik:
        loglama.islem_yaz("misafir_karti", degisiklik)


# ---------------- NOTLAR (1.0.6) ----------------

NOT_TURLERI = ("rezervasyon", "misafir", "referans")


def _simdi():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def metin_anahtari(metin):
    """Ad / referans karşılaştırması için sadeleştirir: Türkçe büyük-küçük harf
    ve fazla boşluk farkı yok ('Başkan  Ahmet Bey' == 'başkan ahmet bey')."""
    return _kimlik_adi(metin)


def _not_anahtari(tur, anahtar):
    if tur not in NOT_TURLERI:
        raise ValueError(f"Bilinmeyen not türü: {tur}")
    if tur == "referans":
        anahtar = metin_anahtari(anahtar)
    anahtar = str(anahtar or "").strip()
    if not anahtar:
        raise ValueError("Not eklenecek kayıt belirtilmedi.")
    return anahtar


def _not_ekle_cur(cur, tur, anahtar, metin, yazan):
    cur.execute(
        "INSERT INTO notlar (tur, anahtar, metin, yazan, zaman) VALUES (?,?,?,?,?)",
        (tur, _not_anahtari(tur, anahtar), metin.strip(), yazan, _simdi()),
    )
    return cur.lastrowid


def not_ekle(tur, anahtar, metin):
    """Not geçmişine yeni not ekler; yazan, giriş yapmış kullanıcıdır.
    tur: 'rezervasyon' (anahtar = rezervasyon id), 'misafir' (anahtar =
    misafir kartı id, bkz. misafir_karti_olustur) ya da 'referans' (anahtar =
    referans adı). Döner: not id."""
    metin = (metin or "").strip()
    if not metin:
        raise ValueError("Not boş olamaz.")
    conn = get_connection()
    try:
        not_id = _not_ekle_cur(conn.cursor(), tur, anahtar, metin, loglama.AKTIF_KULLANICI)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    loglama.islem_yaz("not_ekle", f"{tur.capitalize()} notu ({anahtar}): {metin}")
    return not_id


def not_sil(not_id):
    """Bir notu siler (yanlış yazılan not için); silinen not işlem geçmişine yazılır."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM notlar WHERE id=?", (not_id,)).fetchone()
        if row is None:
            raise ValueError("Not bulunamadı.")
        conn.execute("DELETE FROM notlar WHERE id=?", (not_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    loglama.islem_yaz("not_sil", f"{row['tur'].capitalize()} notu silindi "
                                 f"(yazan {row['yazan'] or '-'}, {row['zaman'] or '-'}): {row['metin']}")


def notlar_listele(tur, anahtar):
    """Bir kaydın notları, en yeniden eskiye (id, metin, yazan, zaman)."""
    try:
        anahtar = _not_anahtari(tur, anahtar)
    except ValueError:
        return []
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM notlar WHERE tur=? AND anahtar=? ORDER BY zaman DESC, id DESC",
            (tur, anahtar),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def not_sayilari(tur):
    """{anahtar: not adedi} — listelerde 'not var' göstergesi için."""
    conn = get_connection()
    try:
        return {r["anahtar"]: r["c"] for r in conn.execute(
            "SELECT anahtar, COUNT(*) c FROM notlar WHERE tur=? GROUP BY anahtar", (tur,))}
    finally:
        conn.close()


def notlar_metni(tur):
    """{anahtar: 'not1 | not2'} (eskiden yeniye) — Excel gibi tek hücrelik
    gösterimler için."""
    conn = get_connection()
    try:
        sonuc = {}
        for r in conn.execute("SELECT anahtar, metin FROM notlar WHERE tur=? ORDER BY zaman, id", (tur,)):
            sonuc[r["anahtar"]] = (sonuc[r["anahtar"]] + " | " if r["anahtar"] in sonuc else "") + r["metin"]
        return sonuc
    finally:
        conn.close()


# ---------------- MİSAFİR LİSTESİ / REFERANSLAR / KONAKLAYAN LİSTESİ (1.0.6) ----------------

_ETKIN_CIKIS = ("COALESCE(NULLIF(ro.cikis_tarihi, ''), "
                "date(ro.giris_tarihi, '+' || ro.gece_sayisi || ' day'))")


def _konaklanan_rezervasyonlar(cur, rez_idler=None):
    """İptal edilmemiş ve en az bir odası check-in yapılmış rezervasyonların
    özetleri (gece = ilk girişten son çıkışa kadar, çok odalıda tekrar sayılmaz)."""
    filtre, parametre = "", []
    if rez_idler is not None:
        if not rez_idler:
            return []
        filtre = f" AND r.id IN ({','.join('?' * len(rez_idler))})"
        parametre = list(rez_idler)
    rows = cur.execute(f"""
        SELECT r.id as rez_id, r.ad_soyad, r.telefon, r.tc_no, r.referans,
               COALESCE(r.geldigi_yer, '') as geldigi_yer, r.olusturan_kullanici,
               MIN(ro.giris_tarihi) as giris, MAX({_ETKIN_CIKIS}) as cikis,
               CAST(julianday(MAX({_ETKIN_CIKIS})) - julianday(MIN(ro.giris_tarihi)) AS INTEGER) as gece,
               GROUP_CONCAT(DISTINCT o.oda_no) as odalar,
               SUM(CASE WHEN ro.checkin_yapildi=1 AND (ro.cikis_tarihi IS NULL OR ro.cikis_tarihi='')
                        THEN 1 ELSE 0 END) as iceride
        FROM rezervasyonlar r
        JOIN rezervasyon_odalar ro ON ro.rezervasyon_id = r.id
        JOIN odalar o ON o.id = ro.oda_id
        WHERE r.iptal = 0{filtre}
        GROUP BY r.id
        HAVING SUM(ro.checkin_yapildi) > 0
        ORDER BY giris DESC, r.id DESC
    """, parametre).fetchall()
    return [dict(r) for r in rows]


def misafir_listesi(arama=""):
    """Konaklamış misafirler, kişi başı tek satır; son konaklamaya göre yeniden
    eskiye. Aynı kişi = aynı telefon (son 10 hane) ya da aynı TC/belge no;
    ikisi de yoksa aynı ad soyad. arama: ad soyad, telefon ya da geldiği yer
    içinde geçen metin (Türkçe harf duyarsız).

    Her satır: anahtar, ad_soyad, telefon, tc_no, geldigi_yer, konaklama,
    toplam_gece, ilk_giris, son_giris, son_cikis, iceride, rez_idler, kart_id,
    puan, sorunlu, sorunlu_nedeni, not_sayisi."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        rezler = _konaklanan_rezervasyonlar(cur)
        kartlar = [dict(r) for r in cur.execute("SELECT * FROM misafir_kartlari")]
    finally:
        conn.close()
    not_sayisi = not_sayilari("misafir")

    # Birleşim-bul: telefon ve TC anahtarları aynı kişiyi bağlar.
    ebeveyn = {}

    def bul(x):
        while ebeveyn.setdefault(x, x) != x:
            ebeveyn[x] = ebeveyn[ebeveyn[x]]
            x = ebeveyn[x]
        return x

    def birlestir(a, b):
        ebeveyn[bul(a)] = bul(b)

    for r in rezler:
        anahtarlar = []
        tel = telefon_anahtari(r["telefon"])
        if tel:
            anahtarlar.append("tel:" + tel)
        if (r["tc_no"] or "").strip():
            anahtarlar.append("tc:" + r["tc_no"].strip())
        if not anahtarlar:
            anahtarlar.append("ad:" + metin_anahtari(r["ad_soyad"]))
        r["_anahtarlar"] = anahtarlar
        for a in anahtarlar[1:]:
            birlestir(anahtarlar[0], a)
        bul(anahtarlar[0])

    kart_tc = {k["tc_no"]: k for k in kartlar if k["tc_no"]}
    kart_tel = {k["telefon_anahtar"]: k for k in kartlar if k["telefon_anahtar"]}

    gruplar = {}
    for r in rezler:  # en yeni konaklama önce gelir
        kok = bul(r["_anahtarlar"][0])
        g = gruplar.get(kok)
        if g is None:
            g = gruplar[kok] = {
                "anahtar": kok, "ad_soyad": " ".join((r["ad_soyad"] or "").split()),
                "telefon": r["telefon"] or "",
                "tc_no": r["tc_no"] or "", "geldigi_yer": r["geldigi_yer"],
                "konaklama": 0, "toplam_gece": 0, "ilk_giris": r["giris"],
                "son_giris": r["giris"], "son_cikis": r["cikis"], "iceride": False,
                "rez_idler": [], "_anahtarlar": set(),
            }
        g["konaklama"] += 1
        g["toplam_gece"] += max(r["gece"] or 0, 0)
        g["ilk_giris"] = min(g["ilk_giris"], r["giris"])
        g["iceride"] = g["iceride"] or bool(r["iceride"])
        g["rez_idler"].append(r["rez_id"])
        g["_anahtarlar"].update(r["_anahtarlar"])
        for alan in ("telefon", "tc_no", "geldigi_yer"):
            if not g[alan] and r[alan]:
                g[alan] = r[alan]

    sonuc = []
    aranan = metin_anahtari(arama)
    aranan_rakam = "".join(c for c in (arama or "") if c.isdigit())
    for g in gruplar.values():
        kart = None
        for a in sorted(g["_anahtarlar"]):  # 'tc:' anahtarları 'tel:'den önce gelir
            if a.startswith("tc:") and a[3:] in kart_tc:
                kart = kart_tc[a[3:]]
                break
        if kart is None:
            for a in g["_anahtarlar"]:
                if a.startswith("tel:") and a[4:] in kart_tel:
                    kart = kart_tel[a[4:]]
                    break
        del g["_anahtarlar"]
        g["kart_id"] = kart["id"] if kart else None
        g["puan"] = int((kart or {}).get("puan") or 0)
        g["sorunlu"] = bool((kart or {}).get("sorunlu"))
        g["sorunlu_nedeni"] = (kart or {}).get("sorunlu_nedeni") or ""
        g["not_sayisi"] = not_sayisi.get(str(kart["id"]), 0) if kart else 0
        if aranan or aranan_rakam:
            metin = metin_anahtari(f"{g['ad_soyad']} {g['geldigi_yer']}")
            rakam = "".join(c for c in g["telefon"] + " " + g["tc_no"] if c.isdigit())
            if not ((aranan and aranan in metin) or (len(aranan_rakam) >= 3 and aranan_rakam in rakam)):
                continue
        sonuc.append(g)
    sonuc.sort(key=lambda x: (x["son_giris"] or "", x["rez_idler"][0]), reverse=True)
    return sonuc


def konaklama_ozetleri(rez_idler):
    """Verilen rezervasyonların konaklama özetleri (misafir/referans detayında
    liste olarak gösterilir), en yeniden eskiye."""
    conn = get_connection()
    try:
        return _konaklanan_rezervasyonlar(conn.cursor(), list(rez_idler))
    finally:
        conn.close()


def gecmis_geldigi_yerler():
    """Daha önce yazılmış 'geldiği yer' değerleri (otomatik tamamlama için)."""
    conn = get_connection()
    try:
        return [r[0] for r in conn.execute(
            "SELECT DISTINCT TRIM(geldigi_yer) FROM rezervasyonlar "
            "WHERE TRIM(COALESCE(geldigi_yer, '')) != '' ORDER BY 1")]
    finally:
        conn.close()


def referans_listesi(arama=""):
    """Referanslar (aynı ad, harf/boşluk farkı gözetmeksizin tek satır):
    anahtar, referans (son yazılış), rezervasyon, konaklayan, son_giris,
    not_sayisi, rez_idler. Son kullanılan en üstte."""
    conn = get_connection()
    try:
        rows = conn.execute(f"""
            SELECT r.id, r.referans, r.iptal, MIN(ro.giris_tarihi) as giris,
                   SUM(ro.checkin_yapildi) as checkin
            FROM rezervasyonlar r
            JOIN rezervasyon_odalar ro ON ro.rezervasyon_id = r.id
            WHERE TRIM(COALESCE(r.referans, '')) != ''
            GROUP BY r.id
            ORDER BY giris DESC, r.id DESC
        """).fetchall()
    finally:
        conn.close()
    not_sayisi = not_sayilari("referans")
    aranan = metin_anahtari(arama)
    gruplar = {}
    for r in rows:
        anahtar = metin_anahtari(r["referans"])
        g = gruplar.setdefault(anahtar, {
            "anahtar": anahtar, "referans": r["referans"].strip(), "rezervasyon": 0,
            "konaklayan": 0, "son_giris": r["giris"], "rez_idler": [],
        })
        if r["iptal"]:
            continue
        g["rezervasyon"] += 1
        if r["checkin"]:
            g["konaklayan"] += 1
        g["rez_idler"].append(r["id"])
    sonuc = []
    for g in gruplar.values():
        if not g["rez_idler"]:
            continue
        if aranan and aranan not in g["anahtar"]:
            continue
        g["not_sayisi"] = not_sayisi.get(g["anahtar"], 0)
        sonuc.append(g)
    return sonuc


def referans_rezervasyonlari(referans):
    """Bir referansla alınmış (iptal edilmemiş) bütün rezervasyonlar —
    henüz gelmemiş olanlar da dahil — en yeniden eskiye."""
    anahtar = metin_anahtari(referans)
    if not anahtar:
        return []
    conn = get_connection()
    try:
        rows = conn.execute(f"""
            SELECT r.id as rez_id, r.ad_soyad, r.telefon, r.referans,
                   COALESCE(r.geldigi_yer, '') as geldigi_yer,
                   MIN(ro.giris_tarihi) as giris, MAX({_ETKIN_CIKIS}) as cikis,
                   CAST(julianday(MAX({_ETKIN_CIKIS})) - julianday(MIN(ro.giris_tarihi)) AS INTEGER) as gece,
                   GROUP_CONCAT(DISTINCT o.oda_no) as odalar,
                   SUM(ro.checkin_yapildi) as checkin
            FROM rezervasyonlar r
            JOIN rezervasyon_odalar ro ON ro.rezervasyon_id = r.id
            JOIN odalar o ON o.id = ro.oda_id
            WHERE r.iptal = 0 AND TRIM(COALESCE(r.referans, '')) != ''
            GROUP BY r.id
            ORDER BY giris DESC, r.id DESC
        """).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows if metin_anahtari(r["referans"]) == anahtar]


def konaklayan_listesi(baslangic_str, bitis_str):
    """Tarih aralığında (iki uç dahil) fiilen kalmış kişiler, kişi başı tek
    satır, giriş tarihine göre sıralı. Yalnızca check-in yapılmış, iptal
    edilmemiş oda satırları sayılır. Oda değiştiren misafir tek satırda
    görünür (odalar '3 → 5' biçiminde). Check-in'de kişi girilmemiş odalarda
    rezervasyon sahibi yazılır.

    Her satır: ad_soyad, tc_no, uyruk, telefon, geldigi_yer, odalar, giris,
    cikis, gece, iceride, referans, alan, rez_id, puan, sorunlu, sorunlu_nedeni."""
    _tarih_dogrula(baslangic_str)
    _tarih_dogrula(bitis_str)
    if bitis_str < baslangic_str:
        baslangic_str, bitis_str = bitis_str, baslangic_str
    import kbs
    conn = get_connection()
    try:
        cur = conn.cursor()
        tum_ro = {r["id"]: dict(r) for r in cur.execute(f"""
            SELECT ro.id, ro.onceki_ro_id, ro.rezervasyon_id, ro.giris_tarihi, ro.cikis_tarihi,
                   {_ETKIN_CIKIS} as etkin_cikis, o.oda_no, o.kat_adi,
                   r.ad_soyad as rez_ad, r.telefon, r.tc_no as rez_tc, r.referans,
                   COALESCE(r.geldigi_yer, '') as geldigi_yer, r.olusturan_kullanici
            FROM rezervasyon_odalar ro
            JOIN rezervasyonlar r ON r.id = ro.rezervasyon_id
            JOIN odalar o ON o.id = ro.oda_id
            WHERE r.iptal = 0 AND ro.checkin_yapildi = 1
        """)}
        misafirler = {}
        for m in cur.execute("SELECT * FROM misafirler ORDER BY rezervasyon_oda_id, sira_no, id"):
            if m["rezervasyon_oda_id"] in tum_ro:
                misafirler.setdefault(m["rezervasyon_oda_id"], []).append(dict(m))
        kartlar = [dict(r) for r in cur.execute("SELECT * FROM misafir_kartlari")]
    finally:
        conn.close()
    kart_tc = {k["tc_no"]: k for k in kartlar if k["tc_no"]}
    kart_tel = {k["telefon_anahtar"]: k for k in kartlar if k["telefon_anahtar"]}

    def kok(ro_id):
        gorulen = set()
        while tum_ro[ro_id]["onceki_ro_id"] in tum_ro and ro_id not in gorulen:
            gorulen.add(ro_id)
            ro_id = tum_ro[ro_id]["onceki_ro_id"]
        return ro_id

    kisiler = {}
    for ro in sorted(tum_ro.values(), key=lambda x: (x["giris_tarihi"], x["id"])):
        liste = misafirler.get(ro["id"]) or [{"ad_soyad": ro["rez_ad"], "tc_no": ro["rez_tc"] or ""}]
        for m in liste:
            kimlik = (m.get("tc_no") or "").strip() or metin_anahtari(m.get("ad_soyad"))
            anahtar = (kok(ro["id"]), kimlik)
            k = kisiler.get(anahtar)
            oda = str(ro["oda_no"])
            if k is None:
                tip = kbs.misafir_tipi(m.get("tc_no"), m) if m.get("id") else "yerli"
                kisiler[anahtar] = {
                    "ad_soyad": m.get("ad_soyad") or ro["rez_ad"], "tc_no": m.get("tc_no") or "",
                    "uyruk": (m.get("uyruk") or "Yabancı") if tip == "yabanci" else "T.C.",
                    "telefon": ro["telefon"] or "", "geldigi_yer": ro["geldigi_yer"],
                    "odalar": [oda], "giris": ro["giris_tarihi"], "cikis": ro["etkin_cikis"],
                    "iceride": not ro["cikis_tarihi"], "referans": ro["referans"] or "",
                    "alan": ro["olusturan_kullanici"] or "", "rez_id": ro["rezervasyon_id"],
                    "rez_tc": ro["rez_tc"] or "", "rez_ad": ro["rez_ad"],
                }
            else:
                if k["odalar"][-1] != oda:
                    k["odalar"].append(oda)
                k["giris"] = min(k["giris"], ro["giris_tarihi"])
                k["cikis"] = max(k["cikis"], ro["etkin_cikis"])
                k["iceride"] = not ro["cikis_tarihi"]

    sonuc = []
    for k in kisiler.values():
        # aralıkta en az bir gece kalmış (ya da aralık içinde aynı gün girip çıkmış)
        if not (k["giris"] <= bitis_str and (k["cikis"] > baslangic_str or k["giris"] >= baslangic_str)):
            continue
        k["odalar"] = " → ".join(k["odalar"])
        k["gece"] = (datetime.strptime(k["cikis"], "%Y-%m-%d")
                     - datetime.strptime(k["giris"], "%Y-%m-%d")).days
        # Misafir kartı: kişinin kendi TC'siyle; bulunamazsa ve kişi
        # rezervasyon sahibiyse rezervasyonun TC'si / telefonuyla.
        rez_tc, rez_ad = k.pop("rez_tc"), k.pop("rez_ad")
        kart = kart_tc.get(k["tc_no"]) if k["tc_no"] else None
        if kart is None and metin_anahtari(k["ad_soyad"]) == metin_anahtari(rez_ad):
            kart = (kart_tc.get(rez_tc) if rez_tc else None) or \
                kart_tel.get(telefon_anahtari(k["telefon"]))
        k["puan"] = int((kart or {}).get("puan") or 0)
        k["sorunlu"] = bool((kart or {}).get("sorunlu"))
        k["sorunlu_nedeni"] = (kart or {}).get("sorunlu_nedeni") or ""
        sonuc.append(k)
    sonuc.sort(key=lambda x: (x["giris"], x["odalar"], metin_anahtari(x["ad_soyad"])))
    return sonuc


# ---------------- HESAP DÖKÜMÜ (1.0.5) ----------------

def hesap_dokumu_verisi(rez_id):
    """Misafire verilecek hesap dökümü için rezervasyonun tüm odaları,
    her odanın gece gece ücretleri ve misafirleri. Rezervasyon yoksa None."""
    rez = rezervasyon_getir(rez_id)
    if rez is None:
        return None
    odalar = []
    for ro in rezervasyon_odalar_listele(rez_id):
        d = dict(ro)
        d["planli_cikis"] = cikis_tarihi_hesapla(ro["giris_tarihi"], ro["gece_sayisi"])
        d["odemeler"] = [dict(o) for o in odasi_odemeler(ro["id"])]
        d["misafirler"] = [dict(m) for m in odasi_misafirler_listele(ro["id"])]
        odalar.append(d)
    toplam = sum(o["tutar"] or 0 for d in odalar for o in d["odemeler"])
    odenen = sum(o["tutar"] or 0 for d in odalar for o in d["odemeler"] if o["odendi"])
    return {"rez": dict(rez), "odalar": odalar, "toplam": toplam,
            "odenen": odenen, "kalan": toplam - odenen}


# ---------------- GÜNÜN ÖZETİ (1.0.5) ----------------

def gunun_ozeti(tarih_str=None):
    """Açılışta gösterilen kısa özet: bugünün girişleri/çıkışları, içerideki
    ve boş odalar, bekleyen faturalar ve açık borçlar."""
    tarih_str = tarih_str or date.today().isoformat()
    girisler = gunun_girisleri(tarih_str)
    bekleyen_giris = [g for g in girisler if not g["checkin_yapildi"]]
    cikacaklar = bugun_cikacaklar(tarih_str)
    oda_durumu = gunun_oda_durumu(tarih_str)
    dolu = [o for o in oda_durumu if o["ro_id"]]
    bos = [o for o in oda_durumu if not o["ro_id"]]
    borclar = acik_borclar(tarih_str)
    conn = get_connection()
    try:
        fatura = conn.execute("""
            SELECT COUNT(*) c FROM rezervasyon_odalar ro
            JOIN rezervasyonlar r ON r.id = ro.rezervasyon_id
            WHERE r.iptal = 0 AND ro.checkin_yapildi = 1
              AND ro.fatura_istiyor = 1 AND COALESCE(ro.fatura_alindi, 0) = 0
        """).fetchone()["c"]
    finally:
        conn.close()
    return {
        "tarih": tarih_str,
        "giris_toplam": len(girisler),
        "giris_bekleyen": len(bekleyen_giris),
        "cikis_bekleyen": len(cikacaklar),
        "dolu_oda": len(dolu),
        "bos_temiz": sum(1 for o in bos if o["aktif_durum"] == "temiz"),
        "bos_temizlikte": sum(1 for o in bos if o["aktif_durum"] == "temizlikte"),
        "bos_arizali": sum(1 for o in bos if o["aktif_durum"] == "arizali"),
        "fatura_bekleyen": fatura,
        "borc_adedi": len(borclar),
        "borc_toplam": sum(b["borc"] or 0 for b in borclar),
    }


def odasi_borclarini_tahsil_et(ro_id, odeme_sekli, tarih_str=None):
    """Bir oda satırının tarih_str'den (varsayılan bugün) ÖNCEKİ ödenmemiş
    gecelerini tek seferde 'ödendi' yapar (Açık Borçlar listesinden tahsilat).
    Döner: (gece adedi, toplam tutar)."""
    tarih_str = tarih_str or date.today().isoformat()
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, tutar FROM odemeler WHERE rezervasyon_oda_id=? AND odendi=0 AND tarih < ? ORDER BY tarih",
            (ro_id, tarih_str),
        ).fetchall()
    finally:
        conn.close()
    for r in rows:
        odeme_guncelle(r["id"], True, odeme_sekli)
    return len(rows), sum(r["tutar"] or 0 for r in rows)
