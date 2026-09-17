# -*- coding: utf-8 -*-
"""
GİRİŞ SORUNU TEŞHİS SCRIPTİ.
"Kullanıcı adı veya şifre hatalı" hatası alıyorsan, aynı klasörde şunu çalıştır:

    python giris_kontrol.py

Bu, hangi veritabanı dosyasının kullanıldığını, içinde hangi kullanıcıların
kayıtlı olduğunu gösterir ve istersen komut satırından bir kullanıcı adı/şifre
kombinasyonunu deneyip sonucu (başarılı/başarısız) doğrudan söyler.

EN SIK GÖRÜLEN NEDEN: Birden fazla "misafirhane_app" klasörün olması (örn.
Masaüstünde bir tane, İndirilenler'de bir tane) ve "test_verisi_olustur.py"
ile "main.py"yi FARKLI klasörlerde çalıştırmış olman — her klasörün kendi
"misafirhane.db" dosyası olur, kullanıcılar farklı dosyalarda kalır.
"""

import os
import database
import auth


def main():
    print("=" * 60)
    print("VERİTABANI DOSYASI:")
    print(f"  {database.DB_PATH}")
    print(f"  Dosya var mı: {os.path.exists(database.DB_PATH)}")
    if os.path.exists(database.DB_PATH):
        boyut = os.path.getsize(database.DB_PATH)
        print(f"  Dosya boyutu: {boyut} bayt")
    print("=" * 60)

    database.init_db()

    kullanicilar = auth.kullanici_listesi()
    print(f"\nKAYITLI KULLANICILAR ({len(kullanicilar)} adet):")
    if not kullanicilar:
        print("  (Hiç kullanıcı yok! Önce 'python test_verisi_olustur.py' çalıştır")
        print("   ya da uygulamayı açıp 'İlk Kullanıcıyı Oluştur' ekranından bir hesap yap.)")
    for k in kullanicilar:
        durum = "Aktif" if k["aktif"] else "PASİF (bu yüzden giriş yapamaz!)"
        print(f"  - kullanıcı adı: '{k['kullanici_adi']}'  |  Ad Soyad: {k['ad_soyad']}  |  {durum}")

    print("\n" + "=" * 60)
    print("GİRİŞ DENEMESİ")
    print("=" * 60)
    kadi = input("Kullanıcı adı: ")
    sifre = input("Şifre: ")

    sonuc = auth.kullanici_dogrula(kadi, sifre)
    print()
    if sonuc:
        print(f"✓ BAŞARILI — Giriş yapabilirsin: {sonuc['ad_soyad'] or sonuc['kullanici_adi']}")
    else:
        print("✗ BAŞARISIZ — Kullanıcı adı veya şifre yanlış.")
        print("  Kontrol et: kullanıcı adı yukarıdaki listede birebir aynı mı?")
        print("  (Büyük/küçük harf önemli değil ama boşluk/yazım hatası olabilir.)")


if __name__ == "__main__":
    main()
