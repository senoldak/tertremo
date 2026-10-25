// Kart 11: Olağan dışı etkinlik. Hücre haritada vurgulu (Türkiye hücresi 1°: bölge haritası; dünya hücresi 5°: dünya
// haritası); sağ üstte levha: gözlenen k, beklenen μ, Poisson %95 aralığı (kuyruk toplamı, scipy'siz) ve BH düzeltilmiş p.
// Büyük sayı: k (birim 'bağımsız deprem'; 26 px'te '(7 gün)' 284 px sütuna sığmaz, 7 gün satır 1'de). Not: "Beklenenden fazla etkinlik tahmin değildir."
import { RENK, genislik, kart, sayiTr, yazi } from '../cekirdek.mjs';
import { bolgeHaritasi, dunyaHaritasi, halka } from '../harita.mjs';
import { altBant, bantUyari, not, notUyari } from '../duzen.mjs';
import { olayBaslik } from './deprem.mjs';

export const NOT_METNI = 'Beklenenden fazla etkinlik tahmin değildir.';

/** Poisson(mu) log olasılık kütlesi. */
function logPmf(k, mu) {
  let lg = 0;
  for (let i = 2; i <= k; i++) lg += Math.log(i);
  return -mu + k * Math.log(mu) - lg;
}

/**
 * Poisson(μ) için iki yanlı %95 aralık [alt, üst] (kuyruk toplamı): alt = P(X ≤ a) ≥ α/2 olan en küçük a,
 * üst = P(X ≤ b) ≥ 1 − α/2 olan en küçük b. μ = 4,1 → [1, 8].
 */
export function poissonAralik(mu, alfa = 0.05) {
  if (!(mu > 0)) return [0, 0];
  let kum = 0, alt = null;
  for (let k = 0; k < 100_000; k++) {
    kum += Math.exp(logPmf(k, mu));
    if (alt === null && kum >= alfa / 2 - 1e-12) alt = k;
    if (kum >= 1 - alfa / 2 - 1e-12) return [alt ?? k, k];
  }
  return [alt ?? 0, Math.ceil(mu + 10 * Math.sqrt(mu))];
}

/** p değeri yazımı: < 0,001 ise "< 0,001"; yoksa üç basamak. */
export const pYazi = (p) => (!Number.isFinite(p) ? '—' : p < 0.001 ? '< 0,001' : sayiTr(p, 3));
const muYazi = (mu) => sayiTr(mu, mu >= 10 ? 0 : 1);

function hucreBilgisi(veri) {
  const o = veri.olagandisi;
  const h = o.hucre;
  if (h && Number.isFinite(h.enlem) && Number.isFinite(h.boylam) && Number.isFinite(h.boyut_derece)) return h;
  const boy = veri.olay?.katalog === 'dunya' ? 5 : 1; // eski/eksik veri: olay konumundan türet
  const e = veri.olay;
  return { enlem: Math.floor(e.enlem / boy) * boy, boylam: Math.floor(e.boylam / boy) * boy, boyut_derece: boy };
}

const enlemYazi = (la) => `${sayiTr(Math.abs(la))}°${la < 0 ? 'G' : 'K'}`;
const boylamYazi = (lo) => `${sayiTr(Math.abs(lo))}°${lo < 0 ? 'B' : 'D'}`;

/** Sağ üst levha: dört satır + aralık şeridi. → {svg, kutu}. */
function panel(o, aralik) {
  const x = 810, y = 28, g = 362, ph = 232;
  let s = `<g data-rol="panel"><rect x="${x}" y="${y}" width="${g}" height="${ph}" rx="10" fill="${RENK.kagit}" fill-opacity="0.94" stroke="${RENK.cizgi}"/>`;
  const sat = (etiket, deger, ty) => yazi(etiket, x + 20, ty, 20, RENK.gri) + yazi(deger, x + g - 20, ty, 24, RENK.murekkep, 'end');
  s += sat('gözlenen k', sayiTr(o.k), y + 42);
  s += sat('uzun dönem ort. μ', muYazi(o.beklenen), y + 80);
  s += sat('%95 aralık', `${sayiTr(aralik[0])} – ${sayiTr(aralik[1])}`, y + 118);
  s += sat('BH düzeltilmiş p', o.bh_p == null ? 'yok' : pYazi(o.bh_p), y + 156);
  // şerit: 0 … max(k, üst) + 1; aralık açık indigo, k koyu çizgi
  const sx = x + 20, sg = g - 40, sy = y + 188;
  const en = Math.max(o.k, aralik[1], 1) + 1;
  const px = (v) => sx + (v / en) * sg;
  s += `<rect x="${sx}" y="${sy}" width="${sg}" height="12" fill="${RENK.ince}" fill-opacity="0.7"/>`;
  s += `<rect x="${px(aralik[0]).toFixed(1)}" y="${sy}" width="${(px(aralik[1] + 1) - px(aralik[0])).toFixed(1)}" height="12" fill="${RENK.indigo}" fill-opacity="0.28"/>`;
  s += `<rect x="${(px(o.k) + (px(o.k + 1) - px(o.k)) / 2 - 2).toFixed(1)}" y="${sy - 5}" width="4" height="22" fill="${RENK.indigo}"/>`;
  s += yazi('0', sx, sy + 38, 16, RENK.gri) + yazi(sayiTr(en - 1), sx + sg, sy + 38, 16, RENK.gri, 'end');
  s += '</g>';
  return s;
}

/** → {svg, uyari, hucre, aralik}. */
export function olagandisiSvg(veri) {
  const o = veri.olagandisi;
  if (!o || !Number.isFinite(o.k) || !Number.isFinite(o.beklenen)) throw new Error('olagandisi: veri.olagandisi {k, beklenen} yok');
  const h = hucreBilgisi(veri);
  const boy = h.boyut_derece;
  const aralik = poissonAralik(o.beklenen);
  const cLa = h.enlem + boy / 2, cLo = h.boylam + boy / 2;
  const dunya = boy > 2;
  const m = dunya
    ? dunyaHaritasi({ boylamMerkez: cLo })
    : bolgeHaritasi({ enlem: cLa, boylam: cLo, kmYaricap: 175 });
  const x1 = m.px(h.boylam), x2 = m.px(h.boylam + boy), y1 = m.py(h.enlem + boy), y2 = m.py(h.enlem);
  let s = m.zemin;
  s += `<g data-rol="hucre"><rect x="${x1.toFixed(1)}" y="${y1.toFixed(1)}" width="${(x2 - x1).toFixed(1)}" height="${(y2 - y1).toFixed(1)}" fill="${RENK.indigo}" fill-opacity="0.2" stroke="${RENK.indigo}" stroke-width="3.5"/></g>`;
  if (dunya) s += halka((x1 + x2) / 2, (y1 + y2) / 2, 15, 6, RENK.indigo);
  s += panel(o, aralik);

  const notMetni = NOT_METNI;
  const satir1 = `Son 7 gün · uzun dönem ort. ${muYazi(o.beklenen)} · %95 aralık ${sayiTr(aralik[0])}–${sayiTr(aralik[1])}`;
  const satir2 = `BH düzeltilmiş p ${o.bh_p == null ? 'yok' : pYazi(o.bh_p)} · hücre ${enlemYazi(h.enlem)} ${boylamYazi(h.boylam)} · ${sayiTr(boy)}°`;
  let baslik = `Olağan dışı etkinlik · ${olayBaslik(veri)}`;
  if (genislik(baslik, 46) > 800) baslik = 'Olağan dışı etkinlik';
  const bant = { sayi: sayiTr(o.k), birim: 'bağımsız deprem', baslik, satir1, satir2 };
  s += not(notMetni) + altBant(bant);
  return { svg: s, uyari: [...bantUyari(bant), ...notUyari(notMetni)], hucre: h, aralik, bant };
}

/** Kart 11 çizicisi: veri → PNG Buffer. */
export async function olagandisi(veri) {
  const r = olagandisiSvg(veri);
  if (r.uyari.length) console.warn('olağan dışı kartı düzen uyarısı:', r.uyari.join(' | '));
  return kart(r.svg);
}
