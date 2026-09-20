# -*- coding: utf-8 -*-
"""
Guncelleme paketi uretici (gelistirici aracı).

Kullanim (proje klasorunde):
  python guncelleme_olustur.py --baseline
      -> Ilk sürümün manifest'ini kaydeder (guncelleme farkının referansi).
  python guncelleme_olustur.py
      -> Uygulamayi yeniden derler, bir onceki baseline ile karsilastirip
         SADECE degisen dosyalari dagitim/guncelle_<SURUM>/ paketine koyar
         ve Misafirhane_Guncelleme_<SURUM>.exe uretir.
  python guncelleme_olustur.py --tam
      -> Ayni islemler + tam kurulum motorunu (Inno) uretir ve
         Kurulum Aracı'nda gomulu kullanilir. Ayri bir
         Misafirhane_Kurulum_<SURUM>.exe artik URETILMEZ — tek kurulum
         araci (Misafirhane_Kurulumu_<SURUM>.exe) tum isleri yapar.

Cikti: dagitim/ klasoru (gitignore'ludur). Masauette dagitim, diger
bilgisayarda calistirilacak guncelleme exe'sidir.
"""

import os
import sys
import json
import shutil
import hashlib
import zipfile
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import versiyon  # noqa: E402

SURUM = versiyon.SURUM
UYGULAMA_ADI = versiyon.UYGULAMA_ADI
YENI_KLASOR = os.path.join(ROOT, "dagitim", f"guncelle_{SURUM}")
MANIFEST = os.path.join(ROOT, "dagitim", "son_manifest.json")
GUNCELLEME_EXE = os.path.join(ROOT, "dagitim", f"Misafirhane_Guncelleme_{SURUM}.exe")
DIST_APP = os.path.join(ROOT, "dist", "Misafirhane")


def dosya_ozet(yol):
    h = hashlib.sha256()
    with open(yol, "rb") as f:
        for blok in iter(lambda: f.read(65536), b""):
            h.update(blok)
    return h.hexdigest()


def manifest_olustur(kok):
    """kok altindaki tum dosyalarin goreli yol -> sha256 haritasi."""
    harita = {}
    for dizin, _, dosyalar in os.walk(kok):
        for ad in dosyalar:
            tam = os.path.join(dizin, ad)
            goreli = os.path.relpath(tam, kok).replace("\\", "/")
            harita[goreli] = dosya_ozet(tam)
    return harita


def surum_dosyasi_yaz():
    with open(os.path.join(ROOT, "surum.txt"), "w", encoding="utf-8") as f:
        f.write(SURUM)


def uygulamayi_derle():
    print(f"[1/4] Uygulama derleniyor (PyInstaller, {SURUM}) ...")
    komut = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onedir", "--windowed",
        "--name", "Misafirhane",
        "--icon", os.path.join(ROOT, "assets", "misafirhane.ico"),
        "--add-data", os.path.join(ROOT, "assets", "misafirhane.ico") + ";assets",
        "main.py",
    ]
    subprocess.run(komut, cwd=ROOT, check=True)


def guncelleme_paketi():
    print(f"[2/4] Fark tespiti ({SURUM}) ...")
    os.makedirs(YENI_KLASOR, exist_ok=True)

    yeni = manifest_olustur(DIST_APP)
    if os.path.exists(MANIFEST):
        with open(MANIFEST, "r", encoding="utf-8") as f:
            eski = json.load(f)
        eski_map = eski.get("dosyalar", {})
        onceki = eski.get("surum", "1.0.0")
    else:
        eski_map = {}
        onceki = "1.0.0"

    degisen = []
    for yol, ozet in yeni.items():
        if eski_map.get(yol) != ozet:
            degisen.append(yol)
    kaldirilacaklar = [y for y in eski_map if y not in yeni]

    print(f"  Degisen/yeni dosya: {len(degisen)} | silinen: {len(kaldirilacaklar)}")
    if not degisen and not kaldirilacaklar:
        print("  Fark yok; paket olusturulmayacak. (Surumu arttirmayi unuttun mu?)")
        return False

    bilgi = {
        "surum": SURUM,
        "onceki_surum": onceki,
        "notlar": versiyon.YENILIKLER.get(SURUM, ""),
        "dosyalar": [
            {"yol": y, "boyut": os.path.getsize(os.path.join(DIST_APP, *y.split("/"))),
             "sha256": yeni[y]}
            for y in sorted(degisen)
        ],
        "kaldirilacaklar": kaldirilacaklar,
    }
    with open(os.path.join(YENI_KLASOR, "guncelle.json"), "w", encoding="utf-8") as f:
        json.dump(bilgi, f, ensure_ascii=False, indent=2)

    for yol in sorted(degisen):
        kaynak = os.path.join(DIST_APP, *yol.split("/"))
        hedef = os.path.join(YENI_KLASOR, *yol.split("/"))
        os.makedirs(os.path.dirname(hedef), exist_ok=True)
        shutil.copy2(kaynak, hedef)

    zip_yol = os.path.join(YENI_KLASOR, "guncelle_patch.zip")
    with zipfile.ZipFile(zip_yol, "w", zipfile.ZIP_DEFLATED) as z:
        for yol in sorted(degisen):
            kaynak = os.path.join(DIST_APP, *yol.split("/"))
            z.write(kaynak, yol)
        z.writestr("guncelle.json", json.dumps(bilgi, ensure_ascii=False, indent=2))
    print(f"  Paket: {YENI_KLASOR}")
    return True


def guncelleme_exe():
    print(f"[3/4] Guncelleme exe uretiliyor ...")
    subprocess.run([
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--windowed", "--uac-admin",
        "--name", "Misafirhane_Guncelleme",
        "--add-data", YENI_KLASOR + ";patch",
        os.path.join(ROOT, "guncelleme_araci", "main.py"),
    ], cwd=ROOT, check=True)
    cikti = os.path.join(ROOT, "dist", "Misafirhane_Guncelleme.exe")
    os.makedirs(os.path.dirname(GUNCELLEME_EXE), exist_ok=True)
    shutil.copy2(cikti, GUNCELLEME_EXE)
    print(f"  Guncelleme exe: {GUNCELLEME_EXE}")


def tam_kurulum():
    print("[4/4] Inno kurulum motoru derleniyor (Kurulum Aracı icin gomulu) ...")
    iscc = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Inno Setup 6", "ISCC.exe")
    if not os.path.exists(iscc):
        iscc = r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    if not os.path.exists(iscc):
        print("  ISCC bulunamadi; kurulum motoru atlandi.")
        return
    subprocess.run([
        iscc, "/DMyAppVersion=" + SURUM, os.path.join(ROOT, "kurulum.iss"),
    ], cwd=ROOT, check=True)
    cikti = os.path.join(ROOT, "dist", "kurulum", "Misafirhane_Kurulum.exe")
    if os.path.exists(cikti):
        print(f"  Motor exe: {cikti}")
        print("  Ayri Misafirhane_Kurulum_<surum>.exe artik uretilmiyor; "
              "tek Kurulum Aracı (Misafirhane_Kurulumu) tum kurulum "
              "islemlerini karsiliyor.")


def manifesti_guncelle(yeni_map):
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump({"surum": SURUM, "dosyalar": yeni_map}, f, ensure_ascii=False, indent=2)


def baseline():
    print("Baseline kaydediliyor (guncelleme referansi) ...")
    surum_dosyasi_yaz()
    harita = manifest_olustur(DIST_APP)
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    manifesti_guncelle(harita)
    print(f"  {len(harita)} dosya kaydedildi -> {MANIFEST}")


def main():
    arg_tam = "--tam" in sys.argv
    arg_baseline = "--baseline" in sys.argv

    if arg_baseline:
        baseline()
        return

    surum_dosyasi_yaz()
    uygulamayi_derle()
    uretildi = guncelleme_paketi()
    if uretildi:
        guncelleme_exe()
        manifesti_guncelle(manifest_olustur(DIST_APP))
        if arg_tam:
            tam_kurulum()
    print(f"\nBitti. Surum {SURUM} paketi dagitim/ altinda.")


if __name__ == "__main__":
    main()