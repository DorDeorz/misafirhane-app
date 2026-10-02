# -*- coding: utf-8 -*-
"""
Misafirler sekmesi (1.0.6).

Üç alt sekme:
- Misafirler: konaklamış her kişi tek satır (aynı telefon / TC = aynı kişi),
  son konaklamaya göre sıralı; ad soyad, telefon ya da geldiği yerle arama.
  Çift tık -> misafir kartı: bütün konaklamaları, puanı, sorunlu işareti
  (nedeni, işaretleyen ve zamanıyla) ve not geçmişi (yazan ve zamanıyla).
- Konaklayan Listesi: seçilen gün / hafta / ay / tarih aralığında kalan
  kişiler; Excel'e aktarma ve yazdırma. Puan ve sorunlu bilgisi yalnızca
  "Puan ve sorunlu bilgisini ekle" işaretlenirse dosyaya / çıktıya girer.
- Referanslar: rezervasyonu ayıran referanslar, kaç rezervasyon getirdikleri
  ve referansa ait not geçmişi.
"""

from datetime import date, datetime, timedelta
from html import escape

from PySide6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget,
    QGroupBox, QComboBox, QCheckBox, QDateEdit, QMessageBox, QFileDialog,
    QSplitter,
)
from PySide6.QtCore import Qt, QDate, QTimer
from PySide6.QtGui import QColor, QTextDocument, QPageLayout, QPageSize
from PySide6.QtCore import QMarginsF

import database
import repository
import export
from notlar_widget import NotlarWidget, zaman_goster


def tarih_goster(s):
    """'2026-10-02' -> '02.10.2026'."""
    try:
        return datetime.strptime((s or "")[:10], "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return s or ""


def yildiz(puan):
    puan = int(puan or 0)
    return ("★" * puan + "☆" * (5 - puan)) if puan else ""


def _tablo(basliklar, esnek_kolon):
    t = QTableWidget(0, len(basliklar))
    t.setHorizontalHeaderLabels(basliklar)
    t.setEditTriggers(QTableWidget.NoEditTriggers)
    t.setSelectionBehavior(QTableWidget.SelectRows)
    t.setSelectionMode(QTableWidget.SingleSelection)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(28)
    hh = t.horizontalHeader()
    for k in range(len(basliklar)):
        hh.setSectionResizeMode(k, QHeaderView.ResizeToContents)
    hh.setSectionResizeMode(esnek_kolon, QHeaderView.Stretch)
    return t


def _hucre(metin, veri=None, sirala=None):
    item = QTableWidgetItem(str(metin) if metin is not None else "")
    if veri is not None:
        item.setData(Qt.UserRole, veri)
    return item


def _konaklamalar_tablosu(konaklamalar, ad_kolonu=False):
    basliklar = ["Giriş", "Çıkış", "Gece", "Oda"]
    if ad_kolonu:
        basliklar += ["Ad Soyad", "Telefon"]
    basliklar += ["Geldiği Yer", "Referans", "Durum"]
    t = _tablo(basliklar, len(basliklar) - 2)
    t.setRowCount(len(konaklamalar))
    bugun = date.today().isoformat()
    for i, k in enumerate(konaklamalar):
        if "iceride" in k:
            durum = "İçeride" if k["iceride"] else "Kaldı"
        else:
            durum = ("Kaldı" if k["cikis"] <= bugun else "İçeride") if k["checkin"] else "Bekleniyor"
        degerler = [tarih_goster(k["giris"]), tarih_goster(k["cikis"]), k["gece"], k["odalar"]]
        if ad_kolonu:
            degerler += [k["ad_soyad"], k["telefon"] or ""]
        degerler += [k["geldigi_yer"], k["referans"] or "", durum]
        for col, v in enumerate(degerler):
            t.setItem(i, col, _hucre(v, k["rez_id"] if col == 0 else None))
    return t


def _rezervasyon_ac(parent, tablo, sonra=None):
    satir = tablo.currentRow()
    if satir < 0:
        return
    from detay_dialog import RezervasyonDetayDialog
    dlg = RezervasyonDetayDialog(tablo.item(satir, 0).data(Qt.UserRole), parent)
    dlg.exec()
    if sonra:
        sonra()


# ============================================================
# MİSAFİR KARTI PENCERESİ
# ============================================================
class MisafirDetayDialog(QDialog):
    """Bir misafirin bütün konaklamaları + puan / sorunlu işareti + notları."""

    def __init__(self, misafir, parent=None):
        super().__init__(parent)
        self.m = misafir
        self.degisti = False
        self.setWindowTitle(f"Misafir Kartı - {misafir['ad_soyad']}")
        self.resize(900, 600)
        self.kart = repository.misafir_karti_getir(misafir["telefon"], misafir["tc_no"]) or {}

        kok = QVBoxLayout(self)
        ust = QLabel(
            f"<b style='font-size:13pt'>{escape(misafir['ad_soyad'])}</b> &nbsp; "
            f"📞 {escape(misafir['telefon'] or '-')}"
            + (f" &nbsp; 🪪 {escape(misafir['tc_no'])}" if misafir["tc_no"] else "")
            + (f" &nbsp; 📍 {escape(misafir['geldigi_yer'])}" if misafir["geldigi_yer"] else "")
            + f"<br><span style='color:#555'>{misafir['konaklama']} konaklama · "
              f"{misafir['toplam_gece']} gece · ilk {tarih_goster(misafir['ilk_giris'])}, "
              f"son {tarih_goster(misafir['son_giris'])}</span>")
        ust.setTextFormat(Qt.RichText)
        kok.addWidget(ust)

        split = QSplitter(Qt.Horizontal)
        sol = QWidget()
        sol_lay = QVBoxLayout(sol)
        sol_lay.setContentsMargins(0, 0, 0, 0)
        kutu = QGroupBox("Konaklamalar (çift tık: rezervasyon detayı)")
        k_lay = QVBoxLayout(kutu)
        self.konaklamalar = _konaklamalar_tablosu(
            repository.konaklama_ozetleri(misafir["rez_idler"]), ad_kolonu=False)
        self.konaklamalar.itemDoubleClicked.connect(
            lambda *_: _rezervasyon_ac(self, self.konaklamalar, self._degisti))
        k_lay.addWidget(self.konaklamalar)
        sol_lay.addWidget(kutu)
        split.addWidget(sol)

        sag = QWidget()
        sag.setMinimumWidth(320)
        sag_lay = QVBoxLayout(sag)
        sag_lay.setContentsMargins(0, 0, 0, 0)
        self.kart_kutusu = MisafirKartiKutusu(self.kart)
        sag_lay.addWidget(self.kart_kutusu)
        notlar_kutu = QGroupBox("Misafir Notları")
        n_lay = QVBoxLayout(notlar_kutu)
        self.notlar = NotlarWidget(
            "misafir", self.kart.get("id"), anahtar_saglayici=self._kart_ac,
            bos_mesaj="Not eklemek için telefon ya da TC gerekli.")
        if not repository.telefon_anahtari(misafir["telefon"]) and not misafir["tc_no"]:
            self.notlar.anahtar_saglayici = None
            self.notlar.yenile()
        self.notlar.degisti.connect(self._degisti)
        n_lay.addWidget(self.notlar)
        sag_lay.addWidget(notlar_kutu, 1)
        split.addWidget(sag)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        kok.addWidget(split, 1)

        alt = QHBoxLayout()
        alt.addStretch(1)
        kapat = QPushButton("Kapat")
        kapat.clicked.connect(self.reject)
        alt.addWidget(kapat)
        kaydet = QPushButton("💾 Kaydet")
        kaydet.setObjectName("birincil")
        kaydet.clicked.connect(self.kaydet)
        alt.addWidget(kaydet)
        kok.addLayout(alt)

    def _degisti(self):
        self.degisti = True

    def _kart_ac(self):
        kart = repository.misafir_karti_olustur(self.m["telefon"], self.m["tc_no"], self.m["ad_soyad"])
        self.kart = kart
        self.kart_kutusu.kart = kart
        return kart["id"]

    def kaydet(self):
        try:
            if self.kart_kutusu.kaydet(self.m["telefon"], self.m["tc_no"], self.m["ad_soyad"]):
                self.degisti = True
        except Exception as e:
            QMessageBox.warning(self, "Kaydedilemedi", str(e))
            return
        self.accept()


class MisafirKartiKutusu(QGroupBox):
    """Puan (1-5) + sorunlu işareti ve nedeni; rezervasyon detayında ve
    misafir kartı penceresinde ortak. kaydet() çağrılınca yazılır."""

    def __init__(self, kart, parent=None):
        super().__init__("Puan ve Uyarı", parent)
        self.kart = kart or {}
        lay = QGridLayout(self)
        lay.setContentsMargins(8, 14, 8, 8)
        lay.setVerticalSpacing(4)

        lay.addWidget(QLabel("Puan:"), 0, 0)
        self.puan = QComboBox()
        self.puan.addItem("Puan yok", 0)
        for p in range(1, 6):
            self.puan.addItem(f"{'★' * p}{'☆' * (5 - p)}  ({p})", p)
        self.puan.setCurrentIndex(int(self.kart.get("puan") or 0))
        lay.addWidget(self.puan, 0, 1)

        self.sorunlu = QCheckBox("⚠ Sorunlu misafir")
        self.sorunlu.setToolTip("Bu misafirle yeni rezervasyon alınırken resepsiyoniste uyarı gösterilir "
                                "(kayıt engellenmez).")
        self.sorunlu.setChecked(bool(self.kart.get("sorunlu")))
        lay.addWidget(self.sorunlu, 1, 0, 1, 2)
        self.neden = QLineEdit(self.kart.get("sorunlu_nedeni") or "")
        self.neden.setPlaceholderText("Sorun neydi? (ör. borcunu ödemedi, gürültü)")
        lay.addWidget(self.neden, 2, 0, 1, 2)
        self.isaretleyen = QLabel("")
        self.isaretleyen.setStyleSheet("color: #777; font-size: 10px;")
        lay.addWidget(self.isaretleyen, 3, 0, 1, 2)
        lay.setColumnStretch(1, 1)
        self.sorunlu.toggled.connect(self._sorunlu_degisti)
        self._sorunlu_degisti(self.sorunlu.isChecked())

    def _sorunlu_degisti(self, isaretli):
        self.neden.setEnabled(isaretli)
        k = self.kart
        if isaretli and k.get("sorunlu") and k.get("sorunlu_isaretleyen"):
            self.isaretleyen.setText(f"İşaretleyen: {k['sorunlu_isaretleyen']} · "
                                     f"{zaman_goster(k.get('sorunlu_zamani'))}")
        else:
            self.isaretleyen.setText("")
        self.isaretleyen.setVisible(bool(self.isaretleyen.text()))

    def degisti_mi(self):
        k = self.kart
        return (self.puan.currentData() != int(k.get("puan") or 0)
                or self.sorunlu.isChecked() != bool(k.get("sorunlu"))
                or (self.sorunlu.isChecked()
                    and self.neden.text().strip() != (k.get("sorunlu_nedeni") or "")))

    def kaydet(self, telefon, tc_no, ad_soyad):
        """Değişiklik varsa kaydeder; kaydettiyse True."""
        if not self.degisti_mi():
            return False
        if self.sorunlu.isChecked() and not self.neden.text().strip():
            raise ValueError("Sorunlu işaretlerken nedenini de yaz.")
        repository.misafir_karti_kaydet(telefon, tc_no, ad_soyad, self.puan.currentData(),
                                        self.sorunlu.isChecked(), self.neden.text().strip())
        return True


# ============================================================
# REFERANS PENCERESİ
# ============================================================
class ReferansDialog(QDialog):
    """Bir referansla gelen rezervasyonlar + referansa ait notlar."""

    def __init__(self, referans, parent=None):
        super().__init__(parent)
        self.referans = referans
        self.setWindowTitle(f"Referans - {referans}")
        self.resize(900, 560)
        kok = QVBoxLayout(self)
        rezler = repository.referans_rezervasyonlari(referans)
        baslik = QLabel(f"<b style='font-size:13pt'>{escape(referans)}</b> &nbsp; "
                        f"<span style='color:#555'>{len(rezler)} rezervasyon</span>")
        baslik.setTextFormat(Qt.RichText)
        kok.addWidget(baslik)

        split = QSplitter(Qt.Horizontal)
        kutu = QGroupBox("Bu referansla gelenler (çift tık: rezervasyon detayı)")
        k_lay = QVBoxLayout(kutu)
        self.tablo = _konaklamalar_tablosu(rezler, ad_kolonu=True)
        self.tablo.itemDoubleClicked.connect(lambda *_: _rezervasyon_ac(self, self.tablo))
        k_lay.addWidget(self.tablo)
        split.addWidget(kutu)
        notlar_kutu = QGroupBox("Referans Notları")
        notlar_kutu.setMinimumWidth(300)
        n_lay = QVBoxLayout(notlar_kutu)
        self.notlar = NotlarWidget("referans", referans)
        n_lay.addWidget(self.notlar)
        split.addWidget(notlar_kutu)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        kok.addWidget(split, 1)

        alt = QHBoxLayout()
        alt.addStretch(1)
        kapat = QPushButton("Kapat")
        kapat.clicked.connect(self.accept)
        alt.addWidget(kapat)
        kok.addLayout(alt)


# ============================================================
# KONAKLAYAN LİSTESİ — yazdırma
# ============================================================
def konaklayan_listesi_html(baslangic_str, bitis_str, satirlar, hassas=False):
    tesis = database.get_ayar("tesis_adi", "") or "Misafirhane"
    aralik = tarih_goster(baslangic_str) if baslangic_str == bitis_str else \
        f"{tarih_goster(baslangic_str)} – {tarih_goster(bitis_str)}"
    basliklar = export.konaklayan_listesi_basliklari(hassas)
    p = ["""<html><head><style>
        body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 8pt; color: #222; }
        h1 { font-size: 13pt; margin: 0; }
        .alt { color: #666; margin-bottom: 6px; }
        table { border-collapse: collapse; width: 100%; }
        th { background: #4472C4; color: white; padding: 3px; border: 1px solid #999; }
        td { padding: 3px; border: 1px solid #bbb; vertical-align: top; }
        tr.z td { background: #F2F5FB; }
        </style></head><body>"""]
    p.append(f"<h1>{escape(tesis)} — Konaklayan Listesi ({aralik})</h1>")
    p.append(f"<div class='alt'>{len(satirlar)} kişi · Oluşturma: "
             f"{datetime.now().strftime('%d.%m.%Y %H:%M')}</div>")
    p.append("<table><tr>" + "".join(f"<th>{escape(b)}</th>" for b in basliklar) + "</tr>")
    for i, k in enumerate(satirlar, start=1):
        hucreler = export.konaklayan_listesi_satiri(i, k, hassas)
        p.append(f"<tr class='{'z' if i % 2 == 0 else ''}'>"
                 + "".join(f"<td>{escape(str(v))}</td>" for v in hucreler) + "</tr>")
    p.append("</table></body></html>")
    return "".join(p)


# ============================================================
# MİSAFİRLER SEKMESİ
# ============================================================
class MisafirlerTab(QWidget):
    def __init__(self, yenile_callback=None):
        super().__init__()
        self.yenile_callback = yenile_callback
        lay = QVBoxLayout(self)
        lay.setSpacing(6)
        self.sekmeler = QTabWidget()
        self.sekmeler.addTab(self._misafirler_sekmesi(), "👥 Misafirler")
        self.sekmeler.addTab(self._konaklayan_sekmesi(), "📄 Konaklayan Listesi")
        self.sekmeler.addTab(self._referans_sekmesi(), "🤝 Referanslar")
        self.sekmeler.currentChanged.connect(lambda _: self.yenile())
        lay.addWidget(self.sekmeler)
        self.yenile()

    # ---------------- misafirler ----------------
    def _misafirler_sekmesi(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        ust = QHBoxLayout()
        ust.addWidget(QLabel("🔍 Bul:"))
        self.arama = QLineEdit()
        self.arama.setPlaceholderText("Ad soyad, telefon ya da geldiği yer… önceden kalmış mı bak")
        self._arama_zaman = QTimer(self)
        self._arama_zaman.setSingleShot(True)
        self._arama_zaman.setInterval(250)
        self._arama_zaman.timeout.connect(self._misafirleri_doldur)
        self.arama.textChanged.connect(lambda: self._arama_zaman.start())
        ust.addWidget(self.arama, 1)
        self.yalniz_sorunlu = QCheckBox("Yalnız sorunlular")
        self.yalniz_sorunlu.toggled.connect(self._misafirleri_doldur)
        ust.addWidget(self.yalniz_sorunlu)
        lay.addLayout(ust)

        self.misafir_tablo = _tablo(["Ad Soyad", "Telefon", "Geldiği Yer", "Konaklama", "Toplam Gece",
                                     "Son Giriş", "Son Çıkış", "Puan", "Durum", "Not"], 8)
        self.misafir_tablo.itemDoubleClicked.connect(self._misafir_ac)
        lay.addWidget(self.misafir_tablo, 1)
        self.misafir_ozet = QLabel("")
        self.misafir_ozet.setStyleSheet("color: #666;")
        lay.addWidget(self.misafir_ozet)
        return w

    def _misafirleri_doldur(self):
        try:
            satirlar = repository.misafir_listesi(self.arama.text())
        except Exception as e:
            self.misafir_ozet.setText(f"Liste yüklenemedi: {e}")
            return
        if self.yalniz_sorunlu.isChecked():
            satirlar = [s for s in satirlar if s["sorunlu"]]
        self._misafirler = satirlar
        t = self.misafir_tablo
        t.setRowCount(len(satirlar))
        for i, m in enumerate(satirlar):
            durum = []
            if m["sorunlu"]:
                durum.append(f"⚠ Sorunlu: {m['sorunlu_nedeni']}" if m["sorunlu_nedeni"] else "⚠ Sorunlu")
            if m["iceride"]:
                durum.append("🛏 İçeride")
            degerler = [m["ad_soyad"], m["telefon"], m["geldigi_yer"], m["konaklama"], m["toplam_gece"],
                        tarih_goster(m["son_giris"]), tarih_goster(m["son_cikis"]), yildiz(m["puan"]),
                        " · ".join(durum), f"📝 {m['not_sayisi']}" if m["not_sayisi"] else ""]
            for col, v in enumerate(degerler):
                item = _hucre(v, i if col == 0 else None)
                if m["sorunlu"]:
                    item.setForeground(QColor("#922b21"))
                t.setItem(i, col, item)
        self.misafir_ozet.setText(f"{len(satirlar)} misafir · çift tıkla: konaklamaları, puan ve notlar")

    def _misafir_ac(self, *_):
        satir = self.misafir_tablo.currentRow()
        if satir < 0:
            return
        m = self._misafirler[self.misafir_tablo.item(satir, 0).data(Qt.UserRole)]
        dlg = MisafirDetayDialog(m, self)
        dlg.exec()
        if dlg.degisti:
            self._misafirleri_doldur()

    # ---------------- konaklayan listesi ----------------
    def _konaklayan_sekmesi(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        ust = QHBoxLayout()
        for ad, fn in (("Bugün", self._bugun), ("Bu Hafta", self._bu_hafta),
                       ("Bu Ay", self._bu_ay), ("Geçen Ay", self._gecen_ay)):
            b = QPushButton(ad)
            b.clicked.connect(fn)
            ust.addWidget(b)
        ust.addSpacing(12)
        ust.addWidget(QLabel("Başlangıç:"))
        self.k_bas = QDateEdit(QDate.currentDate())
        self.k_bas.setCalendarPopup(True)
        self.k_bas.setDisplayFormat("dd.MM.yyyy")
        ust.addWidget(self.k_bas)
        ust.addWidget(QLabel("Bitiş:"))
        self.k_bit = QDateEdit(QDate.currentDate())
        self.k_bit.setCalendarPopup(True)
        self.k_bit.setDisplayFormat("dd.MM.yyyy")
        ust.addWidget(self.k_bit)
        self.k_bas.dateChanged.connect(self._konaklayanlari_doldur)
        self.k_bit.dateChanged.connect(self._konaklayanlari_doldur)
        ust.addStretch(1)
        lay.addLayout(ust)

        alt = QHBoxLayout()
        self.hassas = QCheckBox("Puan ve sorunlu bilgisini ekle")
        self.hassas.setToolTip("Excel dosyası ve kâğıt çıktı bilgisayardan çıkabilir; bu bilgiler "
                               "varsayılan olarak eklenmez.")
        self.hassas.toggled.connect(self._konaklayanlari_doldur)
        alt.addWidget(self.hassas)
        alt.addStretch(1)
        excel_btn = QPushButton("📊 Excel'e Aktar")
        excel_btn.clicked.connect(self.konaklayan_excel)
        alt.addWidget(excel_btn)
        yazdir_btn = QPushButton("🖨 Yazdır")
        yazdir_btn.clicked.connect(self.konaklayan_yazdir)
        alt.addWidget(yazdir_btn)
        lay.addLayout(alt)

        self.k_tablo = _tablo(export.konaklayan_listesi_basliklari(True), 1)
        self.k_tablo.itemDoubleClicked.connect(self._konaklayan_rez_ac)
        lay.addWidget(self.k_tablo, 1)
        self.k_ozet = QLabel("")
        self.k_ozet.setStyleSheet("color: #666;")
        lay.addWidget(self.k_ozet)
        return w

    def _aralik_ayarla(self, bas, bit):
        for w, d in ((self.k_bas, bas), (self.k_bit, bit)):
            w.blockSignals(True)
            w.setDate(QDate(d.year, d.month, d.day))
            w.blockSignals(False)
        self._konaklayanlari_doldur()

    def _bugun(self):
        b = date.today()
        self._aralik_ayarla(b, b)

    def _bu_hafta(self):
        b = date.today()
        pzt = b - timedelta(days=b.weekday())
        self._aralik_ayarla(pzt, pzt + timedelta(days=6))

    def _bu_ay(self):
        b = date.today()
        ilk = b.replace(day=1)
        son = (ilk + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        self._aralik_ayarla(ilk, son)

    def _gecen_ay(self):
        son = date.today().replace(day=1) - timedelta(days=1)
        self._aralik_ayarla(son.replace(day=1), son)

    def _aralik(self):
        bas = self.k_bas.date().toString("yyyy-MM-dd")
        bit = self.k_bit.date().toString("yyyy-MM-dd")
        return (bas, bit) if bas <= bit else (bit, bas)

    def _konaklayanlari_doldur(self):
        bas, bit = self._aralik()
        try:
            self._konaklayanlar = repository.konaklayan_listesi(bas, bit)
        except Exception as e:
            self.k_ozet.setText(f"Liste yüklenemedi: {e}")
            return
        hassas = self.hassas.isChecked()
        t = self.k_tablo
        t.setRowCount(len(self._konaklayanlar))
        for i, k in enumerate(self._konaklayanlar):
            for col, v in enumerate(export.konaklayan_listesi_satiri(i + 1, k, True)):
                t.setItem(i, col, _hucre(v, k["rez_id"] if col == 0 else None))
        for col in (12, 13):
            t.setColumnHidden(col, not hassas)
        self.k_ozet.setText(f"{len(self._konaklayanlar)} kişi · {tarih_goster(bas)} – {tarih_goster(bit)}"
                            " · çift tık: rezervasyon detayı")

    def _konaklayan_rez_ac(self, *_):
        _rezervasyon_ac(self, self.k_tablo, self._konaklayanlari_doldur)

    def _gun_farki_uygun_mu(self, bas, bit):
        if (datetime.strptime(bit, "%Y-%m-%d") - datetime.strptime(bas, "%Y-%m-%d")).days > 400:
            QMessageBox.warning(self, "Çok Geniş Aralık", "Lütfen 400 günden daha kısa bir aralık seç.")
            return False
        return True

    def konaklayan_excel(self):
        bas, bit = self._aralik()
        if not self._gun_farki_uygun_mu(bas, bit):
            return
        dosya, _ = QFileDialog.getSaveFileName(
            self, "Excel Dosyasını Kaydet", f"konaklayan_listesi_{bas}_{bit}.xlsx", "Excel Dosyası (*.xlsx)")
        if not dosya:
            return
        try:
            adet = export.konaklayan_listesi_disa_aktar(dosya, bas, bit, self.hassas.isChecked())
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Excel'e aktarılırken hata oluştu:\n{e}")
            return
        QMessageBox.information(self, "Başarılı", f"{adet} kişilik liste Excel'e aktarıldı:\n{dosya}")

    def konaklayan_yazdir(self):
        from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog
        bas, bit = self._aralik()
        if not self._gun_farki_uygun_mu(bas, bit):
            return
        belge = QTextDocument()
        belge.setHtml(konaklayan_listesi_html(
            bas, bit, repository.konaklayan_listesi(bas, bit), self.hassas.isChecked()))
        yazici = QPrinter(QPrinter.HighResolution)
        yazici.setPageOrientation(QPageLayout.Landscape)
        yazici.setPageSize(QPageSize(QPageSize.A4))
        yazici.setPageMargins(QMarginsF(10, 10, 10, 10), QPageLayout.Millimeter)
        onizleme = QPrintPreviewDialog(yazici, self)
        onizleme.setWindowTitle("Konaklayan Listesi — Yazdır")
        onizleme.paintRequested.connect(belge.print_)
        onizleme.resize(1000, 700)
        onizleme.exec()

    # ---------------- referanslar ----------------
    def _referans_sekmesi(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        ust = QHBoxLayout()
        ust.addWidget(QLabel("🔍 Bul:"))
        self.ref_arama = QLineEdit()
        self.ref_arama.setPlaceholderText("Referans adı…")
        self.ref_arama.textChanged.connect(self._referanslari_doldur)
        ust.addWidget(self.ref_arama, 1)
        lay.addLayout(ust)
        self.ref_tablo = _tablo(["Referans", "Rezervasyon", "Konaklayan", "Son Giriş", "Not"], 0)
        self.ref_tablo.itemDoubleClicked.connect(self._referans_ac)
        lay.addWidget(self.ref_tablo, 1)
        bilgi = QLabel("Çift tıkla: bu referansla gelenler ve referans notları.")
        bilgi.setStyleSheet("color: #666;")
        lay.addWidget(bilgi)
        return w

    def _referanslari_doldur(self):
        try:
            satirlar = repository.referans_listesi(self.ref_arama.text())
        except Exception:
            satirlar = []
        t = self.ref_tablo
        t.setRowCount(len(satirlar))
        for i, r in enumerate(satirlar):
            degerler = [r["referans"], r["rezervasyon"], r["konaklayan"], tarih_goster(r["son_giris"]),
                        f"📝 {r['not_sayisi']}" if r["not_sayisi"] else ""]
            for col, v in enumerate(degerler):
                t.setItem(i, col, _hucre(v, r["referans"] if col == 0 else None))

    def _referans_ac(self, *_):
        satir = self.ref_tablo.currentRow()
        if satir < 0:
            return
        ReferansDialog(self.ref_tablo.item(satir, 0).data(Qt.UserRole), self).exec()
        self._referanslari_doldur()

    def yenile(self):
        i = self.sekmeler.currentIndex()
        if i == 0:
            self._misafirleri_doldur()
        elif i == 1:
            self._konaklayanlari_doldur()
        else:
            self._referanslari_doldur()
