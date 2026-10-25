// Kart 12 — Günlük. Bugünün (TSİ 00:00'dan şimdiye) Türkiye kataloğu Mw ≥ 3 depremleri: Türkiye çevresi haritası, bölge bölge sayı
// (Türkiye / yakın çevre), en büyüğü. Gün boşsa "Bugün Mw ≥ 3 deprem kaydedilmedi" kartı yine gönderilir.
import { kart, sayiTr } from '../cekirdek.mjs';
import { turkiyeCevresi } from '../harita.mjs';
import { altBant, bantUyari, not, notUyari } from '../duzen.mjs';
import { gunAy, kac, kisalt1024, noktalar, olayAdi, mwYazi, saatTr, trOlaylari, tsiGunBasi } from './donem.mjs';

export const ESIK = 3;
const NOT = 'Türkiye kataloğu · Mw ≥ 3 · halka: günün en büyüğü · nokta büyüklüğü Mw ile artar';
const NOT_BOS = 'Türkiye kataloğu · Mw ≥ 3 · gün 00:00 TSİ’den kart saatine kadar';

/** Olaylar (en büyük önce) → {toplam, turkiye, yakin, en}. */
export function ozetle(olaylar) {
  const turkiye = olaylar.filter((o) => o.bolge === 'turkiye').length;
  return { toplam: olaylar.length, turkiye, yakin: olaylar.length - turkiye, en: olaylar[0] ?? null };
}

/** Telegram açıklaması (HTML, ≤ 1024). */
export function aciklama(olaylar, simdi) {
  const ust = `📅 <b>Bugün · ${gunAy(simdi)}</b>`;
  if (!olaylar.length) return kisalt1024(`${ust}\nBugün Mw ≥ 3 deprem kaydedilmedi.`);
  const z = ozetle(olaylar);
  let a = `${ust}\nTürkiye ve çevresinde Mw ≥ 3: ${z.toplam} deprem · en büyüğü ${mwYazi(z.en)} (${kac(olayAdi(z.en))})`;
  if (z.yakin) a += `\nTürkiye ${z.turkiye} · yakın çevre ${z.yakin}`;
  return kisalt1024(a);
}

/** → {svg, uyari}. */
export function gunlukSvg(olaylar, simdi) {
  const m = turkiyeCevresi();
  const z = ozetle(olaylar);
  const bos = !olaylar.length;
  const bant = bos
    ? { sayi: '0', birim: 'deprem · Mw ≥ 3', baslik: 'Bugün Mw ≥ 3 deprem kaydedilmedi', satir1: `${gunAy(simdi)} · Türkiye ve yakın çevresi`, satir2: 'Kayıt: 00:00 TSİ’den kart saatine kadar' }
    : {
      sayi: sayiTr(z.toplam), birim: 'deprem · Mw ≥ 3', baslik: `Bugün · ${gunAy(simdi)}`,
      satir1: `Türkiye ${z.turkiye} · yakın çevre ${z.yakin}`,
      satir2: `En büyüğü ${mwYazi(z.en)} · ${olayAdi(z.en)} · ${saatTr(z.en.zaman)}`,
    };
  const metin = bos ? NOT_BOS : NOT;
  const svg = m.zemin + noktalar(m, olaylar, { esik: ESIK }) + not(metin) + altBant(bant);
  return { svg, uyari: [...bantUyari(bant), ...notUyari(metin)] };
}

/**
 * Dönemsel üretici: (kartVeri, {simdi, db}) → {png, aciklama, hedef: 'kanal'}. Boş gün de kart olur.
 * Günün sınırı: TSİ 00:00 → şimdi (kart 21:00 TSİ'de gider).
 */
export async function gunluk(_kartVeri, { simdi = Date.now(), db } = {}) {
  const d1 = db ?? (await import('../d1.mjs'));
  const olaylar = await trOlaylari(d1, tsiGunBasi(simdi), simdi + 1, ESIK);
  const r = gunlukSvg(olaylar, simdi);
  if (r.uyari.length) console.warn('günlük kart düzen uyarısı:', r.uyari.join(' | '));
  return { png: await kart(r.svg), aciklama: aciklama(olaylar, simdi), hedef: 'kanal' };
}
