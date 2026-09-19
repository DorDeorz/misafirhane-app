# -*- coding: utf-8 -*-
"""
Rezervasyon detay/düzenleme penceresi (ÇOK ODALI model).
Oda Durumu, Takvim Görünümü ve Rezervasyon Yönetimi ekranlarından bir isme
çift tıklandığında açılır. Bir rezervasyonun TÜM odaları ayrı ayrı gösterilir;
her oda için kişi/check-in, tarih ve oda değişikliği oda başına yapılır.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QSpinBox, QComboBox, QTextEdit, QPushButton, QDialogButtonBox, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QCheckBox,
    QDateEdit, QScrollArea, QWidget
)
from PySide6.QtCore import Qt, QDate
from datetime import date

import repository
from database import fiyat_tipi_goster

FIYAT_TIPLERI = ["Sabit", "Uye", "Ozel"]


class TcAlan(QLineEdit):
    """TC No alanı: tıklanınca/fokus olunca mevcut metni otomatik seçer.
    Kayıtlı TC (11 haneli) tam dolu olduğu için 'yazılamıyor' sorununu çözer:
    tıkla → metin seçili gelir → doğrudan yeni TC yazılır."""

    def focusInEvent(self, olay):
        super().focusInEvent(olay)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self.selectAll)


def _ro_durum_metni(ro, rez_iptal=False):
    """Bir oda satırının insan okur durum metni."""
    bugun = date.today().isoformat()
    if rez_iptal:
        return "İptal Edildi"
    if ro["cikis_tarihi"]:
        return "Çıkış yaptı"
    if ro["checkin_yapildi"]:
        return "✓ İçeride"
    if ro["giris_tarihi"] < bugun:
        return "⚠ Gelmedi (No-Show)"
    return "Bekleniyor"


class OdaTarihDialog(QDialog):
    """Tek oda satırının giriş tarihi / gece sayısını değiştirir."""

    def __init__(self, ro_row, parent=None):
        super().__init__(parent)
        self.ro_row = ro_row
        self.setWindowTitle(f"Tarih Değiştir - {ro_row['kat_adi']} Oda {ro_row['oda_no']}")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        bilgi = QLabel(
            f"<b>{ro_row['kat_adi']} - Oda {ro_row['oda_no']}</b> "
            f"({ro_row['gece_sayisi']} gece, {ro_row['kisi_sayisi']} kişi)<br>"
            f"Rezervasyonu alan: {ro_row['ad_soyad']}"
        )
        bilgi.setWordWrap(True)
        layout.addWidget(bilgi)

        form = QFormLayout()
        self.tarih_giris = QDateEdit(QDate.fromString(ro_row["giris_tarihi"], "yyyy-MM-dd"))
        self.tarih_giris.setCalendarPopup(True)
        self.tarih_giris.setDisplayFormat("dd.MM.yyyy")
        form.addRow("Yeni Giriş:", self.tarih_giris)

        self.tarih_gece = QSpinBox()
        self.tarih_gece.setRange(1, 90)
        self.tarih_gece.setValue(ro_row["gece_sayisi"] or 1)
        form.addRow("Gece Sayısı:", self.tarih_gece)
        layout.addLayout(form)

        not_label = QLabel(
            "Ödemeler yeni aralığa göre yeniden kurulur. Önceden ödenmiş geceler "
            "yeni aralığın dışında kalırsa uyarılacaksın (tutarları otomatik iade edilmez)."
        )
        not_label.setWordWrap(True)
        not_label.setStyleSheet("font-style: italic; font-size: 10px;")
        layout.addWidget(not_label)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Save).setText("Uygula")
        btns.accepted.connect(self.uygula)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def uygula(self):
        yeni_giris = self.tarih_giris.date().toString("yyyy-MM-dd")
        yeni_gece = self.tarih_gece.value()
        try:
            dusen_odenmis = repository.rezervasyon_odasi_tarih_degistir(
                self.ro_row["id"], yeni_giris, yeni_gece
            )
        except ValueError as e:
            QMessageBox.warning(self, "Tarih Değiştirilemedi", str(e))
            return
        if dusen_odenmis:
            QMessageBox.information(
                self, "Ödenen Geceler",
                "Şu geceler yeni tarih/gece planının dışında kaldı (ödendi bilgileri "
                "korundu, tutar iade edilmedi):\n" + ", ".join(dusen_odenmis)
            )
        self.accept()


class RezervasyonDetayDialog(QDialog):
    def __init__(self, rez_id, parent=None):
        super().__init__(parent)
        self.rez_id = rez_id
        self.kaydedildi = False
        self.rez = repository.rezervasyon_getir(rez_id)
        self.odalar = repository.rezervasyon_odalar_listele(rez_id) if self.rez else []

        if self.rez is None:
            self.setWindowTitle("Bulunamadı")
            layout = QVBoxLayout(self)
            layout.addWidget(QLabel("Bu rezervasyon bulunamadı (silinmiş olabilir)."))
            return

        self.setWindowTitle(f"Rezervasyon Detayı - {self.rez['ad_soyad']}")
        self.setMinimumSize(980, 620)
        self.resize(1080, 690)
        self._arayuzu_kur()

    def _arayuzu_kur(self):
        r = self.rez
        kok = QVBoxLayout(self)

        ana = QWidget()
        layout = QVBoxLayout(ana)
        layout.setContentsMargins(12, 12, 12, 12)

        if r["iptal"]:
            durum_metni = "İptal Edildi"
        elif self.odalar and all(o["checkin_yapildi"] and not o["cikis_tarihi"] for o in self.odalar):
            durum_metni = "✓ Tüm odalar içeride"
        elif any(o["checkin_yapildi"] for o in self.odalar):
            durum_metni = "Kısmen check-in (bazı odalar içeride)"
        elif self.odalar and all(_ro_durum_metni(o, r["iptal"]) == "⚠ Gelmedi (No-Show)" for o in self.odalar):
            durum_metni = "⚠ GELMEDİ (No-Show)"
        else:
            durum_metni = "Bekleniyor (henüz check-in yapılmadı)"

        alinma_tarihi = (r["olusturma_tarihi"] or "").split(".")[0]
        alan_kullanici = r["olusturan_kullanici"] or "Bilinmiyor (eski kayıt)"
        oda_ozeti = " + ".join(f"{o['kat_adi']} - Oda {o['oda_no']}" for o in self.odalar) or "-"
        giris = min((o["giris_tarihi"] for o in self.odalar), default="-")
        cikis = max(
            (o["cikis_tarihi"] or repository.cikis_tarihi_hesapla(o["giris_tarihi"], o["gece_sayisi"])
             for o in self.odalar), default="-"
        )

        ust_bilgi = QLabel(
            f"<b>{r['ad_soyad']}</b><br>"
            f"Odalar: <b>{oda_ozeti}</b><br>"
            f"Giriş: {giris}  →  Çıkış: {cikis}  ({sum(o['gece_sayisi'] or 0 for o in self.odalar)} gece toplam)<br>"
            f"Durum: <b>{durum_metni}</b><br>"
            f"<span style='color:#555;'>Rezervasyon alınma tarihi: {alinma_tarihi}  |  "
            f"Alan kullanıcı: {alan_kullanici}</span>"
        )
        ust_bilgi.setWordWrap(True)
        layout.addWidget(ust_bilgi)

        if r["iptal"]:
            uyari = QLabel("⚠ Bu rezervasyon iptal edildi. Oda satırları düzenlenemez; "
                           "iptali geri almak için 'Rezervasyon Yönetimi' ekranını kullan.")
            uyari.setWordWrap(True)
            uyari.setStyleSheet("color: #c0392b; background-color: #f8d0d0; padding: 6px; border-radius: 4px;")
            layout.addWidget(uyari)

        # ---- SOL: iletişim bilgileri ----
        form_kutu = QGroupBox("Misafir Bilgileri (düzenlenebilir)")
        form = QFormLayout()
        self.ad_soyad = QLineEdit(r["ad_soyad"] or "")
        form.addRow("Ad Soyad:", self.ad_soyad)
        self.tc_no = QLineEdit(r["tc_no"] or "")
        self.tc_no.setMaxLength(11)
        self.tc_no.setPlaceholderText("Check-in anında girilir")
        form.addRow("TC No:", self.tc_no)
        self.telefon = QLineEdit(r["telefon"] or "")
        form.addRow("Telefon:", self.telefon)
        self.referans = QLineEdit(r["referans"] or "")
        form.addRow("Referans:", self.referans)
        self.notlar = QTextEdit(r["notlar"] or "")
        self.notlar.setMaximumHeight(60)
        form.addRow("Notlar:", self.notlar)
        form_kutu.setLayout(form)
        layout.addWidget(form_kutu)

        # ---- ODALAR TABLOSU ----
        oda_kutu = QGroupBox("Bu Rezervasyonun Odaları (oda bazlı işlemler)")
        oda_lay = QVBoxLayout()

        tablo = QTableWidget()
        tablo.setColumnCount(9)
        tablo.setHorizontalHeaderLabels([
            "Oda", "Giriş", "Gece", "Çıkış", "Kişi", "Fiyat Tipi", "Gecelik", "Durum", "İşlemler"
        ])
        hh = tablo.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(8, QHeaderView.Stretch)
        tablo.verticalHeader().setVisible(False)
        tablo.verticalHeader().setDefaultSectionSize(40)
        tablo.setEditTriggers(QTableWidget.NoEditTriggers)
        tablo.setRowCount(len(self.odalar))

        for i, o in enumerate(self.odalar):
            cikis_str = o["cikis_tarihi"] or repository.cikis_tarihi_hesapla(o["giris_tarihi"], o["gece_sayisi"])
            degerler = [
                f"{o['kat_adi']} - Oda {o['oda_no']}",
                o["giris_tarihi"], str(o["gece_sayisi"]), cikis_str,
                str(o["kisi_sayisi"]), fiyat_tipi_goster(o["fiyat_tipi"]),
                f"{repository.odasi_gecelik_toplami(o):,}₺/gece",
                _ro_durum_metni(o, r["iptal"]),
            ]
            for col, val in enumerate(degerler):
                tablo.setItem(i, col, QTableWidgetItem(val))

            islem_widget = QWidget()
            il = QHBoxLayout(islem_widget)
            il.setContentsMargins(2, 2, 2, 2)
            il.setSpacing(4)

            aktif_mi = not r["iptal"]
            if aktif_mi:
                kisi_btn = QPushButton("Misafirleri Düzenle" if o["checkin_yapildi"] else "👥 Kişiler / Check-in")
                kisi_btn.clicked.connect(lambda checked, oid=o["id"]: self._odada_kisiler(oid))
                il.addWidget(kisi_btn)

                tarih_btn = QPushButton("🗓 Tarih")
                tarih_btn.clicked.connect(lambda checked, oo=o: self._odada_tarih(oo))
                il.addWidget(tarih_btn)

                oddeg_btn = QPushButton("🔁 Oda")
                oddeg_btn.clicked.connect(lambda checked, oo=o: self._odada_oda_degistir(oo))
                il.addWidget(oddeg_btn)

            if o["checkin_yapildi"] and not o["cikis_tarihi"] and not r["iptal"]:
                cikis_btn = QPushButton("🚪 Çıkış Yap")
                cikis_btn.clicked.connect(lambda checked, oo=o: self._odada_cikis(oo))
                il.addWidget(cikis_btn)

            tablo.setCellWidget(i, 8, islem_widget)

        oda_lay.addWidget(tablo)

        toplam = repository.rezervasyon_toplami(self.rez_id)
        toplam_oda_gece = sum((o["gece_sayisi"] or 0) for o in self.odalar)
        ozet_bilgi = QLabel(
            f"<b>Toplam tutar (tüm odalar, tüm geceler): {toplam:,}₺</b>  "
            f"·  {len(self.odalar)} oda  ·  {toplam_oda_gece} gece"
        )
        ozet_bilgi.setStyleSheet("font-size: 11px; padding: 4px; background-color: rgba(127,127,127,0.08); border-radius: 4px;")
        oda_lay.addWidget(ozet_bilgi)
        oda_kutu.setLayout(oda_lay)
        layout.addWidget(oda_kutu)

        iptal_btn = QPushButton("🚫 Rezervasyonu İptal Et")
        iptal_btn.setStyleSheet("color: #c0392b;")
        iptal_btn.clicked.connect(self.iptal_et)
        iptal_btn.setEnabled(not r["iptal"])
        layout.addWidget(iptal_btn)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Close)
        btns.button(QDialogButtonBox.Save).setText("Bilgileri Kaydet")
        btns.button(QDialogButtonBox.Close).setText("Kapat")
        btns.accepted.connect(self.kaydet)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        kaydir = QScrollArea()
        kaydir.setWidgetResizable(True)
        kaydir.setWidget(ana)
        kok.addWidget(kaydir)

    # ---------------- oda bazlı aksiyonlar ----------------
    def _odada_kisiler(self, ro_id):
        dialog = CheckinDialog(ro_id, self)
        dialog.exec()
        if dialog.kaydedildi:
            self.kaydedildi = True
            self.accept()

    def _odada_tarih(self, ro_row):
        dialog = OdaTarihDialog(ro_row, self)
        if dialog.exec() == QDialog.Accepted:
            self.kaydedildi = True
            self.accept()

    def _odada_oda_degistir(self, ro_row):
        from main import OdaDegistirDialog
        dialog = OdaDegistirDialog(ro_row, self)
        if dialog.exec() == QDialog.Accepted:
            yeni_oda_id = dialog.secilen_oda_id()
            degisim_tarihi = dialog.secilen_tarih()
            try:
                repository.oda_degistir(ro_row["id"], yeni_oda_id, degisim_tarihi)
            except ValueError as e:
                QMessageBox.warning(self, "Oda Değiştirilemedi", str(e))
                return
            self.kaydedildi = True
            self.accept()

    def _odada_cikis(self, ro_row):
        cevap = QMessageBox.question(
            self, "Çıkış İşlemi",
            f"{ro_row['kat_adi']} - Oda {ro_row['oda_no']}'daki misafir çıkış yaptı mı? "
            "İşlem sonrası oda 'temiz' durumuna alınır.",
            QMessageBox.Yes | QMessageBox.No
        )
        if cevap != QMessageBox.Yes:
            return
        try:
            repository.odasi_cikis_yap(ro_row["id"])
        except ValueError as e:
            QMessageBox.warning(self, "Çıkış Yapılamadı", str(e))
            return
        self.kaydedildi = True
        self.accept()

    def iptal_et(self):
        cevap = QMessageBox.question(
            self, "Rezervasyonu İptal Et",
            f"'{self.rez['ad_soyad']}' rezervasyonunun TÜM odaları iptal edilecek. Emin misin?",
            QMessageBox.Yes | QMessageBox.No
        )
        if cevap == QMessageBox.Yes:
            repository.rezervasyon_iptal(self.rez_id)
            self.kaydedildi = True
            self.accept()

    def kaydet(self):
        if not self.ad_soyad.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Ad Soyad boş bırakılamaz.")
            return
        try:
            repository.rezervasyon_guncelle(
                self.rez_id,
                ad_soyad=self.ad_soyad.text().strip(),
                tc_no=self.tc_no.text().strip(),
                telefon=self.telefon.text().strip(),
                referans=self.referans.text().strip(),
                notlar=self.notlar.toPlainText().strip(),
            )
        except ValueError as e:
            QMessageBox.warning(self, "Hata", str(e))
            return
        self.kaydedildi = True
        self.accept()


class CheckinDialog(QDialog):
    """Bir ODA SATIRININ misafirlerini kaydetme / check-in tamamlama penceresi.
    Her kişinin fiyatı (Fiyat Tipi + Gecelik Ücret) AYRI AYRI seçilebilir:
    aynı odada kalan kişiler farklı fiyat ödeyebilir (ör. 1'i Üye, 1'i Sabit, 1'i Özel).
    Kaydedince kişiler kaydedilir, oda satırı check-in yapılır ve henüz ödenmemiş
    gecelerin tutarı kişi başı fiyatlara göre otomatik güncellenir."""

    def __init__(self, ro_id, parent=None):
        super().__init__(parent)
        self.ro_id = ro_id
        self.kaydedildi = False
        self.ro = repository.rezervasyon_odasi_getir(ro_id)
        self.misafir_satirlari = []  # [(ad_edit, tc_edit, tip_combo, ucret_spin, sil_btn)]

        if self.ro is None:
            self.setWindowTitle("Bulunamadı")
            layout = QVBoxLayout(self)
            layout.addWidget(QLabel("Bu oda satırı bulunamadı."))
            return

        self.kapasite = self.ro["kapasite"] or 1
        self.ekstra_yatak = False
        self.kayit_limiti = max(self.kapasite + 2, 3)
        baslik = "Check-in Yap" if not self.ro["checkin_yapildi"] else "Misafirleri Düzenle"
        self.setWindowTitle(f"{baslik} - {self.ro['kat_adi']} Oda {self.ro['oda_no']}")
        self.setMinimumSize(760, 520)
        self.resize(820, 560)
        self._arayuzu_kur()

    def _efektif_kapasite(self):
        return self.kayit_limiti + (1 if self.ekstra_yatak else 0)

    def _arayuzu_kur(self):
        r = self.ro
        layout = QVBoxLayout(self)

        cikis = repository.cikis_tarihi_hesapla(r["giris_tarihi"], r["gece_sayisi"])
        ust_bilgi = QLabel(
            f"<b>{r['kat_adi']} - Oda {r['oda_no']}</b> ({r['oda_tipi']}, kapasite {self.kapasite} kişi)<br>"
            f"Giriş: {r['giris_tarihi']} → Çıkış: {cikis} ({r['gece_sayisi']} gece)<br>"
            f"Rezervasyonu alan: {r['ad_soyad']} ({r['telefon'] or '-'})"
        )
        ust_bilgi.setWordWrap(True)
        layout.addWidget(ust_bilgi)

        self.ekstra_yatak_check = QCheckBox("🛏️ Ekstra yatak var (kapasiteyi bu sefer için +1 artır)")
        self.ekstra_yatak_check.toggled.connect(self._ekstra_yatak_degisti)
        layout.addWidget(self.ekstra_yatak_check)

        misafir_kutu = QGroupBox(f"Odada Kalacak Kişiler (en fazla {self._efektif_kapasite()})")
        self.misafir_kutu = misafir_kutu
        misafir_layout = QVBoxLayout()

        self.misafir_tablo = QTableWidget()
        self.misafir_tablo.setColumnCount(5)
        self.misafir_tablo.setHorizontalHeaderLabels(["Ad Soyad", "TC No", "Fiyat Tipi", "Gecelik (TL)", ""])
        tablo_hh = self.misafir_tablo.horizontalHeader()
        tablo_hh.setSectionResizeMode(0, QHeaderView.Stretch)
        tablo_hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        tablo_hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        tablo_hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        misafir_layout.addWidget(self.misafir_tablo)

        self.ekle_btn = QPushButton("➕ Kişi Ekle")
        self.ekle_btn.clicked.connect(lambda: self._kisi_ekle())
        misafir_layout.addWidget(self.ekle_btn)

        self.kapasite_uyari = QLabel("")
        self.kapasite_uyari.setStyleSheet("color: #c0392b; font-style: italic;")
        misafir_layout.addWidget(self.kapasite_uyari)

        misafir_kutu.setLayout(misafir_layout)
        layout.addWidget(misafir_kutu)

        mevcut = repository.odasi_misafirler_listele(self.ro_id)
        baslangic_sayisi = len(mevcut) if mevcut else (r["kisi_sayisi"] or 1)
        if baslangic_sayisi > self.kapasite:
            self.ekstra_yatak_check.setChecked(True)

        if mevcut:
            for m in mevcut:
                self._kisi_ekle(
                    ad_soyad=m["ad_soyad"] or "",
                    tc_no=m["tc_no"] or "",
                    fiyat_tipi=m["fiyat_tipi"] or r["fiyat_tipi"],
                    gecelik_ucret=m["gecelik_ucret"] or r["gecelik_ucret"],
                )
        else:
            for _ in range(baslangic_sayisi):
                self._kisi_ekle()

        self.fiyat_bilgi = QLabel("")
        self.fiyat_bilgi.setWordWrap(True)
        self.fiyat_bilgi.setStyleSheet("font-size: 10px; padding: 3px;")
        layout.addWidget(self.fiyat_bilgi)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Close)
        kaydet_metni = "Check-in'i Tamamla" if not r["checkin_yapildi"] else "Kaydet"
        btns.button(QDialogButtonBox.Save).setText(kaydet_metni)
        btns.button(QDialogButtonBox.Close).setText("Kapat")
        btns.accepted.connect(self.kaydet)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self._kapasite_kontrol_et()
        self._fiyat_ozetini_yenile()

    def _ekstra_yatak_degisti(self, checked):
        self.ekstra_yatak = checked
        self.misafir_kutu.setTitle(f"Odada Kalacak Kişiler (en fazla {self._efektif_kapasite()})")
        self._kapasite_kontrol_et()

    def _kisi_ekle(self, ad_soyad="", tc_no="", fiyat_tipi=None, gecelik_ucret=None):
        efektif = self._efektif_kapasite()
        if len(self.misafir_satirlari) >= efektif:
            self.kapasite_uyari.setText(
                f"En fazla {efektif} kişi kaydedilebilir."
                + ("" if self.ekstra_yatak else " Gerekirse ekstra yatak kutusunu işaretleyebilirsin.")
            )
            return
        row = self.misafir_tablo.rowCount()
        self.misafir_tablo.insertRow(row)

        ad_edit = QLineEdit(ad_soyad)
        ad_edit.setPlaceholderText(f"Kişi {row + 1} Ad Soyad (zorunlu)")
        tc_edit = TcAlan(tc_no)
        tc_edit.setPlaceholderText("TC No - 11 hane (zorunlu)")
        tc_edit.setMaxLength(11)

        r_fiyat = self.ro["fiyat_tipi"]
        r_ucret = self.ro["gecelik_ucret"]
        tip = fiyat_tipi if fiyat_tipi else r_fiyat
        ucret = gecelik_ucret if gecelik_ucret else r_ucret

        tip_combo = QComboBox()
        tip_combo.addItems(FIYAT_TIPLERI)
        tip_combo.setCurrentText(tip)
        tip_combo.currentTextChanged.connect(lambda _: self._tip_degisti(tip_combo, ucret_spin, r_ucret))

        ucret_spin = QSpinBox()
        ucret_spin.setRange(0, 100000)
        ucret_spin.setSingleStep(50)
        ucret_spin.setValue(int(ucret or r_ucret or 0))
        ucret_spin.valueChanged.connect(lambda _: self._fiyat_ozetini_yenile())

        self.misafir_tablo.setCellWidget(row, 0, ad_edit)
        self.misafir_tablo.setCellWidget(row, 1, tc_edit)
        self.misafir_tablo.setCellWidget(row, 2, tip_combo)
        self.misafir_tablo.setCellWidget(row, 3, ucret_spin)

        sil_btn = QPushButton("Sil")
        sil_btn.clicked.connect(lambda: self._kisi_sil(sil_btn))
        self.misafir_tablo.setCellWidget(row, 4, sil_btn)

        self.misafir_satirlari.append((ad_edit, tc_edit, tip_combo, ucret_spin, sil_btn))
        self._kapasite_kontrol_et()
        self._fiyat_ozetini_yenile()

    def _kisi_sil(self, buton):
        for i, satir in enumerate(self.misafir_satirlari):
            if satir[4] is buton:
                self.misafir_tablo.removeRow(i)
                del self.misafir_satirlari[i]
                break
        self._kapasite_kontrol_et()
        self._fiyat_ozetini_yenile()

    def _tip_degisti(self, tip_combo, ucret_spin, r_ucret):
        from database import gecelik_fiyat
        tip = tip_combo.currentText()
        if tip != "Ozel":
            ucret_spin.setValue(gecelik_fiyat(tip, None))
        else:
            if ucret_spin.value() <= 0:
                ucret_spin.setValue(int(r_ucret or 1300))
        self._fiyat_ozetini_yenile()

    def _kapasite_kontrol_et(self):
        dolu = len(self.misafir_satirlari)
        efektif = self._efektif_kapasite()
        self.ekle_btn.setEnabled(dolu < efektif)
        if dolu >= efektif:
            self.kapasite_uyari.setText(f"En fazla {efektif} kişi kaydedilebilir.")
            self.kapasite_uyari.setStyleSheet("color: #c0392b; font-style: italic;")
        elif dolu > self.kapasite:
            self.kapasite_uyari.setText(
                f"Oda kapasitesi {self.kapasite} kişi; {dolu} kişi kaydedildi (fazlalık kabul edilir)."
            )
            self.kapasite_uyari.setStyleSheet("color: #b9770e; font-style: italic;")
        else:
            self.kapasite_uyari.setText(f"{dolu}/{self.kapasite} kişi eklenebilir (en fazla {efektif}).")
            self.kapasite_uyari.setStyleSheet("color: #27ae60; font-style: italic;")

    def _fiyat_ozetini_yenile(self):
        if not hasattr(self, "fiyat_bilgi"):
            return
        gece_toplam = sum(s[3].value() for s in self.misafir_satirlari)
        genel_toplam = gece_toplam * (self.ro["gece_sayisi"] or 1)
        parcalar = []
        for s in self.misafir_satirlari:
            ad = s[0].text().strip() or "?"
            parcalar.append(f"{fiyat_tipi_goster(s[2].currentText())} {s[3].value()}₺")
        self.fiyat_bilgi.setText(
            f"<b>Gecelik toplam: {gece_toplam}₺</b> · Genel toplam: <b>{genel_toplam}₺</b>"
            f" ({self.ro['gece_sayisi']} gece)   —  Kişi bazlı: {', '.join(parcalar) or '—'}"
        )

    def kaydet(self):
        efektif = self._efektif_kapasite()
        if len(self.misafir_satirlari) == 0:
            QMessageBox.warning(self, "Eksik Bilgi", "En az 1 kişi eklemelisin.")
            return
        if len(self.misafir_satirlari) > efektif:
            QMessageBox.warning(self, "Kapasite Aşıldı", f"Bu oda en fazla {efektif} kişi alabilir.")
            return

        misafir_listesi = []
        for i, (ad_edit, tc_edit, tip_combo, ucret_spin, _) in enumerate(self.misafir_satirlari, start=1):
            ad = ad_edit.text().strip()
            tc = tc_edit.text().strip()
            if not ad:
                QMessageBox.warning(self, "Eksik Bilgi", f"{i}. kişinin Ad Soyad bilgisi boş bırakılamaz.")
                return
            if not tc:
                QMessageBox.warning(self, "Eksik Bilgi", f"{i}. kişinin TC No bilgisi boş bırakılamaz.")
                return
            if not (tc.isdigit() and len(tc) == 11):
                QMessageBox.warning(self, "Geçersiz TC No", f"{i}. kişinin TC No'su 11 haneli rakamlardan oluşmalı.")
                return
            tip = tip_combo.currentText()
            ucret = ucret_spin.value()
            if tip == "Ozel" and ucret <= 0:
                QMessageBox.warning(self, "Geçersiz Özel Fiyat", f"{i}. kişi için özel fiyat girilmelidir.")
                return
            misafir_listesi.append((ad, tc, tip, ucret))

        repository.odasi_misafirleri_kaydet(self.ro_id, misafir_listesi, ekstra_yatak=self.ekstra_yatak)
        repository.odasi_checkin_yap(self.ro_id)

        self.kaydedildi = True
        self.accept()