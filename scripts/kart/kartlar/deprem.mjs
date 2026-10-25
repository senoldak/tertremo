// Kart 1: Deprem. Türkiye ve yakın çevre: sabit Türkiye çevresi haritası; kutunun dışına düşen olay: bölge haritası.
// Merkez üssü odak halkası; çevresinde tahmini hissedilme halkaları (MMI 4 · 3 · 2, Allen 2012).
import { RENK, kart, sayiTr, tarihTr } from '../cekirdek.mjs';
import { HARITA_G, HARITA_Y, bolgeHaritasi, halka, turkiyeCevresi } from '../harita.mjs';
import { halkaYaricapi } from '../ipe.mjs';
import { altBant, bantUyari, not, notUyari } from '../duzen.mjs';

const ML_AILESI = new Set(['mw', 'ml', 'md', 'mwr', 'mww', 'mwc', 'mwb']);
const SIRA = { tr: ['afad', 'kandilli', 'emsc', 'usgs'], dunya: ['usgs', 'emsc', 'afad', 'kandilli'] };
const AD = { afad: 'AFAD', kandilli: 'Kandilli', emsc: 'EMSC', usgs: 'USGS' };

/** Büyüklük birimi: Mw ailesi "Mw"; mb/Ms/tanınmayan "M (mb, yaklaşık)"; yalnız "M" → "M (yaklaşık)". */
export function mwBirim(tur) {
  const t = String(tur ?? '').trim();
  if (!t || ML_AILESI.has(t.toLowerCase())) return 'Mw';
  return t === 'M' ? 'M (yaklaşık)' : `M (${t}, yaklaşık)`;
}

/** Başlık: Worker'ın hazır `olay.baslik`ı; yoksa Türkiye içinde "İl / İlçe", değilse yer. */
export function olayBaslik(veri) {
  const o = veri.olay ?? {};
  const hazir = o.baslik ?? veri.baslik;
  if (hazir) return String(hazir);
  if (o.bolge !== 'dunya' && o.il) return o.ilce ? `${o.il} / ${o.ilce}` : o.il;
  return o.yer || 'Bilinmeyen yer';
}

/** "Derinlik 7 km · AFAD 4,6 · Kandilli 4,4" */
export function kaynakSatiri(o) {
  const p = [];
  if (Number.isFinite(o.derinlik)) p.push(`Derinlik ${sayiTr(Math.round(o.derinlik))} km`);
  for (const k of SIRA[o.bolge === 'dunya' ? 'dunya' : 'tr']) {
    const b = o.kaynaklar?.[k]?.buyukluk;
    if (Number.isFinite(b)) p.push(`${AD[k]} ${sayiTr(b, 1)}`);
  }
  return p.join(' · ');
}

const KUTU = { d1: 24.2, d2: 46.2, kuzey: 43.4 };
// Sabit Türkiye çevresi kutusunda (kenarlardan pay bırakarak) mı?
const kutuIcinde = (o) => o.boylam > KUTU.d1 + 1 && o.boylam < KUTU.d2 - 1 && o.enlem < KUTU.kuzey - 0.6 && o.enlem > KUTU.kuzey - HARITA_Y / (HARITA_G / (KUTU.d2 - KUTU.d1)) + 0.8;

const DOLGU = [0.07, 0.11, 0.16];

/** → {svg, uyari}: kartın iç SVG'si ve düzen uyarıları (kart() logoyu ekler). */
export function depremSvg(veri) {
  const o = veri.olay;
  const rs = [2, 3, 4].map((e) => halkaYaricapi(o.mw, o.derinlik, e));
  const kutuda = kutuIcinde(o);
  const m = kutuda ? turkiyeCevresi() : bolgeHaritasi({ enlem: o.enlem, boylam: o.boylam, kmYaricap: Math.min(500, Math.max(120, rs[1] * 1.3)) });
  const cx = m.px(o.boylam), cy = m.py(o.enlem);
  let s = m.zemin;
  let daireler = '';
  rs.forEach((r, i) => {
    const px = m.kmPx(r);
    if (r > 0 && px > 18) daireler += `<circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="${px.toFixed(1)}" fill="${RENK.indigo}" fill-opacity="${DOLGU[i]}" stroke="${RENK.indigo}" stroke-opacity="0.55" stroke-width="1.2"/>`;
  });
  s += `<svg x="0" y="0" width="${HARITA_G}" height="${HARITA_Y}" viewBox="0 0 ${HARITA_G} ${HARITA_Y}" overflow="hidden">${daireler}</svg>`;
  s += halka(cx, cy, 15, 6, RENK.indigo);

  const parca = [[4, 'belirgin'], [3, 'hafif'], [2, 'çok hafif']].map(([e, ad], i) => [e, ad, rs[2 - i]]).filter((p) => p[2] > 0);
  const notMetni = parca.length
    ? 'Halkalar: tahmini hissedilme · ' + parca.map(([e, ad, r]) => `${ad} (${e === 4 ? 'MMI 4' : e}) ${sayiTr(Math.round(r))} km`).join(' · ')
    : 'Tahmini hissedilme alanı çok dar';
  const bant = {
    sayi: sayiTr(o.mw, 1), birim: mwBirim(o.tur), baslik: olayBaslik(veri),
    satir1: kaynakSatiri(o), satir2: tarihTr(o.zaman),
  };
  s += not(notMetni) + altBant(bant);
  return { svg: s, uyari: [...bantUyari(bant), ...notUyari(notMetni)], harita: kutuda ? 'turkiye' : 'bolge' };
}

/** Kart 1 çizicisi: veri (kuyruk satırının `veri` JSON'u) → PNG Buffer. */
export async function deprem(veri) {
  const r = depremSvg(veri);
  if (r.uyari.length) console.warn('deprem kartı düzen uyarısı:', r.uyari.join(' | '));
  return kart(r.svg);
}
