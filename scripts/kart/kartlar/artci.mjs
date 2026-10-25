// Kart 7: Artçı. Reasenberg-Jones (1989) beklenen kümülatif artçı sayısı eğrisi (log zaman), %10–%90 bandı
// (a_ort ± 1,2816 σ), gözlenen artçılar basamak çizgisi. Büyük sayı: 7 günde en büyük eşik için orta olasılık.
import { RENK, kart, sayiTr, yazi } from '../cekirdek.mjs';
import { altBant, bantUyari, not, notUyari } from '../duzen.mjs';
import { olayBaslik, mwBirim } from './deprem.mjs';

const Z90 = 1.2815516; // %10 / %90 normal yüzdeliği
const T1 = 7; // gün
const PX = { x1: 120, x2: 1130, y1: 130, y2: 470 };

/** [t1, t2] gün arası M ≥ M beklenen artçı sayısı (Worker artci.js beklenen ile aynı kapalı form). */
export function beklenenN(a, p, c, b, Mana, M, t1, t2) {
  const k = 10 ** (a + b * (Mana - M));
  if (Math.abs(p - 1) < 1e-12) return k * Math.log((t2 + c) / (t1 + c));
  return (k * ((t2 + c) ** (1 - p) - (t1 + c) ** (1 - p))) / (1 - p);
}

/** Bant değerini grafik alanına [0, yMax] kırpar. */
export const bantKirp = (v, yMax) => Math.min(Math.max(v, 0), yMax);
/** Alt sınır güvenliği: en az `taban`. */
export const yAltSinir = (v, taban) => Math.max(v, taban);

function guzelAdim(yMax) {
  const ham = yMax / 4;
  const us = 10 ** Math.floor(Math.log10(ham));
  const f = ham / us;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * us;
}

/** → {svg, uyari, sayi, birim, yMax, gozlenenSon}. */
export function artciSvg(veri) {
  const o = veri.olay ?? {};
  const a = veri.artci;
  if (!a?.satirlar?.length || !a.param) throw new Error('artci verisi yok (veri.artci.satirlar/param)');
  const { a_ort, a_sapma, p, c, b } = a.param;
  const Mana = Number.isFinite(a.Mana) ? a.Mana : o.mw;
  const sat = a.satirlar[a.satirlar.length - 1];
  const egriM = a.satirlar[0].m - 1; // tr: 4 -> 3, dünya: 6 -> 5
  const f = (as, t) => beklenenN(as, p, c, b, Mana, egriM, 0, t);
  const aAlt = a_ort - Z90 * a_sapma, aUst = a_ort + Z90 * a_sapma;

  const tSimdi = Number.isFinite(a.t_simdi_gun) ? a.t_simdi_gun : null;
  // x ekseni başı: 0,01 gün; şimdi daha erkense (gerçek paylaşım ~2 dk) şimdi görünsün diye geriye çekilir, en erken 0,001 gün.
  const T0 = tSimdi !== null && tSimdi < 0.01 ? Math.max(0.001, tSimdi / 2) : 0.01;
  // Gözlenenler ana depremden itibaren, şimdiye kadar, model ile aynı eşikte (M ≥ egriM) sayılır.
  const gozlenen = (a.gozlenen ?? []).filter((g) => g.mw >= egriM && g.t_gun >= 0 && g.t_gun <= T1 && (tSimdi === null || g.t_gun <= tSimdi)).sort((x, y) => x.t_gun - y.t_gun);
  const medSon = f(a_ort, T1);
  const gozlenenSon = gozlenen.length;
  const yMax = Math.max(1.1 * Math.max(gozlenenSon, 2 * medSon), 1);
  const adim = guzelAdim(yMax);
  const yTepe = Math.ceil(yMax / adim - 1e-9) * adim;

  const lx = (t) => PX.x1 + ((Math.log10(t) - Math.log10(T0)) / (Math.log10(T1) - Math.log10(T0))) * (PX.x2 - PX.x1);
  const ly = (n) => PX.y2 - (n / yTepe) * (PX.y2 - PX.y1);
  const ts = Array.from({ length: 121 }, (_, i) => T0 * (T1 / T0) ** (i / 120));
  const ust = ts.map((t) => bantKirp(f(aUst, t), yTepe));
  const alt = ts.map((t) => bantKirp(f(aAlt, t), yTepe));
  const med = ts.map((t) => bantKirp(f(a_ort, t), yTepe));
  const yol = (dizi) => ts.map((t, i) => `${i ? 'L' : 'M'}${lx(t).toFixed(1)},${ly(dizi[i]).toFixed(1)}`).join('');
  const bant = yol(ust) + [...ts].reverse().map((t, i) => `L${lx(t).toFixed(1)},${ly(alt[ts.length - 1 - i]).toFixed(1)}`).join('') + 'Z';

  let s = `<rect x="${PX.x1}" y="${PX.y1}" width="${PX.x2 - PX.x1}" height="${PX.y2 - PX.y1}" fill="${RENK.kara}" stroke="${RENK.ince}"/>`;
  for (let v = 0; v <= yTepe + 1e-9; v += adim) {
    s += `<line x1="${PX.x1}" x2="${PX.x2}" y1="${ly(v).toFixed(1)}" y2="${ly(v).toFixed(1)}" stroke="${RENK.ince}"/>` +
      yazi(sayiTr(v, adim < 1 ? 1 : 0), PX.x1 - 12, ly(v) + 6, 18, RENK.gri, 'end');
  }
  for (const [t, e] of [[0.001, '0,001 gün'], [0.01, '0,01 gün'], [0.1, '0,1 gün'], [1, '1 gün'], [7, '7 gün']].filter(([t]) => t >= T0 * 0.999)) {
    s += `<line x1="${lx(t).toFixed(1)}" x2="${lx(t).toFixed(1)}" y1="${PX.y1}" y2="${PX.y2}" stroke="${RENK.ince}"/>` +
      yazi(e, Math.min(lx(t), PX.x2 - 20), PX.y2 + 26, 18, RENK.gri, 'middle');
  }
  s += yazi(`Ana depremden bu yana artçı sayısı, M ≥ ${egriM} (ana depremden itibaren, birikimli)`, PX.x1, PX.y1 - 14, 20, RENK.murekkep);
  s += `<path d="${bant}" fill="${RENK.indigo}" fill-opacity="0.16" stroke="none"/>`;
  s += `<path d="${yol(med)}" fill="none" stroke="${RENK.indigo}" stroke-width="3.5"/>`;
  if (gozlenen.length) {
    const once = gozlenen.filter((g) => g.t_gun < T0).length; // eksen başından önceki olaylar baştaki düzeyi verir
    let d = `M${lx(T0).toFixed(1)},${ly(once).toFixed(1)}`;
    gozlenen.forEach((g, i) => {
      if (g.t_gun < T0) return;
      d += `L${lx(g.t_gun).toFixed(1)},${ly(i).toFixed(1)}L${lx(g.t_gun).toFixed(1)},${ly(i + 1).toFixed(1)}`;
    });
    const tSon = tSimdi !== null ? Math.min(Math.max(tSimdi, T0), T1) : Math.max(T0, gozlenen.at(-1).t_gun);
    d += `L${lx(tSon).toFixed(1)},${ly(gozlenen.length).toFixed(1)}`;
    s += `<path d="${d}" fill="none" stroke="${RENK.murekkep}" stroke-width="2.5"/>`;
  }
  if (tSimdi !== null && tSimdi >= T0 && tSimdi < T1) {
    const x = lx(tSimdi);
    s += `<line x1="${x.toFixed(1)}" x2="${x.toFixed(1)}" y1="${PX.y1}" y2="${PX.y2}" stroke="${RENK.gri}" stroke-dasharray="5 5" stroke-width="1.5"/>` +
      yazi('şimdi', Math.min(x + 6, PX.x2 - 60), PX.y2 - 8, 18, RENK.gri);
  }
  // gösterge (grafiğin sol üstü)
  const gx = PX.x1 + 16, gy = PX.y1 + 28;
  s += `<line x1="${gx}" x2="${gx + 30}" y1="${gy - 6}" y2="${gy - 6}" stroke="${RENK.indigo}" stroke-width="3.5"/>` + yazi('model (medyan)', gx + 40, gy, 18, RENK.murekkep) +
    `<rect x="${gx + 230}" y="${gy - 16}" width="30" height="16" fill="${RENK.indigo}" fill-opacity="0.16"/>` + yazi('%10–%90 aralığı', gx + 270, gy, 18, RENK.murekkep) +
    (gozlenen.length ? `<line x1="${gx + 460}" x2="${gx + 490}" y1="${gy - 6}" y2="${gy - 6}" stroke="${RENK.murekkep}" stroke-width="2.5"/>` + yazi('gözlenen', gx + 500, gy, 18, RENK.murekkep) : '');

  const notMetni = 'Tahmin değildir; istatistik model (Reasenberg–Jones 1989, Page ve ark. 2016)';
  const yuzde = (x) => `%${sayiTr(Math.round(x * 100))}`;
  const birim = `7 günde en az bir M≥${sat.m}`;
  const bantB = {
    sayi: yuzde(sat.orta), birim,
    baslik: `${olayBaslik(veri)} · artçı olasılığı`,
    satir1: `${mwBirim(o.tur).startsWith('Mw') ? 'Mw' : 'M'} ${sayiTr(Mana, 1)} depreminden sonra ${a.satirlar.map((x) => `M≥${x.m}: ${yuzde(x.orta)}`).join(' · ')}`,
    satir2: `%10–%90 aralığı (M≥${sat.m}): ${yuzde(sat.alt)}–${yuzde(sat.ust)}` + (gozlenenSon ? ` · gözlenen M≥${egriM}: ${gozlenenSon}` : ''),
  };
  s += not(notMetni) + altBant(bantB);
  return { svg: s, uyari: [...bantUyari(bantB), ...notUyari(notMetni)], sayi: bantB.sayi, birim, yMax: yTepe, gozlenenSon, axisBas: T0, gozlenenVar: gozlenen.length > 0 };
}

/** Kart 7 çizicisi: veri → PNG Buffer. */
export async function artci(veri) {
  const r = artciSvg(veri);
  if (r.uyari.length) console.warn('artçı kartı düzen uyarısı:', r.uyari.join(' | '));
  return kart(r.svg);
}
