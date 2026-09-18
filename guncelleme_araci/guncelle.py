# -*- coding: utf-8 -*-
"""
Misafirhane Güncelleme Araci - cekirdek mantik.

Yalnizca Python standart kutuphaneleri kullanir (sistemde Python olmadan da
PyInstaller ile tek exe olarak calisabilir). Kurulum yerini Windows kayit
defterinden bulur ve guncelleme paketindeki dosyalari eski kurulumun
ustune yazar. Kullanici verileri (_internal/dis veritabani) %LOCALAPPDATA%
altinda oldugundan GUNCELLEMEDEN ETKILENMEZ.
"""

import os
import sys
import json
import hashlib
import shutil
import subprocess
import ctypes
import winreg

UYGULAMA_ADI = "Misafirhane Rezervasyon"
PROSES_ADI = "Misafirhane.exe"


def mesaj(metin, tip=0x40, baslik="Misafirhane Güncelleme"):
    """tip: 0x40 bilgi, 0x30 uyari, 0x10 hata, 0x4 Evet/Hayir."""
    if os.environ.get("MISA_OTOMATIK"):
        with open(os.path.join(os.environ.get("TEMP", "."), "misa_guncelleme.log"),
                  "a", encoding="utf-8") as log:
            log.write(f"[{baslik}] {metin}\n")
        return 6 if tip & 0x4 else 1
    return ctypes.windll.user32.MessageBoxW(0, metin, baslik, tip | 0x1000)


def kurulum_yerini_bul():
    """Kayit defterinden kurulum klasorunu bulur; bulamazsa None."""
    anahtarlar = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for kok, yol in anahtarlar:
        try:
            with winreg.OpenKey(kok, yol) as ust:
                for i in range(winreg.QueryInfoKey(ust)[0]):
                    try:
                        alt = winreg.EnumKey(ust, i)
                        with winreg.OpenKey(ust, alt) as anahtar:
                            ad = winreg.QueryValueEx(anahtar, "DisplayName")[0]
                            if UYGULAMA_ADI in ad:
                                konum = winreg.QueryValueEx(anahtar, "InstallLocation")[0]
                                if (konum and os.path.isdir(konum)
                                        and os.path.exists(os.path.join(konum, PROSES_ADI))):
                                    return konum
                    except OSError:
                        continue
        except OSError:
            continue
    return None


def dosya_ozet(yol):
    h = hashlib.sha256()
    with open(yol, "rb") as f:
        for blok in iter(lambda: f.read(65536), b""):
            h.update(blok)
    return h.hexdigest()


def yaz(baslar):
    os.makedirs(baslar, exist_ok=True)


def uygula(kurulum, paket):
    """paket: guncelle.json iceren dizin. Kurulumu gunceller. Degisen dosya sayisini dondurur."""
    with open(os.path.join(paket, "guncelle.json"), "r", encoding="utf-8") as f:
        bilgi = json.load(f)

    sayi = 0
    for satir in bilgi.get("dosyalar", []):
        kaynak = os.path.join(paket, *satir["yol"].split("/"))
        if not os.path.exists(kaynak):
            raise RuntimeError(f"Paket içinde dosya yok: {satir['yol']}")
        if "sha256" in satir and "boyut" in satir:
            if os.path.getsize(kaynak) != satir["boyut"]:
                raise RuntimeError(f"Bozuk paket (boyut): {satir['yol']}")
            if dosya_ozet(kaynak) != satir["sha256"]:
                raise RuntimeError(f"Bozuk paket (özet): {satir['yol']}")
        hedef = os.path.join(kurulum, *satir["yol"].split("/"))
        yaz(os.path.dirname(hedef))
        shutil.copy2(kaynak, hedef)
        sayi += 1

    for yap in bilgi.get("kaldirilacaklar", []):
        hedef = os.path.join(kurulum, *yap.split("/"))
        if os.path.exists(hedef):
            try:
                os.remove(hedef)
            except OSError:
                pass

    with open(os.path.join(kurulum, "surum.txt"), "w", encoding="utf-8") as f:
        f.write(bilgi.get("surum", ""))
    return sayi


def uygulamayi_kapat():
    subprocess.run(["taskkill", "/IM", PROSES_ADI, "/F"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def eskiyi_yedekle(kurulum, eski_surum):
    """Eski Misafirhane.exe'yi _eski klasorune tasir (son 3 kopya tutulur)."""
    eski_klasor = os.path.join(kurulum, "_eski")
    yaz(eski_klasor)
    kaynak = os.path.join(kurulum, PROSES_ADI)
    if os.path.exists(kaynak):
        ad = f"misafirhane_{eski_surum or 'onceki'}.exe"
        hedef = os.path.join(eski_klasor, ad)
        try:
            if os.path.exists(hedef):
                os.remove(hedef)
            shutil.copy2(kaynak, hedef)
            tetikler = sorted(
                (os.path.join(eski_klasor, f) for f in os.listdir(eski_klasor)),
                key=os.path.getmtime, reverse=True)
            for cok in tetikler[3:]:
                try:
                    os.remove(cok)
                except OSError:
                    pass
        except OSError:
            pass


def ana(paket=None):
    if paket is None:
        taban = getattr(sys, "_MEIPASS", os.getcwd())
        paket = os.path.join(taban, "patch")
    if not os.path.exists(os.path.join(paket, "guncelle.json")):
        mesaj("Güncelleme paketi bulunamadı.\nGüncelleme dosyasının bozuk ya da "
              "yanlış konumda olduğu anlaşılıyor.", 0x10)
        return 2

    with open(os.path.join(paket, "guncelle.json"), "r", encoding="utf-8") as f:
        bilgi = json.load(f)

    kurulum = kurulum_yerini_bul()
    if not kurulum:
        mesaj("Misafirhane uygulamasının kurulu olduğu klasör bulunamadı.\n"
              "Önce kurulum dosyasını çalıştırarak uygulamayı kurmalısın.", 0x10)
        return 3

    mevcut = ""
    surum_dosyasi = os.path.join(kurulum, "surum.txt")
    if os.path.exists(surum_dosyasi):
        with open(surum_dosyasi, "r", encoding="utf-8") as f:
            mevcut = f.read().strip()

    hedef_surum = bilgi.get("surum", "")
    if mevcut == hedef_surum:
        mesaj(f"Kurulu sürüm zaten güncel: {hedef_surum}.", 0x40)
        return 0

    notlar = bilgi.get("notlar", "")
    onay = mesaj(
        f"{UYGULAMA_ADI}\n\n"
        f"Mevcut sürüm : {mevcut or 'bilinmiyor'}\n"
        f"Yeni sürüm   : {hedef_surum}\n"
        f"Notlar       : {notlar}\n\n"
        f"Güncelleme uygulanacak. Uygulama açıksa kapatılacak. Devam edilsin mi?",
        0x4)
    if onay != 6:  # IDYES
        return 130

    uygulamayi_kapat()
    try:
        eskiyi_yedekle(kurulum, mevcut or hedef_surum)
        sayi = uygula(kurulum, paket)
    except RuntimeError as e:
        mesaj(f"Güncelleme BAŞARISIZ:\n{e}", 0x10)
        return 4

    sonuc = mesaj(
        f"Güncelleme tamamlandı.\n\n"
        f"Yeni sürüm: {hedef_surum}\nDeğiştirilen dosya: {sayi}\n\n"
        f"Uygulama şimdi başlatılsın mı?", 0x4)
    if sonuc == 6:
        subprocess.Popen([os.path.join(kurulum, PROSES_ADI)], cwd=kurulum)
    return 0