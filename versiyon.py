# -*- coding: utf-8 -*-
"""Sürüm yönetimi. Her sürümde SURUM arttirilir; guncelleme aracı ve
kurulum paketi bu değeri kullanır."""

UYGULAMA_ADI = "Misafirhane Rezervasyon"
SURUM = "1.0.1"

YENILIKLER = {
    "1.0.0": "İlk yayın sürümü. Rezervasyon, oda durumu, takvim, rapor ve yedekleme.",
    "1.0.1": "Ayarlar sekmesine sürüm bilgisi eklendi. Güncelleme altyapısı hazır.",
}


def gecmise_cevir(surum):
    """'1.0.1' gibi bir sürümü sayısal olarak karşılaştırılabilir demet yapar."""
    bolumler = []
    for p in str(surum).split(".")[:3]:
        try:
            bolumler.append(int(p))
        except ValueError:
            bolumler.append(0)
    while len(bolumler) < 3:
        bolumler.append(0)
    return tuple(bolumler)