# -*- coding: utf-8 -*-
"""
Hesap dökümü (1.0.5): misafire verilecek konaklama ve ödeme dökümünü PDF
olarak üretir. Ek kütüphane gerekmez; Qt'nin QTextDocument + QPdfWriter'ı
kullanılır (PyInstaller derlemesinde zaten var olan QtGui modülü).
"""

from datetime import datetime
from html import escape

from PySide6.QtGui import QTextDocument, QPdfWriter, QPageSize, QPageLayout
from PySide6.QtCore import QMarginsF

import database
import repository


def _tl(tutar):
    return f"{tutar or 0:,}₺"


def _tarih(s):
    """'2026-09-27' -> '27.09.2026' (boş/bozuksa olduğu gibi)."""
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return s or ""


def hesap_dokumu_html(rez_id):
    """Rezervasyonun hesap dökümünü HTML olarak döndürür (bulunamazsa None)."""
    v = repository.hesap_dokumu_verisi(rez_id)
    if v is None:
        return None
    rez = v["rez"]
    tesis = database.get_ayar("tesis_adi", "") or "Misafirhane"
    p = []
    p.append("""<html><head><style>
        body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 10pt; color: #222; }
        h1 { font-size: 16pt; margin: 0; }
        h2 { font-size: 11pt; margin: 14px 0 4px 0; }
        table { border-collapse: collapse; width: 100%; }
        th { background: #e8e8e8; text-align: left; padding: 4px 6px; border: 1px solid #bbb; }
        td { padding: 3px 6px; border: 1px solid #ccc; }
        .sag { text-align: right; }
        .kucuk { color: #666; font-size: 8.5pt; }
    </style></head><body>""")
    p.append(f"<h1>{escape(tesis)}</h1>")
    p.append("<p><b>HESAP DÖKÜMÜ</b> &nbsp;·&nbsp; "
             f"Rezervasyon No: {rez['id']} &nbsp;·&nbsp; Düzenlenme: "
             f"{datetime.now().strftime('%d.%m.%Y %H:%M')}</p>")
    p.append("<table>")
    p.append(f"<tr><td width='25%'><b>Misafir</b></td><td>{escape(rez['ad_soyad'] or '')}</td></tr>")
    if rez["telefon"]:
        p.append(f"<tr><td><b>Telefon</b></td><td>{escape(rez['telefon'])}</td></tr>")
    p.append("</table>")

    for oda in v["odalar"]:
        cikis = oda["cikis_tarihi"] or oda["planli_cikis"]
        p.append(f"<h2>{escape(oda['kat_adi'])} - Oda {oda['oda_no']}</h2>")
        p.append(f"<p>Giriş {_tarih(oda['giris_tarihi'])} · Çıkış {_tarih(cikis)}"
                 f" · {oda['gece_sayisi']} gece · {oda['kisi_sayisi']} kişi</p>")
        if oda["misafirler"]:
            adlar = ", ".join(escape(m["ad_soyad"] or "") for m in oda["misafirler"] if m["ad_soyad"])
            if adlar:
                p.append(f"<p class='kucuk'>Konaklayanlar: {adlar}</p>")
        p.append("<table><tr><th>Gece</th><th class='sag'>Tutar</th><th>Durum</th></tr>")
        for o in oda["odemeler"]:
            durum = f"Ödendi ({escape(o['odeme_sekli'])})" if o["odendi"] and o["odeme_sekli"] \
                else ("Ödendi" if o["odendi"] else "Ödenmedi")
            p.append(f"<tr><td>{_tarih(o['tarih'])}</td><td class='sag'>{_tl(o['tutar'])}</td>"
                     f"<td>{durum}</td></tr>")
        if not oda["odemeler"]:
            p.append("<tr><td colspan='3' class='kucuk'>Ücretlendirilmiş gece yok.</td></tr>")
        p.append("</table>")

    p.append("<h2>Özet</h2><table>")
    p.append(f"<tr><td width='60%'>Toplam konaklama ücreti</td><td class='sag'>{_tl(v['toplam'])}</td></tr>")
    p.append(f"<tr><td>Ödenen</td><td class='sag'>{_tl(v['odenen'])}</td></tr>")
    p.append(f"<tr><td><b>Kalan</b></td><td class='sag'><b>{_tl(v['kalan'])}</b></td></tr>")
    p.append("</table>")
    p.append("<p class='kucuk'>Bu belge bilgi amaçlıdır, fatura yerine geçmez.</p>")
    p.append("</body></html>")
    return "".join(p)


def hesap_dokumu_pdf(rez_id, dosya_yolu):
    """Hesap dökümünü A4 PDF olarak dosya_yolu'na yazar. Rezervasyon yoksa ValueError."""
    html = hesap_dokumu_html(rez_id)
    if html is None:
        raise ValueError("Rezervasyon bulunamadı.")
    yazici = QPdfWriter(dosya_yolu)
    yazici.setPageSize(QPageSize(QPageSize.A4))
    yazici.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Millimeter)
    yazici.setResolution(300)
    belge = QTextDocument()
    belge.setHtml(html)
    belge.print_(yazici)
