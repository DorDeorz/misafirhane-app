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
    QDateEdit, QScrollArea, QWidget, QSplitter, QSizePolicy
)
from PySide6.QtCore import Qt, QDate
from datetime import date

import repository
import tema
from database import fiyat_tipi_goster
from kbs import misafir_tipi, tc_dogrula, YABANCI_ALANLAR

FIYAT_TIPLERI = ["Sabit", "Uye", "Ozel"]


def _satir_getir(satir, anahtar, varsayilan=""):
    """sqlite3.Row'dan kolon olmasa da güvenle değer okur (eski DB uyumu)."""
    try:
        deger = satir[anahtar]
    except (KeyError, IndexError):
        return varsayilan
    return deger or varsayilan


def _rozet(metin, renk):
    """Küçük renkli rozet — durum bildirimleri için ortak görünüm."""
    return tema.rozet(metin, renk)


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


def _tarih_degistir_akisi(ebeveyn, ro, yeni_giris, yeni_gece):
    """Ortak akış: çakışan rezervasyon varsa gece azaltma öner + onay iste; ödenmiş
    geceler kapsam dışına düştüyse uyar. Başarılıysa True döner."""
    cakisma = repository.musaitlik_kontrol(ro["oda_id"], yeni_giris, yeni_gece, haric_ro_id=ro["id"])
    if cakisma:
        isimler = ", ".join(c["ad_soyad"] for c in cakisma[:3])
        max_gece = repository.odasi_max_gece(ro["id"], yeni_giris)
        if max_gece <= 0:
            QMessageBox.warning(ebeveyn, "Tarih Değiştirilemedi",
                                f"Bu giriş tarihinde oda zaten dolu: {isimler}. Hiç gece sığmıyor.")
            return False
        cevap = QMessageBox.question(
            ebeveyn, "Çakışma Var",
            f"<b>{yeni_giris}</b> girişiyle <b>{yeni_gece}</b> gece kalınırsa "
            f"<b>{isimler}</b> rezervasyonuyla çakışıyor.<br><br>"
            f"Bu durumda gece sayısının <b>{max_gece}</b>'ye düşürülmesi gerekir "
            f"(çıkış: <b>{repository.cikis_tarihi_hesapla(yeni_giris, max_gece)}</b>).<br><br>"
            f"Gece sayısı <b>{max_gece}</b> olarak uygulansın mı?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if cevap != QMessageBox.Yes:
            return False
        yeni_gece = max_gece

    try:
        dusen_odenmis = repository.rezervasyon_odasi_tarih_degistir(ro["id"], yeni_giris, yeni_gece)
    except ValueError as e:
        QMessageBox.warning(ebeveyn, "Tarih Değiştirilemedi", str(e))
        return False
    if dusen_odenmis:
        QMessageBox.information(
            ebeveyn, "Ödenen Geceler",
            "Şu geceler yeni tarih/gece planının dışında kaldı (ödendi bilgileri "
            "korundu, tutar iade edilmedi):\n" + ", ".join(dusen_odenmis),
        )
    return True


class OdaTarihDialog(QDialog):
    """Tek oda satırının giriş tarihi / gece sayısını değiştirir.
    Konaklama başlamışsa (giriş geçmişte) giriş tarihi KİLİTLİ, yalnızca gece
    sayısı uzatılabilir/kısaltılabilir. Çakışan rezervasyon varsa gece sayısının
    azaltılması önerilir ve onay istenir."""

    def __init__(self, ro_row, parent=None):
        super().__init__(parent)
        self.ro_row = ro_row
        self.setWindowTitle(f"Tarih / Gece Düzenle - {ro_row['kat_adi']} Oda {ro_row['oda_no']}")
        self.setMinimumWidth(460)

        self.iceride_mi = bool(ro_row["checkin_yapildi"])

        layout = QVBoxLayout(self)
        baslik = QLabel(
            f"<b>{ro_row['kat_adi']} - Oda {ro_row['oda_no']}</b> "
            f"({ro_row['gece_sayisi']} gece, {ro_row['kisi_sayisi']} kişi)<br>"
            f"Rezervasyonu alan: {ro_row['ad_soyad']}"
        )
        baslik.setWordWrap(True)
        layout.addWidget(baslik)

        form = QFormLayout()
        self.tarih_giris = QDateEdit(QDate.fromString(ro_row["giris_tarihi"], "yyyy-MM-dd"))
        self.tarih_giris.setCalendarPopup(True)
        self.tarih_giris.setDisplayFormat("dd.MM.yyyy")
        self.tarih_giris.setEnabled(not self.iceride_mi)
        form.addRow("Giriş Tarihi:", self.tarih_giris)

        self.tarih_gece = QSpinBox()
        self.tarih_gece.setRange(1, 365)
        self.tarih_gece.setValue(ro_row["gece_sayisi"] or 1)
        form.addRow("Gece Sayısı:", self.tarih_gece)
        layout.addLayout(form)

        if self.iceride_mi:
            kilit = QLabel("Konaklama başladı (misafir içeride); giriş tarihi kilitli. "
                           "Yalnızca GEÇE sayısı uzatılabilir/kısaltılabilir.")
            kilit.setWordWrap(True)
            kilit.setStyleSheet("color: #b9770e; font-style: italic; font-size: 10px;")
            layout.addWidget(kilit)

        self.onizle = QLabel("")
        self.onizle.setWordWrap(True)
        self.onizle.setStyleSheet("font-size: 10px; padding: 3px;")
        layout.addWidget(self.onizle)

        not_label = QLabel("Ödemeler yeni aralığa göre yeniden kurulur. Önceden ödenmiş "
                           "geceler yeni aralığın dışında kalırsa uyarılacaksın (tutarlar otomatik iade edilmez).")
        not_label.setWordWrap(True)
        not_label.setStyleSheet("font-style: italic; font-size: 10px;")
        layout.addWidget(not_label)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Save).setText("Uygula")
        btns.button(QDialogButtonBox.Save).setObjectName("birincil")
        btns.button(QDialogButtonBox.Cancel).setText("Vazgeç")
        btns.accepted.connect(self.uygula)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self.tarih_giris.dateChanged.connect(self._onizle)
        self.tarih_gece.valueChanged.connect(self._onizle)
        self._onizle()

    def _onizle(self):
        yeni_giris = self.tarih_giris.date().toString("yyyy-MM-dd")
        yeni_gece = self.tarih_gece.value()
        yeni_cikis = repository.cikis_tarihi_hesapla(yeni_giris, yeni_gece)
        ro = self.ro_row
        try:
            cakisma = repository.musaitlik_kontrol(ro["oda_id"], yeni_giris, yeni_gece,
                                                   haric_ro_id=ro["id"])
            max_gece = repository.odasi_max_gece(ro["id"], yeni_giris)
        except Exception:
            cakisma, max_gece = [], None
        parcalar = [f"Yeni çıkış: <b>{yeni_cikis}</b>"]
        if cakisma:
            isimler = ", ".join(c["ad_soyad"] for c in cakisma[:2])
            parcalar.append(f"<span style='color:#c0392b;'>⚠ Çakışma: {isimler}…</span>")
            if max_gece is not None and max_gece > 0:
                parcalar.append(f"Bu giriş için uygun en fazla gece: <b>{max_gece}</b>")
            elif max_gece == 0:
                parcalar.append("<span style='color:#c0392b;'>Bu girişte gece sığmıyor.</span>")
        self.onizle.setText(" · ".join(parcalar))

    def uygula(self):
        if _tarih_degistir_akisi(
            self, self.ro_row,
            self.tarih_giris.date().toString("yyyy-MM-dd"),
            self.tarih_gece.value(),
        ):
            self.accept()


class YabanciBilgiDialog(QDialog):
    """Yabancı misafirin KBS için zorunlu bilgilerini toplar.

    KBS (1774 sayılı Kanun) yabancı misafir için belge no + ad soyad + uyruk +
    doğum tarihi + cinsiyet + doğum yeri + belge türü ister. Doğum tarihi
    bilinmiyorsa işaretlenebilir; diğer alanlar boş bırakılamaz."""

    def __init__(self, veri=None, parent=None):
        super().__init__(parent)
        veri = veri or {}
        self.setWindowTitle("Yabancı Misafir Bilgileri (KBS)")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        uyari = QLabel("Bu bilgiler KBS bildirimi (1774 sayılı Kanun) için zorunludur.")
        uyari.setWordWrap(True)
        uyari.setStyleSheet("color: #b9770e; font-style: italic;")
        layout.addWidget(uyari)

        form = QFormLayout()
        self.uyruk = QLineEdit(veri.get("uyruk") or "")
        self.uyruk.setPlaceholderText("örn. Alman, Fransız, Suriyeli")
        form.addRow("Uyruk:", self.uyruk)

        self.dogum_tarihi = QDateEdit(QDate.currentDate())
        self.dogum_tarihi.setCalendarPopup(True)
        self.dogum_tarihi.setDisplayFormat("dd.MM.yyyy")
        self.dogum_tarihi.setMaximumDate(QDate.currentDate())
        self.dogum_bilinmiyor = QCheckBox("Bilinmiyor")
        dogum_yer_widget = QWidget()
        dogum_yer_lay = QHBoxLayout(dogum_yer_widget)
        dogum_yer_lay.setContentsMargins(0, 0, 0, 0)
        dogum_yer_lay.addWidget(self.dogum_tarihi, 1)
        dogum_yer_lay.addWidget(self.dogum_bilinmiyor)
        form.addRow("Doğum Tarihi:", dogum_yer_widget)

        self.cinsiyet = QComboBox()
        self.cinsiyet.addItems(["Erkek", "Kadın"])
        self.cinsiyet.setCurrentText(veri.get("cinsiyet") or "Erkek")
        form.addRow("Cinsiyet:", self.cinsiyet)

        self.dogum_yeri = QLineEdit(veri.get("dogum_yeri") or "")
        self.dogum_yeri.setPlaceholderText("örn. Hamburg")
        form.addRow("Doğum Yeri:", self.dogum_yeri)

        self.belge_turu = QComboBox()
        self.belge_turu.setEditable(True)
        self.belge_turu.addItems(["Pasaport", "Yabancı Kimlik No", "İkamet İzni", "Diğer"])
        mevcut_belge = (veri.get("belge_turu") or "").strip()
        if mevcut_belge and self.belge_turu.findText(mevcut_belge) == -1:
            self.belge_turu.addItem(mevcut_belge)
        self.belge_turu.setCurrentText(mevcut_belge or "Pasaport")
        form.addRow("Belge Türü:", self.belge_turu)

        # Kayıtlı doğum tarihi varsa alanı doldur, 'bilinmiyor' bayrağını yükle
        kayit_tarih = (veri.get("dogum_tarihi") or "").strip()
        if kayit_tarih and kayit_tarih != "bilinmiyor":
            tarih = QDate.fromString(kayit_tarih, "yyyy-MM-dd")
            if tarih.isValid():
                self.dogum_tarihi.setDate(tarih)
        self.dogum_bilinmiyor.setChecked(kayit_tarih == "bilinmiyor")

        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Save).setText("Tamam")
        btns.accepted.connect(self._kaydet)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _kaydet(self):
        if not self.uyruk.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Uyruk bilgisi zorunludur.")
            return
        if not self.dogum_bilinmiyor.isChecked() and self.dogum_tarihi.date() > QDate.currentDate():
            QMessageBox.warning(self, "Doğum Tarihi", "Doğum tarihi gelecekte olamaz.")
            return
        if not self.dogum_yeri.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Doğum yeri zorunludur.")
            return
        self.accept()

    def degerler(self):
        return {
            "uyruk": self.uyruk.text().strip(),
            "dogum_tarihi": ("bilinmiyor" if self.dogum_bilinmiyor.isChecked()
                             else self.dogum_tarihi.date().toString("yyyy-MM-dd")),
            "cinsiyet": self.cinsiyet.currentText(),
            "dogum_yeri": self.dogum_yeri.text().strip(),
            "belge_turu": self.belge_turu.currentText().strip() or "Diğer",
        }


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
        self.setMinimumSize(1000, 600)
        self.resize(1120, 640)
        self._arayuzu_kur()

    # ---------------- yardımcı görünümler ----------------
    def _durum_bilgisi(self):
        """Durum metni + rozet rengini döndürür."""
        r, odalar = self.rez, self.odalar
        if r["iptal"]:
            return "İptal Edildi", "#7f8c8d"
        if odalar and all(o["checkin_yapildi"] and not o["cikis_tarihi"] for o in odalar):
            return "✓ Tüm odalar içeride", "#27ae60"
        if any(o["checkin_yapildi"] for o in odalar):
            return "Kısmen check-in", "#b9770e"
        if odalar and all(_ro_durum_metni(o, r["iptal"]) == "⚠ Gelmedi (No-Show)" for o in odalar):
            return "⚠ GELMEDİ (No-Show)", "#c0392b"
        return "Bekleniyor", "#2471a3"

    def _arayuzu_kur(self):
        r = self.rez
        kok = QVBoxLayout(self)
        kok.setContentsMargins(12, 10, 12, 10)
        kok.setSpacing(8)

        # ---- ÜST BİLGİ: tek sıra kompakt başlık ----
        durum_metni, durum_rengi = self._durum_bilgisi()
        alinma_tarihi = (r["olusturma_tarihi"] or "").split(".")[0]
        alan_kullanici = r["olusturan_kullanici"] or "Bilinmiyor (eski kayıt)"
        oda_ozeti = " + ".join(f"{o['kat_adi']} - Oda {o['oda_no']}" for o in self.odalar) or "-"
        giris = min((o["giris_tarihi"] for o in self.odalar), default="-")
        cikis = max(
            (o["cikis_tarihi"] or repository.cikis_tarihi_hesapla(o["giris_tarihi"], o["gece_sayisi"])
             for o in self.odalar), default="-"
        )

        ust = QHBoxLayout()
        ust.setSpacing(8)
        ust.addWidget(QLabel(f"<b>{r['ad_soyad']}</b>"))
        ust.addWidget(_rozet(durum_metni, durum_rengi))
        ust.addSpacing(6)
        ust.addWidget(QLabel(f"🛏 {oda_ozeti}"))
        ust.addWidget(QLabel(f"🗓 {giris} → {cikis} · {sum(o['gece_sayisi'] or 0 for o in self.odalar)} gece"))
        ust.addStretch(1)
        ust.addWidget(QLabel(f"<span style='color:#777;'>Alınma: {alinma_tarihi} · {alan_kullanici}</span>"))
        kok.addLayout(ust)

        if r["iptal"]:
            uyari = QLabel("⚠ Bu rezervasyon iptal edildi. Oda satırları düzenlenemez; "
                           "iptali geri almak için 'Rezervasyon Yönetimi' ekranını kullan.")
            uyari.setWordWrap(True)
            uyari.setStyleSheet("color: #922b21; background-color: #f8d0d0; padding: 5px 8px; border-radius: 5px;")
            kok.addWidget(uyari)

        # ---- ANA BÖLÜM: sol misafir formu | sağ odalar + misafirler ----
        split = QSplitter(Qt.Horizontal)
        split.setHandleWidth(6)

        # --- SOL: misafir bilgileri (sabit genişlik) ---
        sol = QWidget()
        sol.setMinimumWidth(280)
        sol.setMaximumWidth(360)
        sol_lay = QVBoxLayout(sol)
        sol_lay.setContentsMargins(0, 0, 0, 0)
        sol_lay.setSpacing(8)

        form_kutu = QGroupBox("Misafir Bilgileri (düzenlenebilir)")
        form = QFormLayout()
        form.setContentsMargins(8, 14, 8, 8)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(6)
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
        self.notlar.setMaximumHeight(64)
        form.addRow("Notlar:", self.notlar)
        form_kutu.setLayout(form)
        sol_lay.addWidget(form_kutu)
        sol_lay.addStretch(1)
        split.addWidget(sol)

        # --- SAĞ: odalar tablosu + odada kalan misafirler ---
        sag = QWidget()
        sag_lay = QVBoxLayout(sag)
        sag_lay.setContentsMargins(0, 0, 0, 0)
        sag_lay.setSpacing(8)

        oda_kutu = QGroupBox("Odalar")
        oda_lay = QVBoxLayout()
        oda_lay.setContentsMargins(8, 14, 8, 8)
        oda_lay.setSpacing(6)

        tablo = QTableWidget()
        tablo.setColumnCount(8)
        tablo.setHorizontalHeaderLabels([
            "Oda", "Giriş", "Gece", "Çıkış", "Kişi", "Fiyat Tipi", "Gecelik", "Durum"
        ])
        hh = tablo.horizontalHeader()
        for k in range(7):
            hh.setSectionResizeMode(k, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(7, QHeaderView.Stretch)
        tablo.verticalHeader().setVisible(False)
        tablo.verticalHeader().setDefaultSectionSize(34)
        tablo.setEditTriggers(QTableWidget.NoEditTriggers)
        tablo.setSelectionBehavior(QTableWidget.SelectRows)
        tablo.setSelectionMode(QTableWidget.SingleSelection)
        tablo.setRowCount(len(self.odalar))
        self.odalar_tablo = tablo
        self.oda_satirlari = []

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
            self.oda_satirlari.append(o)

        oda_lay.addWidget(tablo, stretch=1)

        self.secim_etiketi = QLabel("Bir odayı seç → işlemi alttaki butonlarla uygula.")
        self.secim_etiketi.setStyleSheet("color: #777; font-style: italic; font-size: 10px;")
        oda_lay.addWidget(self.secim_etiketi)

        islem_satir = QHBoxLayout()
        islem_satir.setSpacing(6)
        islem_satir.addStretch(1)

        self.oda_kisisel_btn = QPushButton("👥 Kişiler / Check-in")
        self.oda_kisisel_btn.clicked.connect(self._oda_kisisel_tikla)
        self.oda_gece_artir_btn = QPushButton("🛏 +1 Gece")
        self.oda_gece_artir_btn.setToolTip("Seçili odanın gece sayısını bir gün uzatır (çakışırsa öneri çıkar)")
        self.oda_gece_artir_btn.clicked.connect(lambda: self._oda_gece_degistir(1))
        self.oda_gece_azalt_btn = QPushButton("🛏 −1 Gece")
        self.oda_gece_azalt_btn.setToolTip("Seçili odanın gece sayısını bir gün kısaltır")
        self.oda_gece_azalt_btn.clicked.connect(lambda: self._oda_gece_degistir(-1))
        self.oda_tarih_btn = QPushButton("🗓 Tarih / Gece")
        self.oda_tarih_btn.clicked.connect(self._oda_tarih_tikla)
        self.oda_degistir_btn = QPushButton("🔁 Oda Değiştir")
        self.oda_degistir_btn.clicked.connect(self._oda_degistir_tikla)
        self.oda_cikis_btn = QPushButton("🚪 Çıkış Yap")
        self.oda_cikis_btn.setObjectName("birincil")
        self.oda_cikis_btn.clicked.connect(self._oda_cikis_tikla)

        islem_satir.addWidget(self.oda_kisisel_btn)
        islem_satir.addWidget(self.oda_tarih_btn)
        islem_satir.addWidget(self.oda_gece_artir_btn)
        islem_satir.addWidget(self.oda_gece_azalt_btn)
        islem_satir.addWidget(self.oda_degistir_btn)
        islem_satir.addWidget(self.oda_cikis_btn)
        oda_lay.addLayout(islem_satir)

        oda_kutu.setLayout(oda_lay)
        sag_lay.addWidget(oda_kutu, stretch=3)

        tablo.itemSelectionChanged.connect(self._oda_secim_degisti)
        tablo.selectRow(0) if self.odalar else self._oda_secim_degisti()

        # ---- ODADA KALAN MİSAFİRLER (check-in + yabancı tespiti) ----
        misafir_kutu = QGroupBox("Odada Kalan Misafirler")
        misafir_lay = QVBoxLayout()
        misafir_lay.setContentsMargins(8, 14, 8, 8)
        misafir_lay.setSpacing(4)
        mt = QTableWidget()
        mt.setColumnCount(5)
        mt.setHorizontalHeaderLabels(["Oda", "Ad Soyad", "Belge No", "Yerli/Yabancı", "Yabancı Bilgisi"])
        mt.setEditTriggers(QTableWidget.NoEditTriggers)
        mt.verticalHeader().setVisible(False)
        mt.verticalHeader().setDefaultSectionSize(24)
        mt_hh = mt.horizontalHeader()
        for k in range(5):
            mt_hh.setSectionResizeMode(k, QHeaderView.ResizeToContents)
        mt.setRowCount(0)
        for o in self.odalar:
            misafirler = repository.odasi_misafirler_listele(o["id"])
            oda_etiketi = f"{o['kat_adi']} - Oda {o['oda_no']}"
            if not misafirler:
                satir = mt.rowCount()
                mt.insertRow(satir)
                mt.setSpan(satir, 0, 1, 5)
                bos = QTableWidgetItem("— check-in yapılmadı / kişi kaydı yok —")
                mt.setItem(satir, 0, bos)
                continue
            for j, m in enumerate(misafirler):
                yabanci_mi = misafir_tipi(m["tc_no"], m) == "yabanci"
                satir = mt.rowCount()
                mt.insertRow(satir)
                eksikler = [etiket for alan, etiket in YABANCI_ALANLAR
                            if not (_satir_getir(m, alan) or "").strip()] if yabanci_mi else []
                yabanci_bilgi = ("" if not eksikler else f"⚠ eksik: {', '.join(eksikler)}") if yabanci_mi else "-"
                degerler = [
                    oda_etiketi if j == 0 else "",
                    m["ad_soyad"] or "",
                    m["tc_no"] or "-",
                    "🌍 Yabancı" if yabanci_mi else "Yerli",
                    yabanci_bilgi,
                ]
                for col, val in enumerate(degerler):
                    mt.setItem(satir, col, QTableWidgetItem(val))
        misafir_lay.addWidget(mt)
        misafir_kutu.setLayout(misafir_lay)
        sag_lay.addWidget(misafir_kutu, stretch=2)

        split.addWidget(sag)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 7)
        split.setSizes([300, 780])
        kok.addWidget(split, stretch=1)

        # ---- ALTAKSİYON ÇUBUĞU: özet + ana aksiyonlar (her zaman görünür) ----
        alt = QHBoxLayout()
        alt.setSpacing(8)
        toplam = repository.rezervasyon_toplami(self.rez_id)
        toplam_oda_gece = sum((o["gece_sayisi"] or 0) for o in self.odalar)
        alt.addWidget(QLabel(
            f"<b>Toplam tutar: {toplam:,}₺</b> · {len(self.odalar)} oda · {toplam_oda_gece} gece"
        ))
        alt.addStretch(1)

        iptal_btn = QPushButton("🚫 Rezervasyonu İptal Et")
        iptal_btn.setObjectName("ikincil")
        iptal_btn.setStyleSheet("color: #c0392b;")
        iptal_btn.setToolTip("Tüm odaları iptal eder (geri alınabilir).")
        iptal_btn.setEnabled(not r["iptal"])
        iptal_btn.clicked.connect(self.iptal_et)
        alt.addWidget(iptal_btn)

        kapat_btn = QPushButton("Kapat")
        kapat_btn.setObjectName("ikincil")
        kapat_btn.clicked.connect(self.reject)
        alt.addWidget(kapat_btn)

        kaydet_btn = QPushButton("💾 Bilgileri Kaydet")
        kaydet_btn.setObjectName("birincil")
        kaydet_btn.clicked.connect(self.kaydet)
        alt.addWidget(kaydet_btn)
        kok.addLayout(alt)

    # ---------------- oda seçimi + aksiyon çubuğu ----------------
    def _secili_oda(self):
        satirlar = self.odalar_tablo.selectionModel().selectedRows()
        if not satirlar:
            return None
        idx = satirlar[0].row()
        if 0 <= idx < len(self.oda_satirlari):
            return self.oda_satirlari[idx]
        return None

    def _oda_secim_degisti(self):
        o = self._secili_oda()
        iptal = bool(self.rez["iptal"])
        if o is None:
            self.secim_etiketi.setText("Bir odayı seç → işlemi alttaki butonlarla uygula.")
            self.secim_etiketi.setStyleSheet("color: #777; font-style: italic; font-size: 10px;")
            self.oda_kisisel_btn.setEnabled(False)
            self.oda_tarih_btn.setEnabled(False)
            self.oda_degistir_btn.setEnabled(False)
            self.oda_cikis_btn.setEnabled(False)
            return
        if o["checkin_yapildi"]:
            self.oda_kisisel_btn.setText("👥 Misafirleri Düzenle")
        else:
            self.oda_kisisel_btn.setText("👥 Kişiler / Check-in")
        canli_mi = not iptal
        self.oda_kisisel_btn.setEnabled(canli_mi)
        self.oda_tarih_btn.setEnabled(canli_mi)
        self.oda_degistir_btn.setEnabled(canli_mi)
        self.oda_gece_artir_btn.setEnabled(canli_mi)
        self.oda_gece_azalt_btn.setEnabled(canli_mi and (o["gece_sayisi"] or 1) > 1)
        self.oda_cikis_btn.setEnabled(
            canli_mi and bool(o["checkin_yapildi"]) and not o["cikis_tarihi"])
        self.secim_etiketi.setText(
            f"Seçili: <b>{o['kat_adi']} - Oda {o['oda_no']}</b> · {_ro_durum_metni(o, iptal)}")
        self.secim_etiketi.setStyleSheet("color: #777; font-size: 10px;")

    def _oda_kisisel_tikla(self):
        o = self._secili_oda()
        if o is not None:
            self._odada_kisiler(o["id"])

    def _oda_tarih_tikla(self):
        o = self._secili_oda()
        if o is not None:
            self._odada_tarih(o)

    def _oda_degistir_tikla(self):
        o = self._secili_oda()
        if o is not None:
            self._odada_oda_degistir(o)

    def _oda_cikis_tikla(self):
        o = self._secili_oda()
        if o is not None:
            self._odada_cikis(o)

    def _oda_gece_degistir(self, delta):
        o = self._secili_oda()
        if o is None:
            return
        yeni_gece = (o["gece_sayisi"] or 1) + delta
        if yeni_gece < 1:
            QMessageBox.warning(self, "Gece Sayısı", "Gece sayısı en az 1 olabilir.")
            return
        if delta > 0:
            # Sadece UZATMA: hemen ertesi günde başka bir rezervasyon varsa genel
            # "gece azaltma önerisi" akışı anlamsız bir diyalog gösterirdi (önerilen
            # sayı zaten mevcut gece sayısına eşit olurdu, çünkü hiç büyüme yeri
            # yok). Bu yüzden burada net ve doğrudan bir "eklenemiyor" uyarısı
            # gösterip akışı burada durduruyoruz.
            cakisma = repository.musaitlik_kontrol(
                o["oda_id"], o["giris_tarihi"], yeni_gece, haric_ro_id=o["id"])
            if cakisma:
                isimler = ", ".join(c["ad_soyad"] for c in cakisma[:3])
                QMessageBox.warning(
                    self, "Gece Eklenemiyor",
                    f"Bu odada ertesi gün {isimler} rezervasyonu var; daha fazla gece eklenemiyor."
                )
                return
        if _tarih_degistir_akisi(self, o, o["giris_tarihi"], yeni_gece):
            self.kaydedildi = True
            # Pencereyi KAPATMADAN içeriği yenile: kullanıcı arka arkaya birden
            # fazla kez +1/-1 Gece'ye basabilsin diye (öncesinde her tıklamada
            # pencere kapanıp yeniden açmak gerekiyordu).
            self._yenile(secili_oda_id=o["id"])

    def _yenile(self, secili_oda_id=None):
        """Rezervasyon/oda verilerini yeniden okuyup arayüzü aynı pencerede
        yeniden kurar (kapatmadan). secili_oda_id verilirse yeniden kurulduktan
        sonra o oda satırı tekrar seçili hale getirilir."""
        self.rez = repository.rezervasyon_getir(self.rez_id)
        self.odalar = repository.rezervasyon_odalar_listele(self.rez_id)
        eski_layout = self.layout()
        if eski_layout is not None:
            QWidget().setLayout(eski_layout)
        self._arayuzu_kur()
        if secili_oda_id is not None:
            for i, satir in enumerate(self.oda_satirlari):
                if satir["id"] == secili_oda_id:
                    self.odalar_tablo.selectRow(i)
                    break

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
        bugun = date.today().isoformat()
        borc = repository.odasi_odenmemis_tutar(ro_row["id"], kesim_tarihi=bugun)
        borc_metni = (f"\n\n⚠ Ödenmemiş borç: {borc:,}₺" if borc else "\n\nÖdenmemiş borcu yok.")
        cevap = QMessageBox.question(
            self, "Çıkış İşlemi",
            f"{ro_row['kat_adi']} - Oda {ro_row['oda_no']}'daki misafir çıkış yaptı mı? "
            "İşlem sonrası oda 'temizlikte' durumuna alınır." + borc_metni,
            QMessageBox.Yes | QMessageBox.No
        )
        if cevap != QMessageBox.Yes:
            return
        try:
            dusen_odenmis = repository.odasi_cikis_yap(ro_row["id"])
        except ValueError as e:
            QMessageBox.warning(self, "Çıkış Yapılamadı", str(e))
            return
        if dusen_odenmis:
            QMessageBox.information(
                self, "Önceden Ödenmiş Geceler",
                "Şu geceler için daha önce ödeme alınmıştı ama misafir planlanandan "
                "erken çıktı (ödendi bilgisi korundu, tutar iade edilmedi):\n"
                + ", ".join(dusen_odenmis),
            )
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
        self.kayit_limiti = repository.oda_liman(self.kapasite)
        baslik = "Check-in Yap" if not self.ro["checkin_yapildi"] else "Misafirleri Düzenle"
        self.setWindowTitle(f"{baslik} - {self.ro['kat_adi']} Oda {self.ro['oda_no']}")
        self.setMinimumSize(720, 480)
        self.resize(780, 520)
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
        self.misafir_tablo.setColumnCount(7)
        self.misafir_tablo.setHorizontalHeaderLabels(
            ["Ad Soyad", "TC / Belge No", "Fiyat Tipi", "Gecelik (TL)",
             "Yerli/Yabancı", "Yabancı Bilg.", ""])
        tablo_hh = self.misafir_tablo.horizontalHeader()
        tablo_hh.setSectionResizeMode(0, QHeaderView.Stretch)
        tablo_hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        tablo_hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        tablo_hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.misafir_tablo.verticalHeader().setVisible(False)
        self.misafir_tablo.verticalHeader().setDefaultSectionSize(34)
        self.misafir_tablo.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
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
                yabanci_mi = misafir_tipi(m["tc_no"], m) == "yabanci"
                self._kisi_ekle(
                    ad_soyad=m["ad_soyad"] or "",
                    tc_no=m["tc_no"] or "",
                    fiyat_tipi=m["fiyat_tipi"] or r["fiyat_tipi"],
                    gecelik_ucret=m["gecelik_ucret"] or r["gecelik_ucret"],
                    tanitim_tipi="yabanci" if yabanci_mi else None,
                    yabanci_bilgi={
                        "uyruk": _satir_getir(m, "uyruk"),
                        "dogum_tarihi": _satir_getir(m, "dogum_tarihi"),
                        "cinsiyet": _satir_getir(m, "cinsiyet"),
                        "dogum_yeri": _satir_getir(m, "dogum_yeri"),
                        "belge_turu": _satir_getir(m, "belge_turu"),
                    },
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
        btns.button(QDialogButtonBox.Save).setObjectName("birincil")
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

    def _kisi_ekle(self, ad_soyad="", tc_no="", fiyat_tipi=None, gecelik_ucret=None,
                   tanitim_tipi=None, yabanci_bilgi=None):
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

        # Yerli / Yabancı seçimi + yabancı bilgileri (KBS)
        tck_combo = QComboBox()
        tck_combo.addItems(["Yerli", "Yabancı"])
        if tanitim_tipi == "yabanci":
            tck_combo.setCurrentText("Yabancı")

        yabanci_data = dict(yabanci_bilgi or {})

        def _tanitim_degisti():
            yabanci_mi = tck_combo.currentText() == "Yabancı"
            tc_edit.setPlaceholderText(
                "Belge / Pasaport No (zorunlu)" if yabanci_mi else "TC No - 11 hane (zorunlu)")
            tc_edit.setMaxLength(32 if yabanci_mi else 11)
            bilgi_btn.setEnabled(yabanci_mi)
            _bilgi_butonu_durumu()

        def _bilgi_butonu_durumu():
            eksikler = [etiket for alan, etiket in YABANCI_ALANLAR
                        if not (yabanci_data.get(alan) or "").strip()]
            bilgi_btn.setText("Yabancı Bilg… ✓" if not eksikler else f"Yabancı Bilg… ({len(eksikler)} eksik)")

        bilgi_btn = QPushButton("Yabancı Bilg…")
        bilgi_btn.setEnabled(tck_combo.currentText() == "Yabancı")
        bilgi_btn.clicked.connect(lambda: _yabanci_duzenle())

        def _yabanci_duzenle():
            dialog = YabanciBilgiDialog(yabanci_data, self)
            if dialog.exec() != QDialog.Accepted:
                return
            yabanci_data.clear()
            yabanci_data.update(dialog.degerler())
            _bilgi_butonu_durumu()

        tck_combo.currentTextChanged.connect(lambda _: _tanitim_degisti())

        sil_btn = QPushButton("Sil")
        sil_btn.clicked.connect(lambda: self._kisi_sil(sil_btn))

        self.misafir_tablo.setCellWidget(row, 0, ad_edit)
        self.misafir_tablo.setCellWidget(row, 1, tc_edit)
        self.misafir_tablo.setCellWidget(row, 2, tip_combo)
        self.misafir_tablo.setCellWidget(row, 3, ucret_spin)
        self.misafir_tablo.setCellWidget(row, 4, tck_combo)
        self.misafir_tablo.setCellWidget(row, 5, bilgi_btn)
        self.misafir_tablo.setCellWidget(row, 6, sil_btn)

        self.misafir_satirlari.append(
            (ad_edit, tc_edit, tip_combo, ucret_spin, sil_btn, tck_combo, bilgi_btn, yabanci_data))
        _tanitim_degisti()
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
        for i, satir in enumerate(self.misafir_satirlari, start=1):
            ad = satir[0].text().strip()
            belge_no = satir[1].text().strip()
            tip = satir[2].currentText()
            ucret = satir[3].value()
            yabanci_mi = satir[5].currentText() == "Yabancı"
            yabanci_data = satir[7]
            if not ad:
                QMessageBox.warning(self, "Eksik Bilgi", f"{i}. kişinin Ad Soyad bilgisi boş bırakılamaz.")
                return
            if not belge_no:
                QMessageBox.warning(self, "Eksik Bilgi",
                                    f"{i}. kişinin {'Belge No' if yabanci_mi else 'TC No'} bilgisi boş bırakılamaz.")
                return
            if tip == "Ozel" and ucret <= 0:
                QMessageBox.warning(self, "Geçersiz Özel Fiyat", f"{i}. kişi için özel fiyat girilmelidir.")
                return

            if yabanci_mi:
                eksikler = [etiket for alan, etiket in YABANCI_ALANLAR
                            if not (yabanci_data.get(alan) or "").strip()]
                if eksikler:
                    QMessageBox.warning(
                        self, "Yabancı Bilgisi Eksik",
                        f"{i}. kişinin şu bilgileri eksik: {', '.join(eksikler)}. "
                        "Önce 'Yabancı Bilg…' butonuyla doldurun.")
                    return
                misafir_listesi.append({
                    "ad_soyad": ad, "tc_no": belge_no, "fiyat_tipi": tip, "gecelik_ucret": ucret,
                    "uyruk": yabanci_data.get("uyruk") or "",
                    "dogum_tarihi": yabanci_data.get("dogum_tarihi") or "",
                    "cinsiyet": yabanci_data.get("cinsiyet") or "",
                    "dogum_yeri": yabanci_data.get("dogum_yeri") or "",
                    "belge_turu": yabanci_data.get("belge_turu") or "",
                })
            else:
                if not tc_dogrula(belge_no):
                    QMessageBox.warning(
                        self, "Geçersiz TC No",
                        f"{i}. kişinin TC No'su geçerli değil (11 haneli olmalı ve "
                        "T.C. Kimlik No sağlama algoritmasına uymalı).")
                    return
                misafir_listesi.append((ad, belge_no, tip, ucret))

        repository.odasi_misafirleri_kaydet_ve_checkin(
            self.ro_id, misafir_listesi, ekstra_yatak=self.ekstra_yatak)

        self.kaydedildi = True
        self.accept()