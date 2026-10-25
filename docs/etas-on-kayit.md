# ETAS ileriye dönük sınav: ön kayıt

Tarih: 2026-10-25. Bu belge sınavın kurallarını sınav başlamadan dondurur. Sonuç görüldükten sonra değiştirilemez.

## Sınanan şey

Her pazartesi yayımlanan haftalık olasılıklar: P(≥ 1 deprem, Mw ≥ 5, 7 gün), 7 coğrafi bölge için (Marmara, Ege, Akdeniz, İç Anadolu, Karadeniz, Doğu Anadolu, Güneydoğu Anadolu). Karşılaştırma tabanı: aynı bölgeler için zamandan bağımsız Poisson olasılığı (bağımsız, yani kümelenmesi ayrılmış olaylardan yıllık oran; Gutenberg–Richter ile Mw 5'e uzatılır).

## Dondurulan ayarlar

- Model sürümü: `MODEL_SURUM = etas-2` (hesap/etas.py).
- Tamamlanma büyüklüğü: Mc 4,0 (eğitim döneminde, `mc_egitim`, b kararlılığıyla seçilir; sınav boyunca değişmez).
- Bölgeler: yukarıdaki 7 bölge (data/bolgeler.json, 30 km tampon).
- Gözlem: EMSC Türkiye kutusunda, tahmin penceresi içinde Mw ≥ 5 olay, bölgeye göre var/yok.
- Kayıt: her tahmin D1 tablosu `etas_kayit`'e (hafta, tahmin) bir kez eklenir, yazıldıktan sonra değiştirilmez. Hafta dolunca gözlem ve skor bir kez doldurulur. Model o hafta güncellenemezse yayımlanan değer Poisson tabanıdır; hafta sınava yine sayılır.

## Ölçütler

1. Brier skill skoru: 1 − (modelin Brier toplamı / tabanın Brier toplamı), haftalar üzerinden. Belirsizlik: haftalar yeniden örneklenerek bootstrap, %95 aralık.
2. Log-olabilirlik bilgi kazancı: model ile taban arasındaki Bernoulli log-olabilirlik farkının gözlenen olay (bölge-hafta) başına değeri.

## Geçme kuralı

52 hafta dolunca: Brier skill için bootstrap %95 aralığının alt sınırı > 0 VE bilgi kazancı > 0 ise haftalık ETAS kartı kanala açılır. İkisinden biri sağlanmazsa kart kanala açılmaz.

Her 13 haftada bir ara rapor yayımlanır. Ara raporlar yalnızca betimleyicidir: erken geçme ya da erken durdurma kararı verilmez.

## Sayaç sıfırlanması

Model (MODEL_SURUM), Mc, bölgeler, ölçütler ya da geçme kuralı bu süre içinde değişirse sayaç sıfırlanır ve 52 hafta yeniden başlar. Yalnızca aynı model sürümüyle kapanmış haftalar sayılır.

Kod: hesap/etas_kayit.py. Testler: hesap/tests/test_etas_kayit.py.
