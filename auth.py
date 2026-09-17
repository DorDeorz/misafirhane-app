# -*- coding: utf-8 -*-
"""
Kullanıcı girişi ve şifre doğrulama.
Resepsiyonda çalışan herkes kendi kullanıcı adı/şifresiyle giriş yapar;
amaç yetki kısıtlamak değil, hangi rezervasyonu kimin aldığını takip etmektir
(herkesin yetkisi aynıdır).
"""

import hashlib
import os
from database import get_connection


def _sifre_hashle(sifre, tuz_hex=None):
    if tuz_hex is None:
        tuz_hex = os.urandom(16).hex()
    tuz_bytes = bytes.fromhex(tuz_hex)
    hash_bytes = hashlib.pbkdf2_hmac("sha256", sifre.encode("utf-8"), tuz_bytes, 100_000)
    return hash_bytes.hex(), tuz_hex


def _sifre_dogrula(sifre, hash_hex, tuz_hex):
    hesaplanan, _ = _sifre_hashle(sifre, tuz_hex)
    return hesaplanan == hash_hex


def kullanici_var_mi():
    conn = get_connection()
    try:
        c = conn.execute("SELECT COUNT(*) as c FROM kullanicilar WHERE aktif=1").fetchone()["c"]
        return c > 0
    finally:
        conn.close()


def kullanici_listesi():
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, kullanici_adi, ad_soyad, aktif FROM kullanicilar ORDER BY kullanici_adi"
        ).fetchall()
        return rows
    finally:
        conn.close()


def kullanici_ekle(kullanici_adi, sifre, ad_soyad=""):
    kullanici_adi = kullanici_adi.strip().lower()
    sifre = sifre.strip()
    if not kullanici_adi or not sifre:
        raise ValueError("Kullanıcı adı ve şifre boş olamaz.")
    hash_hex, tuz_hex = _sifre_hashle(sifre)
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO kullanicilar (kullanici_adi, sifre_hash, tuz, ad_soyad) VALUES (?,?,?,?)",
            (kullanici_adi, hash_hex, tuz_hex, ad_soyad.strip())
        )
        conn.commit()
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        if "UNIQUE" in str(e):
            raise ValueError("Bu kullanıcı adı zaten kayıtlı.")
        raise
    finally:
        conn.close()


def kullanici_dogrula(kullanici_adi, sifre):
    """Doğruysa kullanıcı satırını (id, kullanici_adi, ad_soyad) döner, değilse None."""
    kullanici_adi = kullanici_adi.strip().lower()
    sifre = sifre.strip()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM kullanicilar WHERE kullanici_adi=? AND aktif=1", (kullanici_adi,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    if _sifre_dogrula(sifre, row["sifre_hash"], row["tuz"]):
        return row
    return None


def sifre_degistir(kullanici_id, yeni_sifre):
    yeni_sifre = yeni_sifre.strip()
    hash_hex, tuz_hex = _sifre_hashle(yeni_sifre)
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE kullanicilar SET sifre_hash=?, tuz=? WHERE id=?",
            (hash_hex, tuz_hex, kullanici_id)
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def kullanici_aktiflik_degistir(kullanici_id, aktif):
    conn = get_connection()
    try:
        conn.execute("UPDATE kullanicilar SET aktif=? WHERE id=?", (1 if aktif else 0, kullanici_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
