// Dönemsel kartların (günlük, haftalık, dünya haftası) ortak yardımcıları: TSİ gün sınırları, D1 okumaları (yalnız indeksli,
// sınırlı satır), Türkçe yer adı, enerji eşdeğeri, Telegram açıklaması kısaltma.
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { RENK, sayiTr } from '../cekirdek.mjs';
import { enerjiJ } from './enerji.mjs';
import { HARITA_G, HARITA_Y, halka } from '../harita.mjs';

export const GUN_MS = 86_400_000;
const TSI_MS = 3 * 3_600_000;
export const AYLAR = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'];
export const GUNLER = ['Paz', 'Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt'];   // getUTCDay() sırası (TSİ'ye kaydırılmış tarihte)
const ENCOK_SATIR = 3000;

const tsi = (ms) => new Date(ms + TSI_MS);
const iki = (n) => String(n).padStart(2, '0');

/** ms → o anın TSİ gün başlangıcı (UTC ms). */
export const tsiGunBasi = (ms) => Math.floor((ms + TSI_MS) / GUN_MS) * GUN_MS - TSI_MS;
/** "24 Ekim" */
export const gunAy = (ms) => `${tsi(ms).getUTCDate()} ${AYLAR[tsi(ms).getUTCMonth()]}`;
/** "14:32" (TSİ) */
export const saatTr = (ms) => `${iki(tsi(ms).getUTCHours())}:${iki(tsi(ms).getUTCMinutes())}`;
/** TSİ haftanın gün kısaltması */
export const gunAdi = (ms) => GUNLER[tsi(ms).getUTCDay()];

/** [bas, bit) (UTC ms, bit hariç) → "19–25 Ekim" ya da "28 Ekim – 3 Kasım" (bit−1 ms'ye göre son gün). */
export function aralikYazi(bas, bit) {
  const a = tsi(bas), b = tsi(bit - 1);
  if (a.getUTCMonth() === b.getUTCMonth()) return `${a.getUTCDate()}–${b.getUTCDate()} ${AYLAR[b.getUTCMonth()]}`;
  return `${a.getUTCDate()} ${AYLAR[a.getUTCMonth()]} – ${b.getUTCDate()} ${AYLAR[b.getUTCMonth()]}`;
}

/** Toplam enerji (J) → eşdeğer Mw. */
export const esdegerMw = (j) => (Math.log10(j) - 4.8) / 1.5;
/** Mw dizisi → toplam joule. */
export const toplamJ = (mwler) => mwler.reduce((t, m) => t + enerjiJ(m), 0);
/** "1,2 × 10^12 J" */
export function jouleYazi(e) {
  let us = Math.floor(Math.log10(e));
  let kat = e / 10 ** us;
  if (Number(kat.toFixed(1)) >= 10) { kat /= 10; us += 1; }
  return `${sayiTr(kat, 1)} × 10^${us} J`;
}

/** Telegram açıklamasını ≤ 1024 karakterde tutar; kopuk HTML etiketi bırakmaz. */
export function kisalt1024(a) {
  if (a.length <= 1024) return a;
  return a.slice(0, 1020).replace(/<[^>]*$/, '') + '…';
}

/** HTML kaçışı (Telegram parse_mode HTML). */
export const kac = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

/** Türkiye kataloğu olayının adı: "İl / İlçe", il yoksa kaynağın yer adı. */
export function olayAdi(o) {
  if (o.il) return o.ilce ? `${o.il} / ${o.ilce}` : o.il;
  return o.yer || 'Bilinmeyen yer';
}

// ---- D1 okumaları (hepsi tek sorgu, indeksli, LIMIT'li) ----
const KOLON = 'zaman, enlem, boylam, derinlik, mw, tur, il, ilce, yer, bolge';
const sayi = (x) => (x === null || x === undefined || x === '' ? NaN : Number(x));   // Number(null) = 0 olmasın
const sayisal = (r) => ({ ...r, zaman: sayi(r.zaman), enlem: sayi(r.enlem), boylam: sayi(r.boylam), mw: sayi(r.mw) });
const gecerli = (r) => Number.isFinite(r.mw) && Number.isFinite(r.zaman) && Number.isFinite(r.enlem) && Number.isFinite(r.boylam);

/** Türkiye kataloğu, [bas, bit) aralığı, Mw ≥ esik. İndeks: olay_katalog_zaman. En büyük önce. */
export async function trOlaylari(db, bas, bit, esik = 3) {
  const r = await db.sorgu(
    `SELECT ${KOLON} FROM olay INDEXED BY olay_katalog_zaman WHERE katalog = 'tr' AND zaman >= ? AND zaman < ? AND mw >= ? LIMIT ${ENCOK_SATIR}`,
    [bas, bit, esik],
  );
  return r.satirlar.map(sayisal).filter(gecerli).sort((a, b) => b.mw - a.mw || b.zaman - a.zaman);
}

/** Dünya kataloğu, [bas, bit) aralığı, Mw ≥ esik. İndeks: olay_katalog_mw (katalog, mw, zaman). En büyük önce. */
export async function dunyaOlaylari(db, bas, bit, esik = 5) {
  const r = await db.sorgu(
    `SELECT ${KOLON} FROM olay INDEXED BY olay_katalog_mw WHERE katalog = 'dunya' AND mw >= ? AND zaman >= ? AND zaman < ? LIMIT ${ENCOK_SATIR}`,
    [esik, bas, bit],
  );
  return r.satirlar.map(sayisal).filter(gecerli).sort((a, b) => b.mw - a.mw || b.zaman - a.zaman);
}

// ---- dünya yer adı (ülke içinde: ülke; ≤ 500 km: "<Ülke> açıkları"; yoksa kaynağın adı) ----
const rad = (d) => (d * Math.PI) / 180;
const mesafe = (la1, lo1, la2, lo2) => {
  const a = Math.sin(rad(la2 - la1) / 2) ** 2 + Math.cos(rad(la1)) * Math.cos(rad(la2)) * Math.sin(rad(lo2 - lo1) / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(a));
};
const icinde = (lo, la, h) => {
  let ic = false;
  for (let i = 0, j = h.length - 2; i < h.length; j = i, i += 2) {
    const xi = h[i], yi = h[i + 1], xj = h[j], yj = h[j + 1];
    if (yi > la !== yj > la && lo < ((xj - xi) * (la - yi)) / (yj - yi) + xi) ic = !ic;
  }
  return ic;
};
let ulkeOnbellek;
const ulkeler = () => (ulkeOnbellek ??= JSON.parse(fs.readFileSync(fileURLToPath(new URL('../../../data/harita/ulkeler-dunya.json', import.meta.url)), 'utf8')));

/** Dünya olayının Türkçe adı. */
export function dunyaYeri(o, liste = ulkeler()) {
  const u = liste.find((x) => x.r.some((h) => icinde(o.boylam, o.enlem, h)));
  if (u) return u.ad;
  let en = Infinity, ad = null;
  for (const x of liste) {
    let m = Infinity;
    for (const h of x.r) for (let i = 0; i < h.length; i += 2) m = Math.min(m, mesafe(o.enlem, o.boylam, h[i + 1], h[i]));
    if (m < en) { en = m; ad = x.ad; }
  }
  if (ad && en <= 500) return `${ad} açıkları`;
  return o.yer || 'Bilinmeyen yer';
}

/** Mw yazısı: "Mw 4,1" (veritabanındaki mw dönüştürülmüş Mw'dir). */
export const mwYazi = (o) => `Mw ${sayiTr(o.mw, 1)}`;

/**
 * Harita üstüne olay noktaları: yarıçap Mw ile büyür (eşikte rMin), en büyük olay odak halkası. m: {px, py}.
 * Küçükler önce çizilir (üstte büyükler görünür). Harita alanına kırpılır.
 */
export function noktalar(m, olaylar, { esik, rMin = 5, rAdim = 4.5, rMaks = 22 } = {}) {
  if (!olaylar.length) return '';
  const sirali = [...olaylar].sort((a, b) => a.mw - b.mw);
  const en = sirali[sirali.length - 1];
  let ic = '';
  for (const o of sirali) {
    if (o === en) continue;
    const r = Math.min(rMaks, rMin + Math.max(0, o.mw - esik) * rAdim);
    ic += `<circle cx="${m.px(o.boylam).toFixed(1)}" cy="${m.py(o.enlem).toFixed(1)}" r="${r.toFixed(1)}" fill="${RENK.indigo}" fill-opacity="0.5" stroke="${RENK.kagit}" stroke-width="1.5"/>`;
  }
  ic += halka(m.px(en.boylam), m.py(en.enlem), Math.min(rMaks, rMin + Math.max(0, en.mw - esik) * rAdim) + 6, 6, RENK.indigo);
  return `<svg x="0" y="0" width="${HARITA_G}" height="${HARITA_Y}" viewBox="0 0 ${HARITA_G} ${HARITA_Y}" overflow="hidden">${ic}</svg>`;
}
