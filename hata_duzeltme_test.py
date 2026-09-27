# -*- coding: utf-8 -*-
"""
1.0.4.7 hata düzeltmeleri için izole regresyon testi (arayüzsüz).

27 Eylül 2026 kapsamlı testinde bulunan hataların geri gelmediğini doğrular:
çifte satış (iptal geri al), içerideki misafirin çıkışını geçmişe çekme,
KBS mükerrer/eksik bildirim, konaklamış rezervasyonun iptali, ileri tarihli
check-in, Oda Durumu'nda iptal satırı sızması, çıkış tarihi kontrolleri,
aynı oda iki dönem / A->B->A oda değişimi, temizlikte/arızalı odaya ileri
tarihli rezervasyon, yabancı sayısı, kullanıcı adı ve son aktif kullanıcı.

Kendi GEÇİCİ veritabanını kurar (TEMP altında); gerçek veriye DOKUNMAZ.
Çalıştırma: python hata_duzeltme_test.py
"""
import os
import sys
import shutil
import sqlite3
import tempfile
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TEST_KLASOR = os.path.join(tempfile.gettempdir(), "opencode", "hata_duzeltme_test")
if os.path.isdir(TEST_KLASOR):
    shutil.rmtree(TEST_KLASOR)
os.makedirs(TEST_KLASOR, exist_ok=True)

import database

database.VERI_KLASORU = TEST_KLASOR
database.DB_PATH = os.path.join(TEST_KLASOR, "misafirhane.db")
TAKIP = os.path.join(TEST_KLASOR, "kbs_takip.db")

# Eski (1.0.4.6) şemadaki tekil indeksi taklit et: init_db onu kaldırmalı.
_c = sqlite3.connect(database.DB_PATH)
_c.execute("CREATE TABLE rezervasyon_odalar (id INTEGER PRIMARY KEY AUTOINCREMENT, "
           "rezervasyon_id INTEGER NOT NULL, oda_id INTEGER NOT NULL, giris_tarihi TEXT NOT NULL, "
           "gece_sayisi INTEGER NOT NULL DEFAULT 1, cikis_tarihi TEXT, kisi_sayisi INTEGER NOT NULL DEFAULT 1, "
           "fiyat_tipi TEXT DEFAULT 'Sabit', gecelik_ucret INTEGER DEFAULT 1300, checkin_yapildi INTEGER DEFAULT 0)")
_c.execute("CREATE UNIQUE INDEX uk_rez_oda ON rezervasyon_odalar (rezervasyon_id, oda_id)")
_c.commit()
_c.close()

database.init_db()
database.varsayilan_odalari_yukle()

import repository as R
import kbs
import auth

B = date.today()


def g(n):
    return (B + timedelta(days=n)).isoformat()


O = {o["oda_no"]: o["id"] for o in R.oda_listesi()}
hatalar = []


def kontrol(kosul, mesaj):
    if not kosul:
        hatalar.append(mesaj)
        print("  [HATA]", mesaj)
    else:
        print("  [ok]  ", mesaj)


def hata_verir_mi(f):
    try:
        f()
    except ValueError:
        return True
    return False


def rez(oda_no, ofs, gece, ad="Test", kisi=1):
    rid = R.rezervasyon_olustur([dict(oda_id=O[oda_no], giris_tarihi=g(ofs), gece_sayisi=gece,
                                      kisi_sayisi=kisi, fiyat_tipi="Sabit")], ad, gecmis_kontrol=False)
    return rid, R.rezervasyon_odalar_listele(rid)[0]["id"]


YER = {"ad_soyad": "Ahmet Yilmaz", "tc_no": "10000000146", "fiyat_tipi": "Sabit", "gecelik_ucret": 1300}
YAB = {"ad_soyad": "Hans Muller", "tc_no": "C01X00T47", "fiyat_tipi": "Sabit", "gecelik_ucret": 1300,
       "uyruk": "DEU", "dogum_tarihi": "1980-01-01", "cinsiyet": "Erkek", "dogum_yeri": "Berlin",
       "belge_turu": "Pasaport"}

print("Şema")
idx = [r[1] for r in database.get_connection().execute("PRAGMA index_list(rezervasyon_odalar)")]
kontrol("uk_rez_oda" not in idx, "eski tekil (rezervasyon, oda) indeksi kaldırıldı")

print("Rezervasyon doğrulamaları")
temel = dict(oda_id=O[2], giris_tarihi=g(1), gece_sayisi=2, kisi_sayisi=1, fiyat_tipi="Sabit")
kontrol(hata_verir_mi(lambda: R.rezervasyon_olustur([dict(temel, gece_sayisi=0)], "X")), "0 gece reddedilir")
kontrol(hata_verir_mi(lambda: R.rezervasyon_olustur([dict(temel, kisi_sayisi=0)], "X")), "0 kişi reddedilir")
kontrol(hata_verir_mi(lambda: R.rezervasyon_olustur([temel], "  ")), "boş ad reddedilir")
kontrol(hata_verir_mi(lambda: R.rezervasyon_olustur([dict(temel, giris_tarihi="2026-13-45")], "X")),
        "bozuk tarih anlaşılır hata verir")
kontrol(hata_verir_mi(lambda: R.rezervasyon_olustur([temel, temel], "X")),
        "aynı oda aynı istekte çakışan tarihle iki kez eklenemez")
iki = R.rezervasyon_olustur([dict(temel, oda_id=O[8], giris_tarihi=g(5)),
                             dict(temel, oda_id=O[8], giris_tarihi=g(9))], "Iki Donem")
kontrol(len(R.rezervasyon_odalar_listele(iki)) == 2, "aynı oda iki ayrı dönemle tek rezervasyonda kaydedilir")

print("İptal / iptali geri al")
r1 = R.rezervasyon_olustur([temel], "Eski")
R.rezervasyon_iptal(r1)
R.rezervasyon_olustur([temel], "Yeni")
kontrol(hata_verir_mi(lambda: R.rezervasyon_iptal_geri_al(r1)), "oda başkasına satıldıysa iptal geri alınamaz")
kontrol(len(R.musaitlik_kontrol(O[2], g(1), 2)) == 1, "çifte satış oluşmadı")
oda2 = [x for x in R.gunun_oda_durumu(g(1)) if x["oda_no"] == 2]
kontrol(len(oda2) == 1 and oda2[0]["ad_soyad"] == "Yeni", "Oda Durumu'nda iptal satırı sızmıyor")
kontrol(len([x for x in R.gunun_checkin_durumu(g(1)) if x["oda_no"] == 2]) == 1,
        "Check-in durumunda iptal satırı sızmıyor")

print("Check-in / çıkış")
rf, rof = rez(4, 7, 2, "Gelecek")
kontrol(hata_verir_mi(lambda: R.odasi_misafirleri_kaydet_ve_checkin(rof, [YER])), "ileri tarihli check-in reddedilir")
kontrol(hata_verir_mi(lambda: R.odasi_checkin_yap(rof)), "ileri tarihli check-in (tekil) reddedilir")
R.odasi_misafirleri_kaydet(rof, [YER])
kontrol(not R.rezervasyon_odasi_getir(rof)["checkin_yapildi"], "ileri tarihli misafir listesi check-in olmadan kaydedilir")

ri, roi = rez(6, -3, 5, "Icerde")
R.odasi_misafirleri_kaydet_ve_checkin(roi, [YER])
kontrol(hata_verir_mi(lambda: R.rezervasyon_odasi_tarih_degistir(roi, g(-3), 1)),
        "içerideki misafirin planlı çıkışı geçmişe çekilemez")
kontrol(R.en_az_gece(g(-3)) == 3, "en_az_gece doğru hesaplanır")
R.rezervasyon_odasi_tarih_degistir(roi, g(-3), 3)
kontrol(True, "içerideki misafir bugün çıkacak şekilde kısaltılabilir")
kontrol(hata_verir_mi(lambda: R.rezervasyon_odasi_tarih_degistir(roi, g(-3), 0)), "0 gece reddedilir")
kontrol(hata_verir_mi(lambda: R.odasi_cikis_yap(roi, g(2))), "ileri tarihli çıkış reddedilir")
kontrol(hata_verir_mi(lambda: R.odasi_cikis_yap(roi, g(-10))), "girişten önceki çıkış reddedilir")
R.odasi_cikis_yap(roi)
kontrol(hata_verir_mi(lambda: R.odasi_cikis_yap(roi)), "ikinci kez çıkış reddedilir")
kontrol(hata_verir_mi(lambda: R.odasi_checkin_geri_al(roi)), "çıkışı yapılmış satırda check-in geri alınamaz")
kontrol(hata_verir_mi(lambda: R.rezervasyon_iptal(ri)), "konaklamış rezervasyon iptal edilemez")

print("Oda durumu (temizlikte/arızalı) ve oda değiştirme")
R.oda_durum_ayarla(O[18], "temizlikte")
kontrol(hata_verir_mi(lambda: R.rezervasyon_olustur([dict(temel, oda_id=O[18], giris_tarihi=g(0))], "X")),
        "temizlikteki odaya bugün rezervasyon verilmez")
R.rezervasyon_olustur([dict(temel, oda_id=O[18], giris_tarihi=g(10))], "Ileri")
kontrol(True, "temizlikteki odaya ileri tarihli rezervasyon verilir")
R.oda_durum_ayarla(O[18], "temiz")
R.oda_durum_ayarla(O[17], "arizali", 2)
kontrol(hata_verir_mi(lambda: R.rezervasyon_olustur([dict(temel, oda_id=O[17], giris_tarihi=g(1))], "X")),
        "arıza süresi içinde rezervasyon verilmez")
R.rezervasyon_olustur([dict(temel, oda_id=O[17], giris_tarihi=g(3))], "ArizaSonrasi")
kontrol(True, "arıza bittikten sonrası için rezervasyon verilir")

rg, rog = rez(15, -2, 5, "Gezgin")
R.odasi_misafirleri_kaydet_ve_checkin(rog, [dict(YER, ad_soyad="Ayse", tc_no="10000000528")])
_, yeni = R.oda_degistir(rog, O[16], g(0))
_, geri = R.oda_degistir(yeni, O[15], g(1))
kontrol(geri is not None, "A -> B -> A oda değişimi yapılabilir")

print("KBS")
rk, rok = rez(3, -1, 3, "KBS", kisi=2)
R.odasi_misafirleri_kaydet_ve_checkin(rok, [YER, YAB])
gi, _ = kbs.kbs_bekleyenler(database.DB_PATH, TAKIP)
kbs.kbs_markala(gi, "gonderildi", TAKIP)
R.odasi_misafirleri_kaydet(rok, [YER, dict(YAB, dogum_yeri="Munih")])
gi, _ = kbs.kbs_bekleyenler(database.DB_PATH, TAKIP)
kontrol(len(gi) == 0, "misafir bilgisi düzeltilince 'gönderildi' durumu korunur")
R.odasi_misafirleri_kaydet(rok, [YER])
gi, _ = kbs.kbs_bekleyenler(database.DB_PATH, TAKIP)
kontrol(len(gi) == 0, "misafir listeden çıkarılınca kalanın durumu korunur")

rd, rod = rez(9, -2, 5, "Devam")
R.odasi_misafirleri_kaydet_ve_checkin(rod, [dict(YER, ad_soyad="Ayse", tc_no="10000000528")])
kbs.kbs_markala(kbs.kbs_bekleyenler(database.DB_PATH, TAKIP)[0], "gonderildi", TAKIP)
_, yeni = R.oda_degistir(rod, O[12], g(0))
R.odasi_misafirleri_kaydet(yeni, [dict(YER, ad_soyad="Ayse", tc_no="10000000528"),
                                  dict(YER, ad_soyad="Hasan", tc_no="10000000900")])
gi, ci = kbs.kbs_bekleyenler(database.DB_PATH, TAKIP)
adlar = [x["misafir_ad"] for x in gi]
kontrol(adlar == ["Hasan"], "oda değişiminden sonra eklenen kişi KBS girişine düşer, taşınan kişi düşmez")
kontrol(not [x for x in ci if x["ro_id"] == rod], "oda değiştiren kişi için sahte çıkış üretilmez")

print("Yabancı sayısı")
ry, roy = rez(11, 0, 1, "Yab", kisi=2)
R.odasi_misafirleri_kaydet_ve_checkin(roy, [dict(YAB, tc_no="AB123456789"), dict(YAB, tc_no="99123456780")])
kontrol(R.rezervasyonlar_yabanci_sayilari([ry]).get(ry) == 2, "rakam içeren pasaport ve YKN yabancı sayılır")

print("Günlük bakım: gelmeyenler ve unutulmuş çıkışlar")
rg, rog = rez(1, -3, 2, "Gelmeyen")
rgb, _ = rez(5, 0, 2, "Bugun Gelecek")
rgg, _ = rez(7, -4, 1, "Geri Alinan")
rco = R.rezervasyon_olustur([dict(oda_id=O[10], giris_tarihi=g(-2), gece_sayisi=3, kisi_sayisi=1, fiyat_tipi="Sabit"),
                             dict(oda_id=O[13], giris_tarihi=g(-2), gece_sayisi=3, kisi_sayisi=1, fiyat_tipi="Sabit")],
                            "Cok Odali Yarim", gecmis_kontrol=False)
R.odasi_misafirleri_kaydet_ve_checkin(R.rezervasyon_odalar_listele(rco)[0]["id"],
                                      [dict(YER, ad_soyad="Cok Oda", tc_no="10000000146")])
rs, ros = rez(14, -5, 2, "Cikisi Unutulan")
R.odasi_misafirleri_kaydet_ve_checkin(ros, [dict(YER, ad_soyad="Unutulan", tc_no="10000000146")])
kontrol([x["rezervasyon_id"] for x in R.erken_cikis_adaylari(g(0)) if x["id"] == ros] == [],
        "planlı çıkışı geçmiş kalış Erken Çıkış'ta görünmez")
aday = [r["id"] for r in R.gelmeyen_rezervasyonlar()]
kontrol(rg in aday and rgg in aday, "giriş günü geçen, gelmeyen rezervasyon sorulacaklar listesinde")
kontrol(rgb not in aday, "giriş günü bugün olan rezervasyon sorulmaz")
kontrol(rco not in aday, "odalarından biri check-in yapmış çok odalı rezervasyon sorulmaz")
R.gunluk_bakim()
def rez_satir(rid):
    return database.get_connection().execute("SELECT iptal, iptal_nedeni FROM rezervasyonlar WHERE id=?", (rid,)).fetchone()
kontrol(rez_satir(rg)["iptal"] == 0, "günlük bakım gelmeyeni kendiliğinden iptal etmez")
R.gelmeyenleri_iptal_et([rg, rgg])
R.rezervasyon_iptal_geri_al(rgg)
kontrol(tuple(rez_satir(rg)) == (1, "gelmedi"), "kullanıcı onaylayınca 'gelmedi' olarak iptal edilir")
kontrol(tuple(rez_satir(rgg)) == (0, "geri_alindi"), "iptali geri alınan gelmeyen bir daha sorulmaz")
rgh, _ = rez(7, -2, 1, "Iptal Edilmesin")
R.gelmeyenleri_iptal_etme([rgh])
kalan = [r["id"] for r in R.gelmeyen_rezervasyonlar()]
kontrol(rgg not in kalan and rgh not in kalan, "'iptal edilmesin' denen rezervasyon aktif kalır, tekrar sorulmaz")
etiket = next(r["durum_etiket"] for r in R.rezervasyon_listesi("hepsi") if r["id"] == rg)
kontrol(etiket.startswith("Gelmedi"), "iptal edilen gelmeyen 'Gelmedi' etiketiyle görünür")
kapali = database.get_connection().execute("SELECT cikis_tarihi FROM rezervasyon_odalar WHERE id=?", (ros,)).fetchone()[0]
kontrol(kapali == g(-3), "çıkışı unutulan kalış planlı çıkış tarihiyle kapatılır")
kontrol(R.gunluk_bakim() == 0, "bakım ikinci kez çalışınca bir şey değiştirmez")

print("Kullanıcılar")
auth.kullanici_ekle("İSMAİL", "1234")
kontrol(auth.kullanici_dogrula("ismail", "1234") is not None, "'İSMAİL' hesabına 'ismail' ile girilebilir")
kontrol(auth.kullanici_dogrula("İsmail", "1234") is not None, "'İsmail' ile de girilebilir")
kontrol(hata_verir_mi(lambda: auth.sifre_degistir(1, "")), "boş şifre reddedilir")
tek = auth.kullanici_listesi()[0]["id"]
kontrol(hata_verir_mi(lambda: auth.kullanici_aktiflik_degistir(tek, False)), "son aktif kullanıcı pasif yapılamaz")

print()
if hatalar:
    print("BAŞARISIZ:", len(hatalar))
    sys.exit(1)
print("TUM HATA DUZELTME TESTLERI GECTI")
