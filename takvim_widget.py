# -*- coding: utf-8 -*-
"""
Oda x Gün doluluk ızgarası. İki modda kullanılır:
- interactive=True: Yeni Rezervasyon ekranında oda/tarih seçmek için (tıklanabilir)
- interactive=False: Ayrı "Takvim Görünümü" penceresinde salt-okunur genel bakış için
"""

from datetime import datetime, timedelta, date

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QSpinBox, QHeaderView, QDateEdit, QAbstractItemView
)
from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtGui import QColor

import repository
import tema
from detay_dialog import RezervasyonDetayDialog

AY_ADLARI = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
             "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
GUN_ADLARI_KISA = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]

RENK_BOS = QColor("#e8f7e8")
RENK_DOLU = QColor("#f7c5c5")
RENK_AKTIF_SECIM = QColor("#ffe08a")
RENK_KILITLI_SECIM = QColor("#a8d4ff")
RENK_YETERSIZ = QColor("#d9d9d9")
RENK_GECMIS = QColor("#ececec")
RENK_TEMIZLIKTE = QColor("#fdebd0")
RENK_ARIZA = QColor("#cccccc")


def qdate_to_str(qd: QDate) -> str:
    return qd.toString("yyyy-MM-dd")


class TakvimGridWidget(QWidget):
    # interaktif modda aktif seçim degistiginde bilgi vermek icin
    secim_degisti = Signal()

    def __init__(self, interactive=False, gun_sayisi=14, kompakt=False, parent=None):
        super().__init__(parent)
        self.interactive = interactive
        self.gun_sayisi = gun_sayisi
        self.kompakt = kompakt
        self.baslangic = QDate.currentDate()
        self.odalar = []
        self.doluluk = {}
        self.SABIT_KOLON = 3  # Kat, Oda, Tip

        self.aktif_oda_id = None
        self.aktif_baslangic_str = None
        self.kilitli_secimler = []  # [{oda_id, oda_no, kat_adi, giris, gece, kisi, fiyat_tipi}]
        self.min_kapasite_filtre = 0  # 0 = filtre yok; >0 ise bu kisi sayisini alamayan odalar sonulanir

        self._arayuzu_kur()
        self.yenile()

    def _arayuzu_kur(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        ust = QHBoxLayout()
        geri_btn = QPushButton("◀ Önceki")
        geri_btn.clicked.connect(self._onceki)
        ileri_btn = QPushButton("Sonraki ▶")
        ileri_btn.clicked.connect(self._sonraki)
        bugun_btn = QPushButton("Bugün")
        bugun_btn.clicked.connect(self._bugune_git)

        self.baslik_label = QLabel("")
        self.baslik_label.setStyleSheet("font-weight: bold; font-size: 13px;")

        ust.addWidget(geri_btn)
        ust.addWidget(ileri_btn)
        ust.addWidget(bugun_btn)
        ust.addSpacing(20)
        ust.addWidget(self.baslik_label)
        ust.addStretch()

        if self.interactive:
            ust.addWidget(QLabel("Gece Sayısı (seçim için):"))
            self.gece_spin = QSpinBox()
            self.gece_spin.setRange(1, 60)
            self.gece_spin.setValue(1)
            self.gece_spin.valueChanged.connect(self._aktif_secimi_yenile)
            ust.addWidget(self.gece_spin)

        layout.addLayout(ust)

        self.tablo = QTableWidget()
        self.tablo.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tablo.setSelectionMode(QAbstractItemView.NoSelection)
        self.tablo.verticalHeader().setVisible(False)
        if self.kompakt:
            # Tek ekran kullanımı için sıkı görünüm: küçük satır/yazı, içten kaydırılır
            self.tablo.verticalHeader().setDefaultSectionSize(24)
            self.tablo.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
            self.tablo.horizontalHeader().setMinimumSectionSize(40)
            self.tablo.setMinimumHeight(230)
            self.tablo.setStyleSheet(
                "QTableWidget { font-size: 10pt; } "
                "QHeaderView::section { font-size: 9pt; padding: 2px; }"
            )
        else:
            self.tablo.verticalHeader().setDefaultSectionSize(34)
            self.tablo.horizontalHeader().setMinimumSectionSize(50)
            self.tablo.setMinimumHeight(440)
            self.tablo.setStyleSheet(
                "QTableWidget { font-size: 11pt; } "
                "QHeaderView::section { font-size: 10pt; padding: 4px; }"
            )
        if self.interactive:
            self.tablo.cellClicked.connect(self._hucre_tiklandi)
        self.tablo.cellDoubleClicked.connect(self._hucre_cift_tiklandi)
        layout.addWidget(self.tablo, stretch=1)

        if self.interactive:
            self.durum_label = QLabel("Bir oda ve gün seçmek için boş bir hücreye tıkla.")
            self.durum_label.setStyleSheet("font-style: italic;")
            layout.addWidget(self.durum_label)

    # ---------------- navigasyon ----------------
    def _onceki(self):
        self.baslangic = self.baslangic.addDays(-self.gun_sayisi)
        self.yenile()

    def _sonraki(self):
        self.baslangic = self.baslangic.addDays(self.gun_sayisi)
        self.yenile()

    def _bugune_git(self):
        self.baslangic = QDate.currentDate()
        self.yenile()

    def baslangici_ayarla(self, qdate):
        self.baslangic = qdate
        self.yenile()

    def set_min_kapasite_filtre(self, deger):
        """0 verilirse filtre kapanir. >0 verilirse, o kisi sayisini
        ALAMAYACAK bos odalar tabloda soluk/tiklanamaz gosterilir."""
        self.min_kapasite_filtre = deger
        self.yenile()

    # ---------------- veri yenileme ----------------
    def yenile(self):
        self.odalar = repository.oda_listesi()
        baslangic_str = qdate_to_str(self.baslangic)
        self.doluluk = repository.doluluk_haritasi(baslangic_str, self.gun_sayisi)

        bitis = self.baslangic.addDays(self.gun_sayisi - 1)
        if self.baslangic.month() == bitis.month():
            self.baslik_label.setText(f"{AY_ADLARI[self.baslangic.month()]} {self.baslangic.year()}")
        else:
            self.baslik_label.setText(
                f"{AY_ADLARI[self.baslangic.month()]} - {AY_ADLARI[bitis.month()]} {bitis.year()}"
            )

        self.tablo.setColumnCount(self.SABIT_KOLON + self.gun_sayisi)
        basliklar = ["Kat", "Oda", "Tip"]
        for i in range(self.gun_sayisi):
            gun = self.baslangic.addDays(i)
            gun_index = gun.dayOfWeek() - 1  # Pazartesi=0
            basliklar.append(f"{gun.day()}\n{GUN_ADLARI_KISA[gun_index]}")
        self.tablo.setHorizontalHeaderLabels(basliklar)
        self.tablo.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tablo.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tablo.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        for c in range(self.SABIT_KOLON, self.SABIT_KOLON + self.gun_sayisi):
            self.tablo.horizontalHeader().setSectionResizeMode(c, QHeaderView.Stretch)

        self.tablo.setRowCount(len(self.odalar))
        for row, oda in enumerate(self.odalar):
            self.tablo.setItem(row, 0, QTableWidgetItem(oda["kat_adi"] or ""))
            self.tablo.setItem(row, 1, QTableWidgetItem(str(oda["oda_no"])))
            self.tablo.setItem(row, 2, QTableWidgetItem(oda["oda_tipi"] or ""))
            for col in range(self.gun_sayisi):
                gun = self.baslangic.addDays(col)
                gun_str = qdate_to_str(gun)
                self._hucreyi_ciz(row, col + self.SABIT_KOLON, oda, gun_str)

        self.tablo.resizeRowsToContents()

    def _hucre_blok_nedeni(self, oda, gun_str):
        """Serbest secilebilir olmayan hücrelerin nedeni (dolu/kilitli/aktif seçim
        haric). None dönerse hücre secilebilir."""
        gun = datetime.strptime(gun_str, "%Y-%m-%d").date()
        bugun = date.today()
        if gun < bugun:
            return "gecmis"
        durum = oda.get("aktif_durum") or "temiz"
        if durum == "temizlikte" and gun == bugun:
            return "temizlikte"
        if durum == "arizali":
            bitis = oda.get("ariza_bitis")
            if bitis and gun < datetime.strptime(bitis, "%Y-%m-%d").date():
                return "arizali"
        return None

    def _hucreyi_ciz(self, row, col, oda, gun_str):
        oda_id = oda["id"]
        kayit = self.doluluk.get((oda_id, gun_str))
        kilitli = self._kilitli_mi(oda_id, gun_str)
        aktif = (self.interactive and self.aktif_oda_id == oda_id and
                 self._aktif_araligina_dahil_mi(gun_str))
        yetersiz = (self.min_kapasite_filtre > 0 and (oda["kapasite"] or 1) < self.min_kapasite_filtre
                    and kayit is None and not kilitli)
        blok = self._hucre_blok_nedeni(oda, gun_str) if (kayit is None and not kilitli and not aktif) else None

        if kayit is not None:
            isim = kayit["ad_soyad"]
            kisa_isim = isim.split(" ")[0] if isim else "Dolu"
            item = QTableWidgetItem(kisa_isim)
            tema.renklendir(item, RENK_DOLU)
            item.setToolTip(f"{isim}\nFiyat: {kayit['fiyat_tipi']}"
                             + (f"\nReferans: {kayit['referans']}" if kayit["referans"] else ""))
        elif kilitli:
            item = QTableWidgetItem("SEÇİLDİ")
            tema.renklendir(item, RENK_KILITLI_SECIM)
        elif aktif:
            item = QTableWidgetItem("●")
            tema.renklendir(item, RENK_AKTIF_SECIM)
            item.setTextAlignment(Qt.AlignCenter)
        elif yetersiz:
            item = QTableWidgetItem("✕")
            tema.renklendir(item, RENK_YETERSIZ)
            item.setTextAlignment(Qt.AlignCenter)
            item.setToolTip(
                    f"Bu odanın kapasitesi {oda['kapasite']} kişi, aradığın {self.min_kapasite_filtre} "
                    "kişiyi alamaz. Üstteki 'Filtre yok' (0) seçilirse bu oda seçilebilir."
                )
        elif blok == "gecmis":
            item = QTableWidgetItem("−")
            tema.renklendir(item, RENK_GECMIS)
            item.setTextAlignment(Qt.AlignCenter)
            item.setToolTip("Geçmiş tarihe rezervasyon alınamaz.")
        elif blok == "temizlikte":
            item = QTableWidgetItem("Temizlikte")
            tema.renklendir(item, RENK_TEMIZLIKTE)
            item.setTextAlignment(Qt.AlignCenter)
            item.setToolTip("Oda şu an temizlikte; temiz yapılmadan verilmez.")
        elif blok == "arizali":
            item = QTableWidgetItem("ARIZA")
            tema.renklendir(item, RENK_ARIZA)
            item.setTextAlignment(Qt.AlignCenter)
            bitis = oda.get("ariza_bitis") or ""
            item.setToolTip(f"Oda arızalı: {bitis} tarihine kadar kapalı.")
        else:
            item = QTableWidgetItem("")
            tema.renklendir(item, RENK_BOS)

        self.tablo.setItem(row, col, item)

    def _kilitli_mi(self, oda_id, gun_str):
        from datetime import datetime
        gun = datetime.strptime(gun_str, "%Y-%m-%d").date()
        for sec in self.kilitli_secimler:
            if sec["oda_id"] != oda_id:
                continue
            giris = datetime.strptime(sec["giris"], "%Y-%m-%d").date()
            if giris <= gun < giris + timedelta(days=sec["gece"]):
                return True
        return False

    def _aktif_araligina_dahil_mi(self, gun_str):
        from datetime import datetime
        if not self.aktif_baslangic_str:
            return False
        gun = datetime.strptime(gun_str, "%Y-%m-%d").date()
        baslangic = datetime.strptime(self.aktif_baslangic_str, "%Y-%m-%d").date()
        gece = self.gece_spin.value()
        return baslangic <= gun < baslangic + timedelta(days=gece)

    # ---------------- interaktif secim (Yeni Rezervasyon ekrani icin) ----------------
    def _hucre_tiklandi(self, row, col):
        if col < self.SABIT_KOLON:
            return
        oda = self.odalar[row]
        gun = self.baslangic.addDays(col - self.SABIT_KOLON)
        gun_str = qdate_to_str(gun)

        # Ayni odada, mevcut secimin devaminda ileri bir güne tiklandiysa:
        # bunu "cikis günü" olarak yorumla ve gece sayisini otomatik hesapla.
        # NOT: Cikis günü misafir sabah 11'de cikar, yeni misafir aksam 16'dan sonra
        # girer; o yüzden cikis günü olarak tikanan hücre dolu olsa bile (o gün
        # girisi olan baska rezervasyonun ilk gecesi) izin verilir — cünkü
        # aralik [giris, cikis) yari-acik; cikis günü konaklamaya dahil değildir.
        # Bu yüzden bu kontrol, dolu/kilitli engellerinden ÖNCE gelmelidir.
        if (self.aktif_oda_id == oda["id"] and self.aktif_baslangic_str
                and gun_str > self.aktif_baslangic_str):
            from datetime import datetime
            baslangic = datetime.strptime(self.aktif_baslangic_str, "%Y-%m-%d").date()
            hedef = datetime.strptime(gun_str, "%Y-%m-%d").date()
            istenen_gece = (hedef - baslangic).days

            # araya dolu bir gece giriyorsa, ona kadar kisalt
            # (hedef günün kendisi cikis günü olduğu için kontrol dışıdır)
            gercek_gece = istenen_gece
            for i in range(istenen_gece):
                kontrol_gun = (baslangic + timedelta(days=i)).isoformat()
                if ((oda["id"], kontrol_gun) in self.doluluk
                        or self._kilitli_mi(oda["id"], kontrol_gun)
                        or self._hucre_blok_nedeni(oda, kontrol_gun)):
                    gercek_gece = i
                    break

            if gercek_gece <= 0:
                self.durum_label.setText(f"⚠ Oda {oda['oda_no']} hemen sonraki gece dolu, aralık seçilemedi.")
                self.durum_label.setStyleSheet("color: #c0392b; font-style: italic;")
                return

            self.gece_spin.setValue(gercek_gece)
            if gercek_gece < istenen_gece:
                self.durum_label.setText(
                    f"⚠ Aralıkta dolu gece var, gece sayısı {gercek_gece} ile sınırlandırıldı."
                )
                self.durum_label.setStyleSheet("color: #b9770e; font-style: italic;")
            else:
                self.durum_label.setText(
                    f"Seçili: {oda['kat_adi']} - Oda {oda['oda_no']}, {self.aktif_baslangic_str} → "
                    f"{gun_str} ({gercek_gece} gece). 'Listeye Ekle'ye bas."
                )
                self.durum_label.setStyleSheet("color: #2471a3; font-style: italic;")
            self.secim_degisti.emit()
            self.yenile()
            return

        if (oda["id"], gun_str) in self.doluluk:
            kayit = self.doluluk[(oda["id"], gun_str)]
            self.durum_label.setText(
                f"⚠ Oda {oda['oda_no']} bu tarihte dolu: {kayit['ad_soyad']} kalıyor."
            )
            self.durum_label.setStyleSheet("color: #c0392b; font-style: italic;")
            return

        blok = self._hucre_blok_nedeni(oda, gun_str)
        if blok:
            if blok == "gecmis":
                msg = "Geçmiş tarihe rezervasyon alınamaz."
            elif blok == "temizlikte":
                msg = "Oda şu an temizlikte; bu gece için verilmez, önce temiz yapılmalı."
            else:
                msg = f"Oda {oda['oda_no']} arızalı: {oda.get('ariza_bitis','belirsiz')} tarihine kadar kapalı."
            self.durum_label.setText("⚠ " + msg)
            self.durum_label.setStyleSheet("color: #c0392b; font-style: italic;")
            return

        if self._kilitli_mi(oda["id"], gun_str):
            self.durum_label.setText(
                f"Oda {oda['oda_no']} bu tarihlerde zaten seçildi. 2. kişiye ayrı oda vermek "
                "istiyorsan farklı bir oda seç."
            )
            self.durum_label.setStyleSheet("color: #c0392b; font-style: italic;")
            return

        if self.min_kapasite_filtre > 0 and (oda["kapasite"] or 1) < self.min_kapasite_filtre:
            self.durum_label.setText(
                f"⚠ Oda {oda['oda_no']}'nin kapasitesi {oda['kapasite']} kişi; üstteki filtre "
                f"({self.min_kapasite_filtre} kişi) bu odayı süzdü. Filtreyi 'Filtre yok'a (0) alıp "
                "kişi sayısını elle seçebilirsin."
            )
            self.durum_label.setStyleSheet("color: #c0392b; font-style: italic;")
            return

        # yeni secim baslangici (farkli oda ya da geriye/ayni güne tiklama)
        self.aktif_oda_id = oda["id"]
        self.aktif_baslangic_str = gun_str
        self.gece_spin.blockSignals(True)
        self.gece_spin.setValue(1)
        self.gece_spin.blockSignals(False)
        self.durum_label.setText(
            f"Seçili: {oda['kat_adi']} - Oda {oda['oda_no']}, giriş {gun_str}. "
            f"Çıkış günü için aynı odada ileri bir güne tıkla, ya da 'Gece Sayısı' kutusunu kullan."
        )
        self.durum_label.setStyleSheet("color: #2471a3; font-style: italic;")
        self.secim_degisti.emit()
        self.yenile()

    def _hucre_cift_tiklandi(self, row, col):
        if col < self.SABIT_KOLON:
            return
        oda = self.odalar[row]
        gun = self.baslangic.addDays(col - self.SABIT_KOLON)
        gun_str = qdate_to_str(gun)
        kayit = self.doluluk.get((oda["id"], gun_str))
        if kayit is None:
            return
        dialog = RezervasyonDetayDialog(kayit["rez_id"], self)
        dialog.exec()
        if dialog.kaydedildi:
            self.yenile()

    def _aktif_secimi_yenile(self):
        if self.aktif_oda_id is not None:
            self.yenile()

    def aktif_secim_var_mi(self):
        return self.aktif_oda_id is not None

    def aktif_secim_bilgisi(self):
        """(oda, giris_str, gece_sayisi) döner ya da None."""
        if self.aktif_oda_id is None:
            return None
        oda = next((o for o in self.odalar if o["id"] == self.aktif_oda_id), None)
        return oda, self.aktif_baslangic_str, self.gece_spin.value()

    def aktif_secimi_kilitle(self, kisi_sayisi, fiyat_tipi, ozel_ucret=None):
        """Aktif secimi 'Secilen Odalar' listesine ekler ve aktif secimi temizler."""
        bilgi = self.aktif_secim_bilgisi()
        if not bilgi:
            return None
        oda, giris_str, gece = bilgi
        kayit = {
            "oda_id": oda["id"], "oda_no": oda["oda_no"], "kat_adi": oda["kat_adi"],
            "giris": giris_str, "gece": gece, "kisi": kisi_sayisi, "fiyat_tipi": fiyat_tipi,
            "ozel_ucret": ozel_ucret,
        }
        self.kilitli_secimler.append(kayit)
        self.aktif_oda_id = None
        self.aktif_baslangic_str = None
        self.durum_label.setText("Odaya eklendi. Başka bir oda/gün seçebilirsin.")
        self.durum_label.setStyleSheet("color: #196f3d; font-style: italic;")
        self.yenile()
        return kayit

    def secimi_iptal_et(self):
        self.aktif_oda_id = None
        self.aktif_baslangic_str = None
        self.yenile()

    def kilitli_sil(self, index):
        if 0 <= index < len(self.kilitli_secimler):
            del self.kilitli_secimler[index]
            self.yenile()

    def kilitli_listesi(self):
        return list(self.kilitli_secimler)

    def tumunu_temizle(self):
        self.kilitli_secimler = []
        self.aktif_oda_id = None
        self.aktif_baslangic_str = None
        self.yenile()
