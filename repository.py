# -*- coding: utf-8 -*-
"""
İş mantığı / veri erişim katmanı.
GUI bu fonksiyonları çağırır; SQL burada saklı kalır.
"""

import re
import uuid
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
        # aktif rezervasyonu olan oda silinemez
        aktif_rez = cur.execute(
            "SELECT COUNT(*) as c FROM rezervasyonlar WHERE oda_id=? AND iptal=0 "
            "AND date(giris_tarihi, '+' || gece_sayisi || ' day') > date('now')",
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
        # kapasite dusurulurse, o odadaki aktif rezervasyonlari asmamali
        max_kisi = cur.execute(
            "SELECT MAX(kisi_sayisi) as m FROM rezervasyonlar "
            "WHERE oda_id=? AND iptal=0 "
            "AND date(giris_tarihi, '+' || gece_sayisi || ' day') > date('now')",
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
            "SELECT COUNT(*) as c FROM rezervasyonlar WHERE oda_id=? AND iptal=0 "
            "AND checkin_yapildi=1 AND giris_tarihi <= ? "
            "AND date(COALESCE(NULLIF(cikis_tarihi, ''), "
            "              date(giris_tarihi, '+' || gece_sayisi || ' day'))) > ?",
            (oda_id, bugun, bugun),
        ).fetchone()["c"]
        if odede_mi:
            raise ValueError(f"Oda {oda['oda_no']}'de şu an misafir kalıyor, durumu değiştirilemez.")

        if durum == "temizlikte":
            # bugun giris yapacak / yasiyor olabilecek rezervasyonu olan odaya temizlikte denilemez
            cakisma = cur.execute(
                "SELECT ad_soyad FROM rezervasyonlar WHERE oda_id=? AND iptal=0 "
                "AND giris_tarihi <= ? "
                "AND date(COALESCE(NULLIF(cikis_tarihi, ''), "
                "              date(giris_tarihi, '+' || gece_sayisi || ' day'))) > ?",
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
            # ariza araligina denk gelen aktif rezervasyon varsa engelle
            cakisma = cur.execute(
                "SELECT ad_soyad FROM rezervasyonlar WHERE oda_id=? AND iptal=0 "
                "AND date(giris_tarihi) < date(?) "
                "AND date(COALESCE(NULLIF(cikis_tarihi, ''), "
                "              date(giris_tarihi, '+' || gece_sayisi || ' day'))) > date(?)",
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


# ---------------- REZERVASYONLAR ----------------

def _tarih_araligi(giris_tarihi_str, gece_sayisi):
    baslangic = datetime.strptime(giris_tarihi_str, "%Y-%m-%d").date()
    return [baslangic + timedelta(days=i) for i in range(gece_sayisi)]


def yeni_grup_id():
    """Aynı anda birden fazla oda alan bir rezervasyonun parçalarını birbirine bağlamak için."""
    return uuid.uuid4().hex[:12]


def _musaitlik_sorgusu(cur, oda_id, giris_tarihi, gece_sayisi, haric_rez_id=None):
    """Ayni baglanti/cursor uzerinden cakisma kontrolu (ayri baglanti acmadan).
    Cikis yapilmis rezervasyonlar (cikis_tarihi set) odadan AYNI GUN itibariyle
    ayrilmis sayilir; yani misafirin ciktigi gece oda yeni bir giris alabilir.
    Bu yuzden rezervasyonun odada kaldigi son gece = cikis_tarihi (varsa), yoksa
    giris + gece_sayisi kabul edilir."""
    q = """
        SELECT r.id, r.ad_soyad, r.giris_tarihi, r.gece_sayisi
        FROM rezervasyonlar r
        WHERE r.oda_id = ? AND r.iptal = 0
          AND date(r.giris_tarihi) < date(?, '+' || ? || ' day')
          AND date(COALESCE(NULLIF(r.cikis_tarihi, ''),
                            date(r.giris_tarihi, '+' || r.gece_sayisi || ' day'))) > date(?)
    """
    params = [oda_id, giris_tarihi, gece_sayisi, giris_tarihi]
    if haric_rez_id:
        q += " AND r.id != ?"
        params.append(haric_rez_id)
    return cur.execute(q, params).fetchall()


# ---------------- ODA DEĞİŞTİRME PARÇALARI / ÖDEME YENİDEN KURMA ----------------

def _odemeleri_yeniden_kur(cur, rez, yeni_giris_tarihi, yeni_gece_sayisi):
    """Bir rezervasyonun ödemelerini yeni tarih aralığına göre yeniden kurar.
    Aynı tarihli eski ödemenin ödendi/ödem şekli/notu korunur; kapsam dışı kalan
    ÖDENMİŞ gecelerin tarihleri döndürülür (UI bu listeyi kullanıcıya gösterir)."""
    mevcut = cur.execute(
        "SELECT * FROM odemeler WHERE rezervasyon_id=? ORDER BY tarih", (rez["id"],)
    ).fetchall()
    yeni_set = set(g.isoformat() for g in _tarih_araligi(yeni_giris_tarihi, yeni_gece_sayisi))
    dusen_odenmis = []
    for o in mevcut:
        if o["odendi"] and o["tarih"] not in yeni_set:
            dusen_odenmis.append(o["tarih"])
    dusen_odenmis.sort()

    cur.execute("DELETE FROM odemeler WHERE rezervasyon_id=?", (rez["id"],))
    toplam = (rez["gecelik_ucret"] or 0) * (rez["kisi_sayisi"] or 1)
    for gun in _tarih_araligi(yeni_giris_tarihi, yeni_gece_sayisi):
        gun_str = gun.isoformat()
        eski = next((o for o in mevcut if o["tarih"] == gun_str), None)
        if eski is not None:
            cur.execute(
                "INSERT INTO odemeler (rezervasyon_id, tarih, tutar, odendi, odeme_sekli, odeme_notu) "
                "VALUES (?,?,?,?,?,?)",
                (rez["id"], gun_str, eski["tutar"] or toplam,
                 eski["odendi"], eski["odeme_sekli"], eski["odeme_notu"]),
            )
        else:
            cur.execute(
                "INSERT INTO odemeler (rezervasyon_id, tarih, tutar, odendi) VALUES (?,?,?,0)",
                (rez["id"], gun_str, toplam),
            )
    return dusen_odenmis


def _oda_degistirme_devami(cur, rez):
    """Rez, 'Oda Değiştir' ile ortadan bölünmüş bir rezervasyonun İLK parçasıysa
    devam (ikinci parça) rezervasyonunu döndürür."""
    rows = cur.execute(
        "SELECT r.* FROM rezervasyonlar r "
        "WHERE r.iptal=0 AND r.id!=? AND r.ad_soyad=? AND r.giris_tarihi>?"
        "  AND r.notlar LIKE ?",
        (rez["id"], rez["ad_soyad"], rez["giris_tarihi"],
         f"%Oda değişikliği: önceki oda ID {rez['oda_id']}%"),
    ).fetchall()
    if not rows:
        return None
    for r in rows:
        if r["grup_id"] and rez["grup_id"] and r["grup_id"] != rez["grup_id"]:
            continue
        return r
    return None


def _oda_degistirme_oncesi(cur, rez):
    """Rez bir oda-değiştirme DEĞİŞİMİ (ikinci parça) ise ilk parçasını döndürür."""
    m = re.search(r"önceki oda ID (\d+)", rez["notlar"] or "")
    if not m:
        return None
    onceki_oda_id = int(m.group(1))
    rows = cur.execute(
        "SELECT r.* FROM rezervasyonlar r "
        "WHERE r.iptal=0 AND r.id!=? AND r.ad_soyad=? AND r.oda_id=? AND r.giris_tarihi<?"
        "  AND r.notlar NOT LIKE '%Oda değişikliği%'"
        " ORDER BY r.giris_tarihi DESC LIMIT 1",
        (rez["id"], rez["ad_soyad"], onceki_oda_id, rez["giris_tarihi"]),
    ).fetchall()
    if not rows:
        return None
    r = rows[0]
    if r["grup_id"] and rez["grup_id"] and r["grup_id"] != rez["grup_id"]:
        return None
    return r


def rezervasyon_olustur(oda_id, ad_soyad, tc_no, telefon, kisi_sayisi,
                         giris_tarihi, gece_sayisi, fiyat_tipi, referans="", notlar="",
                         grup_id=None, olusturan_kullanici=None, ozel_ucret=None,
                         gecmis_kontrol=True):
    """gecelik_ucret KİŞİ BAŞI tutardır (600 Üye / 1300 Sabit). Her gecenin toplam
    tutarı = gecelik_ucret * kisi_sayisi olarak hesaplanır (odalara göre değil,
    kişi sayısına göre fiyatlandırma).
    fiyat_tipi 'Ozel' ise gecelik_ucret ozel_ucret parametresinden alınır.
    gecmis_kontrol=True iken gecmis tarihe rezervasyon engellenir.
    GÜVENLİK: Kapasite, tarih çakışması, oda durumu (temizlikte/arızalı) ve
    geçmiş tarih burada da kontrol edilir (tek savunma hattı UI değil,
    veritabanı katmanı da reddeder)."""
    if gecmis_kontrol and giris_tarihi < date.today().isoformat():
        raise ValueError("Geçmiş tarihe rezervasyon alınamaz.")
    conn = get_connection()
    try:
        cur = conn.cursor()
        oda = _oda_durumu_sorgula(cur, oda_id)
        kapasite = oda["kapasite"] or 1
        if kisi_sayisi > kapasite:
            raise ValueError(f"Bu oda en fazla {kapasite} kişi alabilir, {kisi_sayisi} kişi girildi.")

        cakisma = _musaitlik_sorgusu(cur, oda_id, giris_tarihi, gece_sayisi)
        if cakisma:
            isimler = ", ".join(c["ad_soyad"] for c in cakisma)
            raise ValueError(f"Oda bu tarihlerde dolu: {isimler}.")

        ucret = gecelik_fiyat(fiyat_tipi, ozel_ucret)
        if fiyat_tipi == "Ozel" and ucret <= 0:
            raise ValueError("Özel fiyat için geçerli bir tutar girilmelidir.")
        cur.execute("""
            INSERT INTO rezervasyonlar
            (oda_id, ad_soyad, tc_no, telefon, kisi_sayisi, giris_tarihi,
             gece_sayisi, fiyat_tipi, gecelik_ucret, referans, notlar, grup_id, olusturan_kullanici)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (oda_id, ad_soyad, tc_no, telefon, kisi_sayisi, giris_tarihi,
              gece_sayisi, fiyat_tipi, ucret, referans, notlar, grup_id, olusturan_kullanici))
        rez_id = cur.lastrowid

        gecelik_toplam = ucret * kisi_sayisi
        for gun in _tarih_araligi(giris_tarihi, gece_sayisi):
            cur.execute("""
                INSERT INTO odemeler (rezervasyon_id, tarih, tutar, odendi)
                VALUES (?,?,?,0)
            """, (rez_id, gun.isoformat(), gecelik_toplam))

        conn.commit()
        loglama.islem_yaz(
            "rezervasyon_olustur",
            f"{ad_soyad} - {oda['kat_adi']} Oda {oda['oda_no']} ({giris_tarihi}, {gece_sayisi} gece, {kisi_sayisi} kişi, {ucret} TL/kişi/gece)",
            kullanici=olusturan_kullanici,
        )
        return rez_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def rezervasyonlari_toplu_olustur(rezervasyon_listesi):
    """Birden fazla rezervasyonu tek transaction içinde oluşturur (grup rezervasyonu).
    rezervasyon_listesi: her biri rezervasyon_olustur parametrelerini içeren dict listesi.
    Hepsi başarılı olursa commit, herhangi biri hata verirse tamamı geri alınır (atomik)."""
    if not rezervasyon_listesi:
        return []
    bugun = date.today().isoformat()
    for r in rezervasyon_listesi:
        if r.get("gecmis_kontrol", True) and r["giris_tarihi"] < bugun:
            raise ValueError("Geçmiş tarihe rezervasyon alınamaz.")
    conn = get_connection()
    try:
        cur = conn.cursor()
        olusturulan_ids = []
        for r in rezervasyon_listesi:
            oda_id = r["oda_id"]
            kisi_sayisi = r["kisi_sayisi"]
            giris_tarihi = r["giris_tarihi"]
            gece_sayisi = r["gece_sayisi"]

            oda = _oda_durumu_sorgula(cur, oda_id)
            kapasite = oda["kapasite"] or 1
            if kisi_sayisi > kapasite:
                raise ValueError(f"Oda {oda['oda_no']} en fazla {kapasite} kişi alabilir, {kisi_sayisi} girildi.")

            cakisma = _musaitlik_sorgusu(cur, oda_id, giris_tarihi, gece_sayisi)
            if cakisma:
                isimler = ", ".join(c["ad_soyad"] for c in cakisma)
                raise ValueError(f"Oda {oda['oda_no']} bu tarihlerde dolu: {isimler}.")

            ucret = gecelik_fiyat(r["fiyat_tipi"], r.get("ozel_ucret"))
            if r["fiyat_tipi"] == "Ozel" and ucret <= 0:
                raise ValueError("Özel fiyat için geçerli bir tutar girilmelidir.")
            cur.execute("""
                INSERT INTO rezervasyonlar
                (oda_id, ad_soyad, tc_no, telefon, kisi_sayisi, giris_tarihi,
                 gece_sayisi, fiyat_tipi, gecelik_ucret, referans, notlar, grup_id, olusturan_kullanici)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (oda_id, r["ad_soyad"], r.get("tc_no", ""), r.get("telefon", ""),
                  kisi_sayisi, giris_tarihi, gece_sayisi, r["fiyat_tipi"],
                  ucret, r.get("referans", ""), r.get("notlar", ""),
                  r.get("grup_id"), r.get("olusturan_kullanici")))
            rez_id = cur.lastrowid
            olusturulan_ids.append(rez_id)

            gecelik_toplam = ucret * kisi_sayisi
            for gun in _tarih_araligi(giris_tarihi, gece_sayisi):
                cur.execute("""
                    INSERT INTO odemeler (rezervasyon_id, tarih, tutar, odendi)
                    VALUES (?,?,?,0)
                """, (rez_id, gun.isoformat(), gecelik_toplam))

        conn.commit()
        for r in rezervasyon_listesi:
            loglama.islem_yaz(
                "rezervasyon_olustur",
                f"{r['ad_soyad']} - Oda ID {r['oda_id']} ({r['giris_tarihi']}, {r['gece_sayisi']} gece)",
                kullanici=r.get("olusturan_kullanici"),
            )
        return olusturulan_ids
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def rezervasyon_iptal(rez_id):
    """Müşteri tarafından iptal edilen rezervasyonu işaretler."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        rez = cur.execute(
            "SELECT r.*, o.oda_no, o.kat_adi FROM rezervasyonlar r JOIN odalar o ON r.oda_id=o.id WHERE r.id=?",
            (rez_id,),
        ).fetchone()
        if rez:
            cur.execute("UPDATE rezervasyonlar SET iptal=1 WHERE id=?", (rez_id,))
            conn.commit()
            loglama.islem_yaz("rezervasyon_iptal", f"{rez['ad_soyad']} - {rez['kat_adi']} Oda {rez['oda_no']} rezervasyonu iptal edildi.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def rezervasyon_iptal_geri_al(rez_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        rez = cur.execute(
            "SELECT r.*, o.oda_no, o.kat_adi FROM rezervasyonlar r JOIN odalar o ON r.oda_id=o.id WHERE r.id=?",
            (rez_id,),
        ).fetchone()
        if rez:
            cur.execute("UPDATE rezervasyonlar SET iptal=0 WHERE id=?", (rez_id,))
            conn.commit()
            loglama.islem_yaz("rezervasyon_iptal", f"{rez['ad_soyad']} - Oda {rez['oda_no']} rezervasyonunun iptali geri alındı.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def rezervasyon_getir(rez_id):
    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT r.*, o.oda_no, o.kat_adi, o.oda_tipi, o.kapasite
            FROM rezervasyonlar r JOIN odalar o ON r.oda_id = o.id
            WHERE r.id = ?
        """, (rez_id,)).fetchone()
        return row
    finally:
        conn.close()


def rezervasyon_guncelle(rez_id, ad_soyad, tc_no, telefon, kisi_sayisi, referans, notlar):
    """Misafir bilgilerini günceller. Kapasite aşımı burada da engellenir."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        row = cur.execute("SELECT oda_id FROM rezervasyonlar WHERE id=?", (rez_id,)).fetchone()
        if row:
            oda = cur.execute("SELECT kapasite FROM odalar WHERE id=?", (row["oda_id"],)).fetchone()
            kapasite = (oda["kapasite"] if oda else None) or 1
            liman = max(kapasite + 2, 3)
            if kisi_sayisi > liman:
                raise ValueError(f"Bu oda için en fazla {liman} kişi saklanabilir, {kisi_sayisi} kişi girildi.")
        cur.execute("""
            UPDATE rezervasyonlar
            SET ad_soyad=?, tc_no=?, telefon=?, kisi_sayisi=?, referans=?, notlar=?
            WHERE id=?
        """, (ad_soyad, tc_no, telefon, kisi_sayisi, referans, notlar, rez_id))
        # Odeme tutarlarini da senkronize et (kapasite kontrolu icerde yapilir)
        # Burada dogrudan odemeleri guncellemeyelim; cagiran taraf kisi_sayisi_senkronla cagiracak
        conn.commit()
        loglama.islem_yaz("rezervasyon_guncelle", f"Rezervasyon #{rez_id} bilgileri güncellendi: {ad_soyad} ({kisi_sayisi} kişi).")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def kisi_sayisi_senkronla(rez_id, yeni_kisi_sayisi, ekstra_yatak=False):
    """Kişi sayısı değiştiğinde kisi_sayisi'nı günceller ve HENÜZ ÖDENMEMİŞ
    gecelerin tutarını yeniden hesaplar. Kapasite aşımı sert engel değildir:
    resmî kapasitenin +2 fazlasına kadar kayıt kabul edilir (misafir kaydı,
    check-in günü ekstra kişi vb.); ekstra_yatak=True ise +1 daha fazla."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        rez = cur.execute("SELECT oda_id, gecelik_ucret FROM rezervasyonlar WHERE id=?", (rez_id,)).fetchone()
        if not rez:
            return
        oda = cur.execute("SELECT kapasite FROM odalar WHERE id=?", (rez["oda_id"],)).fetchone()
        kapasite = (oda["kapasite"] if oda else None) or 1
        liman = max(kapasite + 2, 3) + (1 if ekstra_yatak else 0)
        if yeni_kisi_sayisi > liman:
            raise ValueError(
                f"Bu oda için en fazla {liman} kişi kaydedilebilir"
                f"{' (ekstra yatak dahil)' if ekstra_yatak else ''}, {yeni_kisi_sayisi} girildi."
            )
        yeni_tutar = rez["gecelik_ucret"] * yeni_kisi_sayisi
        cur.execute("UPDATE rezervasyonlar SET kisi_sayisi=? WHERE id=?", (yeni_kisi_sayisi, rez_id))
        cur.execute(
            "UPDATE odemeler SET tutar=? WHERE rezervasyon_id=? AND odendi=0",
            (yeni_tutar, rez_id)
        )
        conn.commit()
        loglama.islem_yaz("rezervasyon_guncelle", f"Rezervasyon #{rez_id} kişi sayısı {yeni_kisi_sayisi} olarak güncellendi.")
        odeme_tutarlarini_guncelle(rez_id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def rezervasyon_odemeleri(rez_id):
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM odemeler WHERE rezervasyon_id=? ORDER BY tarih", (rez_id,)
        ).fetchall()
        return rows
    finally:
        conn.close()


def rezervasyon_gecelik_toplami(rez_row):
    """Bir rezervasyonun TÜM GECELER için değil, SİNGLE GECELİK toplamını döndürür:
    kayıtlı kişilerin bireysel fiyatları varsa onların toplamı,
    yoksa rezervasyonun (kisi_sayisi * gecelik_ucret) değeri kullanılır.
    Üst seviye tutarların (Oda Durumu, Günün Girişleri, dışa aktarma)
    HEP aynı mantıkla hesaplanması içindir."""
    misafirler = misafirler_listele(rez_row["id"])
    ucretler = [m["gecelik_ucret"] for m in misafirler if m["gecelik_ucret"]]
    if ucretler:
        return sum(ucretler)
    return (rez_row["gecelik_ucret"] or 0) * (rez_row["kisi_sayisi"] or 1)


def odeme_tutarlarini_guncelle(rez_id):
    """Kişi bazlı fiyatları topluca HENÜZ ÖDENMEMİŞ gecelere işler.

    Her gece tutarı = odada kalan her kişinin kendi gecelik ücretinin toplamı.
    Misafir fiyatları yoksa (check-in yapılmadıysa) rezervasyonun kendi
    gecelik_ucret * kisi_sayisi değerine geri döner."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        rez = cur.execute(
            "SELECT kisi_sayisi, gecelik_ucret FROM rezervasyonlar WHERE id=?", (rez_id,)
        ).fetchone()
        if not rez:
            return
        misafirler = cur.execute(
            "SELECT gecelik_ucret FROM misafirler WHERE rezervasyon_id=? ORDER BY sira_no, id",
            (rez_id,),
        ).fetchall()
        gercek_sayilar = [m["gecelik_ucret"] for m in misafirler if m["gecelik_ucret"]]
        if gercek_sayilar:
            gecelik_toplam = sum(gercek_sayilar)
        else:
            gecelik_toplam = (rez["gecelik_ucret"] or 0) * (rez["kisi_sayisi"] or 1)
        cur.execute(
            "UPDATE odemeler SET tutar=? WHERE rezervasyon_id=? AND odendi=0",
            (gecelik_toplam, rez_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------- MİSAFİRLER ----------------

def misafirler_listele(rez_id):
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM misafirler WHERE rezervasyon_id=? ORDER BY sira_no, id", (rez_id,)
        ).fetchall()
        return rows
    finally:
        conn.close()


def misafirleri_kaydet(rez_id, misafir_listesi, ekstra_yatak=False):
    """misafir_listesi: [(ad_soyad, tc_no), ...]
    veya 4 elemanli gelsede kişi başı fiyat bilgisi de saklanır:
        [(ad_soyad, tc_no, fiyat_tipi, gecelik_ucret), ...]
    Mevcut listeyi tamamen değiştirir. Kayıt sayısı resmî kapasiteyi aşabilir
    (+2); ekstra yatak işaretlenirse +1 daha fazlasına izin verilir."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM misafirler WHERE rezervasyon_id=?", (rez_id,))
        for i, satir in enumerate(misafir_listesi, start=1):
            ad_soyad = satir[0]
            tc_no = satir[1] if len(satir) > 1 else ""
            fiyat_tipi = satir[2] if len(satir) > 2 else None
            ucret = satir[3] if len(satir) > 3 else None
            cur.execute(
                "INSERT INTO misafirler (rezervasyon_id, ad_soyad, tc_no, sira_no, fiyat_tipi, gecelik_ucret) "
                "VALUES (?,?,?,?,?,?)",
                (rez_id, ad_soyad, tc_no, i, fiyat_tipi, ucret)
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    yeni_kisi_sayisi = max(len(misafir_listesi), 1)
    kisi_sayisi_senkronla(rez_id, yeni_kisi_sayisi, ekstra_yatak=ekstra_yatak)
    odeme_tutarlarini_guncelle(rez_id)


# ---------------- CHECK-IN ----------------

def checkin_yap(rez_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        rez = cur.execute(
            "SELECT r.*, o.oda_no, o.kat_adi FROM rezervasyonlar r JOIN odalar o ON r.oda_id=o.id WHERE r.id=?",
            (rez_id,),
        ).fetchone()
        cur.execute("UPDATE rezervasyonlar SET checkin_yapildi=1 WHERE id=?", (rez_id,))
        conn.commit()
        if rez:
            loglama.islem_yaz("checkin", f"{rez['ad_soyad']} check-in yaptı ({rez['kat_adi']} Oda {rez['oda_no']}).")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def checkin_geri_al(rez_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        rez = cur.execute(
            "SELECT r.*, o.oda_no, o.kat_adi FROM rezervasyonlar r JOIN odalar o ON r.oda_id=o.id WHERE r.id=?",
            (rez_id,),
        ).fetchone()
        cur.execute("UPDATE rezervasyonlar SET checkin_yapildi=0 WHERE id=?", (rez_id,))
        conn.commit()
        if rez:
            loglama.islem_yaz("checkin", f"{rez['ad_soyad']} check-in iptal edildi ({rez['kat_adi']} Oda {rez['oda_no']}).")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def cikis_yap(rez_id, cikis_tarihi_str=None):
    """Check-out: rezervasyonu cikis_tarihi ile isaretler ve odayi ayni gun
    temizlenip yeni misafire hazir oldugu icin durumunu 'temiz' yapar."""
    tarih = cikis_tarihi_str or date.today().isoformat()
    conn = get_connection()
    try:
        cur = conn.cursor()
        rez = cur.execute(
            "SELECT r.*, o.oda_no, o.kat_adi, o.durum FROM rezervasyonlar r "
            "JOIN odalar o ON r.oda_id=o.id WHERE r.id=? AND r.iptal=0",
            (rez_id,),
        ).fetchone()
        if not rez:
            raise ValueError("Çıkış yapılacak rezervasyon bulunamadı.")
        if not rez["checkin_yapildi"]:
            raise ValueError("Bu misafir check-in yapılmamış, çıkış işlemi uygulanamaz.")
        cur.execute(
            "UPDATE rezervasyonlar SET cikis_tarihi=? WHERE id=?",
            (tarih, rez_id),
        )
        cur.execute(
            "UPDATE odalar SET durum='temiz', ariza_bitis=NULL WHERE id=?",
            (rez["oda_id"],),
        )
        conn.commit()
        loglama.islem_yaz(
            "cikis",
            f"{rez['ad_soyad']} çıkış yaptı ({rez['kat_adi']} Oda {rez['oda_no']}, {tarih}). Oda temiz olarak işaretlendi.",
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def gunun_checkin_durumu(tarih_str):
    """Check-in ekranı için: her oda için o günkü durum + oda durumu (temiz/temizlikte/arızalı)."""
    conn = get_connection()
    try:
        bugun = date.today().isoformat()
        rows = conn.execute("""
            SELECT o.id as oda_id, o.oda_no, o.kat_adi, o.kat_no, o.oda_tipi, o.kapasite,
                   o.durum as oda_durum, o.ariza_bitis,
                   r.id as rez_id, r.ad_soyad, r.telefon, r.kisi_sayisi, r.checkin_yapildi,
                   r.giris_tarihi, r.gece_sayisi, r.referans
            FROM odalar o
            LEFT JOIN rezervasyonlar r ON r.oda_id = o.id AND r.iptal = 0
                   AND r.giris_tarihi <= ?
                   AND date(COALESCE(NULLIF(r.cikis_tarihi, ''),
                                     date(r.giris_tarihi, '+' || r.gece_sayisi || ' day'))) > ?
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
    """O gün çıkış yapacak misafirler — sadece gerçekten check-in yapılmış olanlar
    (no-show / gelmeyen rezervasyonlar çıkış listesinde gösterilmez)."""
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT r.*, o.oda_no, o.kat_adi
            FROM rezervasyonlar r JOIN odalar o ON r.oda_id = o.id
            WHERE r.iptal = 0
              AND r.checkin_yapildi = 1
              AND date(r.giris_tarihi, '+' || r.gece_sayisi || ' day') = date(?)
            ORDER BY o.kat_no, o.oda_no
        """, (tarih_str,)).fetchall()
        return rows
    finally:
        conn.close()


def grup_rezervasyonlari(grup_id, haric_rez_id=None):
    """Aynı rezervasyonda (grup) birlikte alınan diğer odaları getirir."""
    if not grup_id:
        return []
    conn = get_connection()
    try:
        q = """
            SELECT r.*, o.oda_no, o.kat_adi
            FROM rezervasyonlar r JOIN odalar o ON r.oda_id = o.id
            WHERE r.grup_id = ? AND r.iptal = 0
        """
        params = [grup_id]
        if haric_rez_id:
            q += " AND r.id != ?"
            params.append(haric_rez_id)
        rows = conn.execute(q, params).fetchall()
        return rows
    finally:
        conn.close()


def tum_rezervasyonlar():
    """Geriye uyumluluk için: sadece aktif (iptal edilmemiş) rezervasyonlar."""
    return rezervasyon_listesi("aktif")


def rezervasyon_listesi(durum="aktif"):
    """durum: 'aktif', 'iptal', veya 'hepsi'"""
    conn = get_connection()
    try:
        q = """
            SELECT r.*, o.oda_no, o.kat_adi, o.oda_tipi
            FROM rezervasyonlar r JOIN odalar o ON r.oda_id = o.id
        """
        if durum == "aktif":
            q += " WHERE r.iptal = 0"
        elif durum == "iptal":
            q += " WHERE r.iptal = 1"
        q += " ORDER BY r.giris_tarihi DESC"
        rows = conn.execute(q).fetchall()
        return rows
    finally:
        conn.close()


def cikis_tarihi_hesapla(giris_tarihi_str, gece_sayisi):
    baslangic = datetime.strptime(giris_tarihi_str, "%Y-%m-%d").date()
    return (baslangic + timedelta(days=gece_sayisi)).isoformat()


def gelmedi_mi(rez_row, bugun_str=None):
    """Bir rezervasyonun 'gelmedi' (no-show) sayılıp sayılmayacağını hesaplar."""
    if bugun_str is None:
        bugun_str = date.today().isoformat()
    return (not rez_row["iptal"]) and (not rez_row["checkin_yapildi"]) and (rez_row["giris_tarihi"] < bugun_str)


def oda_degistir(eski_rez_id, yeni_oda_id, degisim_tarihi):
    """Bir rezervasyonu başka bir odaya taşır."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        eski = cur.execute("SELECT * FROM rezervasyonlar WHERE id=?", (eski_rez_id,)).fetchone()
        if not eski:
            raise ValueError("Rezervasyon bulunamadı.")
        yeni_oda = _oda_durumu_sorgula(cur, yeni_oda_id)
        if eski["kisi_sayisi"] > (yeni_oda["kapasite"] or 1):
            raise ValueError(f"Hedef oda en fazla {yeni_oda['kapasite'] or 1} kişi alabilir, rezervasyon {eski['kisi_sayisi']} kişi.")

        giris = datetime.strptime(eski["giris_tarihi"], "%Y-%m-%d").date()
        degisim = datetime.strptime(degisim_tarihi, "%Y-%m-%d").date()
        gecirilen_gece = (degisim - giris).days

        if gecirilen_gece <= 0:
            cakisma = _musaitlik_sorgusu(cur, yeni_oda_id, eski["giris_tarihi"], eski["gece_sayisi"], haric_rez_id=eski_rez_id)
            if cakisma:
                isimler = ", ".join(c["ad_soyad"] for c in cakisma)
                raise ValueError(f"Hedef oda istenen tarihlerde dolu: {isimler}.")
            cur.execute("UPDATE rezervasyonlar SET oda_id=? WHERE id=?", (yeni_oda_id, eski_rez_id))
            conn.commit()
            loglama.islem_yaz("oda_degistir", f"{eski['ad_soyad']} rezervasyonu {yeni_oda['kat_adi']} Oda {yeni_oda['oda_no']} odasına taşındı (tüm rezervasyon).")
            return eski_rez_id

        if gecirilen_gece >= eski["gece_sayisi"]:
            raise ValueError("Bu tarihte misafirin zaten çıkışı var, oda değişikliğine gerek yok.")

        kalan_gece = eski["gece_sayisi"] - gecirilen_gece
        cakisma = _musaitlik_sorgusu(cur, yeni_oda_id, degisim_tarihi, kalan_gece, haric_rez_id=eski_rez_id)
        if cakisma:
            isimler = ", ".join(c["ad_soyad"] for c in cakisma)
            raise ValueError(f"Hedef oda bu tarihten sonra dolu: {isimler}.")

        tasinacaklar = cur.execute(
            "SELECT * FROM odemeler WHERE rezervasyon_id=? AND tarih>=?",
            (eski_rez_id, degisim_tarihi)
        ).fetchall()
        odeme_haritasi = {o["tarih"]: o for o in tasinacaklar}

        cur.execute("UPDATE rezervasyonlar SET gece_sayisi=? WHERE id=?", (gecirilen_gece, eski_rez_id))
        cur.execute("DELETE FROM odemeler WHERE rezervasyon_id=? AND tarih>=?", (eski_rez_id, degisim_tarihi))

        eski_notlar = eski["notlar"] or ""
        yeni_notlar = f"{eski_notlar} [Oda değişikliği: önceki oda ID {eski['oda_id']}]".strip()
        cur.execute("""
            INSERT INTO rezervasyonlar
            (oda_id, ad_soyad, tc_no, telefon, kisi_sayisi, giris_tarihi,
             gece_sayisi, fiyat_tipi, gecelik_ucret, referans, notlar, grup_id, checkin_yapildi)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (yeni_oda_id, eski["ad_soyad"], eski["tc_no"], eski["telefon"], eski["kisi_sayisi"],
              degisim_tarihi, kalan_gece, eski["fiyat_tipi"], eski["gecelik_ucret"],
              eski["referans"], yeni_notlar, eski["grup_id"], eski["checkin_yapildi"]))
        yeni_rez_id = cur.lastrowid

        misafirler = cur.execute(
            "SELECT ad_soyad, tc_no, sira_no, fiyat_tipi, gecelik_ucret FROM misafirler WHERE rezervasyon_id=?",
            (eski_rez_id,),
        ).fetchall()
        for m in misafirler:
            cur.execute(
                "INSERT INTO misafirler (rezervasyon_id, ad_soyad, tc_no, sira_no, fiyat_tipi, gecelik_ucret) "
                "VALUES (?,?,?,?,?,?)",
                (yeni_rez_id, m["ad_soyad"], m["tc_no"], m["sira_no"], m["fiyat_tipi"], m["gecelik_ucret"])
            )

        varsayilan_gecelik_toplam = eski["gecelik_ucret"] * eski["kisi_sayisi"]
        for i in range(kalan_gece):
            gun = (degisim + timedelta(days=i)).isoformat()
            eski_odeme = odeme_haritasi.get(gun)
            if eski_odeme:
                odendi = eski_odeme["odendi"]
                sekli = eski_odeme["odeme_sekli"]
                tutar = eski_odeme["tutar"]
            else:
                odendi = 0
                sekli = None
                tutar = varsayilan_gecelik_toplam
            cur.execute("""
                INSERT INTO odemeler (rezervasyon_id, tarih, tutar, odendi, odeme_sekli)
                VALUES (?,?,?,?,?)
            """, (yeni_rez_id, gun, tutar, odendi, sekli))

        conn.commit()
        loglama.islem_yaz("oda_degistir", f"{eski['ad_soyad']} rezervasyonu {degisim_tarihi} itibariyle {yeni_oda['kat_adi']} Oda {yeni_oda['oda_no']} odasına taşındı.")
        odeme_tutarlarini_guncelle(yeni_rez_id)
        return yeni_rez_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------- GÜNLÜK LİSTE / ODA DURUMU ----------------

def gunun_girisleri(tarih_str):
    """O gün check-in yapacak (ilk gecesi bu tarih olan) rezervasyonlar."""
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT r.*, o.oda_no, o.kat_adi
            FROM rezervasyonlar r JOIN odalar o ON r.oda_id = o.id
            WHERE r.giris_tarihi = ? AND r.iptal = 0
            ORDER BY o.kat_no, o.oda_no
        """, (tarih_str,)).fetchall()
        return rows
    finally:
        conn.close()


def gunun_oda_durumu(tarih_str):
    """Tüm odaların o günkü durumu: dolu/boş + o geceki ödeme durumu + oda durumu."""
    conn = get_connection()
    try:
        bugun = date.today().isoformat()
        rows = conn.execute("""
            SELECT o.id as oda_id, o.oda_no, o.kat_adi, o.kat_no, o.oda_tipi, o.kapasite,
                   o.durum as oda_durum, o.ariza_bitis,
                   r.id as rez_id, r.ad_soyad, r.tc_no, r.telefon,
                   r.kisi_sayisi, r.fiyat_tipi, r.checkin_yapildi, r.giris_tarihi, r.gece_sayisi,
                   od.id as odeme_id, od.tutar, od.odendi, od.odeme_sekli, od.odeme_notu,
                   CASE WHEN r.id IS NOT NULL THEN
                       CAST(julianday(date(r.giris_tarihi, '+' || r.gece_sayisi || ' day')) - julianday(?) AS INTEGER)
                   ELSE NULL END as kalan_gece
            FROM odalar o
            LEFT JOIN rezervasyonlar r ON r.oda_id = o.id AND r.iptal = 0
                   AND r.giris_tarihi <= ?
                   AND date(COALESCE(NULLIF(r.cikis_tarihi, ''),
                                     date(r.giris_tarihi, '+' || r.gece_sayisi || ' day'))) > ?
            LEFT JOIN odemeler od ON od.rezervasyon_id = r.id AND od.tarih = ?
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


def odeme_guncelle(odeme_id, odendi, odeme_sekli=None, odeme_notu=None):
    conn = get_connection()
    try:
        cur = conn.cursor()
        o = cur.execute(
            "SELECT od.*, r.ad_soyad, o2.oda_no FROM odemeler od "
            "JOIN rezervasyonlar r ON od.rezervasyon_id = r.id "
            "JOIN odalar o2 ON r.oda_id = o2.id WHERE od.id=?",
            (odeme_id,),
        ).fetchone()
        cur.execute("""
            UPDATE odemeler SET odendi=?, odeme_sekli=?, odeme_notu=? WHERE id=?
        """, (1 if odendi else 0, odeme_sekli, odeme_notu, odeme_id))
        conn.commit()
        if o:
            durum = "ödendi" if odendi else "ödendi değil"
            loglama.islem_yaz("odeme", f"{o['ad_soyad']} (Oda {o['oda_no']}, {o['tarih']} gecesi, {o['tutar']} TL): {durum}. Sekli: {odeme_sekli or 'Yok'}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def musaitlik_kontrol(oda_id, giris_tarihi, gece_sayisi, haric_rez_id=None):
    """Seçilen oda, tarih aralığında dolu mu diye kontrol eder.
    Çıkış yapılmış rezervasyonlar cikis_tarihi'ne kadar odayı tutar."""
    conn = get_connection()
    try:
        q = """
            SELECT r.id, r.ad_soyad, r.giris_tarihi, r.gece_sayisi
            FROM rezervasyonlar r
            WHERE r.oda_id = ? AND r.iptal = 0
              AND date(r.giris_tarihi) < date(?, '+' || ? || ' day')
              AND date(COALESCE(NULLIF(r.cikis_tarihi, ''),
                                date(r.giris_tarihi, '+' || r.gece_sayisi || ' day'))) > date(?)
        """
        params = [oda_id, giris_tarihi, gece_sayisi, giris_tarihi]
        if haric_rez_id:
            q += " AND r.id != ?"
            params.append(haric_rez_id)
        rows = conn.execute(q, params).fetchall()
        return rows
    finally:
        conn.close()


# ---------------- TAKVİM IZGARASI ----------------

def doluluk_haritasi(baslangic_str, gun_sayisi):
    """Belirtilen tarih aralığındaki tüm dolu gece kayıtlarını tek sorguda getirir.
    Çıkış yapılmış rezervasyonlar cikis_tarihi'ne kadar dolu sayılır
    (çıkış günü oda aynı gece yeni misafire verilebilir)."""
    baslangic = datetime.strptime(baslangic_str, "%Y-%m-%d").date()
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT r.id as rez_id, r.oda_id, r.ad_soyad, r.giris_tarihi, r.gece_sayisi,
                   r.cikis_tarihi, r.kisi_sayisi, r.fiyat_tipi, r.referans
            FROM rezervasyonlar r
            WHERE r.iptal = 0
              AND date(r.giris_tarihi) < date(?, '+' || ? || ' day')
              AND date(COALESCE(NULLIF(r.cikis_tarihi, ''),
                                date(r.giris_tarihi, '+' || r.gece_sayisi || ' day'))) > date(?)
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


# ---------------- TARİH DEĞİŞTİRME ----------------

def rezervasyon_tarih_degistir(rez_id, yeni_giris_tarihi, yeni_gece_sayisi):
    """Rezervasyonun tarih/gece sayısını değiştirir. Yeni tarih geçmişte olamaz.
    Yeni aralıkta cakisma olan rezervasyonlar engellenir.
    Ödemeler yeniden kurulur; zaten ödenmiş geceler TARİH EŞLEŞMESİNE göre korunur.
    Düşen (artık kapsamda olmayan) ödenmiş geceler için dondurulen listesi döndürülür.

    ODA DEĞİŞİKLİĞİ DENGESİ: Rezervasyon 'Oda Değiştir' ile ortadan bölünmüşse
    (iki ayrı rezervasyon, aynı misafir), bu parçalardan birinin tarihi/gece sayısı
    değiştirilirken diğer parça da otomatik dengelenir. Amaç: aynı anda iki odada
    görünme (çakışma) oluşmamalı ve toplam gece sayısı korunmalı."""
    bugun = date.today().isoformat()
    if yeni_giris_tarihi < bugun:
        raise ValueError("Geçmiş tarihe rezervasyon taşınamaz.")

    conn = get_connection()
    try:
        cur = conn.cursor()
        rez = cur.execute(
            "SELECT r.*, o.oda_no, o.kat_adi FROM rezervasyonlar r JOIN odalar o ON r.oda_id=o.id "
            "WHERE r.id=? AND r.iptal=0",
            (rez_id,),
        ).fetchone()
        if not rez:
            raise ValueError("Rezervasyon bulunamadı.")

        devam = _oda_degistirme_devami(cur, rez)
        oncesi = _oda_degistirme_oncesi(cur, rez)

        if devam:
            # İlk parça düzenleniyor: kesim (oda değişim) tarihi sabit kalır,
            # toplam gece sayısı iki parçaya paylaştırılır.
            kesim = devam["giris_tarihi"]
            if yeni_giris_tarihi >= kesim:
                raise ValueError(
                    f"Giriş tarihi ({yeni_giris_tarihi}) oda değişim tarihi olan "
                    f"{kesim}'den sonra kalamaz. Devam rezervasyonunun girişini düzenleyebilirsin."
                )
            ilk_gece = (datetime.strptime(kesim, "%Y-%m-%d").date()
                        - datetime.strptime(yeni_giris_tarihi, "%Y-%m-%d").date()).days
            if yeni_gece_sayisi <= ilk_gece:
                raise ValueError(
                    f"Gece sayısı, oda değişim tarihine kadar olan kısmı ({ilk_gece} gece) "
                    f"ancak kapsıyor; devam rezervasyonu kalması için "
                    f"en az {ilk_gece + 1} gece girilmelidir."
                )
            devam_gece = yeni_gece_sayisi - ilk_gece
            efektif_giris = yeni_giris_tarihi
            efektif_gece = ilk_gece
        else:
            efektif_giris = yeni_giris_tarihi
            efektif_gece = yeni_gece_sayisi
            devam_gece = None

        cakisma = _musaitlik_sorgusu(cur, rez["oda_id"], efektif_giris, efektif_gece, haric_rez_id=rez_id)
        if cakisma:
            isimler = ", ".join(c["ad_soyad"] for c in cakisma)
            raise ValueError(f"Bu tarihler hedef odada dolu: {isimler}.")

        dusen_odenmis = _odemeleri_yeniden_kur(cur, rez, efektif_giris, efektif_gece)
        cur.execute(
            "UPDATE rezervasyonlar SET giris_tarihi=?, gece_sayisi=? WHERE id=?",
            (efektif_giris, efektif_gece, rez_id),
        )

        ek_not = ""
        if devam:
            cakisma2 = _musaitlik_sorgusu(
                cur, devam["oda_id"], devam["giris_tarihi"], devam_gece, haric_rez_id=devam["id"])
            if cakisma2:
                isimler = ", ".join(c["ad_soyad"] for c in cakisma2)
                raise ValueError(f"Devam odası bu tarihlerde dolu: {isimler}.")
            dusen_odenmis += _odemeleri_yeniden_kur(
                cur, devam, devam["giris_tarihi"], devam_gece)
            cur.execute("UPDATE rezervasyonlar SET gece_sayisi=? WHERE id=?", (devam_gece, devam["id"]))
            ek_not += f" | devam oda id {devam['oda_id']}" + (f" -> {devam_gece} gece")

        if oncesi and not devam:
            yeni_oncesi_gece = (datetime.strptime(yeni_giris_tarihi, "%Y-%m-%d").date()
                                - datetime.strptime(oncesi["giris_tarihi"], "%Y-%m-%d").date()).days
            if yeni_giris_tarihi <= oncesi["giris_tarihi"]:
                raise ValueError(
                    "Yeni giriş tarihi, oda değişiminden önceki rezervasyonun başlangıcına "
                    "eşit veya öncesinde. Önceki rezervasyonun tarihi elle düzenlenmeli."
                )
            if yeni_oncesi_gece < oncesi["gece_sayisi"]:
                # devamın girişi öne alındı: önceki parçanın geceleri kesimden sonrasını
                # kapsamasın (çakışmayı önlemek için kısaltılır)
                cakisma3 = _musaitlik_sorgusu(
                    cur, oncesi["oda_id"], oncesi["giris_tarihi"], yeni_oncesi_gece,
                    haric_rez_id=oncesi["id"])
                if cakisma3:
                    isimler = ", ".join(c["ad_soyad"] for c in cakisma3)
                    raise ValueError(f"Önceki oda bu tarihlerde dolu: {isimler}.")
                dusen_odenmis += _odemeleri_yeniden_kur(
                    cur, oncesi, oncesi["giris_tarihi"], yeni_oncesi_gece)
                cur.execute(
                    "UPDATE rezervasyonlar SET gece_sayisi=? WHERE id=?",
                    (yeni_oncesi_gece, oncesi["id"]))
                ek_not += f" | önceki oda id {oncesi['oda_id']} -> {yeni_oncesi_gece} gece"

        conn.commit()
        loglama.islem_yaz(
            "rezervasyon_tarih",
            f"{rez['ad_soyad']} (Oda {rez['oda_no']}) tarihi değiştirildi: "
            f"{rez['giris_tarihi']}+{rez['gece_sayisi']} -> {efektif_giris}+{efektif_gece}{ek_not}",
        )
        odeme_tutarlarini_guncelle(rez_id)
        if devam:
            odeme_tutarlarini_guncelle(devam["id"])
        if oncesi and not devam:
            odeme_tutarlarini_guncelle(oncesi["id"])
        dusen_odenmis.sort()
        return dusen_odenmis
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------- İSTATİSTİK ----------------

def aylik_istatistik(ay, yil):
    """Belirli ay/yıl için istatistik: pazarlanan gece, gelir, iptaller, kayıp gece."""
    conn = get_connection()
    try:
        ay_bas = f"{yil:04d}-{ay:02d}-01"
        nxt = (datetime(yil, ay, 1) + timedelta(days=32)).replace(day=1)
        ay_son = (nxt - timedelta(days=1)).isoformat()

        # Satilan geceler + gelir: iptal edilmemis rezervasyonlarin
        # ilgili ay icindeki geceleri (odemeler tablosundaki satirlar)
        reklar = conn.execute("""
            SELECT od.*, r.ad_soyad FROM odemeler od
            JOIN rezervasyonlar r ON od.rezervasyon_id = r.id
            WHERE r.iptal = 0 AND od.tarih >= ? AND od.tarih <= ?
        """, (ay_bas, ay_son)).fetchall()
        satilan_gece = len(reklar)
        # gelir: tutar * (sayilan gece) - burada tutar hep gecelik toplamdir
        # odendi alanindan bagimsiz: satilan (satis degeri). Tahsilat degil.
        gelir = sum(o["tutar"] or 0 for o in reklar)

        # tahsil edilen (odendi=1) ay icindeki tutarlar
        tahsilat = sum(o["tutar"] or 0 for o in reklar if o["odendi"])

        iptal_rez = conn.execute("""
            SELECT r.* FROM rezervasyonlar r
            WHERE r.iptal = 1
              AND substr(r.olusturma_tarihi, 1, 10) >= ? AND substr(r.olusturma_tarihi, 1, 10) <= ?
        """, (ay_bas, ay_son)).fetchall()
        iptal_gece = sum(r["gece_sayisi"] for r in iptal_rez)

        # gun gecmemis/iptal olmayan ama gelmeyen rezervasyonlar o ayda (no-show)
        noshow_rez = conn.execute("""
            SELECT r.* FROM rezervasyonlar r
            WHERE r.iptal = 0 AND r.checkin_yapildi = 0
              AND substr(r.giris_tarihi, 1, 7) = ? AND substr(r.giris_tarihi, 1, 10) <= date('now')
        """, (f"{yil:04d}-{ay:02d}",)).fetchall()
        noshow_gece = sum(r["gece_sayisi"] for r in noshow_rez)

        # aktif rezervasyon sayisi (adet)
        rez_adedi = conn.execute("""
            SELECT COUNT(*) as c FROM rezervasyonlar r
            WHERE r.iptal = 0 AND substr(r.giris_tarihi, 1, 7) = ?
        """, (f"{yil:04d}-{ay:02d}",)).fetchone()["c"]

        return {
            "ay": f"{yil:04d}-{ay:02d}",
            "satilan_gece": satilan_gece,
            "gelir": gelir,
            "tahsilat": tahsilat,
            "iptal_gece": iptal_gece,
            "noshow_gece": noshow_gece,
            "rez_adedi": rez_adedi,
        }
    finally:
        conn.close()
