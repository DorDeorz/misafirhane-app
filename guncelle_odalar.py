# -*- coding: utf-8 -*-
"""
TEK SEFERLİK GÜNCELLEME SCRIPTI.
Eğer uygulamayı daha önce açıp odalar otomatik oluşturulduysa, bu scripti
çalıştırarak oda tiplerini ve eski numaralarını (telefon kodu için) doğru
değerlerle güncelleyebilirsin.

Çalıştırmak için (aynı klasörde):
    python guncelle_odalar.py

Bu script odaları SİLMEZ, sadece oda no'suna göre eşleştirip tip ve eski no
bilgisini günceller. Birden fazla kez çalıştırman bir sorun yaratmaz.
"""

import database
import repository

# oda_no -> (oda_tipi, eski_no)
ESLESTIRME = {
    1: ("Tek", 1),
    2: ("Double", 2),
    3: ("Aile", 3),
    4: ("Tek+Tek", 5),
    5: ("Double", 6),
    6: ("Aile", 7),
    7: ("Tek+Tek", 8),
    8: ("Double", 10),
    9: ("Aile", 11),
    10: ("Tek+Tek", 13),
    11: ("Double", 14),
    12: ("Aile", 15),
    13: ("Tek+Tek", 17),
    14: ("Double", 18),
    15: ("Aile", 19),
    16: ("Tek+Tek", 21),
    17: ("Double", 22),
    18: ("Aile", 24),
}


def main():
    database.init_db()
    odalar = repository.oda_listesi()
    if not odalar:
        print("Henüz oda yok, önce uygulamayı bir kere açıp kapatman gerekiyor.")
        return

    guncellenen = 0
    for oda in odalar:
        if oda["oda_no"] in ESLESTIRME:
            oda_tipi, eski_no = ESLESTIRME[oda["oda_no"]]
            kapasite = database.ODA_TIPI_KAPASITE.get(oda_tipi, 1)
            repository.oda_guncelle(
                oda["id"], oda["kat_no"], oda["kat_adi"], oda["oda_no"], oda_tipi, eski_no,
                kapasite=kapasite
            )
            kod = database.telefon_kodu(eski_no)
            print(f"Oda {oda['oda_no']}: {oda_tipi}, kapasite {kapasite}, eski no {eski_no}, telefon kodu {kod}")
            guncellenen += 1
        else:
            print(f"Oda {oda['oda_no']}: eşleştirme bulunamadı, atlandı.")

    print(f"\nToplam {guncellenen} oda güncellendi.")


if __name__ == "__main__":
    main()
