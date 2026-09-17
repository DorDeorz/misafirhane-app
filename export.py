# -*- coding: utf-8 -*-
"""
Excel'e aktarma işlemleri. openpyxl kullanır.
Tek yönlü aktarım: sistemdeki veriyi Excel'e yazar (rapor/yedek amaçlı).
Excel dosyası düzenlenip geri sisteme YÜKLENMEZ — asıl veri her zaman
misafirhane.db dosyasındadır.
"""

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from datetime import datetime

import repository
from database import fiyat_tipi_goster


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
        "ID", "Kat", "Oda No", "Ad Soyad", "TC No", "Telefon", "Kişi Sayısı",
        "Giriş Tarihi", "Gece Sayısı", "Çıkış Tarihi", "Fiyat Tipi",
        "Gecelik Ücret", "Toplam Tutar", "Referans", "Grup", "Alan Kullanıcı",
        "Alınma Tarihi", "Durum", "Notlar"
    ]
    _baslik_satiri_yaz(ws, basliklar)

    rows = satirlar if satirlar is not None else repository.rezervasyon_listesi(durum)
    for r in rows:
        cikis = repository.cikis_tarihi_hesapla(r["giris_tarihi"], r["gece_sayisi"])
        toplam = repository.rezervasyon_gecelik_toplami(r) * (r["gece_sayisi"] or 1)
        if r["iptal"]:
            durum_metni = "İptal Edildi"
        elif repository.gelmedi_mi(r):
            durum_metni = "Gelmedi (No-Show)"
        elif r["checkin_yapildi"]:
            durum_metni = "Check-in Yapıldı"
        else:
            durum_metni = "Aktif"
        ws.append([
            r["id"], r["kat_adi"], r["oda_no"], r["ad_soyad"], r["tc_no"] or "",
            r["telefon"] or "", r["kisi_sayisi"], r["giris_tarihi"], r["gece_sayisi"],
            cikis, r["fiyat_tipi"], r["gecelik_ucret"], toplam,
            r["referans"] or "", (r["grup_id"][:8] if r["grup_id"] else ""),
            r["olusturan_kullanici"] or "", r["olusturma_tarihi"] or "",
            durum_metni, r["notlar"] or ""
        ])

    for col_letter, genislik in zip(
        "ABCDEFGHIJKLMNOPQRS", [5, 10, 8, 22, 14, 14, 8, 12, 8, 12, 10, 12, 12, 18, 10, 14, 16, 16, 30]
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
            r["ad_soyad"] or "", r["tc_no"] or "", r["telefon"] or "",
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
                r["ad_soyad"] or "", r["tc_no"] or "", r["telefon"] or "",
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
