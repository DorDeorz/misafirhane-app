# Antivirüs / SmartScreen yanlış alarmları

Misafirhane exe'leri PyInstaller ile derleniyor ve şimdilik **imzasız**. Bu iki
durum, bazı antivirüslerin ve Windows'un exe'yi "tanınmayan" ya da "şüpheli"
diye işaretlemesine yol açabiliyor. Bu belge, her release'te yanlış alarmı
azaltmak için yapılacakları anlatır.

## Derlemede otomatik yapılanlar (`guncelleme_olustur.py`)

- Bütün exe'lere sürüm ve yayıncı bilgisi gömülür (exe'ye sağ tık →
  Özellikler → Ayrıntılar). Boş sürüm bilgisi antivirüs sezgisellerinde
  puan düşürüyor.
- UPX sıkıştırması kapalı (`--noupx`). UPX'li exe'ler çok daha sık işaretleniyor.
- `--tam` artık release'in 3 exe'sini de (Kurulum Aracı, Güncelleme, tek dosya
  sürüm) aynı ayarlarla üretir.

## Her release'ten sonra (elle, yaklaşık 10 dakika)

1. **VirusTotal kontrolü:** https://www.virustotal.com adresine 3 exe'yi
   yükle. Kaç motorun alarm verdiğine bak (birkaç küçük motorun alarmı
   PyInstaller exe'lerinde olağan).
2. **Microsoft Defender alarm verirse** (en önemlisi, çünkü Windows'ta varsayılan
   o): https://www.microsoft.com/wdsi/filesubmission adresinden
   "Software developer" olarak dosyayı gönder, "Incorrectly detected as
   malware/malicious" seç, açıklamaya kısaca "PyInstaller ile derlenmiş açık
   kaynak misafirhane yönetim uygulaması, kaynak: github.com/DorDeorz/misafirhane-app"
   yaz. Genelde birkaç gün içinde tanım güncellenir.
3. **Başka bir antivirüs** (Avast, Kaspersky, ESET vb.) alarm verirse, o
   firmanın "false positive" bildirim sayfasından aynı şekilde gönder.

## Kullanıcı tarafında exe engellenirse

- **SmartScreen ("Windows bilgisayarınızı korudu"):** "Ek bilgi" →
  "Yine de çalıştır".
- **İndirilen dosya engelliyse:** exe'ye sağ tık → Özellikler → alttaki
  "Engellemeyi kaldır" kutusu → Tamam.
- **Akıllı Uygulama Denetimi / Windows Uygulama Denetimi:** imzasız exe'leri
  tamamen engelleyebilir ve tek tek izin verilemez. Bu durumda kalıcı çözüm
  exe'leri imzalamaktır (aşağıya bakın).

## İleride: kod imzalama

İmza, Uygulama Denetimi engelini kaldırır ve SmartScreen itibarının zamanla
oluşmasını sağlar. Türkiye'den bireysel olarak en uygun yol Certum
"Open Source Code Signing in the Cloud" sertifikası (repo herkese açık olduğu
için). Azure Artifact Signing bireyler için yalnızca ABD/Kanada'da açık.
Sertifika alınırsa `guncelleme_olustur.py`'ye `signtool` ile imzalama adımı
eklenecek.

## İsteğe bağlı: bootloader'ı kaynaktan derlemek

Hazır PyInstaller bootloader'ı çok sayıda zararlı yazılımda da kullanıldığı
için bazı motorlar doğrudan onu işaretliyor. Alarmlar sürerse PyInstaller
kaynaktan kurulabilir (Visual Studio Build Tools gerekir):

```
pip uninstall pyinstaller
set PYINSTALLER_COMPILE_BOOTLOADER=1
pip install --no-binary pyinstaller pyinstaller
```

Bu adım isteğe bağlı; önce yukarıdaki bildirimler denenmeli.
