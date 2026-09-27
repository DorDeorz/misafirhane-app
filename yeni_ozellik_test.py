# -*- coding: utf-8 -*-
"""
1.0.5 yeni özellikleri için izole test (iş katmanı + offscreen arayüz açılışı).

Kapsam: gün sonu kasa raporu (tahsil zamanı/eden), açık borçlar ve toplu
tahsilat, tekrar gelen misafir (telefon/TC eşleşmesi), misafir kartı (not +
sorunlu uyarısı), hesap dökümü (PDF), günün özeti, genişletilmiş istatistik,
eski veritabanından otomatik şema güncellemesi.

Kendi GEÇİCİ veritabanını kurar (TEMP altında); gerçek veriye DOKUNMAZ.
Çalıştırma: python yeni_ozellik_test.py
"""
import os
import sys
import shutil
import sqlite3
import tempfile
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

TEST_KLASOR = os.path.join(tempfile.gettempdir(), "opencode", "yeni_ozellik_test")
if os.path.isdir(TEST_KLASOR):
    shutil.rmtree(TEST_KLASOR)
os.makedirs(TEST_KLASOR, exist_ok=True)

import database

database.VERI_KLASORU = TEST_KLASOR
database.DB_PATH = os.path.join(TEST_KLASOR, "misafirhane.db")

# Eski şemadaki (1.0.4.7 ve öncesi) odemeler tablosu: init_db yeni kolonları eklemeli.
_c = sqlite3.connect(database.DB_PATH)
_c.execute("CREATE TABLE odemeler (id INTEGER PRIMARY KEY AUTOINCREMENT, rezervasyon_oda_id INTEGER NOT NULL, "
           "tarih TEXT NOT NULL, tutar INTEGER NOT NULL, odendi INTEGER DEFAULT 0, odeme_sekli TEXT, odeme_notu TEXT)")
_c.commit()
_c.close()

database.init_db()
database.varsayilan_odalari_yukle()

import repository as R
import loglama

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


def rez(oda_no, ofs, gece, ad="Test", telefon="", referans="", kisi=1):
    rid = R.rezervasyon_olustur([dict(oda_id=O[oda_no], giris_tarihi=g(ofs), gece_sayisi=gece,
                                      kisi_sayisi=kisi, fiyat_tipi="Sabit")], ad, telefon=telefon,
                                referans=referans, gecmis_kontrol=False)
    return rid, R.rezervasyon_odalar_listele(rid)[0]["id"]


def odemeler(ro_id):
    return {o["tarih"]: o for o in R.odasi_odemeler(ro_id)}


YER = {"ad_soyad": "Ahmet Yilmaz", "tc_no": "10000000146", "fiyat_tipi": "Sabit", "gecelik_ucret": 1300}

loglama.set_aktif_kullanici("oğuz")

print("Şema")
_kol = [r[1] for r in sqlite3.connect(database.DB_PATH).execute("PRAGMA table_info(odemeler)")]
kontrol("tahsil_zamani" in _kol and "tahsil_eden" in _kol, "eski odemeler tablosuna tahsil kolonları eklendi")
_tab = [r[0] for r in sqlite3.connect(database.DB_PATH).execute("SELECT name FROM sqlite_master WHERE type='table'")]
kontrol("misafir_kartlari" in _tab, "misafir_kartlari tablosu oluştu")

print("Gün sonu kasa")
ria, roa = rez(1, -2, 3, ad="Ali Veli", telefon="0532 111 22 33", referans="Başkan Ahmet Bey")
R.odasi_misafirleri_kaydet_ve_checkin(roa, [YER])
od = odemeler(roa)
R.odeme_guncelle(od[g(-2)]["id"], True, "Kredi Karti")
kasa = R.gun_sonu_kasa(g(0))
kontrol(len(kasa["satirlar"]) == 1 and kasa["toplam"] == 1300, "bugün tahsil edilen gece kasada görünür")
kontrol(kasa["satirlar"][0]["gece"] == g(-2), "kasa gecenin değil tahsilin gününe göre (geçmiş gece bugün ödendi)")
kontrol(kasa["sekiller"] == {"Kredi Karti": 1300} and kasa["kullanicilar"] == {"oğuz": 1300},
        "ödeme şekli ve tahsil edene göre toplamlar")
ilk_zaman = odemeler(roa)[g(-2)]["tahsil_zamani"]
R.odeme_guncelle(od[g(-2)]["id"], True, "Havale/IBAN")
kontrol(odemeler(roa)[g(-2)]["tahsil_zamani"] == ilk_zaman, "şekil değişince ilk tahsil zamanı korunur")
R.odeme_guncelle(od[g(-2)]["id"], False)
kontrol(odemeler(roa)[g(-2)]["tahsil_zamani"] is None and not R.gun_sonu_kasa(g(0))["satirlar"],
        "ödendi kaldırılınca kasadan düşer")
kontrol(not R.gun_sonu_kasa(g(-1))["satirlar"], "başka gün boş")
R.odeme_guncelle(od[g(-2)]["id"], True, "Kredi Karti")

print("Açık borçlar")
borc = R.acik_borclar()
kontrol(len(borc) == 1 and borc[0]["gece_adedi"] == 1 and borc[0]["borc"] == 1300,
        "yalnız kalınmış ödenmemiş gece (bu gece hariç) borç sayılır")
rib, rob = rez(2, 1, 2, ad="Gelecek Misafir")
kontrol(all(b["ro_id"] != rob for b in R.acik_borclar()), "check-in yapılmamış satır borç sayılmaz")
adet, tutar = R.odasi_borclarini_tahsil_et(roa, "Havale/IBAN")
kontrol((adet, tutar) == (1, 1300) and not R.acik_borclar(), "toplu tahsilat borcu kapatır")
kontrol(R.gun_sonu_kasa(g(0))["toplam"] == 2600, "toplu tahsilat kasaya girer")
kontrol(odemeler(roa)[g(0)]["odendi"] == 0, "bu gecenin ücreti toplu tahsilata dahil edilmez")

print("Tahsil bilgisi korunur")
R.rezervasyon_odasi_tarih_degistir(roa, g(-2), 4)
kontrol(odemeler(roa)[g(-2)]["tahsil_zamani"] == ilk_zaman or odemeler(roa)[g(-2)]["tahsil_eden"] == "oğuz",
        "gece uzatınca ödenmiş gecenin tahsil bilgisi korunur")
R.odeme_guncelle(odemeler(roa)[g(0)]["id"], True, "Kredi Karti")
_, yeni_ro = R.oda_degistir(roa, O[3], g(0))
tasinan = odemeler(yeni_ro)[g(0)]
kontrol(tasinan["odendi"] == 1 and tasinan["tahsil_eden"] == "oğuz" and tasinan["tahsil_zamani"],
        "oda değiştirmede taşınan ödenmiş gecenin tahsil bilgisi korunur")

print("Tekrar gelen misafir")
kontrol(R.telefon_anahtari("+90 532 111 22 33") == R.telefon_anahtari("0532 111 2233") == "5321112233",
        "telefon farklı yazımlarda aynı anahtar")
gecmis = R.misafir_gecmisi(telefon="532 111 22 33")
kontrol(len(gecmis) == 1 and gecmis[0]["rez_id"] == ria, "aynı telefonla önceki konaklama bulunur")
kontrol(not R.misafir_gecmisi(telefon="0532 111 22 33", haric_rez_id=ria), "haric_rez_id kendi kaydını dışlar")
rez(4, 3, 1, ad="Hiç Gelmemiş", telefon="0555 000 00 00")
kontrol(not R.misafir_gecmisi(telefon="0555 000 00 00"), "check-in yapılmamış rezervasyon konaklama sayılmaz")
kontrol(len(R.misafir_gecmisi(tc_no="10000000146")) == 1, "check-in'deki misafir TC'si ile de bulunur")
kontrol(not R.misafir_gecmisi(telefon="12"), "kısa numara eşleşme yapmaz")

print("Misafir kartı")
kontrol(hata_verir_mi(lambda: R.misafir_karti_kaydet("", "", "X", "not", False)), "telefon/TC olmadan kart reddedilir")
R.misafir_karti_kaydet("0532 111 22 33", "", "Ali Veli", "Gürültü yaptı", True)
kart = R.misafir_karti_getir(telefon="+905321112233")
kontrol(kart and kart["sorunlu"] == 1 and kart["notu"] == "Gürültü yaptı", "kart telefonla bulunur")
R.misafir_karti_kaydet("0532 111 22 33", "10000000146", "Ali Veli", "Sorun çözüldü", False)
kontrol(R.misafir_karti_getir(tc_no="10000000146")["notu"] == "Sorun çözüldü", "kart güncellenir, TC ile de bulunur")
kontrol(len(database.get_connection().execute("SELECT * FROM misafir_kartlari").fetchall()) == 1,
        "güncelleme yeni kart açmaz")
R.misafir_karti_kaydet("0532 111 22 33", "", "Ali Veli", "", False)
kontrol(R.misafir_karti_getir(telefon="05321112233") is None, "boş not + sorunsuz kartı siler")

print("Hesap dökümü verisi")
v = R.hesap_dokumu_verisi(ria)
kontrol(len(v["odalar"]) == 2 and v["toplam"] == 4 * 1300, "iki oda parçası, 4 gece toplam")
kontrol(v["odenen"] == 3 * 1300 and v["kalan"] == 1300, "ödenen/kalan doğru")
kontrol(R.hesap_dokumu_verisi(999999) is None, "olmayan rezervasyon None")

print("Günün özeti")
oz = R.gunun_ozeti()
kontrol(oz["dolu_oda"] == 1, "içerideki oda sayısı")
kontrol(oz["bos_temiz"] + oz["bos_temizlikte"] + oz["bos_arizali"] == len(O) - 1, "boş odalar toplamı")
kontrol(oz["borc_adedi"] == 0, "borç yok")

print("İstatistik")
s = R.aylik_detay_istatistik(B.month, B.year)
gun = int(R._ay_araligi(B.month, B.year)[1][-2:])
kontrol(s["aktif_oda"] == len(O) and s["doluluk"] == round(100.0 * s["satilan_gece"] / (len(O) * gun), 1) > 0,
        "doluluk = satılan gece / (aktif oda × ayın günü)")
kontrol(s["ort_gecelik"] == 1300, "ortalama gecelik fiyat")
kontrol(any(r["referans"] == "Başkan Ahmet Bey" for r in s["referanslar"]), "referans dağılımı")
kontrol(sum(t for _, t in s["tahsilat_sekilleri"]) == s["tahsilat"], "şekil dağılımı toplamı tahsilata eşit")
bos = R.aylik_detay_istatistik(1, 2020)
kontrol(bos["doluluk"] == 0 and bos["ort_gecelik"] == 0, "boş ayda sıfıra bölme yok")

print("Arayüz (offscreen)")
from PySide6.QtWidgets import QApplication
uyg = QApplication.instance() or QApplication(sys.argv)
import hesap_dokumu
pdf = os.path.join(TEST_KLASOR, "dokum.pdf")
hesap_dokumu.hesap_dokumu_pdf(ria, pdf)
with open(pdf, "rb") as f:
    kontrol(f.read(4) == b"%PDF" and os.path.getsize(pdf) > 1000, "hesap dökümü PDF üretildi")
kontrol("Ali Veli" in hesap_dokumu.hesap_dokumu_html(ria), "dökümde misafir adı var")

import main
from kasa_pencere import KasaPenceresi
from detay_dialog import RezervasyonDetayDialog
database.set_ayar("acilis_ozeti", "0")
p = KasaPenceresi()
kontrol(p.kasa_tablo.rowCount() == 3, "kasa penceresi bugünkü 3 tahsilatı listeler")
d = main.GunOzetiDialog(R.gunun_ozeti(), {"giris_bekleyen": 1, "cikis_bekleyen": 0, "toplam_bekleyen": 1})
kontrol(d.windowTitle().startswith("Günün Özeti"), "günün özeti penceresi açılır")
ist = main.IstatistikTab()
kontrol(ist.tablo.rowCount() == len(ist.METRIKLER) and ist.ref_tablo.rowCount() >= 1, "istatistik sekmesi dolar")
R.misafir_karti_kaydet("0532 111 22 33", "", "Ali Veli", "Kara liste", True)
dd = RezervasyonDetayDialog(ria)
kontrol(dd.kart_sorunlu.isChecked() and dd.kart_notu.toPlainText() == "Kara liste", "detayda misafir kartı görünür")
yr = main.YeniRezervasyonTab()
yr.telefon.setText("+90 532 111 22 33")
yr._misafiri_tani()
kontrol(yr._misafir_sorunlu and yr.ad_soyad.text() == "Ali Veli" and not yr.misafir_bilgi.isHidden(),
        "yeni rezervasyonda tekrar gelen + sorunlu misafir uyarısı, ad otomatik dolar")
from PySide6.QtCore import Qt
print("Çıkış ekranında çift tıkla tahsil + çıkış")
import detay_dialog
from PySide6.QtWidgets import QMessageBox
ric, roc = rez(9, -2, 2, ad="Borclu Cikan")
R.odasi_misafirleri_kaydet_ve_checkin(roc, [dict(YER, ad_soyad="Borclu Cikan")])
_orj = (QMessageBox.question, QMessageBox.information, QMessageBox.warning)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
QMessageBox.information = staticmethod(lambda *a, **k: None)
QMessageBox.warning = staticmethod(lambda *a, **k: None)
try:
    ct = main.CikisTab()
    ct._odeme_sekli_sec = lambda: ("Havale/IBAN", True)
    satir = [i for i in range(ct.tablo.rowCount()) if ct.tablo.item(i, 0).data(Qt.UserRole) == roc]
    kontrol(len(satir) == 1 and ct.tablo.item(satir[0], 5).text() == "2,600₺", "çıkış listesinde borç görünür")
    onceki_kasa = R.gun_sonu_kasa(g(0))["toplam"]
    ct._cift_tik_tahsil_cikis(ct.tablo, satir[0])
    od_c = odemeler(roc)
    kontrol(all(o["odendi"] and o["odeme_sekli"] == "Havale/IBAN" for o in od_c.values()) and len(od_c) == 2,
            "çift tık borcu seçilen şekille tahsil eder")
    kontrol(R.gun_sonu_kasa(g(0))["toplam"] == onceki_kasa + 2600, "çift tık tahsilatı kasaya girer")
    ro_c = [r for r in R.rezervasyon_odalar_listele(ric) if r["id"] == roc][0]
    kontrol(ro_c["cikis_tarihi"] == g(0), "tahsilattan sonra çıkış yapılır")
    kontrol(all(ct.tablo.item(i, 0).data(Qt.UserRole) != roc for i in range(ct.tablo.rowCount())),
            "çıkış yapılan satır listeden düşer")
    rid2, ro2 = rez(10, -1, 1, ad="Vazgecen")
    R.odasi_misafirleri_kaydet_ve_checkin(ro2, [dict(YER, ad_soyad="Vazgecen")])
    ct.yenile()
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.No)
    s2 = [i for i in range(ct.tablo.rowCount()) if ct.tablo.item(i, 0).data(Qt.UserRole) == ro2][0]
    ct._cift_tik_tahsil_cikis(ct.tablo, s2)
    kontrol(not any(o["odendi"] for o in odemeler(ro2).values())
            and not [r for r in R.rezervasyon_odalar_listele(rid2) if r["id"] == ro2][0]["cikis_tarihi"],
            "tahsilattan vazgeçilirse ne ödeme ne çıkış yapılır")
finally:
    QMessageBox.question, QMessageBox.information, QMessageBox.warning = _orj

ana = main.AnaPencere()
kontrol(ana.tabs.count() == 11, "ana pencere açılır")

print()
if hatalar:
    print(f"{len(hatalar)} HATA:")
    for h in hatalar:
        print(" -", h)
    sys.exit(1)
print("TUM YENI OZELLIK TESTLERI GECTI")
