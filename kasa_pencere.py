# -*- coding: utf-8 -*-
"""
Kasa ve Borçlar penceresi (1.0.5).

İki sekme:
- Gün Sonu Kasa: seçilen gün TAHSİL EDİLEN gece ücretleri; ödeme şekline ve
  tahsil edene göre toplamlar; Excel'e aktarma. (1.0.5'ten önce ödenmiş
  kayıtların tahsil zamanı bilinmediği için rapora girmez.)
- Açık Borçlar: kalınmış ama henüz ödenmemiş geceler (oda satırı bazında);
  seçili satırın borcu tek seferde tahsil edilebilir, çift tıklayınca
  rezervasyon detayı açılır.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QTabWidget, QLabel, QFileDialog, QMessageBox,
    QHeaderView, QDateEdit, QWidget, QInputDialog,
)
from PySide6.QtCore import Qt, QDate

import database
import repository
import export


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


def _tl(tutar):
    return f"{tutar or 0:,}₺"


class KasaPenceresi(QDialog):
    def __init__(self, parent=None, yenile_callback=None, baslangic_sekmesi=0):
        super().__init__(parent)
        self.yenile_callback = yenile_callback
        self.setWindowTitle("Kasa ve Borçlar")
        self.resize(980, 580)

        dikey = QVBoxLayout(self)
        self.sekmeler = QTabWidget()
        self.sekmeler.addTab(self._kasa_sekmesi(), "💰 Gün Sonu Kasa")
        self.sekmeler.addTab(self._borc_sekmesi(), "⏳ Açık Borçlar")
        dikey.addWidget(self.sekmeler, 1)

        alt = QHBoxLayout()
        alt.addStretch(1)
        kapat = QPushButton("Kapat")
        kapat.setObjectName("ikincil")
        kapat.clicked.connect(self.accept)
        alt.addWidget(kapat)
        dikey.addLayout(alt)

        self.kasa_yenile()
        self.borc_yenile()
        self.sekmeler.setCurrentIndex(baslangic_sekmesi)

    # ---------------- GÜN SONU KASA ----------------
    def _kasa_sekmesi(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(6)

        ust = QHBoxLayout()
        ust.addWidget(QLabel("Tahsilat günü:"))
        self.kasa_tarih = QDateEdit(QDate.currentDate())
        self.kasa_tarih.setCalendarPopup(True)
        self.kasa_tarih.setDisplayFormat("dd.MM.yyyy")
        self.kasa_tarih.dateChanged.connect(self.kasa_yenile)
        ust.addWidget(self.kasa_tarih)
        ust.addStretch(1)
        excel_btn = QPushButton("📊 Excel'e Aktar")
        excel_btn.clicked.connect(self.kasa_excel)
        ust.addWidget(excel_btn)
        lay.addLayout(ust)

        self.kasa_tablo = _tablo(
            ["Saat", "Oda", "Misafir", "Gece", "Tutar", "Ödeme Şekli", "Tahsil Eden", "Not"], 2)
        self.kasa_tablo.setToolTip("Çift tıkla: rezervasyon detayını aç")
        self.kasa_tablo.cellDoubleClicked.connect(
            lambda satir, _k: self._detay_ac(self.kasa_tablo, satir))
        lay.addWidget(self.kasa_tablo, 1)

        self.kasa_ozet = QLabel("")
        self.kasa_ozet.setWordWrap(True)
        self.kasa_ozet.setTextFormat(Qt.RichText)
        lay.addWidget(self.kasa_ozet)

        not_ = QLabel("Rapor, ödemenin 'ödendi' işaretlendiği güne göredir (gecenin tarihine göre "
                      "değil). Bu sürümden önce işaretlenmiş ödemelerin tahsil günü bilinmediği için "
                      "rapora girmez.")
        not_.setWordWrap(True)
        not_.setStyleSheet("color: #777; font-size: 11px;")
        lay.addWidget(not_)
        return w

    def kasa_yenile(self):
        tarih = self.kasa_tarih.date().toString("yyyy-MM-dd")
        try:
            kasa = repository.gun_sonu_kasa(tarih)
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Kasa raporu okunamadı: {e}")
            return
        t = self.kasa_tablo
        t.setRowCount(len(kasa["satirlar"]))
        for i, r in enumerate(kasa["satirlar"]):
            degerler = [
                (r["tahsil_zamani"] or "")[11:16], f"{r['kat_adi']} - Oda {r['oda_no']}",
                r["ad_soyad"], r["gece"], _tl(r["tutar"]), r["odeme_sekli"] or "-",
                r["tahsil_eden"] or "-", r["odeme_notu"] or "",
            ]
            for k, d in enumerate(degerler):
                h = QTableWidgetItem(str(d))
                if k == 0:
                    h.setData(Qt.UserRole, r["rez_id"])
                if k == 4:
                    h.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                t.setItem(i, k, h)
        if not kasa["satirlar"]:
            self.kasa_ozet.setText("Bu gün tahsil edilmiş ödeme yok.")
            return
        sekiller = " · ".join(f"{s}: {_tl(v)}" for s, v in sorted(kasa["sekiller"].items()))
        kisiler = " · ".join(f"{k}: {_tl(v)}" for k, v in sorted(kasa["kullanicilar"].items()))
        self.kasa_ozet.setText(
            f"<b>Toplam tahsilat: {_tl(kasa['toplam'])}</b> ({len(kasa['satirlar'])} gece)"
            f"<br>Ödeme şekline göre: {sekiller}<br>Tahsil edene göre: {kisiler}"
        )

    def kasa_excel(self):
        tarih = self.kasa_tarih.date().toString("yyyy-MM-dd")
        yol, _ = QFileDialog.getSaveFileName(
            self, "Excel Dosyasını Kaydet", f"gun_sonu_kasa_{tarih}.xlsx", "Excel Dosyası (*.xlsx)")
        if not yol:
            return
        try:
            sayi = export.gun_sonu_kasa_disa_aktar(yol, tarih)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Excel'e aktarılırken hata oluştu:\n{e}")
            return
        QMessageBox.information(self, "Başarılı", f"{sayi} tahsilat Excel'e aktarıldı:\n{yol}")

    # ---------------- AÇIK BORÇLAR ----------------
    def _borc_sekmesi(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(6)

        bilgi = QLabel("Check-in yapılmış misafirlerin bugünden önceki (kalınmış) ama henüz "
                       "ödenmemiş geceleri. Çift tıkla: rezervasyon detayını aç.")
        bilgi.setWordWrap(True)
        lay.addWidget(bilgi)

        self.borc_tablo = _tablo(
            ["Misafir", "Telefon", "Oda", "Giriş", "Durum", "Ödenmemiş Gece", "Borç"], 0)
        self.borc_tablo.cellDoubleClicked.connect(
            lambda satir, _k: self._detay_ac(self.borc_tablo, satir))
        lay.addWidget(self.borc_tablo, 1)

        alt = QHBoxLayout()
        self.borc_ozet = QLabel("")
        self.borc_ozet.setStyleSheet("font-weight: 700;")
        alt.addWidget(self.borc_ozet)
        alt.addStretch(1)
        tahsil_btn = QPushButton("💳 Seçili Borcu Tahsil Et")
        tahsil_btn.setObjectName("birincil")
        tahsil_btn.clicked.connect(self.borc_tahsil_et)
        alt.addWidget(tahsil_btn)
        lay.addLayout(alt)
        return w

    def borc_yenile(self):
        try:
            self.borclar = repository.acik_borclar()
        except Exception as e:
            self.borclar = []
            QMessageBox.warning(self, "Hata", f"Açık borçlar okunamadı: {e}")
        t = self.borc_tablo
        t.setRowCount(len(self.borclar))
        for i, b in enumerate(self.borclar):
            durum = f"Çıktı ({b['cikis_tarihi']})" if b["cikis_tarihi"] else "İçeride"
            gece = f"{b['gece_adedi']} gece ({b['ilk_gece']}"
            gece += f" → {b['son_gece']})" if b["son_gece"] != b["ilk_gece"] else ")"
            degerler = [b["ad_soyad"], b["telefon"] or "", f"{b['kat_adi']} - Oda {b['oda_no']}",
                        b["giris_tarihi"], durum, gece, _tl(b["borc"])]
            for k, d in enumerate(degerler):
                h = QTableWidgetItem(str(d))
                if k == 0:
                    h.setData(Qt.UserRole, b["rez_id"])
                if k == 6:
                    h.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if b["cikis_tarihi"]:
                    h.setForeground(Qt.red)
                t.setItem(i, k, h)
        toplam = sum(b["borc"] or 0 for b in self.borclar)
        self.borc_ozet.setText(
            f"Toplam açık borç: {_tl(toplam)} ({len(self.borclar)} oda)" if self.borclar
            else "Açık borç yok.")

    def borc_tahsil_et(self):
        satirlar = self.borc_tablo.selectionModel().selectedRows()
        if not satirlar:
            QMessageBox.information(self, "Seçim Yok", "Önce listeden bir satır seç.")
            return
        b = self.borclar[satirlar[0].row()]
        sekil, ok = QInputDialog.getItem(
            self, "Ödeme Şekli",
            f"{b['ad_soyad']} · {b['kat_adi']} - Oda {b['oda_no']}\n"
            f"{b['gece_adedi']} gece, toplam {_tl(b['borc'])} tahsil edilecek.\nÖdeme nasıl alındı?",
            database.ODEME_SEKILLERI, 0, False)
        if not ok:
            return
        try:
            adet, tutar = repository.odasi_borclarini_tahsil_et(b["ro_id"], sekil)
        except Exception as e:
            QMessageBox.warning(self, "Hata", str(e))
            return
        QMessageBox.information(self, "Tahsil Edildi", f"{adet} gece, {_tl(tutar)} ödendi olarak işaretlendi.")
        self._degisti()

    # ---------------- ortak ----------------
    def _detay_ac(self, tablo, satir):
        h = tablo.item(satir, 0)
        if h is None or h.data(Qt.UserRole) is None:
            return
        from detay_dialog import RezervasyonDetayDialog
        RezervasyonDetayDialog(h.data(Qt.UserRole), self).exec()
        self._degisti()

    def _degisti(self):
        self.kasa_yenile()
        self.borc_yenile()
        if self.yenile_callback:
            self.yenile_callback()
