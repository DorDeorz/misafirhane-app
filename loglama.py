# -*- coding: utf-8 -*-
"""
İşlem geçmişi (denetim izi) kaydı.
Her önemli işlem (rezervasyon alma/iptal, oda değişimi, check-in/çıkış,
ödeme, oda durumu, fiyat değişikliği vb.) "kim, ne zaman, ne yaptı"
şeklinde islem_gecmisi tablosuna yazılır.

Kullanıcı bilgisi, giriş yapan kullanıcı globalde tutulur; giriş ekranında
set_aktif_kullanici() ile ayarlanır, çıkışta sıfırlanır.
"""

from database import get_connection

AKTIF_KULLANICI = None


def set_aktif_kullanici(kullanici_adi):
    global AKTIF_KULLANICI
    AKTIF_KULLANICI = kullanici_adi


def islem_yaz(tur, detay, kullanici=None):
    """Bir işlemi geçmişe kaydeder. Kayıt başarısız olursa sessizce atlanır."""
    try:
        k = kullanici if kullanici is not None else AKTIF_KULLANICI
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO islem_gecmisi (kullanici, tur, detay) VALUES (?,?,?)",
                (k, tur, detay),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


def son_islemler(limit=500, tur=None):
    conn = get_connection()
    try:
        if tur:
            rows = conn.execute(
                "SELECT * FROM islem_gecmisi WHERE tur=? ORDER BY id DESC LIMIT ?",
                (tur, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM islem_gecmisi ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return rows
    finally:
        conn.close()


def islem_turleri():
    conn = get_connection()
    try:
        rows = conn.execute("SELECT DISTINCT tur FROM islem_gecmisi ORDER BY tur").fetchall()
        return [r["tur"] for r in rows]
    finally:
        conn.close()