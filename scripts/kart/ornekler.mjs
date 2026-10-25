// 21 kartın hepsini örnek veriyle çizer (görsel denetim ve sahibe pafta için).
// Kullanım: node scripts/kart/ornekler.mjs [çıktı-klasörü]   → kart-01.png … kart-21.png + pafta-tum.png
// Dönemsel kartlarda veri uydurmadır; köşede "ÖRNEK" damgası taşırlar. Olay kartları gerçekçi örnek olay verisiyle çizilir.
// Hiçbir ağ çağrısı, sır ya da D1 yok: D1 yerine sahte db, USGS yerine test paketindeki kayıtlı ShakeMap yanıtı kullanılır.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';
import { OLAY_CIZICILER, DONEMSEL } from './calistir.mjs';
import { RENK, yazi } from './cekirdek.mjs';

const KOK = fileURLToPath(new URL('../../', import.meta.url));
const klasor = path.resolve(process.argv[2] ?? path.join(KOK, 'ornek'));
fs.mkdirSync(klasor, { recursive: true });

const SAAT = 3_600_000;
const GUN = 86_400_000;
const DK = 60_000;
const T0 = Date.UTC(2026, 9, 24, 8, 32, 5);                  // 24 Ekim 2026 11:32 TSİ
const GUNLUK_ZAMAN = Date.UTC(2026, 9, 24, 18, 0, 0);        // 21:00 TSİ
const HAFTALIK_ZAMAN = Date.UTC(2026, 9, 26, 5, 0, 0);       // Pazartesi 08:00 TSİ
const DUNYA_HAFTA_ZAMAN = Date.UTC(2026, 9, 25, 17, 0, 0);   // Pazar 20:00 TSİ
const AYLIK_ZAMAN = Date.UTC(2026, 10, 1, 4, 0, 0);          // 1 Kasım 2026 07:00 TSİ
const CEYREK_ZAMAN = Date.UTC(2027, 0, 1, 5, 0, 0);          // 1 Ocak 2027
const TARIHTE_ZAMAN = Date.UTC(2026, 7, 17, 6, 0, 0);        // 17 Ağustos: Kocaeli 1999

// Deterministik sahte rastgele (örnekler her çalıştırmada aynı çıksın).
let tohum = 7;
const rnd = () => { tohum = (tohum * 16807) % 2147483647; return (tohum - 1) / 2147483646; };

// ---------- olay kartları ----------
const kaynaklarTR = {
  afad: { id: '1', buyukluk: 5.9, tur: 'Mw', mw: 5.9, enlem: 38.245, boylam: 38.905, derinlik: 7 },
  kandilli: { id: '2', buyukluk: 5.4, tur: 'ML', mw: 5.4, enlem: 38.31, boylam: 38.99, derinlik: 5 },
  emsc: { id: '3', buyukluk: 5.7, tur: 'Mw', mw: 5.7, enlem: 38.2, boylam: 38.85 },
};
const olayTR = {
  id: 'afad:1', zaman: T0, enlem: 38.245, boylam: 38.905, derinlik: 7, mw: 5.9, tur: 'Mw', kaynak: 'afad', yer: 'PÜTÜRGE (MALATYA)',
  il: 'Malatya', ilce: 'Pütürge', bolge: 'turkiye', katalog: 'tr', baslik: 'Malatya / Pütürge', kaynaklar: kaynaklarTR,
};
const olayDunyaKermadec = {
  id: 'usgs:x', zaman: T0, enlem: -29.9, boylam: -177.8, derinlik: 35, mw: 7.1, tur: 'Mw', yer: 'KERMADEC ISLANDS', bolge: 'dunya', katalog: 'dunya',
  tsunami: 1, pager: 'yellow', baslik: 'Kermadec Adaları, Yeni Zelanda', kaynaklar: { usgs: { id: 'us1', buyukluk: 7.1 }, emsc: { id: 'e1', buyukluk: 7.0 } },
};

// Sındırgı tipi dizi: 24 saat Omori benzeri artçılar
const ANA_SINDIRGI = { id: 'a', zaman: T0 - 24 * SAAT, enlem: 39.24, boylam: 28.18, derinlik: 8, mw: 6.1, tur: 'Mw', bolge: 'turkiye', katalog: 'tr', baslik: 'Balıkesir / Sındırgı', il: 'Balıkesir', ilce: 'Sındırgı' };
function diziOlaylari(n, saat, mc) {
  const l = [];
  for (let i = 0; i < n; i++) {
    const t = DK * 3 * (1 + i) ** 1.5 * (saat / 24) ** 0.5;
    if (t > saat * 60 * DK) break;
    l.push({
      zaman: ANA_SINDIRGI.zaman + t, enlem: 39.24 + 0.012 * Math.sin(i * 1.3), boylam: 28.18 + 0.004 * (i % 40) - 0.08,
      derinlik: 5 + ((i * 7) % 9), mw: mc + ((i * 37) % 23) / 10,
    });
  }
  return l;
}
const ARTCI_PARAM = { a_ort: -2.42, a_sapma: 0.63, p: 0.98, c: 0.018, b: 1 };
const dizi24 = { id: 'a', ana: ANA_SINDIRGI, olaylar: diziOlaylari(110, 24, 2.0), saat: 24, mc: 2.0 };
dizi24.toplam = dizi24.olaylar.length;

const veriArtci = {
  olay: ANA_SINDIRGI,
  artci: {
    satirlar: [{ m: 4, orta: 0.83, alt: 0.4, ust: 0.97 }, { m: 5, orta: 0.21, alt: 0.07, ust: 0.45 }],
    param: ARTCI_PARAM, Mana: 6.1, mc: 2.0, t_simdi_gun: 0.02,
    gozlenen: [{ t_gun: 0.011, mw: 3.4 }, { t_gun: 0.015, mw: 3.1 }, { t_gun: 0.019, mw: 2.2 }, { t_gun: 0.02, mw: 2.6 }],
  },
};
const ozetDizi = {
  id: 'd', ana: { zaman: T0, enlem: 39.24, boylam: 28.18, mw: 3.8 },
  olaylar: [[39.24, 28.18, 3.8], [39.36, 28.0, 3.1], [39.1, 28.4, 3.0], [39.31, 28.3, 3.3], [39.18, 28.05, 3.5], [39.4, 28.22, 2.9]]
    .map(([enlem, boylam, mw], i) => ({ zaman: T0 + i * DK, enlem, boylam, mw, derinlik: 8 })),
};

// Etki: test paketindeki kayıtlı USGS ShakeMap yanıtı (Kahramanmaraş 2023, USGS kamu malı)
const FX = JSON.parse(fs.readFileSync(path.join(KOK, 'test', 'kart', 'veri', 'etki-us6000jllz.json'), 'utf8'));
const OLAY_URL = 'https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=us6000jllz&format=geojson';
const sm = FX.olay.properties.products.shakemap[0].contents;
const sahteUsgs = async (url) => {
  const u = String(url);
  if (u === OLAY_URL) return Response.json(FX.olay);
  if (u === sm['download/cont_mmi.json'].url) return Response.json(FX.kontur);
  if (u === sm['download/rupture.json'].url) return Response.json(FX.rupture);
  return new Response('?', { status: 404 });
};
const olayEtki = {
  id: 'us6000jllz', zaman: Date.UTC(2023, 1, 6, 1, 17, 34), enlem: 37.2256, boylam: 37.0143, derinlik: 10, mw: 7.8, tur: 'Mww',
  kaynak: 'afad', bolge: 'turkiye', baslik: 'Kahramanmaraş / Pazarcık', kaynaklar: { usgs: { id: 'us6000jllz', buyukluk: 7.8, tur: 'Mww' } },
};

// ---------- dönemsel kartlar: uydurma veri ----------
const sahteDb = (satirlar) => ({ sorgu: async () => ({ satirlar, degisen: 0 }) });
const gunOlay = (ek = {}) => ({ zaman: GUNLUK_ZAMAN - 1000, enlem: 38.3, boylam: 38.4, derinlik: 8, mw: 3.4, tur: 'Mw', il: 'Malatya', ilce: 'Pütürge', yer: 'X', bolge: 'turkiye', ...ek });
const ILLER = [['Malatya', 'Pütürge', 38.25, 38.9], ['Elazığ', 'Sivrice', 38.45, 39.3], ['Balıkesir', 'Sındırgı', 39.24, 28.18], ['İzmir', 'Seferihisar', 38.2, 26.8], ['Muğla', 'Datça', 36.7, 27.7], ['Van', 'Erciş', 39.0, 43.3], ['Kahramanmaraş', 'Elbistan', 38.2, 37.2], ['Çanakkale', 'Ayvacık', 39.6, 26.4], ['Adana', 'Kozan', 37.4, 35.8], ['Bingöl', 'Karlıova', 39.3, 41.0]];
const gunlukOlaylar = Array.from({ length: 24 }, (_, i) => {
  const [il, ilce, enlem, boylam] = ILLER[i % ILLER.length];
  return gunOlay({ zaman: GUNLUK_ZAMAN - (i + 1) * 40 * DK, enlem: enlem + (rnd() - 0.5) * 0.3, boylam: boylam + (rnd() - 0.5) * 0.3, mw: 3 + Math.round(rnd() * 15) / 10 + (i === 3 ? 0.9 : 0), il, ilce, bolge: i % 6 === 5 ? 'yakin' : 'turkiye' });
});
const HAFTA_BAS = Date.UTC(2026, 9, 18, 21, 0, 0);           // 19 Ekim 00:00 TSİ (geçen hafta)
const haftalikOlaylar = Array.from({ length: 140 }, (_, i) => {
  const [il, ilce, enlem, boylam] = ILLER[i % ILLER.length];
  return gunOlay({ zaman: HAFTA_BAS + Math.floor(rnd() * 7 * GUN), enlem: enlem + (rnd() - 0.5) * 0.4, boylam: boylam + (rnd() - 0.5) * 0.4, mw: 3 + Math.round(-Math.log(1 - rnd() * 0.97) * 4) / 10 + (i === 9 ? 1.4 : 0), il, ilce });
});
const DUNYA_YERLERI = [[36, 138.5, 'Honshu'], [-6.2, 105.8, 'Java'], [-33.2, -71.9, 'Şili'], [15.1, -93.2, 'Meksika'], [51.9, 177.5, 'Aleut'], [-20.1, -176.4, 'Tonga'], [28.3, 84.7, 'Nepal'], [0.5, 126.4, 'Molukalar'], [-9.8, 160.2, 'Solomon'], [38.1, 21.9, 'Yunanistan']];
const dunyaOlaylar = DUNYA_YERLERI.map(([enlem, boylam, yer], i) => ({
  zaman: DUNYA_HAFTA_ZAMAN - (i + 1) * 14 * SAAT, enlem, boylam, derinlik: 15 + i * 9, mw: [6.4, 5.2, 5.8, 5.5, 6.1, 5.3, 5.1, 5.9, 5.4, 5.2][i], tur: 'Mw', il: null, ilce: null, yer, bolge: 'dunya',
}));

function sentetikGR(b, mc, n0, mMax = 6.0) {
  const hist = [];
  const kum = (m) => n0 * 10 ** (-b * (m - (mc - 0.05)));
  for (let m = mc; m <= mMax + 1e-9; m = Math.round((m + 0.1) * 10) / 10) {
    const c = Math.round(kum(m - 0.05) - kum(m + 0.05));
    if (c > 0) hist.push([m, c]);
  }
  for (let m = 1.5; m < mc - 1e-9; m = Math.round((m + 0.1) * 10) / 10) hist.push([Math.round(m * 10) / 10, Math.round(0.5 * n0 * 0.1 * (m - 1))]);
  return hist.sort((x, y) => x[0] - y[0]);
}
const grHist = sentetikGR(1.0, 2.4, 3000);
const grBlok = { ay: '2026-10', n: 3000, toplam: grHist.reduce((t, [, c]) => t + c, 0), mc: 2.4, b: 1.03, sigma: 0.04, dm: 0.1, histogram: grHist };

const hucreler = [];
for (let la = 35; la <= 42; la++) {
  for (let lo = 26; lo <= 44; lo++) {
    const n = Math.floor(10 + rnd() * rnd() * 900);
    const dolu = n >= 50;
    hucreler.push({
      anahtar: `${la}_${lo}`, mc: 2.6 + rnd() * 0.8, n, b: dolu ? 0.75 + rnd() * 0.6 : null, sigma_b: dolu ? 0.04 + rnd() * 0.18 : null, lambda: Math.round(rnd() * rnd() * 90 * 10) / 10,
    });
  }
}
const hucreVeri = (zaman) => ({ hesap: zaman - 3600e3, baslangic: Date.UTC(2018, 0, 1), hucreler, turkiyeB: 1.02 });

const olasTablo = (k) => {
  const c = (v) => v.map((x) => Math.min(1, x));
  return {
    1: { 5: c([0.6 * k, 0.5 * k, 0.7 * k]), 6: c([0.07 * k, 0.04 * k, 0.1 * k]), 7: c([0.01 * k, 0.003 * k, 0.02 * k]) },
    10: { 5: [0.98, 0.95, 0.999], 6: c([0.5 * k, 0.35 * k, 0.65 * k]), 7: c([0.1 * k, 0.04 * k, 0.17 * k]) },
    50: { 5: [1, 1, 1], 6: c([0.95 * k, 0.9 * k, 0.99 * k]), 7: c([0.45 * k, 0.2 * k, 0.7 * k]) },
  };
};
const uzunBlok = {
  surum: 'uzun-1', hesap: Date.UTC(2026, 10, 1, 5), baslangic: Date.UTC(2018, 0, 1), bitis: Date.UTC(2026, 10, 1, 6), yil: 8.8, mc: 3.0, kumeleme: 'en-yakin-komsu', bootstrap: 1000,
  uzunKatalog: { yontem: 'gardner-knopoff', kaynak: 'USGS FDSN', bas6: 1930, bas7: 1900, n6: 72, n7: 20 },
  turkiye: { n: 657, n6: 72, n7: 20, b: 1.13, olasilik: olasTablo(1.6) },
  bolgeler: [['Marmara', 0.9], ['Ege', 1.4], ['Akdeniz', 0.6], ['İç Anadolu', 0.3], ['Karadeniz', 0.15], ['Doğu Anadolu', 1.7]]
    .map(([ad, k]) => ({ ad, n: 200, b: 1.0, kendiB: true, olasilik: olasTablo(k) })),
};

const etasBas = Date.UTC(2026, 9, 24, 3, 0, 0);
const etasVeri = {
  etas: {
    surum: 'etas-2', hesap: etasBas, baslangic: etasBas, bitis: etasBas + 7 * GUN, mod: 'etas', neden: '', simulasyon: 10000,
    turkiye: { p5: 0.183, p6: 0.021, norm5: 0.121, norm6: 0.012 },
    bolgeler: [['Marmara', 0.012, 0.009], ['Ege', 0.05, 0.04], ['Akdeniz', 0.03, 0.025], ['İç Anadolu', 0.004, 0.006], ['Karadeniz', 0.002, 0.003], ['Doğu Anadolu', 0.061, 0.04], ['Güneydoğu Anadolu', 0.02, 0.015]]
      .map(([ad, p5, norm5]) => ({ ad, p5, p6: p5 / 10, norm5, norm6: norm5 / 10 })),
    kapi: { gecti: null, ozet: 'doğrulama yapılmadı', gizliHafta: 0, yayin: false },
  },
};

// ---------- kart listesi ----------
const png = (c) => (c?.png ?? c);
const CIZIM = [
  [1, 'Deprem', () => OLAY_CIZICILER.deprem({ olay: olayTR })],
  [2, 'Nerelerde hissedildi', () => OLAY_CIZICILER.hissedildi({ olay: olayTR })],
  [3, 'Dünya depremi', () => OLAY_CIZICILER.dunya({ olay: olayDunyaKermadec })],
  [4, 'Levha sınırı', () => OLAY_CIZICILER.levha({ olay: olayDunyaKermadec })],
  [5, 'Kaynaklar ne dedi', () => OLAY_CIZICILER.kaynaklar({ olay: olayTR })],
  [6, 'Enerji karşılaştırması', () => OLAY_CIZICILER.enerji({ olay: olayTR }, null)],
  [7, 'Artçı olasılığı', () => OLAY_CIZICILER.artci(veriArtci)],
  [8, '10 dk dizi özeti', () => OLAY_CIZICILER.ozet({ olay: { ...olayTR, baslik: 'Balıkesir / Sındırgı', il: 'Balıkesir', ilce: 'Sındırgı' }, dizi: ozetDizi })],
  [9, 'Dizi gelişimi', () => OLAY_CIZICILER.gelisim({ olay: ANA_SINDIRGI, dizi: dizi24, artci: { param: ARTCI_PARAM, Mana: 6.1, mc: 2.0 } })],
  [10, 'Derinlik kesiti', () => OLAY_CIZICILER.kesit({ olay: ANA_SINDIRGI, dizi: dizi24, artci: { param: ARTCI_PARAM, Mana: 6.1, mc: 2.0 } })],
  [11, 'Olağan dışı etkinlik', () => OLAY_CIZICILER.olagandisi({
    olay: { ...olayTR, mw: 4.6 }, olagandisi: { k: 14, beklenen: 4.1, p: 0.0001, bh_p: 0.001, hucre: { anahtar: '38_38', enlem: 38, boylam: 38, boyut_derece: 1 }, pencere_gun: 7 },
  })],
  [12, 'Günlük özet', () => DONEMSEL.gunluk({}, { simdi: GUNLUK_ZAMAN, db: sahteDb(gunlukOlaylar) }), true],
  [13, 'Haftalık özet', () => DONEMSEL.haftalik({}, { simdi: HAFTALIK_ZAMAN, db: sahteDb(haftalikOlaylar) }), true],
  [14, 'Aylık Gutenberg–Richter', () => DONEMSEL.aylikGr({ gr: grBlok }, { simdi: AYLIK_ZAMAN }), true],
  [15, 'Aylık b haritası', () => DONEMSEL.aylikB({ hucreler: hucreVeri(AYLIK_ZAMAN) }, { simdi: AYLIK_ZAMAN }), true],
  [16, 'Arka plan hızı (λ)', () => DONEMSEL.ceyreklikLambda({ hucreler: hucreVeri(CEYREK_ZAMAN) }, { simdi: CEYREK_ZAMAN }), true],
  [17, 'Dünya haftası', () => DONEMSEL.dunyaHafta({}, { simdi: DUNYA_HAFTA_ZAMAN, db: sahteDb(dunyaOlaylar) }), true],
  [18, 'Tarihte bugün', () => DONEMSEL.tarihteBugun({}, { simdi: TARIHTE_ZAMAN })],
  [19, 'Uzun dönem olasılık', () => DONEMSEL.uzunDonem({ uzunDonem: uzunBlok }, { simdi: Date.UTC(2026, 10, 1, 9) }), true],
  [20, 'Haftalık olasılık (ETAS)', () => DONEMSEL.etas(etasVeri), true],
  [21, 'Etki (ShakeMap)', async () => (await import('./kartlar/etki.mjs')).etki({ olay: olayEtki }, null, { fetchFn: sahteUsgs })],
];

const ornekDamgasi = async (buf) => {
  const g = 118, y = 36, sol = 200;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800"><rect x="${sol}" y="${y - 26}" width="${g}" height="40" rx="8" fill="${RENK.murekkep}" fill-opacity="0.82"/>${yazi('ÖRNEK', sol + g / 2, y + 2, 22, RENK.kagit, 'middle')}</svg>`;
  return sharp(buf).composite([{ input: Buffer.from(svg) }]).png().toBuffer();
};

const sonuc = [];
for (const [no, ad, uret, damga] of CIZIM) {
  const dosya = `kart-${String(no).padStart(2, '0')}.png`;
  try {
    const c = await uret();
    if (!c) throw new Error('kart üretilmedi (null)');
    let b = png(c);
    if (damga) b = await ornekDamgasi(b);
    fs.writeFileSync(path.join(klasor, dosya), b);
    sonuc.push({ no, ad, dosya, b });
  } catch (e) {
    console.error(`kart ${no} (${ad}) çizilemedi: ${e.message}`);
    sonuc.push({ no, ad, dosya, hata: e.message });
  }
}

// ---------- pafta (3 sütun) ----------
const SUT = 3, KW = 600, KH = 400, ET = 46, BOS = 24;
const satir = Math.ceil(CIZIM.length / SUT);
const PW = SUT * KW + (SUT + 1) * BOS, PH = satir * (KH + ET) + (satir + 1) * BOS;
const parcalar = [];
for (let i = 0; i < sonuc.length; i++) {
  const s = sonuc[i];
  const x = BOS + (i % SUT) * (KW + BOS), y = BOS + Math.floor(i / SUT) * (KH + ET + BOS);
  const etiket = `<svg xmlns="http://www.w3.org/2000/svg" width="${KW}" height="${ET}">${yazi(`${s.no}  ${s.ad}${s.hata ? '  (ÇİZİLEMEDİ)' : ''}`, 0, 32, 26, s.hata ? '#b00020' : RENK.murekkep)}</svg>`;
  const girdi = s.b
    ? await sharp(s.b).resize(KW, KH).png().toBuffer()
    : await sharp({ create: { width: KW, height: KH, channels: 3, background: RENK.deniz } }).png().toBuffer();
  parcalar.push({ input: girdi, left: x, top: y });
  parcalar.push({ input: Buffer.from(etiket), left: x, top: y + KH + 4 });
}
await sharp({ create: { width: PW, height: PH, channels: 3, background: RENK.kagit } }).composite(parcalar).png().toFile(path.join(klasor, 'pafta-tum.png'));

console.log('örnekler:', klasor);
const hatali = sonuc.filter((s) => s.hata);
if (hatali.length) { console.error(`${hatali.length} kart çizilemedi`); process.exitCode = 1; }
