# -*- coding: utf-8 -*-
"""
KBS Bildirim Penceresi - izole (standalone) test arayüzü.

Ana uygulamadan bağımsız çalışır:
    python kbs_pencere.py            (varsayılan veritabanı)
    python kbs_pencere.py <veri.db>  (belirli bir veritabanı)

Özellikler:
- Bekleyen GİRİŞ / ÇIKIŞ bildirimlerini tabloda listeler
- Excel bildirim dosyası üretir (kbs.kbs_excel_ure)
- Seçili satırları "gönderildi" işaretler (kbs_takip.db'de tutulur)
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QTabWidget, QLabel, QFileDialog,
    QMessageBox, QLineEdit, QHeaderView,
)
from PySide6.QtCore import Qt

import kbs

_SUTUNLAR = ["TC No", "Ad Soyad", "Telefon", "Kat / Oda", "Tarih", "Kişi Tipi", "Not"]


class KbsPencere(QDialog):
    def __init__(self, db_yolu=None, parent=None, takip_yolu=None):
        super().__init__(parent)
        self.db_yolu = db_yolu or kbs.varsayilan_veri_yolu()
        self.takip_yolu = takip_yolu or kbs.TAKIP_DOSYASI
        self.giris_satirlari = []
        self.cikis_satirlari = []
        self.setWindowTitle("KBS Kimlik Bildirimi - Test Penceresi")
        self.resize(900, 560)
        self._kur_arayuz()
        self.yenile()

    def _kur_arayuz(self):
        dikey = QVBoxLayout(self)

        ust = QHBoxLayout()
        ust.addWidget(QLabel("Veritabanı:"))
        self.db_alani = QLineEdit(self.db_yolu)
        self.db_alani.setReadOnly(True)
        ust.addWidget(self.db_alani, 1)
        db_btn = QPushButton("Seç...")
        db_btn.clicked.connect(self.db_sec)
        ust.addWidget(db_btn)
        dikey.addLayout(ust)

        self.sekmeler = QTabWidget()
        self.giris_tablo = self._yeni_tablo()
        self.cikis_tablo = self._yeni_tablo()
        self.sekmeler.addTab(self.giris_tablo, "GİRİŞ bildirimleri")
        self.sekmeler.addTab(self.cikis_tablo, "ÇIKIŞ bildirimleri")
        dikey.addWidget(self.sekmeler, 1)

        araclar = QHBoxLayout()
        yenile_btn = QPushButton("Yenile")
        yenile_btn.clicked.connect(self.yenile)
        excel_btn = QPushButton("Excel çıkar...")
        excel_btn.clicked.connect(self.excel_cikar)
        gonder_btn = QPushButton("Seçilileri GÖNDERİLDİ işaretle")
        gonder_btn.clicked.connect(self.gonderildi_isaretle)
        araclar.addWidget(yenile_btn)
        araclar.addWidget(excel_btn)
        araclar.addWidget(gonder_btn)
        araclar.addStretch(1)
        dikey.addLayout(araclar)

        self.durum = QLabel("")
        dikey.addWidget(self.durum)

    def _yeni_tablo(self):
        tablo = QTableWidget(0, len(_SUTUNLAR))
        tablo.setHorizontalHeaderLabels(_SUTUNLAR)
        tablo.setSelectionBehavior(QTableWidget.SelectRows)
        tablo.setSelectionMode(QTableWidget.ExtendedSelection)
        tablo.setEditTriggers(QTableWidget.NoEditTriggers)
        tablo.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        return tablo

    def _doldur(self, tablo, satirlar):
        tablo.setUpdatesEnabled(False)
        tablo.setRowCount(len(satirlar))
        for i, s in enumerate(satirlar):
            degerler = [
                s["tc_no"], s["misafir_ad"], s["telefon"], s["oda"],
                s["tarih"], s["tip"].upper(), s["not"],
            ]
            for kol, deger in enumerate(degerler):
                h = QTableWidgetItem(str(deger))
                if kol == 0:
                    h.setData(Qt.UserRole, s["kesit"])
                tablo.setItem(i, kol, h)
        tablo.setUpdatesEnabled(True)

    def yenile(self):
        try:
            giris, cikis = kbs.kbs_bekleyenler(self.db_yolu, self.takip_yolu)
            ozet = kbs.kbs_durum_ozet(self.db_yolu, self.takip_yolu)
        except Exception as e:
            QMessageBox.critical(self, "KBS", "Veri okunamadı:\n%s" % e)
            return
        self.giris_satirlari = giris
        self.cikis_satirlari = cikis
        self._doldur(self.giris_tablo, giris)
        self._doldur(self.cikis_tablo, cikis)
        self.durum.setText(
            "Giriş bekleyen: %d  •  Çıkış bekleyen: %d  •  Toplam gönderilen: %d"
            % (len(giris), len(cikis), ozet["gonderilen"]))

    def _secilen_kayitlar(self):
        """Seçili satırların TAM kayıtlarını (tur/misafir_ad/tc_no/oda/tarih dahil)
        döndürür ki kbs_markala bunları denetim izine (BİLDİRİM GEÇMİŞİ) yazabilsin."""
        tablo = self.sekmeler.currentWidget()
        kaynak = self.giris_satirlari if tablo is self.giris_tablo else self.cikis_satirlari
        haritalar = {s["kesit"]: s for s in kaynak}
        satirlar = sorted({h.row() for h in tablo.selectedIndexes()})
        kayitlar = []
        for satir in satirlar:
            h = tablo.item(satir, 0)
            kesit = h.data(Qt.UserRole) if h is not None else None
            if kesit and kesit in haritalar:
                kayitlar.append(haritalar[kesit])
        return kayitlar

    def gonderildi_isaretle(self):
        kayitlar = self._secilen_kayitlar()
        if not kayitlar:
            QMessageBox.information(self, "KBS", "Önce listeden bir satır seç.")
            return
        try:
            kbs.kbs_markala(kayitlar, "gonderildi", self.takip_yolu)
        except Exception as e:
            QMessageBox.critical(self, "KBS", "İşaretlenemedi:\n%s" % e)
            return
        self.yenile()

    def excel_cikar(self):
        varsayilan = "KBS_Bildirim_%s.xlsx" % datetime.now().strftime("%Y%m%d_%H%M")
        yol, _ = QFileDialog.getSaveFileName(
            self, "Bildirim dosyasını kaydet", varsayilan,
            "Excel dosyası (*.xlsx)")
        if not yol:
            return
        try:
            g, c = kbs.kbs_excel_ure(yol, self.db_yolu, self.takip_yolu)
        except Exception as e:
            QMessageBox.critical(self, "KBS", "Dosya yazılamadı:\n%s" % e)
            return
        QMessageBox.information(
            self, "KBS", "Dosya hazır: %s\nGiriş satırı: %d, Çıkış satırı: %d" % (yol, g, c))

    def db_sec(self):
        yol, _ = QFileDialog.getOpenFileName(
            self, "Veritabanı seç", "", "SQLite (*.db);;Tüm dosyalar (*)")
        if yol:
            self.db_yolu = yol
            self.db_alani.setText(yol)
            self.yenile()


def main():
    app = QApplication(sys.argv)
    db_yolu = sys.argv[1] if len(sys.argv) > 1 else None
    pencere = KbsPencere(db_yolu)
    pencere.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()