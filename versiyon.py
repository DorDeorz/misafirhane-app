# -*- coding: utf-8 -*-
"""Sürüm yönetimi. Sürüm şeması:
- Büyük/belirgin özellik güncellemesi -> 1.0.2 -> 1.0.3
- Yayınlanmış sürümde hata düzeltmesi -> sona bir sayı eklenir: 1.0.2 -> 1.0.2.1
Her sürümde SURUM arttirilir; guncelleme aracı ve kurulum paketi bu değeri kullanır."""

UYGULAMA_ADI = "Misafirhane Rezervasyon"
SURUM = "1.0.4.3"

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
    "1.0.4": "KBS Bildirimi (1774 sayılı Kanun / Kimlik Bildirme Sistemi): ana "
             "pencerede '🛂 KBS Bildirimi' penceresi — bekleyen giriş/çıkışlar, "
             "şahıs TC kontrolü, gönderildi işaretleme, takip veritabanı ve Excel "
             "dışa aktarma. Yabancı misafirler için KBS zorunlu alanların check-in'de "
             "toplanması (uyruk, doğum tarihi/bilinmiyor, cinsiyet, doğum yeri, belge "
             "türü) ve eksik bilgi uyarıları. Geçersiz TC No check-in'de engellenir. "
             "Arayüz yeniden tasarlandı (laptop dostu): rezervasyon detayı kompakt "
             "başlık + splitter düzeni, oda işlemleri tablo içinden seçime dayalı "
             "aksiyon çubuğuna taşındı (butonlar hep tam görünür), ortak rozetler ve "
             "kompakt tema. Gece sayısı uzatma/kısaltma artık içerideki misafir için "
             "de çalışır; tarih değişikliği çakıştığında 'gece sayısını azalt' önerisi "
             "ve onay akışı eklendi.",
    "1.0.4.1": "Kurulum Aracı (tek dosya): Yükle / Güncelle / Tamir Et / Kaldır "
                "işlemlerini tek exe'den yönetir. Programın durumunu (kurulu sürüm, "
                "bozukluk) otomatik algılar, gömülü kurulumu UAC ile çalıştırır; "
                "arayüz Windows'un koyu/açık mod ayarıyla otomatik eşleşir. "
                "Kaldırma sırasında veriler (%LOCALAPPDATA%\\Misafirhane) korunur. "
                "Eski tek amaçlı hibrit Kurulum exe'sinin yerini alır.",
    "1.0.4.2": "Kurulum Aracı'nda Kaldırma seçeneği geliştirildi: uygulama "
                "kaldırılırken 'Veritabanını ve verileri de silmek ister misiniz?' "
                "diye sorulur. Evet seçilirse veri klasörü (%LOCALAPPDATA%\\"
                "Misafirhane: misafirhane.db, kbs_takip.db ve yedekler) kalıcı "
                "olarak silinir; Hayır seçilirse veriler korunur; İptal ile "
                "kaldırma iptal edilir. Veri silme yalnızca kaldırma başarıyla "
                "tamamlanınca yapılır.",
    "1.0.4.3": "Kod incelemesi sonrası hata düzeltmeleri. KBS: oda değiştirmede "
                "yabancı misafirin uyruk/doğum tarihi gibi bilgileri artık "
                "kaybolmuyor; aynı misafir için mükerrer 'giriş' bildirimi ve "
                "hâlâ otelde olan misafirin yanlışlıkla 'bugün çıkıyor' görünmesi "
                "giderildi (rezervasyon_odalar tablosuna oda değiştirme zincirini "
                "izleyen bir kolon eklendi, eski veritabanları otomatik "
                "güncellenir). 'Gönderildi' takibi artık misafir bazlı (aynı "
                "odadaki kişiler birbirini düşürmüyordu); yerli/yabancı ayrımı "
                "TC No şekli yerine check-in'de toplanan bilgilere bakıyor (11 "
                "haneli Yabancı Kimlik No'lu misafirler yanlış sınıflanmıyor); "
                "T.C. Kimlik No artık gerçek sağlama algoritmasıyla doğrulanıyor. "
                "KBS Excel çıktısına formül enjeksiyonu koruması eklendi, "
                "bildirim geçmişi artık misafir/oda/tarih bilgisini de kaydediyor. "
                "Çok odalı rezervasyonda 'Oda Değiştir' penceresini çökerten "
                "eksik bir import düzeltildi. Oda değiştirmede kapasite kontrolü "
                "artık check-in'deki gibi ekstra yatak hakkını da sayıyor. "
                "Güncelleme aracı artık hataları sessizce yutmuyor, yanlış "
                "sürümden gelen bir paketi uygulamıyor ve yedekleme "
                "başarısızlığını kullanıcıya bildiriyor.",
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