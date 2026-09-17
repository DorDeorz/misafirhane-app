# -*- coding: utf-8 -*-
"""
Rezervasyon detay/düzenleme penceresi.
Oda Durumu ve Takvim Görünümü ekranlarından bir isme çift tıklandığında açılır.
Check-in anında TC No / kesin Ad Soyad bilgisini tamamlamak için kullanılır.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QSpinBox, QComboBox, QTextEdit, QPushButton, QDialogButtonBox, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QCheckBox,
    QDateEdit, QScrollArea, QWidget
)
from PySide6.QtCore import Qt, QDate
from datetime import datetime, timedelta

import repository
from database import fiyat_tipi_goster, gecelik_fiyat, FIYAT_TIPLERI


def _kisi_bazli_gecelik_toplam(rez_id, kisi_sayisi, gecelik_ucret):
    """Kayıtlı kişilerin bireysel fiyatlarının toplamını döndürür.
    Kişi başı fiyat yoksa rezervasyonun kendi (kisi * gecelik) değerine döner."""
    misafirler = repository.misafirler_listele(rez_id)
    ucretler = [m["gecelik_ucret"] for m in misafirler if m["gecelik_ucret"]]
    if ucretler:
        return sum(ucretler)
    return (gecelik_ucret or 0) * (kisi_sayisi or 1)


class TcAlan(QLineEdit):
    """TC No alanı: tıklanınca/fokus olunca mevcut metni otomatik seçer.
    Kayıtlı TC (11 haneli) tam dolu olduğu için 'yazılamıyor' sorununu çözer:
    tıkla → metin seçili gelir → doğrudan yeni TC yazılır."""

    def focusInEvent(self, olay):
        super().focusInEvent(olay)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self.selectAll)


class RezervasyonDetayDialog(QDialog):
    def __init__(self, rez_id, parent=None):
        super().__init__(parent)
        self.rez_id = rez_id
        self.kaydedildi = False
        self.rez = repository.rezervasyon_getir(rez_id)

        if self.rez is None:
            self.setWindowTitle("Bulunamadı")
            layout = QVBoxLayout(self)
            layout.addWidget(QLabel("Bu rezervasyon bulunamadı (silinmiş olabilir)."))
            return

        self.setWindowTitle(f"Rezervasyon Detayı - {self.rez['ad_soyad']}")
        self.setMinimumSize(880, 560)
        self.resize(980, 640)
        self._arayuzu_kur()

    def _arayuzu_kur(self):
        r = self.rez
        kok = QVBoxLayout(self)

        ana = QWidget()
        layout = QVBoxLayout(ana)
        layout.setContentsMargins(12, 12, 12, 12)

        cikis = repository.cikis_tarihi_hesapla(r["giris_tarihi"], r["gece_sayisi"])
        if r["iptal"]:
            durum_metni = "İptal Edildi"
        elif repository.gelmedi_mi(r):
            durum_metni = "⚠ GELMEDİ (No-Show)"
        elif r["checkin_yapildi"]:
            durum_metni = "✓ Check-in Yapıldı"
        else:
            durum_metni = "Bekleniyor (henüz check-in yapılmadı)"

        alinma_tarihi = (r["olusturma_tarihi"] or "").split(".")[0]
        alan_kullanici = r["olusturan_kullanici"] or "Bilinmiyor (eski kayıt)"

        ust_bilgi = QLabel(
            f"<b>{r['kat_adi']} - Oda {r['oda_no']}</b> ({r['oda_tipi']})<br>"
            f"Giriş: {r['giris_tarihi']}  →  Çıkış: {cikis}  ({r['gece_sayisi']} gece)<br>"
            f"Durum: <b>{durum_metni}</b><br>"
            f"<span style='color:#555;'>Rezervasyon alınma tarihi: {alinma_tarihi}  |  "
            f"Alan kullanıcı: {alan_kullanici}</span>"
        )
        ust_bilgi.setWordWrap(True)
        layout.addWidget(ust_bilgi)

        if repository.gelmedi_mi(r):
            uyari = QLabel(
                "⚠ Bu misafir giriş tarihinde gelmedi (No-Show). Odayı başkasına vermek "
                "istersen 'Rezervasyon Yönetimi' ekranından iptal edebilirsin."
            )
            uyari.setWordWrap(True)
            uyari.setStyleSheet("color: #c0392b; background-color: #f8d0d0; padding: 6px; border-radius: 4px;")
            layout.addWidget(uyari)

        # ---- İKİ SÜTUNLU YATAY DÜZEN ----
        kolonlar = QHBoxLayout()

        # ---- SOL SÜTUN: Bilgiler ----
        sol = QVBoxLayout()

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

        kapasite = r["kapasite"] or 1
        mevcut_kisi = r["kisi_sayisi"] or 1
        ust_sinir = max(kapasite + 1, mevcut_kisi, 10)
        self.kisi_sayisi = QSpinBox()
        self.kisi_sayisi.setRange(1, ust_sinir)
        self.kisi_sayisi.setValue(mevcut_kisi)
        kapasite_bilgi = QLabel(f"(Bu odanın kapasitesi: {kapasite} kişi, ekstra yatakla {kapasite + 1})")
        kapasite_bilgi.setStyleSheet("font-style: italic; font-size: 10px;")
        form.addRow("Kişi Sayısı:", self.kisi_sayisi)
        form.addRow("", kapasite_bilgi)

        self.referans = QLineEdit(r["referans"] or "")
        form.addRow("Referans:", self.referans)

        self.notlar = QTextEdit(r["notlar"] or "")
        self.notlar.setMaximumHeight(60)
        form.addRow("Notlar:", self.notlar)

        form_kutu.setLayout(form)
        sol.addWidget(form_kutu)

        # ---- Kişi bazlı fiyatlar ----
        kisi_kutu = QGroupBox("Odada Kayıtlı Kişiler (kişi başı fiyatlarla)")
        kisi_layout = QVBoxLayout()
        misafirler = repository.misafirler_listele(self.rez_id)
        if misafirler:
            k_tablo = QTableWidget()
            k_tablo.setColumnCount(4)
            k_tablo.setHorizontalHeaderLabels(["Ad Soyad", "TC No", "Fiyat Tipi", "Gecelik"])
            k_tablo.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
            k_tablo.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
            k_tablo.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
            k_tablo.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
            k_tablo.setEditTriggers(QTableWidget.NoEditTriggers)
            k_tablo.setAlternatingRowColors(True)
            k_tablo.setRowCount(len(misafirler))
            for i, m in enumerate(misafirler):
                k_tablo.setItem(i, 0, QTableWidgetItem(m["ad_soyad"] or ""))
                k_tablo.setItem(i, 1, QTableWidgetItem(m["tc_no"] or ""))
                tip = m["fiyat_tipi"] or r["fiyat_tipi"]
                ucret = m["gecelik_ucret"] or r["gecelik_ucret"]
                k_tablo.setItem(i, 2, QTableWidgetItem(fiyat_tipi_goster(tip)))
                k_tablo.setItem(i, 3, QTableWidgetItem(f"{ucret} TL/kişi/gece"))
            kisi_layout.addWidget(k_tablo)
        else:
            bilgi = QLabel("Henüz kayıtlı kişi yok. 'Odadaki Kişileri Yönet / Check-in' ile "
                           "her kişinin Ad, TC No ve fiyatı ayrı ayrı eklenir.")
            bilgi.setWordWrap(True)
            bilgi.setStyleSheet("font-style: italic; font-size: 10px;")
            kisi_layout.addWidget(bilgi)
        kisi_kutu.setLayout(kisi_layout)
        sol.addWidget(kisi_kutu)

        gecelik_plan = _kisi_bazli_gecelik_toplam(self.rez_id, r["kisi_sayisi"], r["gecelik_ucret"])
        toplam = gecelik_plan * (r["gece_sayisi"] or 1)
        fiyat_bilgi = QLabel(
            f"Rezervasyon fiyat tipi: <b>{fiyat_tipi_goster(r['fiyat_tipi'])}</b> "
            f"(varsayılan {r['gecelik_ucret']} TL/kişi/gece)<br>"
            f"<b>Toplam: {toplam} TL</b>"
            f"<span style='color:#777;'>  ({gecelik_plan} TL/gece × {r['gece_sayisi']} gece)</span>"
        )
        fiyat_bilgi.setWordWrap(True)
        fiyat_bilgi.setStyleSheet("font-size: 11px; padding: 4px; background-color: rgba(127,127,127,0.08); border-radius: 4px;")
        sol.addWidget(fiyat_bilgi)

        sol.addStretch()

        # ---- SAĞ SÜTUN: Ödeme + Tarih + Grup ----
        sag = QVBoxLayout()

        odemeler = repository.rezervasyon_odemeleri(self.rez_id)
        if odemeler:
            odeme_kutu = QGroupBox("Gecelik Ödeme Durumu")
            odeme_layout = QVBoxLayout()
            tablo = QTableWidget()
            tablo.setColumnCount(3)
            tablo.setHorizontalHeaderLabels(["Tarih", "Tutar", "Durum"])
            tablo.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            tablo.setEditTriggers(QTableWidget.NoEditTriggers)
            tablo.setRowCount(len(odemeler))
            tablo.setMaximumHeight(170)
            for i, o in enumerate(odemeler):
                durum = "✓ Ödendi" if o["odendi"] else "✗ Ödenmedi"
                if o["odendi"] and o["odeme_sekli"]:
                    durum += f" ({o['odeme_sekli']})"
                tablo.setItem(i, 0, QTableWidgetItem(o["tarih"]))
                tablo.setItem(i, 1, QTableWidgetItem(f"{o['tutar']} TL"))
                tablo.setItem(i, 2, QTableWidgetItem(durum))
            odeme_layout.addWidget(tablo)
            not_label = QLabel("Ödeme durumunu değiştirmek için 'Oda Durumu' ekranındaki ilgili güne git.")
            not_label.setStyleSheet("font-style: italic; font-size: 10px;")
            odeme_layout.addWidget(not_label)
            odeme_kutu.setLayout(odeme_layout)
            sag.addWidget(odeme_kutu)

        tarih_kutu = QGroupBox("Tarihi Değiştir")
        tarih_layout = QVBoxLayout()
        tarih_satir = QHBoxLayout()
        tarih_satir.addWidget(QLabel("Giriş:"))
        self.tarih_giris = QDateEdit(QDate.fromString(r["giris_tarihi"], "yyyy-MM-dd"))
        self.tarih_giris.setCalendarPopup(True)
        self.tarih_giris.setDisplayFormat("dd.MM.yyyy")
        tarih_satir.addWidget(self.tarih_giris)
        tarih_satir.addWidget(QLabel("Gece:"))
        self.tarih_gece = QSpinBox()
        self.tarih_gece.setRange(1, 90)
        self.tarih_gece.setValue(r["gece_sayisi"] or 1)
        tarih_satir.addWidget(self.tarih_gece)
        tarih_btn = QPushButton("Uygula")
        tarih_btn.clicked.connect(lambda: self._tarihi_uygula())
        tarih_satir.addWidget(tarih_btn)
        tarih_layout.addLayout(tarih_satir)
        tarih_not = QLabel("Yeni giriş tarihi ile gece sayısına göre çıkış ve ödeme planı yeniden kurulur. "
                           "Önceden ödenmiş geceler yeni aralığın dışında kalırsa uyarılacaksın.")
        tarih_not.setWordWrap(True)
        tarih_not.setStyleSheet("font-style: italic; font-size: 10px;")
        tarih_layout.addWidget(tarih_not)
        tarih_kutu.setLayout(tarih_layout)
        sag.addWidget(tarih_kutu)

        if self.rez["grup_id"]:
            grup = repository.grup_rezervasyonlari(self.rez["grup_id"], haric_rez_id=self.rez_id)
            if grup:
                grup_kutu = QGroupBox("Aynı Rezervasyondaki Diğer Odalar")
                grup_layout = QVBoxLayout()
                for g in grup:
                    grup_layout.addWidget(QLabel(
                        f"• {g['kat_adi']} - Oda {g['oda_no']}  ({g['giris_tarihi']}, {g['gece_sayisi']} gece)"
                    ))
                grup_kutu.setLayout(grup_layout)
                sag.addWidget(grup_kutu)

        sag.addStretch()

        kolonlar.addLayout(sol, 1)
        kolonlar.addLayout(sag, 1)
        layout.addLayout(kolonlar)

        misafir_btn = QPushButton("👥 Odadaki Kişileri Yönet / Check-in")
        misafir_btn.clicked.connect(lambda: self._misafirleri_yonet())
        layout.addWidget(misafir_btn)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Close)
        btns.button(QDialogButtonBox.Save).setText("Kaydet")
        btns.button(QDialogButtonBox.Close).setText("Kapat")
        btns.accepted.connect(self.kaydet)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        kaydir = QScrollArea()
        kaydir.setWidgetResizable(True)
        kaydir.setWidget(ana)
        kaydir.setWidgetResizable(True)
        kok.addWidget(kaydir)

    def _misafirleri_yonet(self):
        dialog = CheckinDialog(self.rez_id, self)
        dialog.exec()
        if dialog.kaydedildi:
            self.kaydedildi = True
            self.accept()

    def _hesaplanan_dusen_odenmis(self, yeni_giris_str, yeni_gece):
        """Yeni araliga girmeyecek ODENMIS gecelerin tarihlerini dondurur (on izleme)."""
        odemeler = repository.rezervasyon_odemeleri(self.rez_id)
        g = datetime.strptime(yeni_giris_str, "%Y-%m-%d").date()
        yeni_set = { (g + timedelta(days=i)).isoformat() for i in range(yeni_gece) }
        return sorted(o["tarih"] for o in odemeler if o["odendi"] and o["tarih"] not in yeni_set)

    def _tarihi_uygula(self):
        if self.rez["iptal"]:
            QMessageBox.warning(self, "İptal Edilmiş", "İptal edilen bir rezervasyonun tarihi değiştirilemez.")
            return
        yeni_giris = self.tarih_giris.date().toString("yyyy-MM-dd")
        yeni_gece = self.tarih_gece.value()
        dusenler = self._hesaplanan_dusen_odenmis(yeni_giris, yeni_gece)
        if dusenler:
            cevap = QMessageBox.question(
                self,
                "Önceden Ödenen Geceler",
                "Yeni tarih/gece sayısında şu ÖNCEDEN ÖDENMİŞ geceler yer almayacak:\n"
                + ", ".join(dusenler)
                + "\n\nBu gecelerin tutarı otomatik iade edilmez; iade/avans işlemini "
                  "'Oda Durumu' ekranından elle yapmalısın.\n\nYine de tarihi değiştir?",
            )
            if cevap != QMessageBox.Yes:
                return
        try:
            repository.rezervasyon_tarih_degistir(self.rez_id, yeni_giris, yeni_gece)
        except ValueError as e:
            QMessageBox.warning(self, "Tarih Değiştirilemedi", str(e))
            return
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
                kisi_sayisi=self.kisi_sayisi.value(),
                referans=self.referans.text().strip(),
                notlar=self.notlar.toPlainText().strip(),
            )
        except ValueError as e:
            QMessageBox.warning(self, "Kapasite Aşıldı", str(e))
            return
        try:
            ekstra = self.kisi_sayisi.value() > (self.rez["kapasite"] or 1)
            repository.kisi_sayisi_senkronla(
                self.rez_id, self.kisi_sayisi.value(), ekstra_yatak=ekstra
            )
        except ValueError as e:
            QMessageBox.warning(self, "Kapasite Aşıldı", str(e))
            return
        self.kaydedildi = True
        self.accept()


class CheckinDialog(QDialog):
    """Misafirleri odaya teker teker ekleme / check-in tamamlama penceresi.
    Her kişinin fiyatı (Fiyat Tipi + Gecelik Ücret) AYRI AYRI seçilebilir:
    aynı odada kalan kişiler farklı fiyat ödeyebilir (ör. 1'i Üye, 1'i Sabit, 1'i Özel).
    Kaydedince kisi_sayisi ve ödenmemiş gecelerin tutarı kişi başı fiyatlara göre otomatik güncellenir."""

    def __init__(self, rez_id, parent=None):
        super().__init__(parent)
        self.rez_id = rez_id
        self.kaydedildi = False
        self.rez = repository.rezervasyon_getir(rez_id)
        self.misafir_satirlari = []  # [(ad_edit, tc_edit, tip_combo, ucret_spin, sil_btn)]

        if self.rez is None:
            self.setWindowTitle("Bulunamadı")
            layout = QVBoxLayout(self)
            layout.addWidget(QLabel("Bu rezervasyon bulunamadı."))
            return

        self.kapasite = self.rez["kapasite"] or 1
        self.ekstra_yatak = False
        # Kayıt limiti: resmî kapasitenin ÜZERİNDE de misafir kaydedilebilir
        # (+2 kişi; ekstra yatak işaretlenirse +1 daha). Örn. 2 kişilik odaya
        # 3. misafir, 1 kişilik odaya 2. misafir rahatça eklenebilir.
        self.kayit_limiti = max(self.kapasite + 2, 3)
        baslik = "Check-in Yap" if not self.rez["checkin_yapildi"] else "Misafirleri Düzenle"
        self.setWindowTitle(f"{baslik} - {self.rez['kat_adi']} Oda {self.rez['oda_no']}")
        self.setMinimumSize(760, 520)
        self.resize(820, 560)
        self._arayuzu_kur()

    def _efektif_kapasite(self):
        return self.kayit_limiti + (1 if self.ekstra_yatak else 0)

    def _arayuzu_kur(self):
        r = self.rez
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
        self.misafir_tablo.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.misafir_tablo.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.misafir_tablo.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.misafir_tablo.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        misafir_layout.addWidget(self.misafir_tablo)

        self.ekle_btn = QPushButton("➕ Kişi Ekle")
        self.ekle_btn.clicked.connect(lambda: self._kisi_ekle())
        misafir_layout.addWidget(self.ekle_btn)

        self.kapasite_uyari = QLabel("")
        self.kapasite_uyari.setStyleSheet("color: #c0392b; font-style: italic;")
        misafir_layout.addWidget(self.kapasite_uyari)

        misafir_kutu.setLayout(misafir_layout)
        layout.addWidget(misafir_kutu)

        mevcut = repository.misafirler_listele(self.rez_id)
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
        kaydet_metni = "Check-in'i Tamamla" if not self.rez["checkin_yapildi"] else "Kaydet"
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

        r_fiyat = self.rez["fiyat_tipi"]
        r_ucret = self.rez["gecelik_ucret"]
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
        genel_toplam = gece_toplam * (self.rez["gece_sayisi"] or 1)
        parcalar = []
        for s in self.misafir_satirlari:
            ad = s[0].text().strip() or "?"
            parcalar.append(f"{fiyat_tipi_goster(s[2].currentText())} {s[3].value()}₺")
        self.fiyat_bilgi.setText(
            f"<b>Gecelik toplam: {gece_toplam}₺</b> · Genel toplam: <b>{genel_toplam}₺</b>"
            f" ({self.rez['gece_sayisi']} gece)   —  Kişi bazlı: {', '.join(parcalar) or '—'}"
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

        repository.misafirleri_kaydet(self.rez_id, misafir_listesi, ekstra_yatak=self.ekstra_yatak)
        repository.checkin_yap(self.rez_id)

        self.kaydedildi = True
        self.accept()