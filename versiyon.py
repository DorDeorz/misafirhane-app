# -*- coding: utf-8 -*-
"""Sürüm yönetimi. Sürüm şeması:
- Büyük/belirgin özellik güncellemesi -> 1.0.2 -> 1.0.3
- Yayınlanmış sürümde hata düzeltmesi -> sona bir sayı eklenir: 1.0.2 -> 1.0.2.1
Her sürümde SURUM arttirilir; guncelleme aracı ve kurulum paketi bu değeri kullanır."""

UYGULAMA_ADI = "Misafirhane Rezervasyon"
SURUM = "1.0.3"

YENILIKLER = {
    "1.0.0": "İlk yayın sürümü. Rezervasyon, oda durumu, takvim, rapor ve yedekleme.",
    "1.0.1": "Ayarlar sekmesine sürüm bilgisi eklendi. Güncelleme altyapısı hazır.",
    "1.0.2": "Oda Değiştir ekranı tablo haline getirildi (müsaitlik renk kodlu). "
             "Takvimde adlar yalnızca giriş gününe yazılır, kalışın diğer geceleri X olur "
             "— aynı isimli rezervasyonlar artık ayırt edilebilir.",
    "1.0.2.1": "Hata düzeltmesi: Takvim ipuçlarında (referans bilgisi) yaşanan açılış "
                "hatası giderildi.",
    "1.0.2.2": "Oda değiştirme sonrası giriş tarihi değiştirilince aynı gece iki odada "
                "görünme hatası düzeltildi — oda-parçaları artık otomatik dengelenir.",
    "1.0.3": "Çok odalı rezervasyon: tek rezervasyon birden çok odayı kapsar "
             "(Yeni Rezervasyon, detay ekranı, oda değiştirme ve check-in/çıkış oda "
             "satırı bazlı). Geçmiş Kayıtlar: çıkış yapılmış eski misafirlerin "
             "aranabilir görünümü. Günün Girişleri: çok odalı rezervasyon tek satırda, "
             "her oda için Geldi / Gelmedi / Bekleniyor durumu ayrıca gösterilir. "
             "Performans: arama yalnızca Ad Soyad'da anında filtreler (gecikmeli "
             "yenileme + toplu sorgular ile büyük listelerde kasma giderildi). "
             "Düzeltmeler: Oda Değiştir / Tarih Değiştir pencerelerinin açılmama "
             "hatası, iptal listesinde satır renklendirme çökmesi.",
}


def gecmise_cevir(surum):
    """'1.0.2.1' gibi bir sürümü sayısal olarak karşılaştırılabilir demet yapar.
    4 parçalı yama sürümleri desteklenir (1.0.2.1 > 1.0.2)."""
    bolumler = []
    for p in str(surum).split("."):
        try:
            bolumler.append(int(p))
        except ValueError:
            bolumler.append(0)
    while len(bolumler) < 3:
        bolumler.append(0)
    return tuple(bolumler)