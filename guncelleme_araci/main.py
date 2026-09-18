# -*- coding: utf-8 -*-
"""Misafirhane Guncelleme Araci - giris noktasi.

Kullanim:
  Misafirhane_Guncelleme.exe            -> gomulu (embedded) paketi uygular
  python guncelleme_araci\\main.py <paket_dizini>  -> gelistirme modu (dis dizin)
"""

import sys
import os


def _try_paths():
    taban = getattr(sys, "_MEIPASS", os.getcwd())
    adaylar = []
    aday = os.path.join(taban, "patch")
    adaylar.append(aday)
    dizin = os.path.dirname(os.path.abspath(sys.argv[0]))
    if dizin not in adaylar:
        adaylar.append(os.path.join(dizin, "patch"))
    for aday in adaylar:
        if os.path.isdir(aday) and os.path.exists(os.path.join(aday, "guncelle.json")):
            return aday
    return None


def main():
    import guncelle

    if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]):
        paket = sys.argv[1]
    else:
        paket = _try_paths()

    if paket is None:
        guncelle.mesaj("Güncelleme paketi bulunamadı:\npatch/guncelle.json eksik.", 0x10)
        return 2
    return guncelle.ana(paket)


if __name__ == "__main__":
    sys.exit(main())