# -*- coding: utf-8 -*-
"""
Excel'e aktarma işlemleri. openpyxl kullanır.
Tek yönlü aktarım: sistemdeki veriyi Excel'e yazar (rapor/yedek amaçlı).
Excel dosyası düzenlenip geri sisteme YÜKLENMEZ — asıl veri her zaman
misafirhane.db dosyasındadır.
"""

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from datetime import datetime

import repository
from database import fiyat_tipi_goster


_TEHLIKELI_ON_EK = ("=", "+", "-", "@", "\t", "\r")


def _guvenli_hucre(deger):
    """Excel formül enjeksiyonuna karşı: elle girilen (ad soyad, TC/belge no,
    telefon, referans, not gibi) hücre değerleri '='/'+'/'-'/'@' ile başlıyorsa
    Excel bunu formül sanmasın diye başına tek tırnak eklenir (bkz. kbs.py
    _guvenli_hucre — aynı koruma burada da uygulanır)."""
    if deger is None:
        return deger
    s = str(deger)
    if s.startswith(_TEHLIKELI_ON_EK):
        return "'" + s
    return s


def _baslik_satiri_yaz(ws, basliklar):
    ws.append(basliklar)
    for col in range(1, len(basliklar) + 1):
        hucre = ws.cell(row=1, column=col)
        hucre.font = Font(bold=True, color="FFFFFF")
        hucre.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        hucre.alignment = Alignment(horizontal="center")


def rezervasyonlari_disa_aktar(dosya_yolu, durum="aktif", satirlar=None):
    """Tüm rezervasyon listesini (aktif/iptal/hepsi) Excel'e yazar.
    satirlar verilirse (örn. arama/sıralama uygulanmış özel bir liste),
    durum parametresi yerine doğrudan o liste kullanılır."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Rezervasyonlar"

    basliklar = [
        "ID", "Oda", "Ad Soyad", "TC No", "Telefon", "Kişi Sayısı",
        "Giriş Tarihi", "Toplam Gece", "Çıkış Tarihi", "Fiyat Tipi",
        "Toplam Tutar (TL)", "Referans", "Oda Sayısı", "Alan Kullanıcı",
        "Alınma Tarihi", "Durum", "Notlar"
    ]
    _baslik_satiri_yaz(ws, basliklar)

    rez_notlari = repository.notlar_metni("rezervasyon")
    rows = satirlar if satirlar is not None else repository.rezervasyon_listesi(durum)
    if satirlar is None and durum == "gelmedi":
        rows = [r for r in repository.rezervasyon_listesi("hepsi")
                if r["iptal_nedeni"] == "gelmedi"
                or (not r["iptal"] and (r["gelmedi_odasi"] or 0) > 0)]
    ozet = repository.rezervasyonlari_toplam_ozeti([r["id"] for r in rows]) if rows else {}
    for r in rows:
        o = ozet.get(r["id"]) or {}
        toplam = o.get("toplam", 0)
        fiyat_birimleri = sorted({fiyat_tipi_goster(t) for t in o.get("fiyat_tipleri", set())})
        fiyat_metni = " + ".join(fiyat_birimleri) if fiyat_birimleri else "-"
        ws.append([
            r["id"], r["oda_ozeti"] or "-", _guvenli_hucre(r["ad_soyad"]), _guvenli_hucre(r["tc_no"] or ""),
            _guvenli_hucre(r["telefon"] or ""), r["toplam_kisi"], r["giris_tarihi"], r["toplam_gece"],
            r["cikis_tarihi"] or "", fiyat_metni, toplam,
            _guvenli_hucre(r["referans"] or ""), r["oda_sayisi"], r["olusturan_kullanici"] or "",
            r["olusturma_tarihi"] or "", r["durum_etiket"] or "", _guvenli_hucre(rez_notlari.get(str(r["id"]), ""))
        ])

    for col_letter, genislik in zip(
        "ABCDEFGHIJKLMNOPQ", [5, 28, 22, 14, 14, 8, 12, 10, 12, 12, 14, 18, 9, 14, 16, 16, 30]
    ):
        ws.column_dimensions[col_letter].width = genislik

    wb.save(dosya_yolu)
    return len(rows)


def gunluk_durumu_disa_aktar(dosya_yolu, tarih_str):
    """Belirli bir günün oda durumunu (doluluk + ödeme) Excel'e yazar."""
    wb = Workbook()
    ws = wb.active
    ws.title = f"Oda Durumu {tarih_str}"

    basliklar = [
        "Kat", "Oda No", "Durum", "Ad Soyad", "TC No", "Telefon",
        "Kişi Sayısı", "Fiyat Tipi", "Gecelik Tutar", "Ödeme Durumu", "Ödeme Şekli"
    ]
    _baslik_satiri_yaz(ws, basliklar)

    rows = repository.gunun_oda_durumu(tarih_str)
    for r in rows:
        dolu_mu = r["rez_id"] is not None
        if dolu_mu:
            durum_metni = "Dolu"
        else:
            oda_durum = r.get("aktif_durum") or "temiz"
            if oda_durum == "temizlikte":
                durum_metni = "Boş (Temizlikte)"
            elif oda_durum == "arizali":
                durum_metni = "Boş (Arızalı)"
            else:
                durum_metni = "Boş"
        ws.append([
            r["kat_adi"], r["oda_no"], durum_metni,
            _guvenli_hucre(r["ad_soyad"] or ""), _guvenli_hucre(r["tc_no"] or ""), _guvenli_hucre(r["telefon"] or ""),
            r["kisi_sayisi"] or "", fiyat_tipi_goster(r["fiyat_tipi"]) or "",
            r["tutar"] or "", "Ödendi" if r["odendi"] else ("Ödenmedi" if dolu_mu else ""),
            r["odeme_sekli"] or ""
        ])

    for col_letter, genislik in zip("ABCDEFGHIJK", [10, 8, 8, 22, 14, 14, 8, 10, 12, 12, 14]):
        ws.column_dimensions[col_letter].width = genislik

    wb.save(dosya_yolu)
    return len(rows)


def tarih_araligi_raporu_disa_aktar(dosya_yolu, baslangic_str, bitis_str):
    """Belirtilen tarih aralığındaki (baslangic ve bitis dahil) her gün için tüm
    odaların durumunu tek bir tabloda listeler (günlük/haftalık/aylık/özel rapor
    ihtiyaçlarının hepsi bu fonksiyonla karşılanır — tarih aralığı ne kadar geniş
    olursa o kadar kapsamlı rapor olur). Ayrıca özet bir sayfa da ekler."""
    from datetime import datetime as dt, timedelta as td

    baslangic = dt.strptime(baslangic_str, "%Y-%m-%d").date()
    bitis = dt.strptime(bitis_str, "%Y-%m-%d").date()
    if bitis < baslangic:
        baslangic, bitis = bitis, baslangic

    wb = Workbook()
    ws = wb.active
    ws.title = "Detay"

    basliklar = [
        "Tarih", "Kat", "Oda No", "Durum", "Ad Soyad", "TC No", "Telefon",
        "Kişi Sayısı", "Fiyat Tipi", "Gecelik Tutar", "Ödeme Durumu", "Ödeme Şekli"
    ]
    _baslik_satiri_yaz(ws, basliklar)

    toplam_dolu_gece = 0
    toplam_odenen = 0
    toplam_odenmeyen = 0
    toplam_gun_sayisi = (bitis - baslangic).days + 1

    gun = baslangic
    while gun <= bitis:
        gun_str = gun.isoformat()
        rows = repository.gunun_oda_durumu(gun_str)
        for r in rows:
            dolu_mu = r["rez_id"] is not None
            if dolu_mu:
                toplam_dolu_gece += 1
                if r["odendi"]:
                    toplam_odenen += r["tutar"] or 0
                else:
                    toplam_odenmeyen += r["tutar"] or 0
            if dolu_mu:
                durum_metni = "Dolu"
            else:
                oda_durum = r.get("aktif_durum") or "temiz"
                if oda_durum == "temizlikte":
                    durum_metni = "Boş (Temizlikte)"
                elif oda_durum == "arizali":
                    durum_metni = "Boş (Arızalı)"
                else:
                    durum_metni = "Boş"
            ws.append([
                gun_str, r["kat_adi"], r["oda_no"], durum_metni,
                _guvenli_hucre(r["ad_soyad"] or ""), _guvenli_hucre(r["tc_no"] or ""), _guvenli_hucre(r["telefon"] or ""),
                r["kisi_sayisi"] or "", fiyat_tipi_goster(r["fiyat_tipi"]) or "",
                r["tutar"] or "", "Ödendi" if r["odendi"] else ("Ödenmedi" if dolu_mu else ""),
                r["odeme_sekli"] or ""
            ])
        gun += td(days=1)

    for col_letter, genislik in zip("ABCDEFGHIJKL", [12, 10, 8, 8, 22, 14, 14, 8, 10, 12, 12, 14]):
        ws.column_dimensions[col_letter].width = genislik

    # Ozet sayfasi
    ws2 = wb.create_sheet("Özet")
    _baslik_satiri_yaz(ws2, ["Bilgi", "Değer"])
    ws2.append(["Başlangıç Tarihi", baslangic_str])
    ws2.append(["Bitiş Tarihi", bitis_str])
    ws2.append(["Toplam Gün Sayısı", toplam_gun_sayisi])
    ws2.append(["Toplam Dolu Oda-Gece", toplam_dolu_gece])
    ws2.append(["Tahsil Edilen Toplam Tutar (TL)", toplam_odenen])
    ws2.append(["Tahsil Edilmemiş Toplam Tutar (TL)", toplam_odenmeyen])
    ws2.append(["Beklenen Toplam Gelir (TL)", toplam_odenen + toplam_odenmeyen])
    for col_letter, genislik in zip("AB", [30, 20]):
        ws2.column_dimensions[col_letter].width = genislik

    wb.save(dosya_yolu)
    return toplam_gun_sayisi


def gun_sonu_kasa_disa_aktar(dosya_yolu, tarih_str):
    """Gün sonu kasa raporunu (o gün tahsil edilen geceler + ödeme şekli ve
    tahsil edene göre toplamlar) Excel'e yazar. Döner: satır sayısı."""
    kasa = repository.gun_sonu_kasa(tarih_str)
    wb = Workbook()
    ws = wb.active
    ws.title = "Gün Sonu Kasa"
    _baslik_satiri_yaz(ws, ["Saat", "Oda", "Misafir", "Gece", "Tutar (TL)",
                            "Ödeme Şekli", "Tahsil Eden", "Not"])
    for r in kasa["satirlar"]:
        ws.append([
            (r["tahsil_zamani"] or "")[11:16], f"{r['kat_adi']} - Oda {r['oda_no']}",
            _guvenli_hucre(r["ad_soyad"]), r["gece"], r["tutar"],
            r["odeme_sekli"] or "", r["tahsil_eden"] or "", _guvenli_hucre(r["odeme_notu"] or ""),
        ])
    ws.append([])
    ws.append(["", "", "TOPLAM", "", kasa["toplam"]])
    ws.cell(row=ws.max_row, column=3).font = Font(bold=True)
    ws.cell(row=ws.max_row, column=5).font = Font(bold=True)
    for sekil, tutar in sorted(kasa["sekiller"].items()):
        ws.append(["", "", sekil, "", tutar])
    ws.append([])
    for kisi, tutar in sorted(kasa["kullanicilar"].items()):
        ws.append(["", "", f"Tahsil eden: {kisi}", "", tutar])
    for col_letter, genislik in zip("ABCDEFGH", [7, 18, 26, 12, 12, 14, 14, 30]):
        ws.column_dimensions[col_letter].width = genislik
    wb.save(dosya_yolu)
    return len(kasa["satirlar"])


def _tarih_tr(s):
    """'2026-10-02' -> '02.10.2026'."""
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return s or ""


def konaklayan_listesi_basliklari(hassas=False):
    basliklar = ["No", "Ad Soyad", "TC / Belge No", "Uyruk", "Telefon", "Geldiği Yer",
                 "Oda", "Giriş", "Çıkış", "Gece", "Referans", "Kaydı Alan"]
    if hassas:
        basliklar += ["Puan", "Sorunlu"]
    return basliklar


def konaklayan_listesi_satiri(no, k, hassas=False):
    """Konaklayan listesinin tek satırı (Excel ve yazdırma aynı sütunları kullanır)."""
    cikis = _tarih_tr(k["cikis"]) + (" (içeride)" if k["iceride"] else "")
    satir = [no, k["ad_soyad"], k["tc_no"], k["uyruk"], k["telefon"], k["geldigi_yer"],
             k["odalar"], _tarih_tr(k["giris"]), cikis, k["gece"], k["referans"], k["alan"]]
    if hassas:
        satir += ["★" * k["puan"] if k["puan"] else "",
                  ("Evet: " + k["sorunlu_nedeni"]) if k["sorunlu"] and k["sorunlu_nedeni"]
                  else ("Evet" if k["sorunlu"] else "")]
    return satir


def konaklayan_listesi_disa_aktar(dosya_yolu, baslangic_str, bitis_str, hassas=False):
    """Tarih aralığında kalan kişilerin listesi: kişi başı bir satır, başlık
    satırı sabit, sütun genişlikleri ayarlı, A4 yatay tek sayfa genişliğinde
    yazdırılmaya hazır. hassas=True ise puan ve sorunlu bilgisi de eklenir
    (varsayılan kapalı: dosya bilgisayardan çıkabilir). Döner: kişi sayısı."""
    satirlar = repository.konaklayan_listesi(baslangic_str, bitis_str)
    basliklar = konaklayan_listesi_basliklari(hassas)
    wb = Workbook()
    ws = wb.active
    ws.title = "Konaklayan Listesi"

    tesis = _tesis_adi()
    aralik = _tarih_tr(baslangic_str) if baslangic_str == bitis_str else \
        f"{_tarih_tr(baslangic_str)} – {_tarih_tr(bitis_str)}"
    ws.append([f"{tesis} — Konaklayan Listesi ({aralik})"])
    ws.cell(row=1, column=1).font = Font(bold=True, size=14)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(basliklar))
    ws.append([f"{len(satirlar)} kişi · Oluşturma: {datetime.now().strftime('%d.%m.%Y %H:%M')}"])
    ws.cell(row=2, column=1).font = Font(italic=True, color="666666")
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(basliklar))

    ws.append(basliklar)
    ince = Side(style="thin", color="BBBBBB")
    kenar = Border(left=ince, right=ince, top=ince, bottom=ince)
    for col in range(1, len(basliklar) + 1):
        hucre = ws.cell(row=3, column=col)
        hucre.font = Font(bold=True, color="FFFFFF")
        hucre.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        hucre.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        hucre.border = kenar

    zebra = PatternFill(start_color="F2F5FB", end_color="F2F5FB", fill_type="solid")
    for i, k in enumerate(satirlar, start=1):
        ws.append([_guvenli_hucre(v) if isinstance(v, str) else v
                   for v in konaklayan_listesi_satiri(i, k, hassas)])
        for col in range(1, len(basliklar) + 1):
            hucre = ws.cell(row=ws.max_row, column=col)
            hucre.border = kenar
            hucre.alignment = Alignment(vertical="top", wrap_text=col in (2, 6, 11) or col > 12)
            if i % 2 == 0:
                hucre.fill = zebra

    genislikler = [5, 24, 15, 10, 16, 14, 8, 11, 17, 6, 18, 12, 8, 26]
    for col in range(1, len(basliklar) + 1):
        ws.column_dimensions[get_column_letter(col)].width = genislikler[col - 1]

    ws.freeze_panes = "A4"
    if satirlar:
        ws.auto_filter.ref = f"A3:{get_column_letter(len(basliklar))}{ws.max_row}"
    ws.print_title_rows = "3:3"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_options.horizontalCentered = True
    ws.oddFooter.center.text = "Sayfa &P / &N"
    wb.save(dosya_yolu)
    return len(satirlar)


def _tesis_adi():
    import database
    return database.get_ayar("tesis_adi", "") or "Misafirhane"
