# -*- coding: utf-8 -*-
"""
Misafirhane Kurulum Araci (A secenegi).

Tek exe: PyInstaller onefile + gomulu Misafirhane_Kurulum.exe.
Acilista kayit defterinden kurulum durumu tespit edilir ve uc islem sunulur:
  - Yükle (program yüklü degilse),  - Güncelle / Tamir Et (yüklüyse).
Secilen islem, gomulu hibrit kurulum exe'sini calistirir (dosyalar
ignoreversion ile yenilenir; kurulum/guncelleme/tamir ayni exe).

Gomulu exe admin gerektirdigi icin ShellExecuteEx 'runas' ile acilir (UAC).

Tema: Windows'un koyu/acik mod ayariyla otomatik eşleşir.
Elle zorlamak icin MISAFIRHANE_TEMA=acik|karanlik ortam degiskeni verilebilir.
"""

import ctypes
import os
import shutil
import subprocess
import sys
import threading
import winreg
from ctypes import wintypes
from tkinter import Tk, Label, Button, Frame, messagebox

ROOT = os.path.dirname(os.path.abspath(__file__))


def windows_temasi():
    """Windows koyu/acik mod ayarini okur (AppsUseLightTheme)."""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            0, winreg.KEY_READ,
        ) as k:
            deger, _ = winreg.QueryValueEx(k, "AppsUseLightTheme")
            return "karanlik" if deger == 0 else "acik"
    except OSError:
        return "acik"


TEMA_OVERRIDE = os.getenv("MISAFIRHANE_TEMA", "").strip().lower()
TEMA_ADI = TEMA_OVERRIDE if TEMA_OVERRIDE in ("acik", "karanlik") else windows_temasi()

UNINSTALL_SUBKEY = (
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    r"\{7F3A1B9E-4C62-4D8A-9E2B-MISAFIRHANE0001}_is1"
)
VARSAYILAN_YOL = r"C:\Program Files\Misafirhane Rezervasyon"

# Renk paletleri (uygulama tema.py ile uyumlu acik/koyu)
ACIK_TEMA = {
    "pencere": "#ffffff",
    "vurgu": "#4a90d9",
    "vurgu_koju": "#3d6fb4",
    "yazi": "#1a1a1a",
    "yazi_acik": "#555555",
    "yazi_alt": "#999999",
    "buton": "#f0f2f5",
    "buton_hover": "#dde4ee",
    "buton_kilitli_bg": "#e4e4e4",
    "buton_kilitli_fg": "#9a9a9a",
    "kutu": "#f7f7f7",
    "saglikli_bg": "#d5f5e3",
    "saglikli_fg": "#1e8449",
    "hasar_bg": "#fde3cf",
    "hasar_fg": "#b9770e",
    "yok_bg": "#d6eaf8",
    "yok_fg": "#2471a3",
    "bilgi_bg": "#eaf2f8",
    "bilgi_fg": "#34495e",
    "tehlike": "#c0392b",
    "tehlike_koju": "#922b21",
}

KARANLIK_TEMA = {
    "pencere": "#232323",
    "vurgu": "#5a9fe0",
    "vurgu_koju": "#3d6fb4",
    "yazi": "#e8e8e8",
    "yazi_acik": "#a0a0a0",
    "yazi_alt": "#707070",
    "buton": "#3a3a3a",
    "buton_hover": "#4a4a4a",
    "buton_kilitli_bg": "#2c2c2c",
    "buton_kilitli_fg": "#6a6a6a",
    "kutu": "#2a2a2a",
    "saglikli_bg": "#1f3d2c",
    "saglikli_fg": "#7be0a5",
    "hasar_bg": "#3d2c1e",
    "hasar_fg": "#f0b45f",
    "yok_bg": "#1f2f45",
    "yok_fg": "#85b8ea",
    "bilgi_bg": "#2a2f38",
    "bilgi_fg": "#b8c6d4",
    "tehlike": "#d9534f",
    "tehlike_koju": "#b13a37",
}

TEMA = KARANLIK_TEMA if TEMA_ADI == "karanlik" else ACIK_TEMA


class ShellExecuteInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("fMask", ctypes.c_ulong),
        ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", ctypes.c_void_p),
        ("lpClass", wintypes.LPCWSTR),
        ("hkeyClass", wintypes.HKEY),
        ("dwHotKey", wintypes.DWORD),
        ("hIcon", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
    ]


SEE_MASK_NOCLOSEPROCESS = 0x00000040
SW_SHOW = 1


def kurulum_durumu():
    """Kayit defterinden kurulum durumunu tespit eder."""
    bilgi = {"kurulu": False, "yol": VARSAYILAN_YOL, "surum": "", "hasarli": False}
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, UNINSTALL_SUBKEY, 0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        ) as k:
            bilgi["kurulu"] = True
            try:
                yol, _ = winreg.QueryValueEx(k, "InstallLocation")
            except OSError:
                yol = ""
            if yol:
                bilgi["yol"] = yol.rstrip("\\")
    except OSError:
        bilgi["kurulu"] = False

    if bilgi["kurulu"]:
        exe = os.path.join(bilgi["yol"], "Misafirhane.exe")
        bilgi["hasarli"] = not os.path.isfile(exe)
        yol_surum = os.path.join(bilgi["yol"], "surum.txt")
        try:
            with open(yol_surum, "r", encoding="utf-8") as f:
                satirlar = f.read().splitlines()
            if satirlar:
                bilgi["surum"] = satirlar[0].strip()
        except OSError:
            bilgi["surum"] = ""
    return bilgi


def kaldirma_yolu():
    """Kayit defterindeki Inno kaldirici (unins000.exe) yolunu dondurur."""
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, UNINSTALL_SUBKEY, 0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        ) as k:
            deger, _ = winreg.QueryValueEx(k, "UninstallString")
    except OSError:
        return ""
    deger = (deger or "").strip()
    if len(deger) >= 2 and deger[0] == '"' and deger[-1] == '"':
        deger = deger[1:-1]
    return deger


def veri_klasoru():
    """Uygulama verilerinin tutuldugu klasor (%LOCALAPPDATA%\\Misafirhane).

    database.py ile ayni kural: dondurulmus surumde veri LOCALAPPDATA altina
    yazilir. Bu araç da verileri doğrudan bu yoldan bulur.
    """
    taban = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(taban, "Misafirhane")


def gomulu_kurulum_arac():
    """Gomulu kurulum exe'sinin yolunu bulur (frozen veya kaynak)."""
    if getattr(sys, "frozen", False):
        taban = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        return os.path.join(taban, "Misafirhane_Kurulum.exe")
    return os.path.join(ROOT, "dist", "kurulum", "Misafirhane_Kurulum.exe")


def kaynak_yolu(goreli):
    if getattr(sys, "frozen", False):
        taban = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        return os.path.join(taban, goreli)
    return os.path.join(ROOT, goreli)


def calistir_bekle(exe):
    """Gomulu exe'yi runas (UAC) ile calistirir ve cikis kodunu dondurur.
    WinAPI cagrilarindan biri basarisiz olursa (gecersiz handle vb.) -1
    (basarisiz) dondurulur; 0 asla varsayilan/tahmini bir deger olarak
    dondurulmez cunku cagiranlar kod==0'i "basarili" sayip ona gore islem
    yapiyor (ornegin kaldirmada veri klasorunu silme kararini buna baglar)."""
    info = ShellExecuteInfo()
    info.cbSize = ctypes.sizeof(ShellExecuteInfo)
    info.fMask = SEE_MASK_NOCLOSEPROCESS
    info.lpVerb = "runas"
    info.lpFile = exe
    info.nShow = SW_SHOW
    ok = ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info))
    if not ok:
        return -1
    proc = info.hProcess
    try:
        WAIT_OBJECT_0 = 0
        bekleme_sonucu = ctypes.windll.kernel32.WaitForSingleObject(proc, 0xFFFFFFFF)
        if bekleme_sonucu != WAIT_OBJECT_0:
            return -1
        kod = wintypes.DWORD(0)
        okundu_mu = ctypes.windll.kernel32.GetExitCodeProcess(proc, ctypes.byref(kod))
        if not okundu_mu:
            return -1
        return kod.value
    finally:
        ctypes.windll.kernel32.CloseHandle(proc)


class KurulumAraci:
    def __init__(self):
        self.root = Tk()
        self.root.title("Misafirhane Rezervasyon - Kurulum")
        self.root.resizable(False, False)
        self.root.config(bg=TEMA["pencere"])

        simge = kaynak_yolu(os.path.join("assets", "misafirhane.ico"))
        if os.path.exists(simge):
            try:
                self.root.iconbitmap(default=simge)
            except Exception:
                pass

        self.bilgi = kurulum_durumu()
        self.calisiyor = False
        self.verileri_sil = False

        self._arayuz_kur()
        self._durumu_goster()

        self.root.update_idletasks()
        genislik = self.root.winfo_reqwidth()
        yukseklik = self.root.winfo_reqheight()
        x = (self.root.winfo_screenwidth() - genislik) // 2
        y = (self.root.winfo_screenheight() - yukseklik) // 3
        self.root.geometry(f"+{x}+{y}")
        self.root.protocol("WM_DELETE_WINDOW", self._kapat)

    def _arayuz_kur(self):
        # Ust vurgu seridi
        ust = Frame(self.root, bg=TEMA["vurgu"], height=4)
        ust.pack(fill="x")

        ic = Frame(self.root, bg=TEMA["pencere"], padx=20, pady=14)
        ic.pack(fill="both", expand=True)

        # Baslik
        baslik = Label(
            ic, text="Misafirhane Rezervasyon",
            font=("Segoe UI", 15, "bold"), bg=TEMA["pencere"], fg=TEMA["yazi"],
        )
        baslik.pack(anchor="w")

        alt_baslik = Label(
            ic, text="Kurulum ve Güncelleme Aracı",
            font=("Segoe UI", 9), bg=TEMA["pencere"], fg=TEMA["yazi_acik"],
        )
        alt_baslik.pack(anchor="w", pady=(0, 12))

        # Durum kutusu
        self.durum_kutu = Frame(ic, bg=TEMA["bilgi_bg"], padx=12, pady=10)
        self.durum_kutu.pack(fill="x")
        self.durum_label = Label(
            self.durum_kutu,
            text="",
            justify="left",
            anchor="w",
            wraplength=400,
            font=("Segoe UI", 10, "bold"),
            bg=TEMA["bilgi_bg"],
            fg=TEMA["bilgi_fg"],
        )
        self.durum_label.pack(fill="x")

        bosluk = Frame(ic, height=14, bg=TEMA["pencere"])
        bosluk.pack()

        # Islem butonlari
        self.btn_kur = self._yeni_buton(ic, "Uygulamayı Yükle",
                                        lambda: self._islemi_baslat("Yükleme"))
        self.btn_guncelle = self._yeni_buton(ic, "Uygulamayı Güncelle",
                                             lambda: self._islemi_baslat("Güncelleme"))
        self.btn_tamir = self._yeni_buton(ic, "Uygulamayı Tamir Et",
                                          lambda: self._islemi_baslat("Tamir (yeniden kurulum)"))
        self.btn_kaldir = self._yeni_buton(ic, "Uygulamayı Kaldır",
                                           self._kaldirmayi_baslat)
        for b in (self.btn_kur, self.btn_guncelle, self.btn_tamir):
            b.pack(fill="x", pady=4)
        self.btn_kaldir.pack(fill="x", pady=(10, 4))

        bosluk2 = Frame(ic, height=12, bg=TEMA["pencere"])
        bosluk2.pack()

        # Aciklama kutusu
        info = Frame(ic, bg=TEMA["kutu"], padx=12, pady=8)
        info.pack(fill="x")
        Label(
            info,
            text=(
                "Güncelleme/Tamir işlemleri tüm program dosyalarını yeniler; "
                "verileriniz (misafirhane.db ve yedekler) %LOCALAPPDATA%\\Misafirhane "
                "içinde saklandığından KORUNUR. Kaldırma sırasında verilerin "
                "korunup korunmayacağı ayrıca size sorulur."
            ),
            justify="left",
            anchor="w",
            wraplength=390,
            font=("Segoe UI", 8),
            bg=TEMA["kutu"],
            fg=TEMA["yazi_acik"],
        ).pack(fill="x")

        bosluk3 = Frame(ic, height=10, bg=TEMA["pencere"])
        bosluk3.pack()

        # Alt bar: surum + kapat
        alt = Frame(ic, bg=TEMA["pencere"])
        alt.pack(fill="x")
        Label(
            alt,
            text=self._paket_surumu(),
            font=("Segoe UI", 8),
            bg=TEMA["pencere"],
            fg=TEMA["yazi_alt"],
        ).pack(side="left")
        self.btn_kapat = Button(
            alt, text="Kapat", width=10,
            relief="flat", bd=0, highlightthickness=0,
            bg=TEMA["buton"], fg=TEMA["yazi"],
            activebackground=TEMA["buton_hover"], activeforeground=TEMA["yazi"],
            cursor="hand2", command=self._kapat,
        )
        self.btn_kapat.pack(side="right")

    def _paket_surumu(self):
        try:
            import versiyon
            return "Paket sürümü " + versiyon.SURUM
        except Exception:
            return "Paket sürümü bilinmiyor"

    def _yeni_buton(self, ebeveyn, metin, komut):
        return Button(
            ebeveyn, text=metin, command=komut, anchor="center",
            font=("Segoe UI", 10), padx=10, pady=6,
        )

    def _butonu_boya(self, btn, birincil, aktif=True, tehlikeli=False):
        ortak = dict(relief="flat", bd=0, highlightthickness=0)
        if not aktif:
            btn.config(state="disabled", bg=TEMA["buton_kilitli_bg"],
                       fg=TEMA["buton_kilitli_fg"], activebackground=TEMA["buton_kilitli_bg"],
                       activeforeground=TEMA["buton_kilitli_fg"], **ortak)
        elif tehlikeli:
            btn.config(state="normal", bg=TEMA["tehlike"], fg="#ffffff",
                       activebackground=TEMA["tehlike_koju"], activeforeground="#ffffff",
                       font=("Segoe UI", 10, "bold"), cursor="hand2", **ortak)
        elif birincil:
            btn.config(state="normal", bg=TEMA["vurgu"], fg="#ffffff",
                       activebackground=TEMA["vurgu_koju"], activeforeground="#ffffff",
                       font=("Segoe UI", 10, "bold"), cursor="hand2", **ortak)
        else:
            btn.config(state="normal", bg=TEMA["buton"], fg=TEMA["yazi"],
                       activebackground=TEMA["buton_hover"], activeforeground=TEMA["yazi"],
                       font=("Segoe UI", 10), cursor="hand2", **ortak)

    def _durumu_goster(self, mesaj=None, kutu_bg=None, kutu_fg=None):
        b = self.bilgi

        if mesaj:
            text = mesaj
            bg = kutu_bg or TEMA["bilgi_bg"]
            fg = kutu_fg or TEMA["bilgi_fg"]
            birincil_kur = birincil_guncelle = birincil_tamir = False
        elif b["kurulu"]:
            if b["hasarli"]:
                text = (
                    "Program yüklü görünüyor ancak dosyalar eksik/bozuk tespit "
                    "edildi. En uygun seçim: Tamir Et."
                )
                bg, fg = TEMA["hasar_bg"], TEMA["hasar_fg"]
                birincil_kur = birincil_guncelle = False
                birincil_tamir = True
            else:
                if b["surum"]:
                    text = (
                        f"Program yüklü görünüyor (sürüm {b['surum']}) ve sağlıklı. "
                        "Güncelle veya Tamir Et seçebilirsiniz."
                    )
                else:
                    text = (
                        "Program yüklü görünüyor ve sağlıklı. "
                        "Güncelle veya Tamir Et seçebilirsiniz."
                    )
                bg, fg = TEMA["saglikli_bg"], TEMA["saglikli_fg"]
                birincil_kur = birincil_tamir = False
                birincil_guncelle = True
        else:
            text = (
                "Program bilgisayarınızda bulunamadı. Yüklemek için "
                "'Uygulamayı Yükle'yi seçin."
            )
            bg, fg = TEMA["yok_bg"], TEMA["yok_fg"]
            birincil_guncelle = birincil_tamir = False
            birincil_kur = True

        self.durum_kutu.config(bg=bg)
        self.durum_label.config(text=text, bg=bg, fg=fg)

        aktif = not self.calisiyor
        self._butonu_boya(self.btn_kur, birincil_kur, aktif and not b["kurulu"])
        self._butonu_boya(self.btn_guncelle, birincil_guncelle, aktif and b["kurulu"])
        self._butonu_boya(self.btn_tamir, birincil_tamir, aktif and b["kurulu"])
        self._butonu_boya(self.btn_kaldir, False, aktif and b["kurulu"], tehlikeli=True)

    def _islemi_baslat(self, islem):
        if self.calisiyor:
            return
        sorma = messagebox.askyesno(
            "İşlemi onaylayın",
            f"{islem} işlemi başlatılacak.\n\n"
            "Program halen açıksa önce kapatılacak. Devam edilsin mi?",
        )
        if not sorma:
            return
        arac = gomulu_kurulum_arac()
        if not os.path.exists(arac):
            messagebox.showerror(
                "Dosya bulunamadı",
                "Kurulum aracı dosyası bulunamadı: " + arac,
            )
            return
        self.calisiyor = True
        self._durumu_goster(mesaj="İşlem başlatılıyor... UAC onayı açılacak.")
        threading.Thread(target=self._calistir_ve_bekle, args=(islem, arac), daemon=True).start()

    def _calistir_ve_bekle(self, islem, arac):
        kod = calistir_bekle(arac)
        self.root.after(0, self._islem_bitti, islem, kod)

    def _islem_bitti(self, islem, kod):
        self.calisiyor = False
        self.bilgi = kurulum_durumu()
        if kod == 0:
            mesaj = f"Uğurlu olsun: {islem} başarıyla tamamlandı."
            kutubg, kutufg = TEMA["saglikli_bg"], TEMA["saglikli_fg"]
        elif kod == 2:
            mesaj = "İşlem kullanıcı tarafından iptal edildi."
            kutubg, kutufg = TEMA["bilgi_bg"], TEMA["bilgi_fg"]
        else:
            mesaj = f"İşlem sonlandı (kod {kod})."
            kutubg, kutufg = TEMA["hasar_bg"], TEMA["hasar_fg"]
        self._durumu_goster(mesaj=mesaj, kutu_bg=kutubg, kutu_fg=kutufg)
        if kod == 0:
            messagebox.showinfo("Tamamlandı", mesaj)

    def _kaldirmayi_baslat(self):
        if self.calisiyor:
            return
        yol = kaldirma_yolu()
        if not yol:
            messagebox.showerror(
                "Kaldırma aracı bulunamadı",
                "Kayıt defterinde kaldırma programı bulunamadı. "
                "Program zaten kaldırılmış olabilir.",
            )
            self.bilgi = kurulum_durumu()
            self._durumu_goster()
            return
        onay = messagebox.askyesnocancel(
            "Kaldırmayı onaylayın",
            "Misafirhane Rezervasyon bilgisayardan KALDIRILACAK.\n\n"
            "Verileriniz (misafirhane.db, kbs_takip.db ve yedekler) "
            "%LOCALAPPDATA%\\Misafirhane klasöründe tutulur.\n\n"
            "Veritabanını ve verileri de silmek ister misiniz?\n"
            "  • Evet  → Uygulama kaldırılır, veriler DE SİLİNİR\n"
            "  • Hayır → Uygulama kaldırılır, veriler KORUNUR\n"
            "  • İptal → Kaldırma iptal edilir",
        )
        if onay is None:
            return
        self.verileri_sil = bool(onay)
        subprocess.run(["taskkill", "/F", "/T", "/IM", "Misafirhane.exe"],
                       capture_output=True)
        self.calisiyor = True
        if self.verileri_sil:
            mesaj = "Kaldırma işlemi başlatılıyor... Veriler silinecek. UAC onayı açılacak."
        else:
            mesaj = "Kaldırma işlemi başlatılıyor... Veriler korunacak. UAC onayı açılacak."
        self._durumu_goster(mesaj=mesaj)
        threading.Thread(target=self._calistir_kaldir, args=(yol,), daemon=True).start()

    def _calistir_kaldir(self, yol):
        kod = calistir_bekle(yol)
        self.root.after(0, self._kaldirma_bitti, kod)

    def _verileri_sil(self):
        """Uygulama veri klasorunu siler; sorun olursa hata mesajini dondurur."""
        klasor = veri_klasoru()
        if not os.path.isdir(klasor):
            return ""
        try:
            shutil.rmtree(klasor)
            return "" if not os.path.isdir(klasor) else "klasör hâlâ duruyor"
        except OSError as hata:
            return str(hata)

    def _kaldirma_bitti(self, kod):
        self.calisiyor = False
        self.bilgi = kurulum_durumu()
        if kod == 0 and self.verileri_sil:
            veri_hatasi = self._verileri_sil()
        else:
            veri_hatasi = ""
        if kod == 0:
            if self.verileri_sil and not veri_hatasi:
                mesaj = "Uygulama başarıyla kaldırıldı. Veriler de silindi."
            elif self.verileri_sil and veri_hatasi:
                mesaj = ("Uygulama kaldırıldı ancak veri klasörü silinemedi "
                         f"({veri_hatasi}). El ile silmeniz gerekebilir.")
            else:
                mesaj = "Uygulama başarıyla kaldırıldı. Verileriniz korundu."
            kutubg, kutufg = TEMA["saglikli_bg"], TEMA["saglikli_fg"]
        elif kod == 2:
            mesaj = "Kaldırma işlemi iptal edildi."
            kutubg, kutufg = TEMA["bilgi_bg"], TEMA["bilgi_fg"]
        else:
            mesaj = f"Kaldırma işlemi sonlandı (kod {kod})."
            kutubg, kutufg = TEMA["hasar_bg"], TEMA["hasar_fg"]
        self._durumu_goster(mesaj=mesaj, kutu_bg=kutubg, kutu_fg=kutufg)
        if kod == 0:
            messagebox.showinfo("Tamamlandı", mesaj)

    def _kapat(self):
        if self.calisiyor:
            return
        self.root.destroy()


def main():
    app = KurulumAraci()
    app.root.mainloop()


if __name__ == "__main__":
    main()