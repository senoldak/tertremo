# tertremo kart kılavuzu

Kanaldaki her paylaşım çizimlidir. 20 kart var: 11 olay kartı (bir depreme ya da diziye bağlı) ve 9 dönemsel kart (takvimle). Kodu `scripts/kart/` içindedir; örnek PNG'ler ve pafta için `node scripts/kart/ornekler.mjs [klasör]` (dönemsel örneklerde veri uydurmadır, köşede "ÖRNEK" damgası taşır).

## Düzen kuralları

- 1200 × 800 PNG. Harita ya da grafik alanı y 0–560; alt bant y 560–800, üstünde 6 px indigo çizgi.
- Sol sütunda büyük sayı (112 px), **birimi altında** (26 px). Sağ sütun x 360'tan başlar: başlık 46 px, iki satır 28 px gri. Sağ sütun yazısı 800 px'i aşarsa "…" ile kısalır; logo ya da sayıyla asla çakışmaz.
- Logo sol üstte (34 px), kâğıt rengi levhada (0,94 opaklık, köşe 10).
- Renkler: kâğıt `#f5f4ef`, mürekkep `#16181d`, indigo `#3d36c9` (koyu zeminde `#8f88ff`; yalnız vurgu ve merkez üssü halkası), gri `#6b6a64`, deniz `#dfe3e6`, Türkiye kara `#fbfaf6`, komşu kara `#efede6`, çizgi `#c9c5b8`. Kırmızı yok.
- Yazı tipi yalnız Manrope Bold; harfler yol olarak çizilir. Sayılar Türkçe: ondalık virgül, binlik nokta, eksi için −.
- Levha çizgisi çizen her kartta atıf: "Levha sınırları: Bird (2003), ODC-By".

## Dil kuralları

- "tehlike" ve "uyarı" hiçbir kartta geçmez.
- Her olasılık ve olağan dışı kartında "Tahmin değildir." (olasılık kartlarında "Olasılık hesabıdır; depremin yeri ve zamanı önceden bilinemez.") notu bulunur.
- Olasılık "en az bir" diye yazılır ("7 günde en az bir M≥5"), "olacak" diye değil.
- Yorum, süs, abartı yok.
- Yer adları Türkçe: Türkiye'de il / ilçe, dünyada ülke adı ya da "… açıkları".

## Kartlar

Saatler TSİ. Eşikler Worker'daki uygulamadır (`vesaire/tertremo/src/kart.js`, `dizikilometre.js`, `etki.js`, `ozet.js`) ve vesaire cron'unun tetik saatleridir (`vesaire/tertremo/src/takvim.js`).

### Olay kartları (kanala giden olaylar; Worker kuyruğa yazar, iş akışı çizer; 2 dakikada gelmezse düz metin gider)

| # | Kart (tür) | Tetik | Gösterdiği | Veri / lisans | Not |
|---|---|---|---|---|---|
| 1 | Deprem (`deprem`) | kanala giden her olay | Türkiye çevresi ya da bölge haritası, merkez üssü halkası, hissedilme halkaları (MMI 4 / 3 / 2) | AFAD, Kandilli, EMSC, USGS; harita Natural Earth (kamu malı) | Mw dışı büyüklük "M (tür, yaklaşık)" yazılır |
| 2 | Nerelerde hissedildi (`hissedildi`) | Türkiye ve Mw ≥ 4,5 | 81 il merkezinde medyan MMI, en yüksek 10 il çubuğu | Allen vd. (2012) IPE; il sınırları Natural Earth | Tahmini şiddettir, ölçüm değildir |
| 3 | Dünya depremi (`dunya`) | dünya ve Mw ≥ 6 | merkez üssüne ortalanmış dünya haritası, Türkiye'ye uzaklık, tsunami / PAGER | USGS (kamu malı), EMSC; Natural Earth | Tarih çizgisinde (±180°) harita ortalanır, halka kesilmez |
| 4 | Levha sınırı (`levha`) | dünya ve Mw ≥ 7 | bölge haritası, PB2002 levha sınırları, en yakın sınır ve türü | PB2002, Bird (2003), ODC-By | Atıf kartta yazılıdır |
| 5 | Kaynaklar ne dedi (`kaynaklar`) | kaynaklar arası \|ΔM\| ≥ 0,4 ya da konum farkı ≥ 20 km | her kaynağın noktası ve büyüklüğü | AFAD, Kandilli, EMSC, USGS | Ham kaynak büyüklükleri gösterilir |
| 6 | Enerji karşılaştırması (`enerji`) | Mw ≥ 5,5 | E = 10^(1,5 Mw + 4,8) J, "kaç M4'e eşit", Türkiye'nin son 12 ay enerjisine oran | D1 kataloğu | 12 aylık toplam çizimde hesaplanır |
| 7 | Artçı olasılığı (`artci`) | dizinin ana olayı (Türkiye Mw ≥ 4, dünya Mw ≥ 6; sonsal fit varsa) | Reasenberg–Jones beklenen kümülatif sayı, %10–%90 bandı, gözlenen artçılar | RJ 1989, Page vd. 2016 biçimi | "Tahmin değildir" |
| 8 | 10 dk dizi özeti (`ozet`) | aynı dizide son 10 dakikada kanala ≥ 3 tekil gönderim olacaksa tek özet | il sınırları ve adları olan bölge haritası, 50 km ölçek, olaylar büyüklükle orantılı | D1 kataloğu; Natural Earth | |
| 9 | Dizi gelişimi (`gelisim`) | Mw ≥ 5 dizisinde 24 saat / 3 gün / 7 gün | büyüklük–zaman, Omori uyumu, en büyük artçı ve Båth | D1 kataloğu | Mc üstü olaylar |
| 10 | Derinlik kesiti (`kesit`) | Mw ≥ 5,5 dizisinde 24 saat (≥ 3 derinlikli olay) | dizinin ana doğrultusu (temel bileşen) boyunca mesafe–derinlik | D1 kataloğu | Derinlikler ilk kayıttır, değişebilir |
| 11 | Olağan dışı etkinlik (`olagandisi`) | hücrede bh_p < 0,05 ve canlı p < 0,05; hücre başına günde en çok bir | hücre haritada, gözlenen / beklenen, Poisson %95 aralığı | D1 kataloğu | "Tahmin değildir." |
| 21 | Etki (`etki`) | Türkiye ve yakın Mw ≥ 6, dünya Mw ≥ 7, USGS kimliği olan olay; olay + 45 dk, ürün çıkana kadar 10 dk'da bir, olay + 3 saatte vazgeçilir | USGS ShakeMap MMI konturları, kırılma çizgisi, DYFI bildirim sayısı | USGS ShakeMap / DYFI (kamu malı) | Ayrı gönderi, sessiz; kayıp ya da PAGER bilgisi yok; ilk sürümler güncellenir |

### Dönemsel kartlar (Cloudflare'deki vesaire cron'u `kart.yml`'i aynı TSİ saatlerinde `workflow_dispatch` ile tetikler; GitHub `schedule` kullanılmaz; başarısızsa o gün atlanır, düz metin yedeği yok)

| # | Kart (tür) | Zaman | Gösterdiği | Veri / lisans | Not |
|---|---|---|---|---|---|
| 12 | Günlük özet (`gunluk`) | her gün 21:00 | günün Mw ≥ 3 depremleri haritada, bölge sayıları | D1 kataloğu | Boş gün de kart olur: "Bugün Mw ≥ 3 deprem kaydedilmedi" |
| 13 | Haftalık özet (`haftalik`) | Pazartesi 08:00 | geçen haftanın haritası, günlük çubuklar, toplam enerji | D1 kataloğu | |
| 14 | Aylık Gutenberg–Richter (`aylikGr`) | ayın 1'i 10:00 | kümülatif büyüklük–sıklık, b ± σ, Mc | EMSC kataloğu (önbellek) | Önceki ayın bloğu yoksa atlanır |
| 15 | Aylık b haritası (`aylikB`) | ayın 1'i 10:30 | 1° hücrelerde b (n ≥ 50) | EMSC kataloğu | n < 50 hücre boş; betimleyicidir, "tahmin değildir" |
| 16 | Arka plan hızı (`ceyreklikLambda`) | Oca / Nis / Tem / Eki 1'i 11:00 | bağımsız deprem hızı λ (yıl⁻¹, M ≥ 4'e çevrilmiş), hücre haritası | EMSC kataloğu, kümeleme ayıklanmış | "Tahmin değildir" |
| 17 | Dünya haftası (`dunyaHafta`) | Pazar 20:00 | son 7 günün Mw ≥ 5 dünya depremleri, levha sınırları | USGS (kamu malı), EMSC; PB2002 | Levha atfı kartta |
| 19 | Uzun dönem olasılık (`uzunDonem`) | ayın 1'i 12:00 | P = 1 − e^(−λT), T = 1 / 10 / 50 yıl, Mw ≥ 5 / 6 / 7; bölge ve Türkiye; bootstrap %10–%90 | EMSC (2018–), USGS uzun katalog (`data/uzun-katalog.json`; gece işi yenilerini önbellekte birleştirir; Mw ≥ 6 ve 7), Gardner–Knopoff ayıklama | Bölgeler birbiriyle kıyaslanmaz; kısa katalog notu; "Olasılık hesabıdır; depremin yeri ve zamanı önceden bilinemez." |
| 20 | Haftalık olasılık, ETAS (`etas`) | Pazartesi 10:00 | önümüzdeki 7 günde en az bir Mw ≥ 5 / 6 olasılığı, Türkiye ve 7 bölge | ETAS (Ogata; Mizrahi vd. 2021) | Yayın kapısı: 52 haftalık ileriye dönük sınavı geçmedikçe kanala gitmez, yalnızca özel sohbete düşer. Ön kayıt: [docs/etas-on-kayit.md](../docs/etas-on-kayit.md) |

## Veri kaynakları ve lisansları

- Natural Earth (ülke ve il sınırları): kamu malı.
- PB2002 levha sınırları: Bird (2003), ODC-By; her levha çizen kartta atıf.
- USGS (olay kataloğu, ShakeMap, DYFI): kamu malı.
- EMSC, AFAD, Kandilli: kaynak olarak anılır; kartlarda yalnızca olay verisi ve kurum adları yer alır.
- Manrope: SIL OFL 1.1.

Sır, sohbet kimliği ya da sahibin konumu hiçbir kartta ve bu belgede yer almaz.
