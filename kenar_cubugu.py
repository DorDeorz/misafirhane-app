# -*- coding: utf-8 -*-
"""
Sol kenar çubuğu (1.0.6): ana penceredeki sekmeler ve araç pencereleri
(Takvim, Excel Raporu, KBS, Kasa, Günün Özeti) üstte yan yana değil, solda
alt alta durur. Üstteki ☰ düğmesiyle (ya da Ctrl+B) daraltılıp
genişletilir: dar halde yalnızca simgeler görünür (üzerine gelince adı
çıkar), geniş halde simge + ad. Son durum Ayarlar tablosunda
(`kenar_cubugu_dar`) saklanır, uygulama aynı halde açılır.
"""

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QPushButton, QLabel, QButtonGroup, QScrollArea, QWidget,
)
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QParallelAnimationGroup, QEasingCurve

import database


def ikon_ve_ad(metin):
    """'➕ Yeni Rezervasyon' -> ('➕', 'Yeni Rezervasyon')."""
    parca = metin.split(" ", 1)
    return (parca[0], parca[1].strip()) if len(parca) == 2 else ("•", metin)


class KenarCubugu(QFrame):
    sayfa_secildi = Signal(int)

    GENIS = 210
    DAR = 54
    SURE_MS = 160

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("kenar_cubugu")
        self._sayfa_butonlari = []
        self._tum_butonlar = []  # (buton, ikon, ad)
        self._basliklar = []
        self._animasyon = None
        self.dar = database.get_ayar("kenar_cubugu_dar", "0") == "1"

        dis = QVBoxLayout(self)
        dis.setContentsMargins(6, 6, 6, 6)
        dis.setSpacing(4)

        self.daralt_btn = QPushButton("☰")
        self.daralt_btn.setObjectName("kenar_daralt")
        self.daralt_btn.setToolTip("Menüyü daralt / genişlet (Ctrl+B)")
        self.daralt_btn.setCursor(Qt.PointingHandCursor)
        self.daralt_btn.clicked.connect(lambda: self.daralt(not self.dar))
        dis.addWidget(self.daralt_btn, 0, Qt.AlignLeft)

        alan = QScrollArea()
        alan.setObjectName("kenar_alan")
        alan.setWidgetResizable(True)
        alan.setFrameShape(QFrame.NoFrame)
        alan.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        icerik = QWidget()
        icerik.setObjectName("kenar_icerik")
        self._lay = QVBoxLayout(icerik)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(2)
        self._sayfa_lay = QVBoxLayout()
        self._sayfa_lay.setSpacing(2)
        self._lay.addLayout(self._sayfa_lay)
        self._lay.addSpacing(8)
        self._arac_basligi = self._baslik_ekle("ARAÇLAR")
        self._arac_lay = QVBoxLayout()
        self._arac_lay.setSpacing(2)
        self._lay.addLayout(self._arac_lay)
        self._lay.addStretch(1)
        alan.setWidget(icerik)
        dis.addWidget(alan, 1)

        self._grup = QButtonGroup(self)
        self._grup.setExclusive(True)
        self._grup.idClicked.connect(self.sayfa_secildi)

        self._genislik_ayarla(self.DAR if self.dar else self.GENIS)

    # ---------------- kurulum ----------------
    def _baslik_ekle(self, metin):
        etiket = QLabel(metin)
        etiket.setObjectName("kenar_baslik")
        self._lay.addWidget(etiket)
        self._basliklar.append(etiket)
        return etiket

    def _buton(self, metin, ipucu=""):
        ikon, ad = ikon_ve_ad(metin)
        b = QPushButton()
        b.setObjectName("kenar_btn")
        b.setCursor(Qt.PointingHandCursor)
        b.setProperty("ipucu", ipucu)
        self._tum_butonlar.append((b, ikon, ad))
        self._metni_ayarla(b, ikon, ad)
        return b

    def sayfa_ekle(self, metin):
        """Bir sekmeye karşılık gelen seçilebilir düğme (sıra = sekme sırası)."""
        b = self._buton(metin)
        b.setCheckable(True)
        self._grup.addButton(b, len(self._sayfa_butonlari))
        self._sayfa_butonlari.append(b)
        self._sayfa_lay.addWidget(b)
        return b

    def arac_ekle(self, metin, fonksiyon, ipucu=""):
        """Ayrı pencere açan düğme (seçili kalmaz)."""
        b = self._buton(metin, ipucu)
        b.clicked.connect(fonksiyon)
        self._arac_lay.addWidget(b)
        return b

    def secili_yap(self, indeks):
        if 0 <= indeks < len(self._sayfa_butonlari):
            self._sayfa_butonlari[indeks].setChecked(True)

    # ---------------- daraltma ----------------
    def _metni_ayarla(self, b, ikon, ad):
        ipucu = b.property("ipucu") or ""
        if self.dar:
            b.setText(ikon)
            b.setToolTip(ad + (f"\n{ipucu}" if ipucu else ""))
        else:
            b.setText(f"{ikon}   {ad}")
            b.setToolTip(ipucu)

    def _metinleri_guncelle(self):
        for b, ikon, ad in self._tum_butonlar:
            self._metni_ayarla(b, ikon, ad)
        for etiket in self._basliklar:
            etiket.setVisible(not self.dar)

    def _genislik_ayarla(self, genislik):
        self.setMinimumWidth(genislik)
        self.setMaximumWidth(genislik)
        self._metinleri_guncelle()

    def daralt(self, dar, animasyonlu=True):
        """dar=True: yalnız simgeler; False: simge + ad. Durum kaydedilir."""
        if dar == self.dar:
            return
        self.dar = dar
        try:
            database.set_ayar("kenar_cubugu_dar", "1" if dar else "0")
        except Exception:
            pass
        hedef = self.DAR if dar else self.GENIS
        if not animasyonlu or not self.isVisible():
            self._genislik_ayarla(hedef)
            return
        if dar:
            # daralırken yazılar hemen kalkar ki sıkışıp kesilmesin
            self._metinleri_guncelle()
        grup = QParallelAnimationGroup(self)
        for ozellik in (b"minimumWidth", b"maximumWidth"):
            a = QPropertyAnimation(self, ozellik)
            a.setDuration(self.SURE_MS)
            a.setStartValue(self.width())
            a.setEndValue(hedef)
            a.setEasingCurve(QEasingCurve.OutCubic)
            grup.addAnimation(a)
        grup.finished.connect(lambda: self._genislik_ayarla(hedef))
        self._animasyon = grup
        grup.start()
