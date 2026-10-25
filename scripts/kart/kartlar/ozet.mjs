// Kart 8: Dizi özeti (ilk 10 dakika). Bölge haritası: il sınırları ve adları, ölçek; olaylar büyüklükle orantılı daire,
// ana olay halka. Büyük sayı: dizideki deprem sayısı.
import { RENK, genislik, kart, sayiTr, tarihTr, yazi } from '../cekirdek.mjs';
import { HARITA_G, HARITA_Y, bolgeHaritasi, halka } from '../harita.mjs';
import { mesafeKm } from '../ipe.mjs';
import { altBant, bantUyari, not, notUyari } from '../duzen.mjs';
import { olayBaslik } from './deprem.mjs';

/** Harita yarıçapı (km): en az 30, en uzak olayın 1,5 katı. */
export function ozetYaricap(ana, olaylar) {
  let uzak = 0;
  for (const e of olaylar) if (Number.isFinite(e.enlem) && Number.isFinite(e.boylam)) uzak = Math.max(uzak, mesafeKm(ana.enlem, ana.boylam, e.enlem, e.boylam));
  return Math.max(30, 1.5 * uzak);
}

const yaricap = (mw) => Math.max(4, (mw - 1.5) * 7);

/** → {svg, uyari, sayi, yaricapKm}. */
export function ozetSvg(veri) {
  const d = veri.dizi;
  if (!d?.ana || !Number.isFinite(d.ana.enlem)) throw new Error('dizi özeti verisi yok (veri.dizi.ana)');
  const ana = d.ana;
  const liste = (d.olaylar ?? []).filter((e) => Number.isFinite(e.enlem) && Number.isFinite(e.boylam));
  const tum = liste.some((e) => e.zaman === ana.zaman) || !Number.isFinite(ana.zaman) ? liste : [ana, ...liste];
  const km = ozetYaricap(ana, tum);
  const m = bolgeHaritasi({ enlem: ana.enlem, boylam: ana.boylam, kmYaricap: km });
  let daireler = '';
  for (const e of [...tum].sort((x, y) => (y.mw ?? 0) - (x.mw ?? 0))) {
    const r = yaricap(Number.isFinite(e.mw) ? e.mw : 2.5);
    daireler += `<circle cx="${m.px(e.boylam).toFixed(1)}" cy="${m.py(e.enlem).toFixed(1)}" r="${r.toFixed(1)}" fill="${RENK.indigo}" fill-opacity="0.25" stroke="${RENK.indigo}" stroke-width="1.5"/>`;
  }
  let s = m.zemin + `<svg x="0" y="0" width="${HARITA_G}" height="${HARITA_Y}" viewBox="0 0 ${HARITA_G} ${HARITA_Y}" overflow="hidden">${daireler}</svg>`;
  s += halka(m.px(ana.boylam), m.py(ana.enlem), 15, 6, RENK.indigo);
  // İl (ve ilçe) adı her zaman çizilir: il merkezi görünür alanın dışında kalsa bile ana olayın yanında.
  const yer = veri.olay?.il ? (veri.olay.ilce ? `${veri.olay.il} / ${veri.olay.ilce}` : veri.olay.il) : '';
  if (yer) {
    const g = genislik(yer, 22);
    const x0 = Math.min(Math.max(m.px(ana.boylam) + 28, 24), 1176 - g), y0 = Math.min(Math.max(m.py(ana.enlem) + 40, 120), 500);
    s += `<rect x="${(x0 - 8).toFixed(1)}" y="${(y0 - 22).toFixed(1)}" width="${(g + 16).toFixed(1)}" height="32" rx="6" fill="${RENK.kagit}" fill-opacity="0.9"/>` + yazi(yer, x0, y0, 22, RENK.murekkep);
  }

  const enBuyuk = Math.max(...tum.map((e) => (Number.isFinite(e.mw) ? e.mw : -Infinity)));
  const ad = veri.olay?.baslik ?? veri.baslik ?? ana.baslik ?? (veri.olay?.il || veri.olay?.yer ? olayBaslik({ olay: veri.olay }) : 'Deprem dizisi');
  const notMetni = 'Ana olay halka ile · son 10 dakikanın depremleri büyüklükleriyle orantılı · ilk kayıtlar, değişebilir';
  const bant = {
    sayi: String(tum.length), birim: 'deprem',
    baslik: `${ad} · son 10 dakika`,
    satir1: Number.isFinite(enBuyuk) ? `En büyüğü Mw ${sayiTr(enBuyuk, 1)}` : 'Büyüklükler henüz yok',
    satir2: Number.isFinite(ana.zaman) ? tarihTr(ana.zaman, { saniye: false }) : '',
  };
  s += not(notMetni) + altBant(bant);
  return { svg: s, uyari: [...bantUyari(bant), ...notUyari(notMetni)], sayi: bant.sayi, yaricapKm: km, yer };
}

/** Kart 8 çizicisi: veri → PNG Buffer. */
export async function ozet(veri) {
  const r = ozetSvg(veri);
  if (r.uyari.length) console.warn('özet kartı düzen uyarısı:', r.uyari.join(' | '));
  return kart(r.svg);
}
