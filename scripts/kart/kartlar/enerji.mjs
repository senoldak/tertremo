// Kart 6: Enerji. E = 10^(1,5·Mw + 4,8) J (Gutenberg–Richter). "≈ N tane M4" log ölçekli çubuklarla; varsa
// Türkiye'nin son 12 aylık toplam enerjisine oran (Actions D1'den hesaplar; alınamazsa o satır çizilmez).
import { RENK, kart, sayiTr, tarihTr, yazi } from '../cekirdek.mjs';
import { altBant, bantUyari, not, notUyari } from '../duzen.mjs';
import { olayBaslik } from './deprem.mjs';

const YIL_MS = 365 * 86_400_000;

/** Mw → enerji (joule). */
export const enerjiJ = (mw) => 10 ** (1.5 * mw + 4.8);
/** Mw → kaç tane M4 depremine eşdeğer (10^(1,5·(Mw−4))). */
export const m4Esdeger = (mw) => 10 ** (1.5 * (mw - 4));

/** Kutular: [{k, n}] (k = round(mw·20) → 0,05'lik büyüklük kutusu, n = adet) → toplam joule. */
export function toplamEnerji(kutular) {
  return kutular.reduce((t, { k, n }) => t + n * enerjiJ(k / 20), 0);
}

/** Türkiye kataloğunun son 12 aylık toplam enerjisi (J). Tek toplu sorgu (olay_katalog_zaman indeksi). Hata fırlatır. */
export async function enerji12AyHesapla({ db, simdi = Date.now() } = {}) {
  const d1 = db ?? (await import('../d1.mjs'));
  const r = await d1.sorgu(
    'SELECT CAST(ROUND(mw * 20) AS INTEGER) AS k, COUNT(*) AS n FROM olay WHERE katalog = ? AND zaman > ? AND mw IS NOT NULL GROUP BY k',
    ['tr', simdi - YIL_MS],
  );
  const kutular = r.satirlar.map((x) => ({ k: Number(x.k), n: Number(x.n) })).filter((x) => Number.isFinite(x.k) && Number.isFinite(x.n));
  return kutular.length ? toplamEnerji(kutular) : null;
}

let onbellek = null; // süreç başına bir kez: kuyruktaki birden çok enerji kartı aynı sorguyu paylaşır
/** Çizici girişi: D1 hazır değilse ya da sorgu düşerse null (kart oransız çizilir). db verilirse önbelleksiz. */
export async function enerji12Ay({ db } = {}) {
  if (db) {
    try { return await enerji12AyHesapla({ db }); } catch (e) { console.warn('12 aylık enerji alınamadı:', e.message); return null; }
  }
  const d1 = await import('../d1.mjs');
  if (!d1.hazir()) return null;
  onbellek ??= enerji12AyHesapla({}).catch((e) => { console.warn('12 aylık enerji alınamadı:', e.message); return null; });
  return onbellek;
}

/** 12 aylık toplamla oran metni: "%12,3" (< 1) ya da "3,4 kat" (≥ 1). */
export function oranMetni(e, toplam) {
  if (!(toplam > 0) || !Number.isFinite(e)) return null;
  const r = e / toplam;
  if (r >= 1) return `${sayiTr(r, r < 10 ? 1 : 0)} kat`;
  const yuzde = r * 100;
  return `%${sayiTr(yuzde, yuzde < 10 ? 1 : 0)}`;
}

/** Joule → "1,6 × 10^15 J". */
export function jouleMetni(e) {
  let us = Math.floor(Math.log10(e));
  let kat = e / 10 ** us;
  if (Number(kat.toFixed(1)) >= 10) { kat /= 10; us += 1; }
  return `${sayiTr(kat, 1)} × 10^${us} J`;
}

const nMetni = (n) => (n >= 100 ? sayiTr(Math.round(n)) : sayiTr(n, n >= 1 ? 1 : 2));

/** → {svg, uyari, n, enerji, oran}. */
export function enerjiSvg(veri, { toplam12 } = {}) {
  const o = veri.olay;
  const mw = o.mw;
  if (!Number.isFinite(mw)) throw new Error('enerji kartı: olay.mw yok');
  const E = enerjiJ(mw), N = m4Esdeger(mw);
  const toplam = toplam12 ?? veri.enerji12Ay ?? null;
  const oran = oranMetni(E, toplam);

  // Çubuk merdiveni: tam büyüklükler (M4…) ve olay; uzunluk log10(N)
  const tamlar = [];
  for (let m = 4; m <= Math.ceil(mw) + 0.0001 && tamlar.length < 7; m++) tamlar.push(m);
  const satirlar = tamlar.filter((m) => Math.abs(m - mw) > 0.05).map((m) => ({ m, olay: false }));
  satirlar.push({ m: mw, olay: true });
  satirlar.sort((a, b) => a.m - b.m);
  const lo = Math.min(0, Math.log10(N)) - 0.6, hi = Math.log10(N) + 0.25;
  const x0 = 250, xMax = 1010, ust = 150, adim = Math.min(56, 330 / satirlar.length);
  let s = '';
  s += yazi('Aynı enerjiyi kaç tane M4 depremi verir?', 56, 124, 24, RENK.gri);
  satirlar.forEach((r, i) => {
    const y = ust + 20 + i * adim;
    const n = m4Esdeger(r.m);
    const g = Math.max(8, ((Math.log10(n) - lo) / (hi - lo)) * (xMax - x0));
    s += yazi(`Mw ${sayiTr(r.m, 1)}`, 56, y + 10, r.olay ? 26 : 22, r.olay ? RENK.murekkep : RENK.gri);
    s += `<rect x="${x0}" y="${y - 14}" width="${g.toFixed(1)}" height="${(adim * 0.62).toFixed(1)}" rx="4" fill="${r.olay ? RENK.indigo : RENK.ince}"/>`;
    s += yazi(`× ${nMetni(n)}`, x0 + g + 14, y + 10, r.olay ? 26 : 22, r.olay ? RENK.indigo : RENK.gri);
  });
  const altY = ust + 20 + satirlar.length * adim + 22;
  s += yazi(`E = 10^(1,5 · Mw + 4,8) J  →  yaklaşık ${jouleMetni(E)}`, 56, Math.min(altY + 18, 500), 22, RENK.murekkep);

  const notMetni = 'Çubuk uzunluğu log ölçeklidir: 1 büyüklük ≈ 31,6 kat enerji · Gutenberg–Richter bağıntısı, ortalama değerdir';
  const bant = {
    sayi: `×${nMetni(N)}`, birim: 'M4 deprem eşdeğeri', baslik: olayBaslik(veri),
    satir1: `Mw ${sayiTr(mw, 1)} · yaklaşık enerji ${jouleMetni(E)}`,
    satir2: oran ? `Türkiye ve çevresinin son 12 ay toplamına oranı: ${oran}` : tarihTr(o.zaman, { saniye: false }),
  };
  s += not(notMetni) + altBant(bant);
  return { svg: s, uyari: [...bantUyari(bant).filter((u) => !u.startsWith('sayı küçültüldü')), ...notUyari(notMetni)], n: N, enerji: E, oran };
}

/** Kart 6 çizicisi: veri → PNG Buffer. toplam12: 12 aylık Türkiye enerjisi (J); verilmezse D1'den alınır. */
export async function enerji(veri, satir, { toplam12 } = {}) {
  const t = toplam12 ?? veri.enerji12Ay ?? (await enerji12Ay());
  const r = enerjiSvg(veri, { toplam12: t });
  if (r.uyari.length) console.warn('enerji kartı düzen uyarısı:', r.uyari.join(' | '));
  return kart(r.svg);
}
