# -*- coding: utf-8 -*-
"""
Not geçmişi kutusu (1.0.6): bir rezervasyonun, misafirin ya da referansın
notları, her birinin yanında YAZAN kullanıcı ve zaman. Yeni not yazılıp
"Ekle"ye basılınca hemen kaydedilir (pencerenin Kaydet düğmesini beklemez);
yazan, giriş yapmış kullanıcıdır (loglama.AKTIF_KULLANICI). Yanlış yazılan
not seçilip silinebilir; silinen not İşlem Geçmişi'ne düşer.

Rezervasyon detayı, Misafirler sekmesindeki misafir/referans pencereleri
bu kutuyu ortak kullanır.
"""

from datetime import datetime
from html import escape

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLineEdit, QPushButton, QLabel, QMessageBox,
)
from PySide6.QtCore import Qt, Signal

import repository


def zaman_goster(zaman):
    """'2026-10-02 14:05:33' -> '02.10.2026 14:05' (bozuksa olduğu gibi)."""
    try:
        return datetime.strptime((zaman or "")[:16], "%Y-%m-%d %H:%M").strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return zaman or ""


def not_satiri_html(n):
    """Tek notu 'metin — yazan · zaman' biçiminde (uyarı kutuları için)."""
    return (f"{escape(n['metin'])} <span style='color:#777;'>— {escape(n['yazan'] or '?')} · "
            f"{zaman_goster(n['zaman'])}</span>")


class NotlarWidget(QWidget):
    """tur: 'rezervasyon' / 'misafir' / 'referans'.
    anahtar: ilgili kaydın anahtarı; None ise kutu pasif kalır ve bos_mesaj
    gösterilir. anahtar_saglayici verilirse anahtar ilk not eklenirken ondan
    alınır (ör. misafir kartı not eklenirken açılır)."""

    degisti = Signal()

    def __init__(self, tur, anahtar=None, anahtar_saglayici=None, bos_mesaj="", parent=None):
        super().__init__(parent)
        self.tur = tur
        self.anahtar = anahtar
        self.anahtar_saglayici = anahtar_saglayici
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self.liste = QListWidget()
        self.liste.setWordWrap(True)
        self.liste.setAlternatingRowColors(True)
        self.liste.setMinimumHeight(60)
        lay.addWidget(self.liste, 1)

        self.bos_etiket = QLabel(bos_mesaj)
        self.bos_etiket.setWordWrap(True)
        self.bos_etiket.setStyleSheet("color: #777; font-style: italic;")
        lay.addWidget(self.bos_etiket)

        satir = QHBoxLayout()
        satir.setSpacing(4)
        self.yeni = QLineEdit()
        self.yeni.setPlaceholderText("Yeni not yaz, Enter ya da Ekle")
        self.yeni.returnPressed.connect(self.ekle)
        satir.addWidget(self.yeni, 1)
        self.ekle_btn = QPushButton("Ekle")
        self.ekle_btn.clicked.connect(self.ekle)
        satir.addWidget(self.ekle_btn)
        self.sil_btn = QPushButton("Sil")
        self.sil_btn.setToolTip("Seçili notu siler (İşlem Geçmişi'ne yazılır).")
        self.sil_btn.setStyleSheet("color: #c0392b;")
        self.sil_btn.clicked.connect(self.sil)
        satir.addWidget(self.sil_btn)
        lay.addLayout(satir)

        self.yenile()

    def _aktif_mi(self):
        return self.anahtar is not None or self.anahtar_saglayici is not None

    def yenile(self):
        self.liste.clear()
        aktif = self._aktif_mi()
        notlar = repository.notlar_listele(self.tur, self.anahtar) if self.anahtar is not None else []
        for n in notlar:
            item = QListWidgetItem(f"{n['metin']}\n— {n['yazan'] or '?'} · {zaman_goster(n['zaman'])}")
            item.setData(Qt.UserRole, n["id"])
            self.liste.addItem(item)
        self.liste.setVisible(bool(notlar))
        self.bos_etiket.setVisible(not notlar)
        if aktif and not notlar:
            self.bos_etiket.setText("Henüz not yok.")
        for w in (self.yeni, self.ekle_btn):
            w.setEnabled(aktif)
        self.sil_btn.setEnabled(bool(notlar))
        self.notlar = notlar

    def not_sayisi(self):
        return len(self.notlar)

    def ekle(self):
        metin = self.yeni.text().strip()
        if not metin:
            return
        try:
            if self.anahtar is None and self.anahtar_saglayici is not None:
                self.anahtar = self.anahtar_saglayici()
            repository.not_ekle(self.tur, self.anahtar, metin)
        except Exception as e:
            QMessageBox.warning(self, "Not Eklenemedi", str(e))
            return
        self.yeni.clear()
        self.yenile()
        self.degisti.emit()

    def sil(self):
        item = self.liste.currentItem()
        if item is None:
            QMessageBox.information(self, "Not Seçilmedi", "Silmek için önce listeden bir not seç.")
            return
        if QMessageBox.question(self, "Notu Sil", "Seçili not silinsin mi?",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            repository.not_sil(item.data(Qt.UserRole))
        except Exception as e:
            QMessageBox.warning(self, "Silinemedi", str(e))
            return
        self.yenile()
        self.degisti.emit()
