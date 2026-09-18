# -*- coding: utf-8 -*-
"""
Misafirhane Rezervasyon Sistemi
Basit, internetsiz çalışan masaüstü uygulaması.
"""

import sys
import os
from datetime import date, datetime

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QDateEdit, QComboBox, QLineEdit, QSpinBox, QFormLayout, QMessageBox,
    QHeaderView, QGroupBox, QCheckBox, QTextEdit, QDialog, QDialogButtonBox,
    QFileDialog, QScrollArea, QSplitter, QGridLayout, QFrame
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QIcon

import database
import repository
import export
import auth
import loglama
import tema
import versiyon
from database import fiyat_tipi_goster
from takvim_widget import TakvimGridWidget
from detay_dialog import RezervasyonDetayDialog, CheckinDialog
from login_dialog import GirisDialog, IlkKullaniciDialog


def qdate_to_str(qd: QDate) -> str:
    return qd.toString("yyyy-MM-dd")


def str_to_qdate(s: str) -> QDate:
    return QDate.fromString(s, "yyyy-MM-dd")


def tabloyu_kompakt_yap(tablo, satir_yuksekligi=30):
    """Tabloları laptop dostu yapmak için ortak kompakt ayar: satır no'suz,
    sabit (küçük) satır yüksekliği, içerik enine sığacak şekilde uzatma."""
    tablo.verticalHeader().setVisible(False)
    tablo.verticalHeader().setDefaultSectionSize(satir_yuksekligi)
    tablo.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)


def _telefon_gecerli_mi(metin):
    """Telefon numarasi gecerli mi? Sadece rakami tutup 9-12 hane olup
    olmadigina bakar (cep +90'li veya sabit dahil)."""
    rakamlar = "".join(c for c in metin if c.isdigit())
    if not rakamlar:
        return False
    if not (9 <= len(rakamlar) <= 12):
        return False
    if len(rakamlar) == 12 and rakamlar.startswith("90"):
        rakamlar = rakamlar[2:]
    return rakamlar.startswith("0") and len(rakamlar) in (10, 11)


# ============================================================
# TAB 1: ODA DURUMU (o günün check-in listesi -> 2.jpeg sağ sayfa)
# ============================================================
class OdaDurumuTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        ust = QHBoxLayout()
        ust.addWidget(QLabel("Tarih:"))
        self.tarih_sec = QDateEdit(QDate.currentDate())
        self.tarih_sec.setCalendarPopup(True)
        self.tarih_sec.dateChanged.connect(self.yenile)
        ust.addWidget(self.tarih_sec)

        geri_btn = QPushButton("< Önceki Gün")
        geri_btn.clicked.connect(lambda: self.tarih_sec.setDate(self.tarih_sec.date().addDays(-1)))
        ileri_btn = QPushButton("Sonraki Gün >")
        ileri_btn.clicked.connect(lambda: self.tarih_sec.setDate(self.tarih_sec.date().addDays(1)))
        bugun_btn = QPushButton("Bugün")
        bugun_btn.clicked.connect(lambda: self.tarih_sec.setDate(QDate.currentDate()))

        ust.addWidget(geri_btn)
        ust.addWidget(ileri_btn)
        ust.addWidget(bugun_btn)
        ust.addStretch()

        excel_btn = QPushButton("📊 Bu Günü Excel'e Aktar")
        excel_btn.clicked.connect(self.excele_aktar)
        ust.addWidget(excel_btn)

        layout.addLayout(ust)

        self.ozet_label = QLabel("")
        layout.addWidget(self.ozet_label)

        self.tablo = QTableWidget()
        self.tablo.setColumnCount(12)
        self.tablo.setHorizontalHeaderLabels([
            "Kat", "Oda No", "Tip", "Ad Soyad", "TC No", "Telefon",
            "Kişi/Kapasite", "Fiyat Tipi", "Tutar", "Çıkışa Kalan", "Ödeme Durumu",
            "Oda Durumu"
        ])
        self.tablo.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tablo.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tablo.cellDoubleClicked.connect(self._hucre_cift_tiklandi)
        tabloyu_kompakt_yap(self.tablo)
        self.tablo.setToolTip(
            "Ödeme durumuna çift tıklayarak ödendi/ödenmedi işaretleyebilirsin. "
            "Diğer sütunlara (isim, TC vb.) çift tıklayarak misafirin bilgilerini düzenleyebilirsin."
        )
        layout.addWidget(self.tablo, stretch=1)

        self.ozet_label = QLabel("")
        self.cikis_uyari = QLabel("")
        self.cikis_uyari.setWordWrap(True)
        layout.addWidget(self.ozet_label)
        layout.addWidget(self.cikis_uyari)

        self.yenile()

    def yenile(self):
        tarih_str = qdate_to_str(self.tarih_sec.date())
        rows = repository.gunun_oda_durumu(tarih_str)
        bugun = date.today().isoformat()
        self.tablo.setRowCount(0)
        dolu = 0
        for r in rows:
            row_idx = self.tablo.rowCount()
            self.tablo.insertRow(row_idx)
            dolu_mu = r["rez_id"] is not None
            if dolu_mu:
                dolu += 1

            gelmedi = dolu_mu and not r["checkin_yapildi"] and r["giris_tarihi"] < bugun

            kisi_kapasite = f"{r['kisi_sayisi']}/{r['kapasite']}" if dolu_mu else f"-/{r['kapasite']}"

            if gelmedi:
                kalan_metin = "⚠ GELMEDİ (No-Show)"
            elif dolu_mu:
                kalan = r["kalan_gece"]
                if kalan == 1:
                    kalan_metin = "🔴 Son gece (yarın çıkış)"
                else:
                    kalan_metin = f"{kalan} gece kaldı"
            else:
                kalan_metin = ""

            degerler = [
                r["kat_adi"] or "",
                str(r["oda_no"]),
                r["oda_tipi"] or "",
                r["ad_soyad"] or "— Boş —",
                r["tc_no"] or "",
                r["telefon"] or "",
                kisi_kapasite,
                fiyat_tipi_goster(r["fiyat_tipi"]) if dolu_mu else (r["fiyat_tipi"] or ""),
                str(r["tutar"]) + " TL" if r["tutar"] else "",
                kalan_metin,
                "",
                self._oda_durum_metni(r) if not dolu_mu else "",
            ]
            for col, val in enumerate(degerler):
                item = QTableWidgetItem(val)
                if not dolu_mu:
                    tema.renklendir(item, "#eeeeee")
                    if col == 11:
                        durum = r.get("aktif_durum") or "temiz"
                        if durum == "temizlikte":
                            tema.renklendir(item, "#fdebd0")
                        elif durum == "arizali":
                            tema.renklendir(item, "#d9d9d9")
                else:
                    item.setData(Qt.UserRole, r["rez_id"])
                    if gelmedi:
                        tema.renklendir(item, "#f8d0d0")
                    elif col == 9 and r["kalan_gece"] == 1:
                        tema.renklendir(item, "#fde3cf")
                self.tablo.setItem(row_idx, col, item)

            odeme_col = 10
            if dolu_mu:
                if r["odendi"]:
                    metin = "✓ ÖDENDİ"
                    if r["odeme_sekli"]:
                        metin += f" ({r['odeme_sekli']})"
                    item = QTableWidgetItem(metin)
                    tema.renklendir(item, "#c8f7c5")
                else:
                    item = QTableWidgetItem("✗ ÖDENMEDİ")
                    tema.renklendir(item, "#f7c5c5")
                item.setData(Qt.UserRole, r["odeme_id"])
                item.setData(Qt.UserRole + 1, bool(r["odendi"]))
                self.tablo.setItem(row_idx, odeme_col, item)

        self.ozet_label.setText(f"Toplam oda: {len(rows)}  |  Dolu: {dolu}  |  Boş: {len(rows) - dolu}")

        cikacaklar = repository.bugun_cikacaklar(tarih_str)
        if cikacaklar:
            satirlar = [f"• {c['kat_adi']} - Oda {c['oda_no']}: {c['ad_soyad']}" for c in cikacaklar]
            self.cikis_uyari.setText("🚪 Bugün çıkış yapacaklar: " + "  ".join(satirlar))
            self.cikis_uyari.setVisible(True)
        else:
            self.cikis_uyari.setText("")
            self.cikis_uyari.setVisible(False)

    def _oda_durum_metni(self, r):
        durum = r.get("aktif_durum") or "temiz"
        if durum == "temizlikte":
            return "🧹 Temizlikte"
        if durum == "arizali":
            return f"🔧 Arızalı (bitiş: {r.get('ariza_bitis') or '?'})"
        return "Temiz"

    def _hucre_cift_tiklandi(self, row, col):
        if col == 10:
            self.odeme_isle(row, col)
            return
        if col == 11:
            return  # oda durumu bogundaydi, detay yok
        item = self.tablo.item(row, 3)  # Ad Soyad sütunundan rez_id oku
        if item is None:
            return
        rez_id = item.data(Qt.UserRole)
        if rez_id is None:
            return  # bos oda
        dialog = RezervasyonDetayDialog(rez_id, self)
        dialog.exec()
        if dialog.kaydedildi:
            self.yenile()

    def odeme_isle(self, row, col):
        odeme_item = self.tablo.item(row, 10)
        if odeme_item is None:
            return
        odeme_id = odeme_item.data(Qt.UserRole)
        if odeme_id is None:
            return  # boş oda

        mevcut_odendi = bool(odeme_item.data(Qt.UserRole + 1))
        yeni_durum = not mevcut_odendi

        odeme_sekli = None
        if yeni_durum:
            secim, ok = self._odeme_sekli_sec()
            if not ok:
                return
            odeme_sekli = secim

        repository.odeme_guncelle(odeme_id, yeni_durum, odeme_sekli)
        self.yenile()

    def _odeme_sekli_sec(self):
        from PySide6.QtWidgets import QInputDialog
        secim, ok = QInputDialog.getItem(
            self, "Ödeme Şekli", "Ödeme nasıl alındı?",
            database.ODEME_SEKILLERI, 0, False
        )
        return secim, ok

    def excele_aktar(self):
        from PySide6.QtWidgets import QFileDialog
        tarih_str = qdate_to_str(self.tarih_sec.date())
        varsayilan_ad = f"oda_durumu_{tarih_str}.xlsx"
        dosya_yolu, _ = QFileDialog.getSaveFileName(
            self, "Excel Dosyasını Kaydet", varsayilan_ad, "Excel Dosyası (*.xlsx)"
        )
        if not dosya_yolu:
            return
        try:
            sayi = export.gunluk_durumu_disa_aktar(dosya_yolu, tarih_str)
            QMessageBox.information(self, "Başarılı", f"{sayi} oda kaydı Excel'e aktarıldı:\n{dosya_yolu}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Excel'e aktarılırken hata oluştu:\n{e}")


# ============================================================
# TAB 2: GÜNÜN GİRİŞLERİ (o gün check-in yapacaklar -> 2.jpeg sol sayfa)
# ============================================================
class GunlukGirisTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        ust = QHBoxLayout()
        ust.addWidget(QLabel("Tarih:"))
        self.tarih_sec = QDateEdit(QDate.currentDate())
        self.tarih_sec.setCalendarPopup(True)
        self.tarih_sec.dateChanged.connect(self.yenile)
        ust.addWidget(self.tarih_sec)

        geri_btn = QPushButton("< Önceki Gün")
        geri_btn.clicked.connect(lambda: self.tarih_sec.setDate(self.tarih_sec.date().addDays(-1)))
        ileri_btn = QPushButton("Sonraki Gün >")
        ileri_btn.clicked.connect(lambda: self.tarih_sec.setDate(self.tarih_sec.date().addDays(1)))
        bugun_btn = QPushButton("Bugün")
        bugun_btn.clicked.connect(lambda: self.tarih_sec.setDate(QDate.currentDate()))
        ust.addWidget(geri_btn)
        ust.addWidget(ileri_btn)
        ust.addWidget(bugun_btn)
        ust.addStretch()
        layout.addLayout(ust)

        self.tablo = QTableWidget()
        self.tablo.setColumnCount(8)
        self.tablo.setHorizontalHeaderLabels([
            "Oda", "Ad Soyad", "Telefon", "Kişi", "Gece", "Fiyat Tipi", "Toplam Tutar", "Durum"
        ])
        self.tablo.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tablo.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tablo.cellDoubleClicked.connect(self._hucre_cift_tiklandi)
        tabloyu_kompakt_yap(self.tablo)
        self.tablo.setToolTip("Bir satıra çift tıklayarak rezervasyon detayına ulaşabilirsin.")
        layout.addWidget(self.tablo, stretch=1)

        self.yenile()

    def yenile(self):
        tarih_str = qdate_to_str(self.tarih_sec.date())
        rows = repository.gunun_girisleri(tarih_str)
        bugun = date.today().isoformat()
        self.tablo.setRowCount(0)
        for r in rows:
            row_idx = self.tablo.rowCount()
            self.tablo.insertRow(row_idx)
            toplam = repository.rezervasyon_gecelik_toplami(r) * (r["gece_sayisi"] or 1)

            if r["checkin_yapildi"]:
                durum_metni = "✓ Geldi"
                renk = QColor("#c8f7c5")
            elif repository.gelmedi_mi(r, bugun):
                durum_metni = "⚠ Gelmedi (No-Show)"
                renk = QColor("#f8d0d0")
            else:
                durum_metni = "Henüz Gelmedi"
                renk = QColor("#fff3cd")

            degerler = [
                str(r["oda_no"]),
                r["ad_soyad"],
                r["telefon"] or "",
                str(r["kisi_sayisi"]),
                str(r["gece_sayisi"]),
                fiyat_tipi_goster(r["fiyat_tipi"]),
                f"{toplam} TL",
                durum_metni,
            ]
            for col, val in enumerate(degerler):
                item = QTableWidgetItem(val)
                item.setData(Qt.UserRole, r["id"])
                if col == 7:
                    tema.renklendir(item, renk)
                self.tablo.setItem(row_idx, col, item)

    def _hucre_cift_tiklandi(self, row, col):
        item = self.tablo.item(row, 0)
        if item is None:
            return
        rez_id = item.data(Qt.UserRole)
        if rez_id is None:
            return
        dialog = RezervasyonDetayDialog(rez_id, self)
        dialog.exec()
        if dialog.kaydedildi:
            self.yenile()


# ============================================================
# TAB: CHECK-IN (misafirleri odalara teker teker yerleştirme)
# ============================================================
class CheckinTab(QWidget):
    def __init__(self, yenile_callback=None):
        super().__init__()
        self.yenile_callback = yenile_callback
        layout = QVBoxLayout(self)

        ust = QHBoxLayout()
        ust.addWidget(QLabel("Tarih:"))
        self.tarih_sec = QDateEdit(QDate.currentDate())
        self.tarih_sec.setCalendarPopup(True)
        self.tarih_sec.dateChanged.connect(self.yenile)
        ust.addWidget(self.tarih_sec)

        geri_btn = QPushButton("< Önceki Gün")
        geri_btn.clicked.connect(lambda: self.tarih_sec.setDate(self.tarih_sec.date().addDays(-1)))
        ileri_btn = QPushButton("Sonraki Gün >")
        ileri_btn.clicked.connect(lambda: self.tarih_sec.setDate(self.tarih_sec.date().addDays(1)))
        bugun_btn = QPushButton("Bugün")
        bugun_btn.clicked.connect(lambda: self.tarih_sec.setDate(QDate.currentDate()))
        ust.addWidget(geri_btn)
        ust.addWidget(ileri_btn)
        ust.addWidget(bugun_btn)
        ust.addStretch()
        layout.addLayout(ust)

        self.tablo = QTableWidget()
        self.tablo.setColumnCount(7)
        self.tablo.setHorizontalHeaderLabels(
            ["Kat", "Oda", "Tip", "Kapasite", "Durum", "Kişi/Kapasite", "İşlem"])
        self.tablo.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tablo.horizontalHeader().setStretchLastSection(False)
        self.tablo.setEditTriggers(QTableWidget.NoEditTriggers)
        tabloyu_kompakt_yap(self.tablo, 32)
        self.tablo.setToolTip(
            "🟩 BOŞ = rezervasyon yok  |  🟨 BEKLENİYOR = rezerve edildi ama misafir gelmedi  |  "
            "🟦 İÇERİDE = check-in yapıldı, misafir odada"
        )
        layout.addWidget(self.tablo, stretch=1)

        self.yenile()

    def yenile(self):
        tarih_str = qdate_to_str(self.tarih_sec.date())
        rows = repository.gunun_checkin_durumu(tarih_str)
        self.tablo.setRowCount(0)
        for r in rows:
            row_idx = self.tablo.rowCount()
            self.tablo.insertRow(row_idx)

            if r["rez_id"] is None:
                oda_durum = r.get("aktif_durum") or "temiz"
                if oda_durum == "temizlikte":
                    durum = "🧹 TEMİZLİKTE (temizlenmeden verilmez)"
                    renk = QColor("#fdebd0")
                elif oda_durum == "arizali":
                    durum = f"🔧 ARIZALI (bitiş: {r.get('ariza_bitis') or '?'})"
                    renk = QColor("#d9d9d9")
                else:
                    durum = "⬜ BOŞ"
                    renk = QColor("#f5f5f5")
                kisi_bilgi = f"-/{r['kapasite']}"
            elif r["checkin_yapildi"]:
                durum = f"🟦 İÇERİDE — {r['ad_soyad']}"
                renk = QColor("#cfe2ff")
                kisi_bilgi = f"{r['kisi_sayisi']}/{r['kapasite']}"
            else:
                durum = f"🟨 BEKLENİYOR — Rezerve: {r['ad_soyad']} ({r['telefon'] or '-'})"
                renk = QColor("#fff3cd")
                kisi_bilgi = f"{r['kisi_sayisi']} kişi bekleniyor / {r['kapasite']}"

            degerler = [
                r["kat_adi"] or "", str(r["oda_no"]), r["oda_tipi"] or "",
                str(r["kapasite"]), durum, kisi_bilgi
            ]
            for col, val in enumerate(degerler):
                item = QTableWidgetItem(val)
                tema.renklendir(item, renk)
                self.tablo.setItem(row_idx, col, item)

            islem_widget = QWidget()
            islem_layout = QHBoxLayout(islem_widget)
            islem_layout.setContentsMargins(2, 2, 2, 2)
            if r["rez_id"] is not None:
                if r["checkin_yapildi"]:
                    btn = QPushButton("Misafirleri Düzenle")
                else:
                    btn = QPushButton("✅ Check-in Yap")
                btn.clicked.connect(lambda checked, rid=r["rez_id"]: self._checkin_ac(rid))
                islem_layout.addWidget(btn)
            self.tablo.setCellWidget(row_idx, 6, islem_widget)

    def _checkin_ac(self, rez_id):
        dialog = CheckinDialog(rez_id, self)
        dialog.exec()
        if dialog.kaydedildi:
            self.yenile()
            if self.yenile_callback:
                self.yenile_callback()


# ============================================================
# TAB 3: YENİ REZERVASYON (takvim ızgarasından çoklu oda seçimi)
# ============================================================
class YeniRezervasyonTab(QWidget):
    """Tek ekran tasarımı — kaydırma gerektirmez.

    Sol panel: takvim + seçim kontrolleri. Sağ panel: misafir bilgileri +
    seçilen odalar (her oda için birim ve toplam tutar görünür, altında genel
    toplam). 'Özel' fiyat seçilince kişi başı gecelik tutarı belirgin bir alanda
    açılır (varsayılan Sabit önerilir) ve toplam tutar anlık önizlenir.
    """
    def __init__(self, yenile_callback=None, olusturan_kullanici=None):
        super().__init__()
        self.yenile_callback = yenile_callback
        self.olusturan_kullanici = olusturan_kullanici

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # ---------------- ÜST BAR (her zaman görünür, sabit) ----------------
        ust = QHBoxLayout()

        baslik = QLabel("Yeni Rezervasyon")
        baslik.setObjectName("baslik")
        ust.addWidget(baslik)

        ust.addSpacing(18)
        ust.addWidget(QLabel("Toplam misafir:"))
        self.toplam_kisi = QSpinBox()
        self.toplam_kisi.setRange(0, 50)
        self.toplam_kisi.setValue(0)
        self.toplam_kisi.setSpecialValueText("—")
        self.toplam_kisi.setMaximumWidth(110)
        self.toplam_kisi.valueChanged.connect(self._dagitim_durumunu_guncelle)
        ust.addWidget(self.toplam_kisi)

        self.dagitim_label = QLabel("")
        self.dagitim_label.setStyleSheet("font-weight: 600;")
        ust.addWidget(self.dagitim_label)
        ust.addStretch()

        temizle_btn = QPushButton("Baştan Başla")
        temizle_btn.setObjectName("ikincil")
        temizle_btn.clicked.connect(self.formu_temizle)
        ust.addWidget(temizle_btn)

        self.kaydet_btn = QPushButton("💾 Rezervasyonu Kaydet")
        self.kaydet_btn.setObjectName("birincil")
        self.kaydet_btn.clicked.connect(self.kaydet)
        ust.addWidget(self.kaydet_btn)
        root.addLayout(ust)

        # ---------------- ANA BÖLÜM: sol takvim | sağ panel ----------------
        split = QSplitter(Qt.Horizontal)
        split.setHandleWidth(4)
        root.addWidget(split, stretch=1)

        # ===================== SOL: TAKVİM + SEÇİM =====================
        sol = QWidget()
        sol.setMinimumWidth(620)
        sol_lay = QVBoxLayout(sol)
        sol_lay.setContentsMargins(0, 0, 6, 0)
        sol_lay.setSpacing(6)

        self.grid = TakvimGridWidget(interactive=True, gun_sayisi=14, kompakt=True)
        self.grid.secim_degisti.connect(self._aktif_secim_degisti)
        sol_lay.addWidget(self.grid, stretch=1)

        kontrol = QWidget()
        k_lay = QHBoxLayout(kontrol)
        k_lay.setContentsMargins(0, 0, 0, 0)
        k_lay.setSpacing(6)

        k_lay.addWidget(QLabel("Kişi:"))
        self.secim_kisi = QSpinBox()
        self.secim_kisi.setRange(1, 10)
        self.secim_kisi.setValue(1)
        self.secim_kisi.setMaximumWidth(70)
        k_lay.addWidget(self.secim_kisi)

        k_lay.addWidget(QLabel("Fiyat tipi:"))
        self.secim_fiyat = QComboBox()
        _sabit = database.gecelik_fiyat("Sabit")
        _uye = database.gecelik_fiyat("Uye")
        self.secim_fiyat.addItem(f"Sabit ({_sabit:,}₺)", "Sabit")
        self.secim_fiyat.addItem(f"Üye ({_uye:,}₺)", "Uye")
        self.secim_fiyat.addItem("Özel (kişi başı)", "Ozel")
        self.secim_fiyat.setMaximumWidth(200)
        self.secim_fiyat.currentIndexChanged.connect(self._fiyat_tipi_degisti)
        k_lay.addWidget(self.secim_fiyat)

        self.ozel_ucret = QSpinBox()
        self.ozel_ucret.setRange(0, 100000)
        self.ozel_ucret.setValue(0)
        self.ozel_ucret.setSuffix(" ₺/kişi/gece")
        self.ozel_ucret.setMaximumWidth(160)
        self.ozel_ucret.setToolTip(
            "Özel fiyat: kişi başı gecelik tutarı gir (örn. indirimli misafirler için). "
            "Varsayılan olarak 'Sabit' fiyat önerilir, istediğin gibi değiştir."
        )
        self.ozel_ucret.hide()
        k_lay.addWidget(self.ozel_ucret)

        k_lay.addWidget(QLabel("Süz:"))
        self.oda_filtre_kisi = QSpinBox()
        self.oda_filtre_kisi.setRange(0, 10)
        self.oda_filtre_kisi.setValue(0)
        self.oda_filtre_kisi.setSpecialValueText("tümü")
        self.oda_filtre_kisi.setMaximumWidth(80)
        self.oda_filtre_kisi.setToolTip("Kaç kişi alacak oda arıyorsun? Küçük odalar soluk görünür (opsiyonel).")
        self.oda_filtre_kisi.valueChanged.connect(lambda v: self.grid.set_min_kapasite_filtre(v))
        k_lay.addWidget(self.oda_filtre_kisi)
        k_lay.addStretch()

        self.ekle_btn = QPushButton("✚ Listeye Ekle")
        self.ekle_btn.setObjectName("birincil")
        self.ekle_btn.setEnabled(False)
        self.ekle_btn.clicked.connect(self.secimi_ekle)
        k_lay.addWidget(self.ekle_btn)

        iptal_btn = QPushButton("✕ Seçimi Bırak")
        iptal_btn.setObjectName("ikincil")
        iptal_btn.clicked.connect(self.grid.secimi_iptal_et)
        k_lay.addWidget(iptal_btn)
        sol_lay.addWidget(kontrol)

        self.secim_kapasite_label = QLabel("")
        self.secim_kapasite_label.setStyleSheet("font-style: italic; font-size: 10px;")
        sol_lay.addWidget(self.secim_kapasite_label)

        self.tutar_ozeti = QLabel("")
        self.tutar_ozeti.setStyleSheet("font-weight: 600;")
        sol_lay.addWidget(self.tutar_ozeti)
        split.addWidget(sol)

        # ===================== SAĞ: MİSAFİR + SEÇİLENLER =====================
        sag = QWidget()
        sag.setMinimumWidth(330)
        sag_lay = QVBoxLayout(sag)
        sag_lay.setContentsMargins(6, 0, 0, 0)
        sag_lay.setSpacing(8)

        form_kutu = QGroupBox("Rezervasyonu Alan Misafir")
        form = QGridLayout()
        form.setVerticalSpacing(6)

        form.addWidget(QLabel("Ad Soyad *"), 0, 0)
        self.ad_soyad = QLineEdit()
        form.addWidget(self.ad_soyad, 0, 1)

        form.addWidget(QLabel("Telefon *"), 1, 0)
        self.telefon = QLineEdit()
        self.telefon.setPlaceholderText("Örn: 0532 123 45 67")
        form.addWidget(self.telefon, 1, 1)

        form.addWidget(QLabel("Referans"), 2, 0)
        self.referans = QLineEdit()
        self.referans.setPlaceholderText("Örn: Başkan Ahmet Bey")
        form.addWidget(self.referans, 2, 1)

        form.addWidget(QLabel("Notlar"), 3, 0)
        self.notlar = QLineEdit()
        self.notlar.setPlaceholderText("Opsiyonel — TC No check-in ekranında girilir")
        form.addWidget(self.notlar, 3, 1)
        form.setColumnStretch(1, 1)
        form_kutu.setLayout(form)
        sag_lay.addWidget(form_kutu)

        secilen_kutu = QGroupBox("Seçilen Odalar")
        s_lay = QVBoxLayout(secilen_kutu)

        self.secilenler_tablo = QTableWidget()
        self.secilenler_tablo.setColumnCount(7)
        self.secilenler_tablo.setHorizontalHeaderLabels(
            ["Oda", "Giriş", "Gece", "Kişi", "Birim", "Tutar", ""])
        self.secilenler_tablo.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.secilenler_tablo.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.secilenler_tablo.setEditTriggers(QTableWidget.NoEditTriggers)
        self.secilenler_tablo.verticalHeader().setDefaultSectionSize(28)
        self.secilenler_tablo.setMinimumHeight(150)
        s_lay.addWidget(self.secilenler_tablo)

        self.toplam_ozet = QLabel("Henüz oda seçilmedi")
        self.toplam_ozet.setStyleSheet("font-weight: 700;")
        s_lay.addWidget(self.toplam_ozet)
        sag_lay.addWidget(secilen_kutu, stretch=1)
        split.addWidget(sag)

        split.setStretchFactor(0, 7)
        split.setStretchFactor(1, 4)
        split.setSizes([760, 400])

        self.secim_kisi.valueChanged.connect(self._tutar_ozetini_guncelle)
        self.ozel_ucret.valueChanged.connect(self._tutar_ozetini_guncelle)

    # ---------------- fiyat / özel fiyat ----------------
    def _fiyat_tipi_degisti(self):
        ozel_mi = self.secim_fiyat.currentData() == "Ozel"
        self.ozel_ucret.setVisible(ozel_mi)
        if ozel_mi and self.ozel_ucret.value() <= 0:
            # Varsayılan olarak Sabit fiyatı öner, kullanıcı isterse değiştirsin
            self.ozel_ucret.setValue(database.gecelik_fiyat("Sabit"))
        self._tutar_ozetini_guncelle()

    def _secim_fiyati_birimi(self):
        kod = self.secim_fiyat.currentData()
        ozel = self.ozel_ucret.value() if kod == "Ozel" else None
        return database.gecelik_fiyat(kod, ozel)

    # ---------------- takvim seçimleri ----------------
    def _aktif_secim_degisti(self):
        var_mi = self.grid.aktif_secim_var_mi()
        self.ekle_btn.setEnabled(var_mi)
        if var_mi:
            bilgi = self.grid.aktif_secim_bilgisi()
            if bilgi:
                oda, giris_str, gece = bilgi
                kapasite = oda["kapasite"] or 1
                self.secim_kisi.setMaximum(kapasite)
                # Onerilen kisi sayisi: once "kalan dagitilmasi gereken", yoksa filtre
                kalan = self._kalan_kisi_sayisi()
                oneri_kaynagi = kalan if kalan > 0 else self.oda_filtre_kisi.value()
                if oneri_kaynagi > 0:
                    onerilen = min(oneri_kaynagi, kapasite)
                    self.secim_kisi.setValue(onerilen)
                ipucu = ""
                if self.toplam_kisi.value() > 0 and kalan > 0:
                    ipucu = f" · {kalan} kişi kaldı; öneriyi kullanabilir ya da azaltıp başka oda seçebilirsin"
                self.secim_kapasite_label.setText(f"(Bu odanın kapasitesi: {kapasite} kişi{ipucu})")
        else:
            self.secim_kisi.setMaximum(10)
            self.secim_kapasite_label.setText("")
        self._tutar_ozetini_guncelle()

    def _kalan_kisi_sayisi(self):
        """Toplam kişi belirtildiyse, henüz odaya konmamış kalan sayı. Belirtilmediyse 0."""
        toplam = self.toplam_kisi.value()
        if toplam <= 0:
            return 0
        dagitilan = sum(s["kisi"] for s in self.grid.kilitli_listesi())
        return max(toplam - dagitilan, 0)

    def _dagitim_durumunu_guncelle(self, *_):
        toplam = self.toplam_kisi.value()
        if toplam <= 0:
            self.dagitim_label.setText("")
            return
        dagitilan = sum(s["kisi"] for s in self.grid.kilitli_listesi())
        kalan = toplam - dagitilan
        if kalan > 0:
            self.dagitim_label.setText(
                f"Dağıtılan: {dagitilan}/{toplam} · {kalan} kişiye ayrı oda gerekiyor"
            )
            self.dagitim_label.setStyleSheet("color: #b9770e; font-weight: 600;")
        elif kalan == 0:
            self.dagitim_label.setText(f"✓ {dagitilan}/{toplam} kişiye oda atandı")
            self.dagitim_label.setStyleSheet("color: #196f3d; font-weight: 700;")
        else:
            self.dagitim_label.setText(
                f"⚠ {-kalan} kişi fazla dağıtıldı"
            )
            self.dagitim_label.setStyleSheet("color: #c0392b; font-weight: 700;")

    def _tutar_ozetini_guncelle(self, *_):
        birim = self._secim_fiyati_birimi()
        aktif = self.grid.aktif_secim_var_mi()
        if aktif:
            bilgi = self.grid.aktif_secim_bilgisi()
            if bilgi:
                oda, _, gece = bilgi
                kisi = self.secim_kisi.value()
                toplam = birim * kisi * gece
                self.tutar_ozeti.setText(
                    f"Oda {oda['oda_no']} · {birim:,}₺ × {kisi} kişi × {gece} gece "
                    f"= <b>{toplam:,}₺</b>"
                )
                return
        self.tutar_ozeti.setText(f"{fiyat_tipi_goster(self.secim_fiyat.currentData())}: {birim:,}₺ / kişi / gece")

    # ---------------- liste işlemleri ----------------
    def secimi_ekle(self):
        bilgi = self.grid.aktif_secim_bilgisi()
        if bilgi:
            oda, _, _ = bilgi
            kapasite = oda["kapasite"] or 1
            if self.secim_kisi.value() > kapasite:
                QMessageBox.warning(self, "Kapasite Aşıldı", f"Bu oda en fazla {kapasite} kişi alabilir.")
                return
        fiyat_kodu = self.secim_fiyat.currentData()
        if fiyat_kodu == "Ozel" and self.ozel_ucret.value() <= 0:
            QMessageBox.warning(
                self, "Özel Fiyat",
                "Özel fiyat için kişi başı gecelik tutarı 0'dan büyük girmelisin."
            )
            return
        ozel_ucret = self.ozel_ucret.value() if fiyat_kodu == "Ozel" else None
        kayit = self.grid.aktif_secimi_kilitle(
            self.secim_kisi.value(), fiyat_kodu, ozel_ucret=ozel_ucret
        )
        if kayit is None:
            return
        self.ekle_btn.setEnabled(False)
        self.secim_kapasite_label.setText("")
        self._secilenler_tablosunu_ciz()
        self._dagitim_durumunu_guncelle()
        self._tutar_ozetini_guncelle()

    def _secilenler_tablosunu_ciz(self):
        secilenler = self.grid.kilitli_listesi()
        self.secilenler_tablo.setRowCount(0)
        for i, s in enumerate(secilenler):
            row = self.secilenler_tablo.rowCount()
            self.secilenler_tablo.insertRow(row)
            birim = database.gecelik_fiyat(s["fiyat_tipi"], s.get("ozel_ucret"))
            tutar = birim * s["kisi"] * s["gece"]
            ozel_mi = s["fiyat_tipi"] == "Ozel"
            birim_metin = f"Özel {birim:,}₺" if ozel_mi else f"{birim:,}₺"
            degerler = [
                f"{s['kat_adi']} - {s['oda_no']}",
                s["giris"],
                str(s["gece"]),
                str(s["kisi"]),
                birim_metin,
                f"{tutar:,}₺",
            ]
            for col, val in enumerate(degerler):
                self.secilenler_tablo.setItem(row, col, QTableWidgetItem(val))
            sil_btn = QPushButton("Çıkar")
            sil_btn.clicked.connect(lambda checked, idx=i: self._secimi_cikar(idx))
            self.secilenler_tablo.setCellWidget(row, 6, sil_btn)

        toplam = sum(
            database.gecelik_fiyat(s["fiyat_tipi"], s.get("ozel_ucret")) * s["kisi"] * s["gece"]
            for s in secilenler
        )
        kisi = sum(s["kisi"] for s in secilenler)
        oda = len(secilenler)
        if secilenler:
            self.toplam_ozet.setText(
                f"TOPLAM: <b>{toplam:,}₺</b>  ·  {oda} oda  ·  {kisi} kişi"
            )
        else:
            self.toplam_ozet.setText("Henüz oda seçilmedi")

    def _secimi_cikar(self, index):
        self.grid.kilitli_sil(index)
        self._secilenler_tablosunu_ciz()
        self._dagitim_durumunu_guncelle()
        self._tutar_ozetini_guncelle()

    # ---------------- sıfırlama / kaydet ----------------
    def formu_temizle(self):
        """Tüm seçim ve girilen bilgileri sıfırlar (Baştan Başla / kayıt sonrası)."""
        self.ad_soyad.clear()
        self.telefon.clear()
        self.referans.clear()
        self.notlar.clear()
        self.toplam_kisi.setValue(0)
        self.oda_filtre_kisi.setValue(0)
        self.secim_kisi.setValue(1)
        self.secim_fiyat.setCurrentIndex(0)
        self.grid.tumunu_temizle()
        self._secilenler_tablosunu_ciz()
        self._dagitim_durumunu_guncelle()
        self._tutar_ozetini_guncelle()
        self.ekle_btn.setEnabled(False)

    def kaydet(self):
        secilenler = self.grid.kilitli_listesi()
        if not secilenler:
            QMessageBox.warning(self, "Oda Seçilmedi", "Önce takvimden bir oda/gün seçip 'Listeye Ekle'ye basmalısın.")
            return
        if not self.ad_soyad.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Ad Soyad boş bırakılamaz.")
            return
        if not self.telefon.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Telefon numarası boş bırakılamaz.")
            return
        if not _telefon_gecerli_mi(self.telefon.text().strip()):
            QMessageBox.warning(
                self, "Geçersiz Telefon",
                "Telefon numarası geçerli görünmüyor. Örn: 0532 123 45 67 veya 05321234567."
            )
            return

        toplam = self.toplam_kisi.value()
        if toplam > 0:
            dagitilan = sum(s["kisi"] for s in secilenler)
            if dagitilan != toplam:
                cevap = QMessageBox.question(
                    self, "Kişi Sayısı Uyuşmuyor",
                    f"Toplam {toplam} kişi belirttin ama odalara dağıttığın kişi sayısı {dagitilan}. "
                    f"Yine de kaydetmek istiyor musun?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if cevap == QMessageBox.No:
                    return

        grup_id = repository.yeni_grup_id() if len(secilenler) > 1 else None

        ad_soyad = self.ad_soyad.text().strip()
        telefon = self.telefon.text().strip()
        referans = self.referans.text().strip()
        notlar = self.notlar.text().strip()
        try:
            if len(secilenler) == 1:
                s = secilenler[0]
                repository.rezervasyon_olustur(
                    oda_id=s["oda_id"], ad_soyad=ad_soyad, tc_no="",
                    telefon=telefon, kisi_sayisi=s["kisi"],
                    giris_tarihi=s["giris"], gece_sayisi=s["gece"],
                    fiyat_tipi=s["fiyat_tipi"], referans=referans,
                    notlar=notlar, grup_id=grup_id,
                    olusturan_kullanici=self.olusturan_kullanici,
                    ozel_ucret=s.get("ozel_ucret"),
                )
            else:
                toplu = [
                    dict(oda_id=s["oda_id"], ad_soyad=ad_soyad, tc_no="",
                         telefon=telefon, kisi_sayisi=s["kisi"],
                         giris_tarihi=s["giris"], gece_sayisi=s["gece"],
                         fiyat_tipi=s["fiyat_tipi"], referans=referans,
                         notlar=notlar, grup_id=grup_id,
                         olusturan_kullanici=self.olusturan_kullanici,
                         ozel_ucret=s.get("ozel_ucret"))
                    for s in secilenler
                ]
                repository.rezervasyonlari_toplu_olustur(toplu)
        except ValueError as e:
            QMessageBox.warning(self, "Hata", str(e))
            return

        oda_sayisi = len(secilenler)
        QMessageBox.information(
            self, "Başarılı",
            f"Rezervasyon kaydedildi ({oda_sayisi} oda için).\n"
            f"Misafir geldiğinde 'Check-in' ekranından TC No girmeyi unutma." if oda_sayisi > 1
            else "Rezervasyon kaydedildi.\nMisafir geldiğinde 'Check-in' ekranından TC No girmeyi unutma."
        )

        self.formu_temizle()
        if self.yenile_callback:
            self.yenile_callback()

    def yenile(self):
        self.grid.yenile()


# ============================================================
# ODA DEĞİŞTİR DİYALOĞU
# ============================================================
class OdaDegistirDialog(QDialog):
    def __init__(self, rez_row, parent=None):
        super().__init__(parent)
        self.rez_row = rez_row
        self.setWindowTitle(f"Oda Değiştir - {rez_row['ad_soyad']}")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        bilgi = QLabel(
            f"<b>{rez_row['ad_soyad']}</b> şu an <b>{rez_row['kat_adi']} - Oda {rez_row['oda_no']}</b>'de kalıyor.\n"
            f"Giriş: {rez_row['giris_tarihi']}  |  {rez_row['gece_sayisi']} gece\n\n"
            f"Not: Misafir henüz gelmediyse (rezervasyon ileri tarihte veya bugün check-in yapılmadıysa) "
            f"tarih seçimi önemli değil — tüm rezervasyon yeni odaya taşınır."
        )
        bilgi.setWordWrap(True)
        layout.addWidget(bilgi)

        form = QFormLayout()

        self.degisim_tarihi = QDateEdit(str_to_qdate(rez_row["giris_tarihi"]))
        self.degisim_tarihi.setCalendarPopup(True)
        form.addRow("Değişim Tarihi:", self.degisim_tarihi)

        self.yeni_oda_combo = QComboBox()
        for oda in repository.oda_listesi():
            if oda["id"] != rez_row["oda_id"]:
                self.yeni_oda_combo.addItem(
                    f"{oda['kat_adi']} - Oda {oda['oda_no']} ({oda['oda_tipi']})", oda["id"]
                )
        form.addRow("Yeni Oda:", self.yeni_oda_combo)

        layout.addLayout(form)

        uyari = QLabel(
            "Not: Eski odadaki kalan geceler silinip yeni odaya taşınacak.\n"
            "Zaten ödenmiş geceler varsa ödendi bilgisi korunur."
        )
        uyari.setStyleSheet("font-style: italic;")
        uyari.setWordWrap(True)
        layout.addWidget(uyari)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def secilen_tarih(self):
        return qdate_to_str(self.degisim_tarihi.date())

    def secilen_oda_id(self):
        return self.yeni_oda_combo.currentData()


# ============================================================
# TAB 4: REZERVASYON YÖNETİMİ (iptal, oda değiştir, excel'e aktar)
# ============================================================
class RezervasyonYonetimiTab(QWidget):
    def __init__(self, yenile_callback=None):
        super().__init__()
        self.yenile_callback = yenile_callback
        layout = QVBoxLayout(self)

        ust = QHBoxLayout()
        ust.addWidget(QLabel("Göster:"))
        self.durum_filtre = QComboBox()
        self.durum_filtre.addItems([
            "Aktif Rezervasyonlar", "Gelmeyenler (No-Show)", "İptal Edilenler", "Hepsi"
        ])
        self.durum_filtre.currentIndexChanged.connect(self.yenile)
        ust.addWidget(self.durum_filtre)

        ust.addSpacing(15)
        ust.addWidget(QLabel("Sırala:"))
        self.sirala_combo = QComboBox()
        self.sirala_combo.addItems([
            "Giriş Tarihi (Yeni → Eski)", "Giriş Tarihi (Eski → Yeni)",
            "Alınma Tarihi (Yeni → Eski)", "Alınma Tarihi (Eski → Yeni)",
        ])
        self.sirala_combo.currentIndexChanged.connect(self.yenile)
        ust.addWidget(self.sirala_combo)

        ust.addSpacing(15)
        ust.addWidget(QLabel("En Fazla Göster:"))
        self.limit_combo = QComboBox()
        self.limit_combo.addItems(["Hepsi", "Son 100", "Son 250", "Son 500"])
        self.limit_combo.currentIndexChanged.connect(self.yenile)
        ust.addWidget(self.limit_combo)
        ust.addStretch()

        excel_btn = QPushButton("📊 Excel'e Aktar")
        excel_btn.clicked.connect(self.excele_aktar)
        ust.addWidget(excel_btn)
        layout.addLayout(ust)

        arama_satiri = QHBoxLayout()
        arama_satiri.addWidget(QLabel("🔍 Bul:"))
        self.arama_kutusu = QLineEdit()
        self.arama_kutusu.setPlaceholderText("İsim, telefon, TC, oda no, referans... yazınca anında filtreler")
        self.arama_kutusu.textChanged.connect(self.yenile)
        arama_satiri.addWidget(self.arama_kutusu)
        temizle_btn = QPushButton("✕")
        temizle_btn.setMaximumWidth(30)
        temizle_btn.clicked.connect(lambda: self.arama_kutusu.clear())
        arama_satiri.addWidget(temizle_btn)
        layout.addLayout(arama_satiri)

        renk_bilgi = QLabel(
            "🔴 Kırmızı satır = Gelmedi (No-Show). İsme çift tıkla → tam detay. "
            "Tablo arayüzü iki yönlü: alttan kaydırmaz, filtreler üstte."
        )
        renk_bilgi.setWordWrap(False)
        renk_bilgi.setStyleSheet("font-style: italic; font-size: 10px;")
        layout.addWidget(renk_bilgi)

        self.tablo = QTableWidget()
        self.tablo.setColumnCount(14)
        self.tablo.setHorizontalHeaderLabels([
            "ID", "Oda", "Ad Soyad", "Telefon", "Kişi", "Giriş", "Gece", "Çıkış",
            "Fiyat Tipi", "Referans", "Grup", "Alan Kullanıcı", "Durum", "İşlemler"
        ])
        self.tablo.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tablo.horizontalHeader().setStretchLastSection(True)
        self.tablo.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tablo.cellDoubleClicked.connect(self._hucre_cift_tiklandi)
        tabloyu_kompakt_yap(self.tablo, 32)
        self.tablo.setColumnWidth(13, 210)
        layout.addWidget(self.tablo, stretch=1)

        self.ozet_label = QLabel("")
        self.ozet_label.setStyleSheet("")
        layout.addWidget(self.ozet_label)

        self.yenile()

    def _durum_kodu(self):
        secim = self.durum_filtre.currentText()
        if secim == "Aktif Rezervasyonlar":
            return "aktif"
        elif secim == "İptal Edilenler":
            return "iptal"
        elif secim == "Gelmeyenler (No-Show)":
            return "gelmedi"
        return "hepsi"

    def _satirlari_getir(self, limit=None):
        durum = self._durum_kodu()
        if durum == "gelmedi":
            rows = repository.rezervasyon_listesi("aktif")
            rows = [r for r in rows if repository.gelmedi_mi(r)]
        else:
            rows = repository.rezervasyon_listesi(durum)

        arama = self.arama_kutusu.text().strip().lower()
        if arama:
            def eslesiyor_mu(r):
                alanlar = [
                    r["ad_soyad"] or "", r["telefon"] or "", r["tc_no"] or "",
                    str(r["oda_no"]), r["kat_adi"] or "", r["referans"] or "",
                    r["olusturan_kullanici"] or "",
                ]
                return any(arama in (str(a).lower()) for a in alanlar)
            rows = [r for r in rows if eslesiyor_mu(r)]

        sirala = self.sirala_combo.currentText()
        if sirala.startswith("Giriş Tarihi"):
            anahtar = lambda r: r["giris_tarihi"]
        else:
            anahtar = lambda r: r["olusturma_tarihi"] or ""
        ters = "Yeni → Eski" in sirala
        rows = sorted(rows, key=anahtar, reverse=ters)
        if limit is not None and limit > 0:
            rows = rows[:limit]
        return rows

    def _secili_limit(self):
        metin = self.limit_combo.currentText()
        if metin == "Son 100":
            return 100
        elif metin == "Son 250":
            return 250
        elif metin == "Son 500":
            return 500
        return 0  # Hepsi

    def yenile(self):
        rows = self._satirlari_getir(limit=self._secili_limit())
        rows = list(rows)
        self.tablo.setRowCount(0)
        bugun = date.today().isoformat()
        gelmedi_sayisi = 0

        for r in rows:
            row_idx = self.tablo.rowCount()
            self.tablo.insertRow(row_idx)
            cikis = repository.cikis_tarihi_hesapla(r["giris_tarihi"], r["gece_sayisi"])
            grup_kisa = r["grup_id"][:8] if r["grup_id"] else ""
            gelmedi = repository.gelmedi_mi(r, bugun)
            if gelmedi:
                gelmedi_sayisi += 1

            if r["iptal"]:
                durum_metni = "İptal Edildi"
            elif gelmedi:
                durum_metni = "⚠ Gelmedi (No-Show)"
            elif r["checkin_yapildi"]:
                durum_metni = "✓ Check-in Yapıldı"
            elif r["giris_tarihi"] <= bugun:
                durum_metni = "Bekleniyor"
            else:
                durum_metni = "Aktif (İleri Tarih)"

            degerler = [
                str(r["id"]), f"{r['kat_adi']} - {r['oda_no']}", r["ad_soyad"],
                r["telefon"] or "", str(r["kisi_sayisi"]), r["giris_tarihi"],
                str(r["gece_sayisi"]), cikis, fiyat_tipi_goster(r["fiyat_tipi"]), r["referans"] or "",
                grup_kisa, r["olusturan_kullanici"] or "", durum_metni,
            ]
            for col, val in enumerate(degerler):
                item = QTableWidgetItem(val)
                item.setData(Qt.UserRole, r["id"])
                if r["iptal"]:
                    tema.renklendir(item, "#f0f0f0", yazi="#888888")
                elif gelmedi:
                    tema.renklendir(item, "#f8d0d0")
                self.tablo.setItem(row_idx, col, item)

            # İşlem butonları
            islem_widget = QWidget()
            islem_layout = QHBoxLayout(islem_widget)
            islem_layout.setContentsMargins(2, 2, 2, 2)

            if not r["iptal"]:
                degistir_btn = QPushButton("Oda Değiştir")
                degistir_btn.clicked.connect(lambda checked, rid=r["id"]: self.oda_degistir(rid))
                islem_layout.addWidget(degistir_btn)

                iptal_btn = QPushButton("İptal Et")
                iptal_btn.setStyleSheet("color: #c0392b;")
                iptal_btn.clicked.connect(lambda checked, rid=r["id"]: self.iptal_et(rid))
                islem_layout.addWidget(iptal_btn)
            else:
                geri_btn = QPushButton("İptali Geri Al")
                geri_btn.clicked.connect(lambda checked, rid=r["id"]: self.iptal_geri_al(rid))
                islem_layout.addWidget(geri_btn)

            self.tablo.setCellWidget(row_idx, 13, islem_widget)

        self.tablo.resizeColumnsToContents()
        self.tablo.setColumnWidth(13, 210)
        self.ozet_label.setText(f"Toplam {len(rows)} kayıt gösteriliyor  |  Gelmeyen (No-Show): {gelmedi_sayisi}")

    def _hucre_cift_tiklandi(self, row, col):
        if col == 13:
            return  # islemler sutunu, zaten butonlar var
        item = self.tablo.item(row, 0)
        if item is None:
            return
        rez_id = item.data(Qt.UserRole)
        if rez_id is None:
            return
        dialog = RezervasyonDetayDialog(rez_id, self)
        dialog.exec()
        if dialog.kaydedildi:
            self.yenile()
            if self.yenile_callback:
                self.yenile_callback()

    def iptal_et(self, rez_id):
        cevap = QMessageBox.question(
            self, "Rezervasyonu İptal Et",
            "Bu rezervasyonu iptal etmek istediğine emin misin?",
            QMessageBox.Yes | QMessageBox.No
        )
        if cevap == QMessageBox.Yes:
            repository.rezervasyon_iptal(rez_id)
            self.yenile()
            if self.yenile_callback:
                self.yenile_callback()

    def iptal_geri_al(self, rez_id):
        repository.rezervasyon_iptal_geri_al(rez_id)
        self.yenile()
        if self.yenile_callback:
            self.yenile_callback()

    def oda_degistir(self, rez_id):
        rez = repository.rezervasyon_getir(rez_id)
        if not rez:
            return
        dialog = OdaDegistirDialog(rez, self)
        if dialog.exec() == QDialog.Accepted:
            yeni_oda_id = dialog.secilen_oda_id()
            degisim_tarihi = dialog.secilen_tarih()

            # Yeni odada gercekten dolacak tarih araligini hesapla:
            # (degisim tarihi giristen once ise, tam rezervasyon araligi kullanilir)
            cikis_tarihi = repository.cikis_tarihi_hesapla(rez["giris_tarihi"], rez["gece_sayisi"])
            etkin_baslangic = max(rez["giris_tarihi"], degisim_tarihi)
            etkin_gece = (datetime.strptime(cikis_tarihi, "%Y-%m-%d")
                          - datetime.strptime(etkin_baslangic, "%Y-%m-%d")).days

            if etkin_gece <= 0:
                QMessageBox.warning(self, "Geçersiz Tarih", "Bu rezervasyonun zaten çıkışı yapılmış.")
                return

            cakisma = repository.musaitlik_kontrol(yeni_oda_id, etkin_baslangic, etkin_gece)
            if cakisma:
                isimler = ", ".join([c["ad_soyad"] for c in cakisma])
                cevap = QMessageBox.question(
                    self, "Yeni Oda Dolu Olabilir",
                    f"Seçtiğin yeni odada bu tarihlerde başka rezervasyon var: {isimler}.\n"
                    f"Yine de devam etmek istiyor musun?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if cevap == QMessageBox.No:
                    return
            try:
                repository.oda_degistir(rez_id, yeni_oda_id, degisim_tarihi)
                QMessageBox.information(self, "Başarılı", "Oda değişikliği tamamlandı.")
            except ValueError as e:
                QMessageBox.warning(self, "Hata", str(e))
                return
            self.yenile()
            if self.yenile_callback:
                self.yenile_callback()

    def excele_aktar(self):
        durum = self._durum_kodu()
        rows = self._satirlari_getir(limit=0)  # export her zaman tam liste
        varsayilan_ad = f"rezervasyonlar_{durum}_{date.today().isoformat()}.xlsx"
        dosya_yolu, _ = QFileDialog.getSaveFileName(
            self, "Excel Dosyasını Kaydet", varsayilan_ad, "Excel Dosyası (*.xlsx)"
        )
        if not dosya_yolu:
            return
        try:
            sayi = export.rezervasyonlari_disa_aktar(dosya_yolu, durum, satirlar=rows)
            QMessageBox.information(self, "Başarılı", f"{sayi} kayıt Excel'e aktarıldı:\n{dosya_yolu}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Excel'e aktarılırken hata oluştu:\n{e}")


# ============================================================
# TAB 5: ODA YÖNETİMİ (oda ekle/düzenle/sil, eski no / telefon kodu)
# ============================================================
class OdaYonetimiTab(QWidget):
    def __init__(self, yenile_callback=None):
        super().__init__()
        self.yenile_callback = yenile_callback
        self.secili_oda_id = None
        layout = QVBoxLayout(self)

        self.tablo = QTableWidget()
        self.tablo.setColumnCount(8)
        self.tablo.setHorizontalHeaderLabels(
            ["Kat No", "Kat Adı", "Oda No", "Oda Tipi", "Kapasite", "Eski No", "Telefon Kodu", "Durum"])
        self.tablo.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tablo.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tablo.cellClicked.connect(self._satir_secildi)
        tabloyu_kompakt_yap(self.tablo, 30)
        self.tablo.setToolTip(
            "Telefon kodu otomatik hesaplanır: '1' + eski numara (örn. eski no 14 → 114 çevrilir). "
            "Bir oda satırına tıklayınca sağdaki form dolar."
        )

        sag_panel = QWidget()
        sag_dikey = QVBoxLayout(sag_panel)
        sag_dikey.setContentsMargins(8, 0, 0, 0)

        form_kutu = QGroupBox("Oda Ekle / Düzenle")
        izgara = QGridLayout()
        izgara.setHorizontalSpacing(10)
        izgara.setVerticalSpacing(5)

        self.kat_no = QSpinBox()
        self.kat_no.setRange(0, 20)
        self.kat_adi = QLineEdit()
        self.oda_no = QSpinBox()
        self.oda_no.setRange(1, 999)
        self.oda_tipi = QComboBox()
        self.oda_tipi.addItems(database.ODA_TIPLERI)
        self.oda_tipi.currentTextChanged.connect(self._tip_degisince_kapasite_oner)
        self.kapasite = QSpinBox()
        self.kapasite.setRange(1, 10)
        self.kapasite.setValue(1)
        self.eski_no = QLineEdit()
        self.eski_no.setPlaceholderText("Boş bırakılabilir")

        alanlar = [
            ("Kat No (0=Lobi)", self.kat_no), ("Kat Adı", self.kat_adi), ("Oda No", self.oda_no),
            ("Oda Tipi", self.oda_tipi), ("Kapasite (max kişi)", self.kapasite),
            ("Eski No", self.eski_no),
        ]
        for i, (ad, widget) in enumerate(alanlar):
            satir = (i // 3) * 2
            izgara.addWidget(QLabel(ad), satir, i % 3)
            izgara.addWidget(widget, satir + 1, i % 3)
        form_kutu.setLayout(izgara)
        sag_dikey.addWidget(form_kutu)

        durum_kutu = QGroupBox("Oda Durumu (Temizlik / Arıza)")
        durum_dikey = QVBoxLayout()
        durum_satir = QHBoxLayout()
        durum_satir.addWidget(QLabel("Yeni Durum:"))
        self.durum_combo = QComboBox()
        self.durum_combo.addItem("Temiz", "temiz")
        self.durum_combo.addItem("Temizlikte", "temizlikte")
        self.durum_combo.addItem("Arızalı", "arizali")
        durum_satir.addWidget(self.durum_combo)
        self.ariza_gun = QSpinBox()
        self.ariza_gun.setRange(1, 90)
        self.ariza_gun.setValue(3)
        self.ariza_gun.setSuffix(" gün")
        durum_satir.addWidget(self.ariza_gun)
        durum_uygula_btn = QPushButton("Durumu Uygula")
        durum_uygula_btn.clicked.connect(self.durumu_uygula)
        durum_satir.addWidget(durum_uygula_btn)
        durum_satir.addStretch()
        durum_dikey.addLayout(durum_satir)
        durum_ipucu = QLabel(
            "Temizlikte = çıkış sonrası temizlik bekliyor (bu gece verilmez)  |  "
            "Arızalı = gün sayısı kadar kapalı, süresi dolunca otomatik temiz."
        )
        durum_ipucu.setWordWrap(True)
        durum_ipucu.setStyleSheet("font-style: italic; font-size: 10px;")
        durum_dikey.addWidget(durum_ipucu)
        durum_kutu.setLayout(durum_dikey)
        sag_dikey.addWidget(durum_kutu)

        btn_satir = QHBoxLayout()
        ekle_btn = QPushButton("✚ Yeni Oda Ekle")
        ekle_btn.clicked.connect(self.yeni_oda_ekle)
        guncelle_btn = QPushButton("Seçili Odayı Güncelle")
        guncelle_btn.clicked.connect(self.secili_odayi_guncelle)
        sil_btn = QPushButton("Sil")
        sil_btn.setStyleSheet("color: #c0392b;")
        sil_btn.clicked.connect(self.secili_odayi_sil)
        temizle_btn = QPushButton("Formu Temizle")
        temizle_btn.clicked.connect(self._formu_temizle)

        btn_satir.addWidget(ekle_btn)
        btn_satir.addWidget(guncelle_btn)
        btn_satir.addWidget(sil_btn)
        btn_satir.addWidget(temizle_btn)
        sag_dikey.addLayout(btn_satir)
        sag_dikey.addStretch(1)

        bolucu = QSplitter(Qt.Horizontal)
        bolucu.addWidget(self.tablo)
        bolucu.addWidget(sag_panel)
        bolucu.setStretchFactor(0, 5)
        bolucu.setStretchFactor(1, 1)
        bolucu.setSizes([760, 300])
        layout.addWidget(bolucu, stretch=1)

        self.yenile()

    def yenile(self):
        odalar = repository.oda_listesi()
        self.tablo.setRowCount(0)
        for oda in odalar:
            row = self.tablo.rowCount()
            self.tablo.insertRow(row)
            kod = database.telefon_kodu(oda["eski_no"])
            durum = oda.get("aktif_durum") or "temiz"
            if durum == "temizlikte":
                durum_metni = "🧹 Temizlikte"
            elif durum == "arizali":
                durum_metni = f"🔧 Arızalı (bitiş: {oda.get('ariza_bitis') or '?'})"
            else:
                durum_metni = "Temiz"
            degerler = [
                str(oda["kat_no"]), oda["kat_adi"] or "", str(oda["oda_no"]),
                oda["oda_tipi"] or "", str(oda["kapasite"] or 1),
                str(oda["eski_no"]) if oda["eski_no"] else "", kod, durum_metni
            ]
            for col, val in enumerate(degerler):
                item = QTableWidgetItem(val)
                item.setData(Qt.UserRole, oda["id"])
                if col == 7:
                    if durum == "temizlikte":
                        tema.renklendir(item, "#fdebd0")
                    elif durum == "arizali":
                        tema.renklendir(item, "#d9d9d9")
                    elif durum == "temiz":
                        tema.renklendir(item, "#e8f7e8")
                self.tablo.setItem(row, col, item)

    def durumu_uygula(self):
        if self.secili_oda_id is None:
            QMessageBox.warning(self, "Oda Seçilmedi", "Önce tablodan bir oda satırına tıkla.")
            return
        durum = self.durum_combo.currentData()
        ariza_gun = self.ariza_gun.value() if durum == "arizali" else 0
        try:
            repository.oda_durum_ayarla(self.secili_oda_id, durum, ariza_gun)
        except ValueError as e:
            QMessageBox.warning(self, "Durum Değiştirilemedi", str(e))
            return
        self.yenile()
        if self.yenile_callback:
            self.yenile_callback()

    def _tip_degisince_kapasite_oner(self, tip):
        self.kapasite.setValue(database.ODA_TIPI_KAPASITE.get(tip, 1))

    def _satir_secildi(self, row, col):
        item = self.tablo.item(row, 0)
        oda_id = item.data(Qt.UserRole)
        self.secili_oda_id = oda_id
        self.kat_no.setValue(int(self.tablo.item(row, 0).text()))
        self.kat_adi.setText(self.tablo.item(row, 1).text())
        self.oda_no.setValue(int(self.tablo.item(row, 2).text()))
        idx = self.oda_tipi.findText(self.tablo.item(row, 3).text())
        if idx >= 0:
            self.oda_tipi.setCurrentIndex(idx)
        self.kapasite.setValue(int(self.tablo.item(row, 4).text()))
        self.eski_no.setText(self.tablo.item(row, 5).text())

    def _formu_temizle(self):
        self.secili_oda_id = None
        self.kat_no.setValue(0)
        self.kat_adi.clear()
        self.oda_no.setValue(1)
        self.oda_tipi.setCurrentIndex(0)
        self.kapasite.setValue(1)
        self.eski_no.clear()

    def _eski_no_deger(self):
        metin = self.eski_no.text().strip()
        return int(metin) if metin.isdigit() else None

    def yeni_oda_ekle(self):
        if not self.kat_adi.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Kat adı boş bırakılamaz.")
            return
        try:
            repository.oda_ekle(
                self.kat_no.value(), self.kat_adi.text().strip(),
                self.oda_no.value(), self.oda_tipi.currentText(),
                eski_no=self._eski_no_deger(), kapasite=self.kapasite.value()
            )
        except ValueError as e:
            QMessageBox.warning(self, "Hata", str(e))
            return
        QMessageBox.information(self, "Başarılı", "Oda eklendi.")
        self._formu_temizle()
        self.yenile()
        if self.yenile_callback:
            self.yenile_callback()

    def secili_odayi_guncelle(self):
        if self.secili_oda_id is None:
            QMessageBox.warning(self, "Oda Seçilmedi", "Önce tablodan bir oda satırına tıkla.")
            return
        try:
            repository.oda_guncelle(
                self.secili_oda_id, self.kat_no.value(), self.kat_adi.text().strip(),
                self.oda_no.value(), self.oda_tipi.currentText(), self._eski_no_deger(),
                kapasite=self.kapasite.value()
            )
        except ValueError as e:
            QMessageBox.warning(self, "Hata", str(e))
            return
        QMessageBox.information(self, "Başarılı", "Oda güncellendi.")
        self.yenile()
        if self.yenile_callback:
            self.yenile_callback()

    def secili_odayi_sil(self):
        if self.secili_oda_id is None:
            QMessageBox.warning(self, "Oda Seçilmedi", "Önce tablodan bir oda satırına tıkla.")
            return
        cevap = QMessageBox.question(
            self, "Odayı Sil",
            "Bu odayı silmek istediğine emin misin? (Geçmiş rezervasyon kayıtları saklanır.)",
            QMessageBox.Yes | QMessageBox.No
        )
        if cevap == QMessageBox.Yes:
            try:
                repository.oda_sil(self.secili_oda_id)
            except ValueError as e:
                QMessageBox.warning(self, "Hata", str(e))
                return
            self._formu_temizle()
            self.yenile()
            if self.yenile_callback:
                self.yenile_callback()


# ============================================================
# AYRI PENCERE: TAKVİM GÖRÜNÜMÜ (1.jpeg tarzı, salt-okunur genel bakış)
# ============================================================
class TakvimPenceresi(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Takvim Görünümü - Tüm Odalar")
        self.resize(1300, 700)

        merkez = QWidget()
        layout = QVBoxLayout(merkez)

        bilgi = QLabel(
            "Bu pencere tüm odaların önümüzdeki günlerdeki doluluğunu gösterir (salt okunur). "
            "Rezervasyon eklemek için ana penceredeki 'Yeni Rezervasyon' sekmesini kullan."
        )
        bilgi.setWordWrap(True)
        bilgi.setStyleSheet("font-style: italic;")
        layout.addWidget(bilgi)

        self.grid = TakvimGridWidget(interactive=False, gun_sayisi=16)
        layout.addWidget(self.grid)

        self.setCentralWidget(merkez)

    def yenile(self):
        self.grid.yenile()


# ============================================================
# AYRI PENCERE: EXCEL RAPORLARI (günlük / haftalık / aylık / özel aralık)
# ============================================================
class ExcelRaporPenceresi(QDialog):
    AY_ADLARI = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                 "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Excel Raporu Oluştur")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)

        bilgi = QLabel(
            "Seçtiğin aralıktaki tüm odaların günlük doluluk/ödeme bilgisini ve bir "
            "özet sayfasını Excel'e aktarır."
        )
        bilgi.setWordWrap(True)
        bilgi.setStyleSheet("font-style: italic;")
        layout.addWidget(bilgi)

        form = QFormLayout()

        self.rapor_tipi = QComboBox()
        self.rapor_tipi.addItems(["Günlük", "Haftalık", "Aylık", "Özel Tarih Aralığı"])
        self.rapor_tipi.currentTextChanged.connect(self._tip_degisti)
        form.addRow("Rapor Tipi:", self.rapor_tipi)

        self.referans_tarih = QDateEdit(QDate.currentDate())
        self.referans_tarih.setCalendarPopup(True)
        self.referans_tarih_label = QLabel("Tarih:")
        form.addRow(self.referans_tarih_label, self.referans_tarih)

        self.ay_combo = QComboBox()
        self.ay_combo.addItems(self.AY_ADLARI)
        self.ay_combo.setCurrentIndex(QDate.currentDate().month() - 1)
        self.yil_spin = QSpinBox()
        self.yil_spin.setRange(2020, 2100)
        self.yil_spin.setValue(QDate.currentDate().year())
        ay_yil_satir = QHBoxLayout()
        ay_yil_satir.addWidget(self.ay_combo)
        ay_yil_satir.addWidget(self.yil_spin)
        self.ay_yil_widget = QWidget()
        self.ay_yil_widget.setLayout(ay_yil_satir)
        form.addRow("Ay / Yıl:", self.ay_yil_widget)

        self.baslangic_sec = QDateEdit(QDate.currentDate())
        self.baslangic_sec.setCalendarPopup(True)
        form.addRow("Başlangıç:", self.baslangic_sec)

        self.bitis_sec = QDateEdit(QDate.currentDate())
        self.bitis_sec.setCalendarPopup(True)
        form.addRow("Bitiş:", self.bitis_sec)

        layout.addLayout(form)

        olustur_btn = QPushButton("📊 Excel Oluştur")
        olustur_btn.setStyleSheet("font-weight: bold; padding: 8px;")
        olustur_btn.clicked.connect(self.excel_olustur)
        layout.addWidget(olustur_btn)

        self._tip_degisti(self.rapor_tipi.currentText())

    def _tip_degisti(self, tip):
        self.referans_tarih_label.setVisible(tip in ("Günlük", "Haftalık"))
        self.referans_tarih.setVisible(tip in ("Günlük", "Haftalık"))
        self.ay_yil_widget.setVisible(tip == "Aylık")
        self.baslangic_sec.setVisible(tip == "Özel Tarih Aralığı")
        self.bitis_sec.setVisible(tip == "Özel Tarih Aralığı")

    def _tarih_araligi_hesapla(self):
        tip = self.rapor_tipi.currentText()
        if tip == "Günlük":
            t = qdate_to_str(self.referans_tarih.date())
            return t, t
        elif tip == "Haftalık":
            secilen = self.referans_tarih.date()
            pazartesi = secilen.addDays(-(secilen.dayOfWeek() - 1))
            pazar = pazartesi.addDays(6)
            return qdate_to_str(pazartesi), qdate_to_str(pazar)
        elif tip == "Aylık":
            ay = self.ay_combo.currentIndex() + 1
            yil = self.yil_spin.value()
            ilk_gun = QDate(yil, ay, 1)
            son_gun = QDate(yil, ay, ilk_gun.daysInMonth())
            return qdate_to_str(ilk_gun), qdate_to_str(son_gun)
        else:
            return qdate_to_str(self.baslangic_sec.date()), qdate_to_str(self.bitis_sec.date())

    def excel_olustur(self):
        baslangic_str, bitis_str = self._tarih_araligi_hesapla()

        gun_farki = (datetime.strptime(bitis_str, "%Y-%m-%d") - datetime.strptime(baslangic_str, "%Y-%m-%d")).days
        if gun_farki > 400:
            QMessageBox.warning(self, "Çok Geniş Aralık", "Lütfen 400 günden daha kısa bir aralık seç.")
            return

        varsayilan_ad = f"rapor_{baslangic_str}_{bitis_str}.xlsx"
        dosya_yolu, _ = QFileDialog.getSaveFileName(
            self, "Excel Dosyasını Kaydet", varsayilan_ad, "Excel Dosyası (*.xlsx)"
        )
        if not dosya_yolu:
            return
        try:
            gun_sayisi = export.tarih_araligi_raporu_disa_aktar(dosya_yolu, baslangic_str, bitis_str)
            QMessageBox.information(
                self, "Başarılı",
                f"{gun_sayisi} günlük rapor Excel'e aktarıldı:\n{dosya_yolu}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Excel'e aktarılırken hata oluştu:\n{e}")


# ============================================================
# TAB: ÇIKIŞ (o gün çıkış yapacakları işaretle, oda temizlikte olur)
# ============================================================
class CikisTab(QWidget):
    def __init__(self, yenile_callback=None):
        super().__init__()
        self.yenile_callback = yenile_callback
        layout = QVBoxLayout(self)

        ust = QHBoxLayout()
        ust.addWidget(QLabel("Tarih:"))
        self.tarih_sec = QDateEdit(QDate.currentDate())
        self.tarih_sec.setCalendarPopup(True)
        self.tarih_sec.dateChanged.connect(self.yenile)
        ust.addWidget(self.tarih_sec)
        geri_btn = QPushButton("< Önceki Gün")
        geri_btn.clicked.connect(lambda: self.tarih_sec.setDate(self.tarih_sec.date().addDays(-1)))
        ileri_btn = QPushButton("Sonraki Gün >")
        ileri_btn.clicked.connect(lambda: self.tarih_sec.setDate(self.tarih_sec.date().addDays(1)))
        bugun_btn = QPushButton("Bugün")
        bugun_btn.clicked.connect(lambda: self.tarih_sec.setDate(QDate.currentDate()))
        ust.addWidget(geri_btn)
        ust.addWidget(ileri_btn)
        ust.addWidget(bugun_btn)
        ust.addStretch()
        layout.addLayout(ust)

        aciklama = QLabel(
            "Bu liste, check-in yapılmış ve beklenen çıkış günü seçtiğin tarih olan misafirleri gösterir. "
            "Çıkış yapınca oda otomatik 'temizlikte' durumuna alınır."
        )
        aciklama.setWordWrap(False)
        aciklama.setStyleSheet("font-style: italic; font-size: 10px;")
        layout.addWidget(aciklama)

        self.tablo = QTableWidget()
        self.tablo.setColumnCount(6)
        self.tablo.setHorizontalHeaderLabels(
            ["Oda", "Ad Soyad", "Telefon", "Giriş", "Gece", "İşlem"])
        self.tablo.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tablo.setEditTriggers(QTableWidget.NoEditTriggers)
        tabloyu_kompakt_yap(self.tablo, 34)
        self.tablo.setColumnWidth(5, 150)
        layout.addWidget(self.tablo, stretch=1)

        self.ozet_label = QLabel("")
        self.ozet_label.setStyleSheet("")
        layout.addWidget(self.ozet_label)

        self.yenile()

    def yenile(self):
        tarih_str = qdate_to_str(self.tarih_sec.date())
        rows = repository.bugun_cikacaklar(tarih_str)
        self.tablo.setRowCount(0)
        for r in rows:
            row_idx = self.tablo.rowCount()
            self.tablo.insertRow(row_idx)
            degerler = [
                f"{r['kat_adi']} - {r['oda_no']}", r["ad_soyad"],
                r["telefon"] or "", r["giris_tarihi"], str(r["gece_sayisi"]), ""
            ]
            for col, val in enumerate(degerler):
                self.tablo.setItem(row_idx, col, QTableWidgetItem(val))
            cikis_btn = QPushButton("🚪 Çıkış Yap")
            cikis_btn.clicked.connect(lambda checked, rid=r["id"]: self.cikis_yap(rid))
            islem_widget = QWidget()
            il = QHBoxLayout(islem_widget)
            il.setContentsMargins(2, 2, 2, 2)
            il.addWidget(cikis_btn)
            self.tablo.setCellWidget(row_idx, 5, islem_widget)
        self.ozet_label.setText(f"Çıkış yapacak misafir: {len(rows)}")

    def cikis_yap(self, rez_id):
        cevap = QMessageBox.question(
            self, "Çıkış İşlemi",
            "Misafir çıkış yaptı mı? İşlem sonrası oda 'temizlikte' durumuna alınır.",
            QMessageBox.Yes | QMessageBox.No
        )
        if cevap != QMessageBox.Yes:
            return
        try:
            repository.cikis_yap(rez_id)
        except ValueError as e:
            QMessageBox.warning(self, "Çıkış Yapılamadı", str(e))
            return
        QMessageBox.information(self, "Tamamlandı", "Çıkış işlemi tamamlandı. Oda temizlikte durumuna alındı.")
        self.yenile()
        if self.yenile_callback:
            self.yenile_callback()


# ============================================================
# TAB: İSTATİSTİK (aylık özet)
# ============================================================
class IstatistikTab(QWidget):
    AY_ADLARI = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                 "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        ust = QHBoxLayout()
        ust.addStretch()
        ust.addWidget(QLabel("Ay:"))
        self.ay_combo = QComboBox()
        self.ay_combo.addItems(self.AY_ADLARI)
        self.ay_combo.setCurrentIndex(QDate.currentDate().month() - 1)
        self.ay_combo.currentIndexChanged.connect(self.hesapla)
        ust.addWidget(self.ay_combo)
        self.yil_spin = QSpinBox()
        self.yil_spin.setRange(2020, 2100)
        self.yil_spin.setValue(QDate.currentDate().year())
        self.yil_spin.valueChanged.connect(self.hesapla)
        ust.addWidget(self.yil_spin)
        ust.addStretch()
        layout.addLayout(ust)

        self.tablo = QTableWidget()
        self.tablo.setColumnCount(2)
        self.tablo.setHorizontalHeaderLabels(["Metrik", "Değer"])
        self.tablo.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tablo.setEditTriggers(QTableWidget.NoEditTriggers)
        tabloyu_kompakt_yap(self.tablo)
        self.tablo.setToolTip(
            "Satışlar, ilgili aya düşen gecelere göre hesaplanır (rezervasyonun tamamı değil, "
            "sadece o ay içindeki geceler). Tutarlar satış değerini gösterir."
        )
        layout.addWidget(self.tablo, stretch=1)

        self.hesapla()

    def hesapla(self):
        ay = self.ay_combo.currentIndex() + 1
        yil = self.yil_spin.value()
        try:
            s = repository.aylik_istatistik(ay, yil)
        except Exception as e:
            s = {}
        satirlar = [
            ("Rezervasyon adedi (o ayda girişli)", s.get("rez_adedi", 0)),
            ("Satılan gece (o aya düşen)", s.get("satilan_gece", 0)),
            ("Satış değeri (TL)", s.get("gelir", 0)),
            ("Tahsil edilen (ödendi, TL)", s.get("tahsilat", 0)),
            ("İptal gece (o ayda iptal)", s.get("iptal_gece", 0)),
            ("Gelmeyen (no-show) gece", s.get("noshow_gece", 0)),
        ]
        self.tablo.setRowCount(0)
        for ad, deger in satirlar:
            row = self.tablo.rowCount()
            self.tablo.insertRow(row)
            self.tablo.setItem(row, 0, QTableWidgetItem(ad))
            self.tablo.setItem(row, 1, QTableWidgetItem(str(deger)))


# ============================================================
# TAB: AYARLAR (fiyatlar + yedekleme)
# ============================================================
class AyarlarTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        fiyat_kutu = QGroupBox("Fiyat Ayarları (kişi başı gecelik TL)")
        fiyat_form = QFormLayout()
        try:
            mevcut_sabit = int(database.get_ayar("sabit_fiyat", database.FIYAT_SABIT))
        except (ValueError, TypeError):
            mevcut_sabit = database.FIYAT_SABIT
        try:
            mevcut_uye = int(database.get_ayar("uye_fiyat", database.FIYAT_UYE))
        except (ValueError, TypeError):
            mevcut_uye = database.FIYAT_UYE
        self.sabit_fiyat = QSpinBox()
        self.sabit_fiyat.setRange(0, 100000)
        self.sabit_fiyat.setValue(mevcut_sabit)
        self.sabit_fiyat.setSuffix(" TL")
        fiyat_form.addRow("Sabit fiyat:", self.sabit_fiyat)
        self.uye_fiyat = QSpinBox()
        self.uye_fiyat.setRange(0, 100000)
        self.uye_fiyat.setValue(mevcut_uye)
        self.uye_fiyat.setSuffix(" TL")
        fiyat_form.addRow("Üye fiyatı:", self.uye_fiyat)
        fiyat_kutu.setLayout(fiyat_form)

        fiyat_btn = QPushButton("💾 Fiyatları Kaydet")
        fiyat_btn.clicked.connect(self.fiyatlari_kaydet)
        fiyat_not = QLabel(
            "Yeni fiyatlar bundan SONRA alınan rezervasyonlarda geçerli olur. "
            "Mevcut rezervasyonların ücretleri (gecelik_ucret) değişmez."
        )
        fiyat_not.setWordWrap(True)
        fiyat_not.setStyleSheet("font-style: italic; font-size: 10px;")
        fiyat_sol = QVBoxLayout()
        fiyat_sol.addWidget(fiyat_kutu)
        fiyat_sol.addWidget(fiyat_btn)
        fiyat_sol.addWidget(fiyat_not)
        fiyat_sol.addStretch(1)

        tema_kutu = QGroupBox("Görünüm (Tema)")
        tema_dikey = QVBoxLayout()
        tema_satir = QHBoxLayout()
        tema_satir.addWidget(QLabel("Tema seçimi:"))
        self.tema_combo = QComboBox()
        self.tema_combo.addItem("Sistem (Windows görünümü)", tema.TEMA_SISTEM)
        self.tema_combo.addItem("Aydınlık", tema.TEMA_AYDINLIK)
        self.tema_combo.addItem("Karanlık", tema.TEMA_KARANLIK)
        mevcut_tema = str(database.get_ayar("tema", tema.TEMA_SISTEM)).lower()
        indeks = self.tema_combo.findData(mevcut_tema)
        self.tema_combo.setCurrentIndex(indeks if indeks >= 0 else 0)
        self.tema_combo.currentIndexChanged.connect(self.temayi_kaydet_uygula)
        tema_satir.addWidget(self.tema_combo, stretch=1)
        tema_dikey.addLayout(tema_satir)
        tema_not = QLabel(
            "Tema seçimi anında uygulanır. 'Sistem' seçilirse Windows'un karanlık/aydınlık "
            "ayarını izler."
        )
        tema_not.setWordWrap(True)
        tema_not.setStyleSheet("font-style: italic; font-size: 10px;")
        tema_dikey.addWidget(tema_not)
        tema_dikey.addStretch(1)
        tema_kutu.setLayout(tema_dikey)

        tema_sag = QVBoxLayout()
        tema_sag.addWidget(tema_kutu)
        tema_sag.addStretch(1)

        ust_izgara = QGridLayout()
        ust_izgara.addLayout(fiyat_sol, 0, 0)
        ust_izgara.addLayout(tema_sag, 0, 1)
        ust_izgara.setColumnStretch(0, 1)
        ust_izgara.setColumnStretch(1, 1)
        layout.addLayout(ust_izgara)

        yedek_kutu = QGroupBox("Yedekleme")
        yedek_layout = QVBoxLayout()
        yedek_al_btn = QPushButton("💾 Yedek Al (şimdi)")
        yedek_al_btn.clicked.connect(self.yedek_al)
        yedek_layout.addWidget(yedek_al_btn)
        geri_satir = QHBoxLayout()
        geri_satir.addWidget(QLabel("Yedekten geri yükle:"))
        self.yedek_combo = QComboBox()
        geri_satir.addWidget(self.yedek_combo, stretch=1)
        geri_yukle_btn = QPushButton("Geri Yükle")
        geri_yukle_btn.clicked.connect(self.geri_yukle)
        geri_satir.addWidget(geri_yukle_btn)
        yedek_layout.addLayout(geri_satir)
        self.yedek_listele()
        yedek_not = QLabel(
            "Yedekler 'yedekler' klasöründe misafirhane_yedek_TARIH_SAAT.db adıyla saklanır. "
            "Geri yükleme mevcut veritabanını değiştirir; uygulamayı yeniden başlatman önerilir."
        )
        yedek_not.setWordWrap(True)
        yedek_not.setStyleSheet("font-style: italic; font-size: 10px;")
        yedek_layout.addWidget(yedek_not)
        yedek_kutu.setLayout(yedek_layout)
        layout.addWidget(yedek_kutu)

        surum_satir = QHBoxLayout()
        surum_satir.addStretch(1)
        surum_label = QLabel(f"{versiyon.UYGULAMA_ADI} — Sürüm {versiyon.SURUM}")
        surum_label.setStyleSheet("color: #999999; font-size: 11px;")
        surum_satir.addWidget(surum_label)
        layout.addLayout(surum_satir)

        layout.addStretch()

    def temayi_kaydet_uygula(self):
        secim = self.tema_combo.currentData() or tema.TEMA_SISTEM
        database.set_ayar("tema", secim)
        loglama.islem_yaz("ayar", f"Tema değiştirildi: {secim}")
        app = QApplication.instance()
        if app is not None:
            tema.temayi_uygula(app, secim)

    def yedek_listele(self):
        self.yedek_combo.clear()
        for f in database.yedek_listele():
            self.yedek_combo.addItem(f, f)

    def fiyatlari_kaydet(self):
        database.set_ayar("sabit_fiyat", self.sabit_fiyat.value())
        database.set_ayar("uye_fiyat", self.uye_fiyat.value())
        loglama.islem_yaz(
            "ayar",
            f"Fiyatlar güncellendi: Sabit {self.sabit_fiyat.value()} TL, Üye {self.uye_fiyat.value()} TL.",
        )
        QMessageBox.information(
            self, "Kaydedildi",
            "Fiyatlar kaydedildi. Bundan sonraki rezervasyonlarda geçerli olacak."
        )

    def yedek_al(self):
        try:
            hedef = database.yedek_al()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Yedek alınamadı:\n{e}")
            return
        self.yedek_listele()
        QMessageBox.information(self, "Başarılı", f"Yedek alındı:\n{hedef}")

    def geri_yukle(self):
        secilen = self.yedek_combo.currentData()
        if not secilen:
            QMessageBox.warning(self, "Yedek Yok", "Geri yüklenecek bir yedek seçmelisin.")
            return
        cevap = QMessageBox.question(
            self, "Geri Yükle",
            f"'{secilen}' yedeği geri yüklenecek. MEVCUT TÜM VERİLER bu yedekteki halleriyle "
            f"değiştirilir. Devam etmek istediğine emin misin?",
            QMessageBox.Yes | QMessageBox.No
        )
        if cevap != QMessageBox.Yes:
            return
        try:
            database.yedek_geri_yukle(secilen)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Geri yükleme başarısız:\n{e}")
            return
        QMessageBox.information(
            self, "Geri Yüklendi",
            "Yedek geri yüklendi. Değişikliklerin güvenli görünmesi için uygulamayı "
            "kapatıp yeniden başlatman önerilir."
        )


# ============================================================
# TAB: İŞLEM GEÇMİŞİ (denetim izi)
# ============================================================
class IslemGecmisiTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        ust = QHBoxLayout()
        ust.addWidget(QLabel("Filtre (işlem türü):"))
        self.tur_filtre = QComboBox()
        self.tur_filtre.addItem("Hepsi", None)
        for t in loglama.islem_turleri():
            self.tur_filtre.addItem(t, t)
        self.tur_filtre.currentIndexChanged.connect(self.yenile)
        ust.addWidget(self.tur_filtre, stretch=1)
        yenile_btn = QPushButton("Yenile")
        yenile_btn.clicked.connect(self.yenile)
        ust.addWidget(yenile_btn)
        ust.addWidget(QLabel("Son 500 kayıt gösterilir."))
        ust.addStretch()
        layout.addLayout(ust)

        self.tablo = QTableWidget()
        self.tablo.setColumnCount(4)
        self.tablo.setHorizontalHeaderLabels(["Zaman", "Kullanıcı", "İşlem Türü", "Detay"])
        self.tablo.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tablo.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tablo.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tablo.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.tablo.setEditTriggers(QTableWidget.NoEditTriggers)
        tabloyu_kompakt_yap(self.tablo, 30)
        layout.addWidget(self.tablo, stretch=1)

        self.yenile()

    def yenile(self):
        tur = self.tur_filtre.currentData()
        satirlar = loglama.son_islemler(limit=500, tur=tur)
        self.tablo.setRowCount(0)
        for satir in satirlar:
            row = self.tablo.rowCount()
            self.tablo.insertRow(row)
            self.tablo.setItem(row, 0, QTableWidgetItem(satir["zaman"] or ""))
            self.tablo.setItem(row, 1, QTableWidgetItem(satir["kullanici"] or ""))
            self.tablo.setItem(row, 2, QTableWidgetItem(satir["tur"] or ""))
            self.tablo.setItem(row, 3, QTableWidgetItem(satir["detay"] or ""))


# ============================================================
# ANA PENCERE
# ============================================================
class AnaPencere(QMainWindow):
    def __init__(self, aktif_kullanici=None, cikis_callback=None):
        super().__init__()
        self.aktif_kullanici = aktif_kullanici  # sqlite3.Row (id, kullanici_adi, ad_soyad, ...)
        self.cikis_callback = cikis_callback
        self.setWindowTitle("Misafirhane Rezervasyon Sistemi")
        self.resize(1200, 700)
        self.takvim_penceresi = None

        merkez = QWidget()
        ana_layout = QVBoxLayout(merkez)
        ana_layout.setContentsMargins(0, 0, 0, 0)

        ust_cubuk = QFrame()
        ust_cubuk.setObjectName("ust_bar")
        ust_bar = QHBoxLayout(ust_cubuk)
        ust_bar.setContentsMargins(14, 8, 14, 8)

        baslik = QLabel("🏨 Misafirhane Rezervasyon Sistemi")
        baslik.setObjectName("baslik")
        ust_bar.addWidget(baslik)
        ust_bar.addStretch()

        if self.aktif_kullanici is not None:
            gosterilen_ad = self.aktif_kullanici["ad_soyad"] or self.aktif_kullanici["kullanici_adi"]
            kullanici_label = QLabel(f"👤 Giriş yapan: <b>{gosterilen_ad}</b>")
            ust_bar.addWidget(kullanici_label)
            cikis_btn = QPushButton("🚪 Çıkış Yap")
            cikis_btn.setObjectName("ikincil")
            cikis_btn.clicked.connect(self.cikis_yap)
            ust_bar.addWidget(cikis_btn)

        takvim_btn = QPushButton("📅 Takvim Görünümü")
        takvim_btn.setToolTip("Tüm odaların ~16 günlük doluluğunu ayrı pencere olarak gösterir.")
        takvim_btn.clicked.connect(self.takvim_penceresini_ac)
        ust_bar.addWidget(takvim_btn)

        excel_rapor_btn = QPushButton("📊 Excel Raporu")
        excel_rapor_btn.clicked.connect(self.excel_raporu_penceresini_ac)
        ust_bar.addWidget(excel_rapor_btn)
        ana_layout.addWidget(ust_cubuk)

        self.tabs = QTabWidget()
        ana_layout.addWidget(self.tabs)
        self.setCentralWidget(merkez)

        olusturan = None
        if self.aktif_kullanici is not None:
            olusturan = self.aktif_kullanici["kullanici_adi"]
            loglama.set_aktif_kullanici(olusturan)

        self.oda_durumu_tab = OdaDurumuTab()
        self.gunluk_giris_tab = GunlukGirisTab()
        self.checkin_tab = CheckinTab(yenile_callback=self._tumunu_yenile)
        self.cikis_tab = CikisTab(yenile_callback=self._tumunu_yenile)
        self.yeni_rez_tab = YeniRezervasyonTab(yenile_callback=self._tumunu_yenile, olusturan_kullanici=olusturan)
        self.yonetim_tab = RezervasyonYonetimiTab(yenile_callback=self._tumunu_yenile)
        self.istatistik_tab = IstatistikTab()
        self.oda_yonetim_tab = OdaYonetimiTab(yenile_callback=self._tumunu_yenile)
        self.ayarlar_tab = AyarlarTab()
        self.islem_gecmisi_tab = IslemGecmisiTab()
        self.kullanici_yonetim_tab = KullaniciYonetimiTab(aktif_kullanici=self.aktif_kullanici)

        self.tabs.addTab(self.yeni_rez_tab, "➕ Yeni Rezervasyon")
        self.tabs.addTab(self.oda_durumu_tab, "🏨 Oda Durumu")
        self.tabs.addTab(self.checkin_tab, "🔑 Check-in")
        self.tabs.addTab(self.gunluk_giris_tab, "📋 Günün Girişleri")
        self.tabs.addTab(self.cikis_tab, "🚪 Çıkış")
        self.tabs.addTab(self.yonetim_tab, "🗂️ Rezervasyon Yönetimi")
        self.tabs.addTab(self.istatistik_tab, "📊 İstatistik")
        self.tabs.addTab(self.oda_yonetim_tab, "🔧 Oda Yönetimi")
        self.tabs.addTab(self.ayarlar_tab, "⚙️ Ayarlar")
        self.tabs.addTab(self.islem_gecmisi_tab, "🗒️ İşlem Geçmişi")
        self.tabs.addTab(self.kullanici_yonetim_tab, "👤 Kullanıcılar")

    def cikis_yap(self):
        loglama.set_aktif_kullanici(None)
        self.close()
        if self.cikis_callback:
            self.cikis_callback()

    def takvim_penceresini_ac(self):
        if self.takvim_penceresi is None:
            self.takvim_penceresi = TakvimPenceresi()
        self.takvim_penceresi.yenile()
        self.takvim_penceresi.show()
        self.takvim_penceresi.raise_()
        self.takvim_penceresi.activateWindow()

    def excel_raporu_penceresini_ac(self):
        dialog = ExcelRaporPenceresi(self)
        dialog.exec()

    def _tumunu_yenile(self):
        self.oda_durumu_tab.yenile()
        self.checkin_tab.yenile()
        self.gunluk_giris_tab.yenile()
        self.cikis_tab.yenile()
        self.yeni_rez_tab.yenile()
        self.yonetim_tab.yenile()
        self.istatistik_tab.hesapla()
        self.oda_yonetim_tab.yenile()
        self.islem_gecmisi_tab.yenile()
        if self.takvim_penceresi is not None:
            self.takvim_penceresi.yenile()


# ============================================================
# TAB: KULLANICI YÖNETİMİ (resepsiyon çalışanları)
# ============================================================
class KullaniciYonetimiTab(QWidget):
    def __init__(self, aktif_kullanici=None):
        super().__init__()
        self.aktif_kullanici = aktif_kullanici
        layout = QVBoxLayout(self)

        bilgi = QLabel(
            "👤  Resepsiyon çalışanlarına ayrı hesap açabilirsin (yetki aynıdır; fark yalnızca "
            "kimin aldığını görmektir). Şu an: <b>admin</b>"
        )
        bilgi.setWordWrap(False)
        bilgi.setStyleSheet("font-size: 10px;")
        layout.addWidget(bilgi)

        self.tablo = QTableWidget()
        self.tablo.setColumnCount(4)
        self.tablo.setHorizontalHeaderLabels(["Kullanıcı Adı", "Ad Soyad", "Durum", "İşlemler"])
        self.tablo.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tablo.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tablo.setColumnWidth(3, 230)
        tabloyu_kompakt_yap(self.tablo, 34)
        layout.addWidget(self.tablo, stretch=1)

        yeni_satir = QHBoxLayout()
        yeni_satir.addWidget(QLabel("Yeni kullanıcı:"))
        self.yeni_ad_soyad = QLineEdit()
        self.yeni_ad_soyad.setPlaceholderText("Ad Soyad")
        yeni_satir.addWidget(self.yeni_ad_soyad, stretch=2)
        self.yeni_kullanici_adi = QLineEdit()
        self.yeni_kullanici_adi.setPlaceholderText("Kullanıcı adı")
        yeni_satir.addWidget(self.yeni_kullanici_adi, stretch=1)
        self.yeni_sifre = QLineEdit()
        self.yeni_sifre.setEchoMode(QLineEdit.Password)
        self.yeni_sifre.setPlaceholderText("Şifre (min 4)")
        yeni_satir.addWidget(self.yeni_sifre, stretch=1)
        ekle_btn = QPushButton("✚ Ekle")
        ekle_btn.setObjectName("birincil")
        ekle_btn.clicked.connect(self.kullanici_ekle)
        yeni_satir.addWidget(ekle_btn)
        layout.addLayout(yeni_satir)

        self.yenile()

    def yenile(self):
        kullanicilar = auth.kullanici_listesi()
        self.tablo.setRowCount(0)
        for k in kullanicilar:
            row = self.tablo.rowCount()
            self.tablo.insertRow(row)
            self.tablo.setItem(row, 0, QTableWidgetItem(k["kullanici_adi"]))
            self.tablo.setItem(row, 1, QTableWidgetItem(k["ad_soyad"] or ""))
            self.tablo.setItem(row, 2, QTableWidgetItem("Aktif" if k["aktif"] else "Pasif"))

            islem_widget = QWidget()
            islem_layout = QHBoxLayout(islem_widget)
            islem_layout.setContentsMargins(2, 2, 2, 2)

            sifre_btn = QPushButton("Şifre Sıfırla")
            sifre_btn.clicked.connect(lambda checked, kid=k["id"], adi=k["kullanici_adi"]: self._sifre_sifirla(kid, adi))
            islem_layout.addWidget(sifre_btn)

            if k["aktif"]:
                durum_btn = QPushButton("Pasif Yap")
                durum_btn.clicked.connect(lambda checked, kid=k["id"]: self._aktiflik_degistir(kid, False))
            else:
                durum_btn = QPushButton("Aktif Yap")
                durum_btn.clicked.connect(lambda checked, kid=k["id"]: self._aktiflik_degistir(kid, True))
            islem_layout.addWidget(durum_btn)

            self.tablo.setCellWidget(row, 3, islem_widget)

    def kullanici_ekle(self):
        if not self.yeni_kullanici_adi.text().strip() or not self.yeni_sifre.text():
            QMessageBox.warning(self, "Eksik Bilgi", "Kullanıcı adı ve şifre gerekli.")
            return
        try:
            auth.kullanici_ekle(
                self.yeni_kullanici_adi.text().strip(),
                self.yeni_sifre.text(),
                self.yeni_ad_soyad.text().strip()
            )
        except ValueError as e:
            QMessageBox.warning(self, "Hata", str(e))
            return
        QMessageBox.information(self, "Başarılı", "Kullanıcı eklendi.")
        self.yeni_ad_soyad.clear()
        self.yeni_kullanici_adi.clear()
        self.yeni_sifre.clear()
        self.yenile()

    def _sifre_sifirla(self, kullanici_id, kullanici_adi):
        from PySide6.QtWidgets import QInputDialog
        yeni_sifre, ok = QInputDialog.getText(
            self, "Şifre Sıfırla", f"'{kullanici_adi}' için yeni şifre:",
            QLineEdit.Password
        )
        if ok and yeni_sifre:
            if len(yeni_sifre) < 4:
                QMessageBox.warning(self, "Zayıf Şifre", "Şifre en az 4 karakter olmalı.")
                return
            auth.sifre_degistir(kullanici_id, yeni_sifre)
            QMessageBox.information(self, "Başarılı", "Şifre güncellendi.")

    def _aktiflik_degistir(self, kullanici_id, aktif):
        auth.kullanici_aktiflik_degistir(kullanici_id, aktif)
        self.yenile()


def main():
    database.init_db()
    if database.odalar_bos_mu():
        database.varsayilan_odalari_yukle()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Dondurulmus (exe) surumde varliklar uygulama klasorundeki assets altindadir
    if getattr(sys, "frozen", False):
        taban = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        taban = os.path.dirname(os.path.abspath(__file__))
    ikon_yolu = os.path.join(taban, "assets", "misafirhane.ico")
    if os.path.exists(ikon_yolu):
        app.setWindowIcon(QIcon(ikon_yolu))

    tema.temayi_uygula(app, database.get_ayar("tema", tema.TEMA_SISTEM))

    # Ilk kurulumda hic kullanici yoksa, once bir hesap olusturulmasi istenir
    if not auth.kullanici_var_mi():
        ilk_dialog = IlkKullaniciDialog()
        if ilk_dialog.exec() != QDialog.Accepted:
            sys.exit(0)

    pencere_kutusu = {}  # AnaPencere referansini canli tutmak icin (cop toplayiciya karsi)

    def giris_ekranini_goster():
        giris = GirisDialog()
        if giris.exec() == QDialog.Accepted:
            pencere = AnaPencere(aktif_kullanici=giris.giris_yapan,
                                  cikis_callback=giris_ekranini_goster)
            pencere_kutusu["pencere"] = pencere
            pencere.show()
        else:
            app.quit()

    giris_ekranini_goster()
    # Kapanışta veri değiştiyse otomatik yedek alınır (yedekler klasöründe sınırlı sayıda tutulur)
    app.aboutToQuit.connect(database.yedek_otomatik)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
