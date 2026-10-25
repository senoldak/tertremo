// Kart 18 — Tarihte bugün. data/tarihte-bugun.json (USGS FDSN, Mw ≥ 6, Türkiye çevresi, 1900–): o günün (gün-ay, Türkiye yerel saati) en büyük
// depremi; aynı güne düşen başkaları alt satırda. Haritada Türkiye çevresi, ana deprem odak halkası, diğerleri gri nokta.
// Dil sade: yorum ve duygu sözcüğü yok. O gün kayıt yoksa null (çağıran hiçbir şey göndermez).
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { RENK, kart, sayiTr } from '../cekirdek.mjs';
import { halka, turkiyeCevresi } from '../harita.mjs';
import { yerelZaman } from '../veri-hazirla.mjs';
import { altBant, bantUyari, not, notUyari } from '../duzen.mjs';

const VERI = fileURLToPath(new URL('../../../data/tarihte-bugun.json', import.meta.url));
const AYLAR = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'];
const NOT = 'Kayıt: USGS, Mw ≥ 6 · Türkiye ve yakın çevresi · yerel saat';

let onbellek;
const tumKayitlar = () => (onbellek ??= JSON.parse(fs.readFileSync(VERI, 'utf8')));

/** "1999-08-17" → "17 Ağustos 1999". */
export const tarihYazi = (t) => { const [y, a, g] = t.split('-').map(Number); return `${g} ${AYLAR[a - 1]} ${y}`; };

/** simdi gününe (Europe/Istanbul) düşen kayıtlar, en büyük önce (eşitte eski önce). */
export function bugunKayitlari(kayitlar, simdi) {
  const d = yerelZaman(simdi).t.slice(5);
  return kayitlar.filter((k) => k.t.slice(5) === d).sort((a, b) => b.mw - a.mw || a.t.localeCompare(b.t));
}

const yilOnce = (k, simdi) => Number(yerelZaman(simdi).t.slice(0, 4)) - Number(k.t.slice(0, 4));
const mwYazi = (k) => sayiTr(k.mw, 1);
const digerleri = (l) => l.slice(1).map((k) => `${k.t.slice(0, 4)} ${k.yer} Mw ${mwYazi(k)}`).join(' · ');

/** Telegram açıklaması (HTML, ≤ 1024). */
export function aciklama(l) {
  const k = l[0];
  let a = `🗓 <b>Tarihte bugün</b>\n${tarihYazi(k.t)} · ${k.yer} · Mw ${mwYazi(k)}`;
  if (l.length > 1) a += `\nAynı gün: ${digerleri(l)}`;
  return a.length > 1024 ? a.slice(0, 1020).replace(/<[^>]*$/, '') + '…' : a;
}

/** → {svg, uyari}: kartın iç SVG'si (logo kart() ile eklenir). */
export function tarihteBugunSvg(l, simdi = Date.now()) {
  const k = l[0];
  const m = turkiyeCevresi();
  let s = m.zemin;
  // Diğer kayıtlar önce (altta), ana deprem üstte
  for (const d of l.slice(1)) s += `<circle cx="${m.px(d.boylam).toFixed(1)}" cy="${m.py(d.enlem).toFixed(1)}" r="8" fill="${RENK.gri}" fill-opacity="0.75" stroke="${RENK.kagit}" stroke-width="2"/>`;
  s += halka(m.px(k.boylam), m.py(k.enlem), 20, 7, RENK.indigo);
  const yil = yilOnce(k, simdi);
  const bant = {
    sayi: mwYazi(k), birim: 'Mw',
    baslik: `${k.yer} · ${tarihYazi(k.t)}`,
    satir1: `Tarihte bugün${yil > 0 ? ` · ${yil} yıl önce` : ''} · saat ${k.s}`,
    satir2: l.length > 1 ? `Aynı gün: ${digerleri(l)}` : `${sayiTr(k.enlem, 2)} K · ${sayiTr(k.boylam, 2)} D`,
  };
  s += not(NOT) + altBant(bant);
  return { svg: s, uyari: [...bantUyari(bant), ...notUyari(NOT)] };
}

/**
 * Dönemsel üretici: (kartVeri, {simdi, kayitlar}) → {png, aciklama, hedef: 'kanal'} ya da o gün kayıt yoksa null.
 * kartVeri kullanılmaz (kart-veri.json olmadan da çalışır).
 */
export async function tarihteBugun(_kartVeri, { simdi = Date.now(), kayitlar = tumKayitlar() } = {}) {
  const l = bugunKayitlari(kayitlar, simdi);
  if (!l.length) return null;
  const r = tarihteBugunSvg(l, simdi);
  if (r.uyari.length) console.warn('tarihte bugün kartı düzen uyarısı:', r.uyari.join(' | '));
  return { png: await kart(r.svg), aciklama: aciklama(l), hedef: 'kanal' };
}
