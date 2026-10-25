// Kart 3: Dünya. Merkez üssünün boylamına döndürülmüş dünya haritası (merkez üssü hep x = 600); Türkiye gri halka;
// büyük sayı Mw; satır 1: derinlik + tsunami/PAGER; satır 2: tarih. Türkiye'ye uzaklık (haversine) notta.
import { RENK, genislik, kart, sayiTr, tarihTr } from '../cekirdek.mjs';
import { LEVHA_ATIF, dunyaHaritasi, halka } from '../harita.mjs';
import { mesafeKm } from '../ipe.mjs';
import { altBant, bantUyari, not, notUyari } from '../duzen.mjs';
import { mwBirim, olayBaslik } from './deprem.mjs';

export const TURKIYE = { enlem: 39.0, boylam: 35.0 };
const PAGER = { green: 'yeşil', yellow: 'sarı', orange: 'turuncu', red: 'kırmızı' };
const R = 15;

export const turkiyeUzaklikKm = (enlem, boylam) => mesafeKm(enlem, boylam, TURKIYE.enlem, TURKIYE.boylam);

/** "Derinlik 35 km · tsunami bildirimi · PAGER sarı" (olmayan alan atlanır). */
export function dunyaSatiri(o) {
  const p = [];
  if (Number.isFinite(o.derinlik)) p.push(`Derinlik ${sayiTr(Math.round(o.derinlik))} km`);
  if (o.tsunami) p.push('tsunami bildirimi');
  const pg = PAGER[String(o.pager ?? '').toLowerCase()];
  if (pg) p.push(`PAGER ${pg}`);
  return p.join(' · ');
}

/** → {svg, uyari, merkez, satir1, satir2, not, uzaklikKm}. */
export function dunyaSvg(veri) {
  const o = veri.olay;
  const h = dunyaHaritasi({ boylamMerkez: o.boylam, levha: true });
  // Merkez üssü haritanın üst/alt kenarında kesilmesin (enlem ±84 sınırı).
  const cx = h.px(o.boylam), cy = Math.min(560 - R - 4, Math.max(R + 4, h.py(o.enlem)));
  const tx = Math.min(1200 - 14, Math.max(14, h.px(TURKIYE.boylam))), ty = h.py(TURKIYE.enlem);
  const uzaklikKm = turkiyeUzaklikKm(o.enlem, o.boylam);
  let s = h.zemin;
  s += halka(tx, ty, 9, 3.5, RENK.gri);
  s += halka(cx, cy, R, 6, RENK.indigo);
  const notMetni = `Türkiye'ye ${sayiTr(Math.round(uzaklikKm))} km · gri halka: Türkiye · ${LEVHA_ATIF}`;
  const bant = {
    sayi: sayiTr(o.mw, 1), birim: mwBirim(o.tur), baslik: olayBaslik(veri),
    satir1: dunyaSatiri(o), satir2: tarihTr(o.zaman, { saniye: false }),
  };
  s += `<rect x="44" y="524" width="${(genislik(notMetni, 18) + 24).toFixed(1)}" height="32" rx="8" fill="${RENK.kagit}" fill-opacity="0.88"/>` + not(notMetni) + altBant(bant);
  return {
    svg: s, uyari: [...bantUyari(bant), ...notUyari(notMetni)], merkez: { cx, cy }, satir1: bant.satir1, satir2: bant.satir2, not: notMetni, uzaklikKm,
  };
}

/** Kart 3 çizicisi: veri → PNG Buffer. */
export async function dunya(veri) {
  const r = dunyaSvg(veri);
  if (r.uyari.length) console.warn('dünya kartı düzen uyarısı:', r.uyari.join(' | '));
  return kart(r.svg);
}
