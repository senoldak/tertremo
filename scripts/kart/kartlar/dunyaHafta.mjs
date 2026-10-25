// Kart 17 — Dünya haftası. Son 7 günün (bugün dahil, TSİ gün sınırlarıyla) dünya kataloğu Mw ≥ 5 depremleri:
// eşdikdörtgen dünya haritası (Pasifik ortada), PB2002 levha sınırları, büyüklükle büyüyen noktalar, Türkiye gri halka.
import { RENK, genislik, kart, sayiTr } from '../cekirdek.mjs';
import { LEVHA_ATIF, dunyaHaritasi, halka } from '../harita.mjs';
import { altBant, bantUyari, not, notUyari } from '../duzen.mjs';
import { GUN_MS, aralikYazi, dunyaOlaylari, dunyaYeri, gunAy, kac, kisalt1024, mwYazi, tsiGunBasi } from './donem.mjs';

export const ESIK = 5;
const MERKEZ = 150;   // Pasifik ateş kuşağı bütün kalsın
const TURKIYE = { enlem: 39.0, boylam: 35.0 };
const NOT = `Mw ≥ 5 · halka: haftanın en büyüğü · gri halka: Türkiye · ${LEVHA_ATIF}`;

/** Pencere: [bas, bit) = 6 gün öncesinin 00:00 TSİ'sinden şimdiye (pazar akşamı kartı: pazartesi–pazar). */
export const pencere = (simdi) => ({ bas: tsiGunBasi(simdi) - 6 * GUN_MS, bit: simdi + 1 });

/** Olaylar → {toplam, buyuk (Mw ≥ 6), en}. */
export function ozetle(olaylar) {
  return { toplam: olaylar.length, buyuk: olaylar.filter((o) => o.mw >= 6).length, en: olaylar[0] ?? null };
}

/** Telegram açıklaması (HTML, ≤ 1024). `ad`: olay → Türkçe yer. */
export function aciklama(olaylar, bas, bit, ad = dunyaYeri) {
  const ust = `🌍 <b>Dünya haftası · ${aralikYazi(bas, bit)}</b>`;
  if (!olaylar.length) return kisalt1024(`${ust}\nBu hafta dünyada Mw ≥ 5 deprem kaydedilmedi.`);
  const z = ozetle(olaylar);
  const satirlar = [ust, `Mw ≥ 5: ${z.toplam} deprem · Mw ≥ 6: ${z.buyuk}`, 'En büyükler:'];
  olaylar.slice(0, 5).forEach((o, i) => satirlar.push(`${i + 1}. ${mwYazi(o)} · ${kac(ad(o))} · ${gunAy(o.zaman)}`));
  return kisalt1024(satirlar.join('\n'));
}

const R_MIN = 4, R_ADIM = 5, R_MAKS = 20;
const yaricap = (mw) => Math.min(R_MAKS, R_MIN + Math.max(0, mw - ESIK) * R_ADIM);

/** → {svg, uyari}. */
export function dunyaHaftaSvg(olaylar, bas, bit, ad = dunyaYeri) {
  const h = dunyaHaritasi({ boylamMerkez: MERKEZ, levha: true });
  let ic = halka(h.px(TURKIYE.boylam), h.py(TURKIYE.enlem), 10, 3.5, RENK.gri);
  const sirali = [...olaylar].sort((a, b) => a.mw - b.mw);
  const en = sirali.at(-1);
  for (const o of sirali) {
    if (o === en) continue;
    ic += `<circle cx="${h.px(o.boylam).toFixed(1)}" cy="${h.py(o.enlem).toFixed(1)}" r="${yaricap(o.mw).toFixed(1)}" fill="${RENK.indigo}" fill-opacity="0.5" stroke="${RENK.kagit}" stroke-width="1.5"/>`;
  }
  if (en) ic += halka(h.px(en.boylam), Math.min(560 - 26, Math.max(26, h.py(en.enlem))), yaricap(en.mw) + 6, 6, RENK.indigo);
  let s = h.zemin + `<svg x="0" y="0" width="1200" height="560" viewBox="0 0 1200 560" overflow="hidden">${ic}</svg>`;
  const z = ozetle(olaylar);
  const baslik = `Dünya haftası · ${aralikYazi(bas, bit)}`;
  const bant = z.en
    ? {
      sayi: sayiTr(z.toplam), birim: 'deprem · Mw ≥ 5', baslik,
      satir1: `En büyüğü ${mwYazi(z.en)} · ${ad(z.en)} · ${gunAy(z.en.zaman)}`,
      satir2: `Mw ≥ 6: ${z.buyuk} · Mw 5–6: ${z.toplam - z.buyuk}`,
    }
    : { sayi: '0', birim: 'deprem · Mw ≥ 5', baslik, satir1: 'Bu hafta dünyada Mw ≥ 5 deprem kaydedilmedi', satir2: 'Dünya kataloğu' };
  s += `<rect x="44" y="524" width="${(genislik(NOT, 18) + 24).toFixed(1)}" height="32" rx="8" fill="${RENK.kagit}" fill-opacity="0.88"/>` + not(NOT) + altBant(bant);
  return { svg: s, uyari: [...bantUyari(bant), ...notUyari(NOT)] };
}

/** Dönemsel üretici: (kartVeri, {simdi, db}) → {png, aciklama, hedef: 'kanal'}. Boş hafta da kart olur. */
export async function dunyaHafta(_kartVeri, { simdi = Date.now(), db } = {}) {
  const d1 = db ?? (await import('../d1.mjs'));
  const { bas, bit } = pencere(simdi);
  const olaylar = await dunyaOlaylari(d1, bas, bit, ESIK);
  const onbellek = new Map();
  const ad = (o) => { if (!onbellek.has(o)) onbellek.set(o, dunyaYeri(o)); return onbellek.get(o); };
  const r = dunyaHaftaSvg(olaylar, bas, bit, ad);
  if (r.uyari.length) console.warn('dünya haftası kartı düzen uyarısı:', r.uyari.join(' | '));
  return { png: await kart(r.svg), aciklama: aciklama(olaylar, bas, bit, ad), hedef: 'kanal' };
}
