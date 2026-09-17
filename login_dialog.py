# -*- coding: utf-8 -*-
"""
Giriş ekranları: ilk çalıştırmada kullanıcı oluşturma + normal giriş penceresi.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLabel, QLineEdit, QPushButton,
    QMessageBox, QDialogButtonBox
)
from PySide6.QtCore import Qt

import auth


class IlkKullaniciDialog(QDialog):
    """Veritabanında hiç kullanıcı yoksa (ilk kurulum) gösterilir."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("İlk Kullanıcıyı Oluştur")
        self.setMinimumWidth(360)
        self.olusturulan_kullanici_adi = None

        layout = QVBoxLayout(self)
        bilgi = QLabel(
            "Sistemde henüz kullanıcı yok. Resepsiyonda çalışan herkes için "
            "ayrı bir hesap oluşturabilirsin (bu sayede hangi rezervasyonu "
            "kimin aldığı görülebilir). Önce kendi hesabını oluştur:"
        )
        bilgi.setWordWrap(True)
        layout.addWidget(bilgi)

        form = QFormLayout()
        self.ad_soyad = QLineEdit()
        form.addRow("Ad Soyad:", self.ad_soyad)

        self.kullanici_adi = QLineEdit()
        self.kullanici_adi.setPlaceholderText("örn. ayse")
        form.addRow("Kullanıcı Adı:", self.kullanici_adi)

        self.sifre = QLineEdit()
        self.sifre.setEchoMode(QLineEdit.Password)
        form.addRow("Şifre:", self.sifre)

        self.sifre_tekrar = QLineEdit()
        self.sifre_tekrar.setEchoMode(QLineEdit.Password)
        form.addRow("Şifre (Tekrar):", self.sifre_tekrar)

        layout.addLayout(form)

        olustur_btn = QPushButton("Hesabı Oluştur ve Giriş Yap")
        olustur_btn.setStyleSheet("font-weight: bold; padding: 8px;")
        olustur_btn.clicked.connect(self.olustur)
        layout.addWidget(olustur_btn)

    def olustur(self):
        if not self.kullanici_adi.text().strip() or not self.sifre.text():
            QMessageBox.warning(self, "Eksik Bilgi", "Kullanıcı adı ve şifre gerekli.")
            return
        if self.sifre.text() != self.sifre_tekrar.text():
            QMessageBox.warning(self, "Şifre Uyuşmuyor", "Girilen şifreler birbiriyle eşleşmiyor.")
            return
        if len(self.sifre.text()) < 4:
            QMessageBox.warning(self, "Zayıf Şifre", "Şifre en az 4 karakter olmalı.")
            return
        try:
            auth.kullanici_ekle(
                self.kullanici_adi.text().strip(),
                self.sifre.text(),
                self.ad_soyad.text().strip()
            )
        except ValueError as e:
            QMessageBox.warning(self, "Hata", str(e))
            return
        self.olusturulan_kullanici_adi = self.kullanici_adi.text().strip().lower()
        self.accept()


class GirisDialog(QDialog):
    """Normal giriş penceresi (kullanıcı zaten mevcutsa)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Misafirhane Sistemi - Giriş")
        self.setMinimumWidth(340)
        self.giris_yapan = None  # basarili girişte kullanici satiri (sqlite3.Row)

        layout = QVBoxLayout(self)
        baslik = QLabel("<h3>Giriş Yap</h3>")
        layout.addWidget(baslik)

        form = QFormLayout()
        self.kullanici_adi = QLineEdit()
        form.addRow("Kullanıcı Adı:", self.kullanici_adi)

        self.sifre = QLineEdit()
        self.sifre.setEchoMode(QLineEdit.Password)
        self.sifre.returnPressed.connect(self.giris_yap)
        form.addRow("Şifre:", self.sifre)
        layout.addLayout(form)

        self.hata_label = QLabel("")
        self.hata_label.setStyleSheet("color: #c0392b;")
        layout.addWidget(self.hata_label)

        giris_btn = QPushButton("Giriş Yap")
        giris_btn.setStyleSheet("font-weight: bold; padding: 8px;")
        giris_btn.clicked.connect(self.giris_yap)
        layout.addWidget(giris_btn)

        self.kullanici_adi.setFocus()

    def giris_yap(self):
        kullanici = auth.kullanici_dogrula(self.kullanici_adi.text(), self.sifre.text())
        if kullanici is None:
            self.hata_label.setText("Kullanıcı adı veya şifre hatalı.")
            self.sifre.clear()
            self.sifre.setFocus()
            return
        self.giris_yapan = kullanici
        self.accept()
