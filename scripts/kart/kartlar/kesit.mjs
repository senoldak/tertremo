// Kart 10: Derinlik kesiti. Dizi olaylarının temel bileşen doğrultusu (2×2 kovaryans özvektörü) boyunca
// mesafe (km) – derinlik (km, aşağı) saçılımı + küçük harita. Büyük sayı: medyan derinlik (km).
import { RENK, kart, sayiTr, yazi } from '../cekirdek.mjs';
import { altBant, bantUyari, not, notUyari } from '../duzen.mjs';
import { halka } from '../harita.mjs';
import { olayBaslik } from './deprem.mjs';
import { guzelAdim } from './gelisim.mjs';

const DERECE_KM = 111.195;
const S = { x1: 120, x2: 740, y1: 134, y2: 496 }; // kesit
const H = { x1: 800, x2: 1130, y1: 134, y2: 420 }; // küçük harita (iç kutu)
const R = (x) => x.toFixed(1);

/**
 * Noktaların ({enlem, boylam}) en büyük yayılım doğrultusu (2×2 kovaryans özvektörü).
 * → {aci: kuzeyden saat yönünde derece [0,180), ux, uy (doğu/kuzey birim vektör), x[], y[] (km), d[] (eksen boyunca km), enlem0, boylam0}.
 */
export function temelDogrultu(noktalar) {
  const n = noktalar.length;
  const la0 = noktalar.reduce((a, p) => a + p.enlem, 0) / n;
  const lo0 = noktalar.reduce((a, p) => a + p.boylam, 0) / n;
  const kos = Math.cos((la0 * Math.PI) / 180);
  const x = noktalar.map((p) => (p.boylam - lo0) * DERECE_KM * kos);
  const y = noktalar.map((p) => (p.enlem - la0) * DERECE_KM);
  let sxx = 0, syy = 0, sxy = 0;
  for (let i = 0; i < n; i++) { sxx += x[i] * x[i]; syy += y[i] * y[i]; sxy += x[i] * y[i]; }
  sxx /= n; syy /= n; sxy /= n;
  const teta = 0.5 * Math.atan2(2 * sxy, sxx - syy); // doğudan saat yönü tersine
  let ux = Math.cos(teta), uy = Math.sin(teta);
  if (ux < -1e-12 || (Math.abs(ux) <= 1e-12 && uy < 0)) { ux = -ux; uy = -uy; } // eksen doğuya (ya da kuzeye) baksın
  let aci = 90 - (Math.atan2(uy, ux) * 180) / Math.PI; // kuzeyden saat yönünde
  aci = ((aci % 180) + 180) % 180;
  const d = x.map((xi, i) => xi * ux + y[i] * uy);
  return { aci, ux, uy, x, y, d, enlem0: la0, boylam0: lo0 };
}

const yuzdelik = (dizi, q) => {
  const s = [...dizi].sort((a, b) => a - b);
  const i = (s.length - 1) * q, a = Math.floor(i), b = Math.ceil(i);
  return s[a] + (s[b] - s[a]) * (i - a);
};
/** Medyan derinlik (km). */
export const medyan = (dizi) => yuzdelik(dizi, 0.5);

/** → {svg, uyari, sayi, birim, aci, medyan, n}. */
export function kesitSvg(veri) {
  const dz = veri.dizi;
  const ana = dz?.ana ?? veri.olay;
  if (!dz || !ana) throw new Error('kesit verisi yok (veri.dizi.olaylar)');
  const olaylar = (dz.olaylar ?? []).filter((e) => [e.enlem, e.boylam, e.derinlik, e.mw].every(Number.isFinite));
  if (olaylar.length < 3) throw new Error(`kesit için en az 3 derinlikli olay gerekir (${olaylar.length})`);
  const anaVar = [ana.enlem, ana.boylam, ana.derinlik].every(Number.isFinite);
  const hepsi = anaVar ? [{ enlem: ana.enlem, boylam: ana.boylam, derinlik: ana.derinlik, mw: ana.mw, ana: true }, ...olaylar] : olaylar;
  const t = temelDogrultu(hepsi);
  const derinlikler = olaylar.map((e) => e.derinlik);
  const med = medyan(derinlikler);
  const p10 = yuzdelik(derinlikler, 0.1), p90 = yuzdelik(derinlikler, 0.9);

  const dMin = Math.min(...t.d), dMax = Math.max(...t.d);
  const uzun = Math.max(dMax - dMin, 1);
  const pay = uzun * 0.08;
  const d1 = dMin - pay, d2 = dMax + pay;
  const zTepe0 = Math.max(...hepsi.map((e) => e.derinlik)) * 1.12;
  const zAdim = guzelAdim(Math.max(zTepe0, 4));
  const zTepe = Math.ceil(zTepe0 / zAdim - 1e-9) * zAdim;
  const kx = (d) => S.x1 + ((d - d1) / (d2 - d1)) * (S.x2 - S.x1);
  const kz = (z) => S.y1 + (z / zTepe) * (S.y2 - S.y1);

  let s = `<rect x="${S.x1}" y="${S.y1}" width="${S.x2 - S.x1}" height="${S.y2 - S.y1}" fill="${RENK.kara}" stroke="${RENK.ince}"/>`;
  for (let z = 0; z <= zTepe + 1e-9; z += zAdim) {
    s += `<line x1="${S.x1}" x2="${S.x2}" y1="${R(kz(z))}" y2="${R(kz(z))}" stroke="${RENK.ince}"/>` + yazi(sayiTr(z), S.x1 - 12, kz(z) + 6, 18, RENK.gri, 'end');
  }
  const xAdim = guzelAdim(d2 - d1);
  for (let v = Math.ceil(d1 / xAdim) * xAdim; v <= d2 + 1e-9; v += xAdim) {
    s += `<line x1="${R(kx(v))}" x2="${R(kx(v))}" y1="${S.y1}" y2="${S.y2}" stroke="${RENK.ince}"/>` + yazi(sayiTr(Math.round(v * 10) / 10, xAdim < 1 ? 1 : 0), kx(v), S.y2 + 26, 18, RENK.gri, 'middle');
  }
  s += yazi('Derinlik (km, aşağı) — doğrultu boyunca mesafe (km)', S.x1, S.y1 - 14, 20, RENK.murekkep);
  // medyan derinlik çizgisi
  s += `<line x1="${S.x1}" x2="${S.x2}" y1="${R(kz(med))}" y2="${R(kz(med))}" stroke="${RENK.gri}" stroke-width="2" stroke-dasharray="8 6"/>` +
    `<rect x="${S.x2 - 190}" y="${S.y1 + 6}" width="184" height="30" rx="6" fill="${RENK.kara}" fill-opacity="0.94"/>` +
    `<line x1="${S.x2 - 180}" x2="${S.x2 - 150}" y1="${S.y1 + 21}" y2="${S.y1 + 21}" stroke="${RENK.gri}" stroke-width="2" stroke-dasharray="8 6"/>` +
    yazi(`medyan ${sayiTr(Math.round(med))} km`, S.x2 - 142, S.y1 + 27, 18, RENK.gri);
  let nokta = '';
  const mc = Number.isFinite(dz.mc) ? dz.mc : Math.min(...olaylar.map((e) => e.mw));
  hepsi.forEach((e, i) => {
    if (e.ana) return;
    const r = Math.min(9, 2.5 + Math.max(0, e.mw - mc) * 1.8);
    nokta += `<circle cx="${R(kx(t.d[i]))}" cy="${R(kz(e.derinlik))}" r="${R(r)}" fill="${RENK.indigo}" fill-opacity="0.3" stroke="${RENK.indigo}" stroke-width="1"/>`;
  });
  s += nokta;
  if (anaVar) s += halka(kx(t.d[0]), kz(ana.derinlik), 14, 5, RENK.indigo);

  // ---- küçük harita (yerel km düzlemi, kuzey yukarı)
  const hx = Math.max(...t.x.map(Math.abs), 1), hy = Math.max(...t.y.map(Math.abs), 1);
  const yar = Math.max(hx, hy) * 1.25;
  const hw = H.x2 - H.x1, hh = H.y2 - H.y1;
  const olc = Math.min(hw, hh) / 2 / yar; // px/km
  const cx = (H.x1 + H.x2) / 2, cy = (H.y1 + H.y2) / 2;
  const mx = (x) => cx + x * olc, my = (y) => cy - y * olc;
  s += yazi('Harita', H.x1, H.y1 - 14, 20, RENK.murekkep);
  s += `<rect x="${H.x1}" y="${H.y1}" width="${hw}" height="${hh}" fill="${RENK.kara}" stroke="${RENK.ince}"/>`;
  const a = { x: t.ux * (dMin - pay), y: t.uy * (dMin - pay) }, b = { x: t.ux * (dMax + pay), y: t.uy * (dMax + pay) };
  // eksen merkezden (ortalama) geçer; harita merkezi = ortalama konum
  s += `<line x1="${R(mx(a.x))}" y1="${R(my(a.y))}" x2="${R(mx(b.x))}" y2="${R(my(b.y))}" stroke="${RENK.gri}" stroke-width="2" stroke-dasharray="8 6"/>`;
  hepsi.forEach((e, i) => {
    if (e.ana) return;
    s += `<circle cx="${R(mx(t.x[i]))}" cy="${R(my(t.y[i]))}" r="3.5" fill="${RENK.indigo}" fill-opacity="0.45"/>`;
  });
  if (anaVar) s += halka(mx(t.x[0]), my(t.y[0]), 11, 4, RENK.indigo);
  // uç etiketleri: kutu içinde kalacak biçimde
  const kenar = (p, harf) => {
    const x = Math.min(Math.max(mx(p.x), H.x1 + 14), H.x2 - 14), y = Math.min(Math.max(my(p.y), H.y1 + 24), H.y2 - 8);
    return yazi(harf, x, y, 20, RENK.murekkep, 'middle');
  };
  s += kenar(a, 'A') + kenar(b, 'B');
  // ölçek çubuğu + kuzey
  const olcKm = [1, 2, 5, 10, 20, 50, 100, 200].find((k) => k * olc >= 50) ?? 200;
  s += `<rect x="${H.x2 - 12 - olcKm * olc}" y="${H.y2 - 22}" width="${olcKm * olc}" height="4" fill="${RENK.murekkep}"/>` + yazi(`${olcKm} km`, H.x2 - 12, H.y2 - 30, 16, RENK.murekkep, 'end');
  s += yazi('K', H.x1 + 14, H.y1 + 26, 18, RENK.gri, 'middle') + `<path d="M${H.x1 + 14},${H.y1 + 32}l-5,10h10z" fill="${RENK.gri}"/>`;
  s += yazi(`A → B: ${sayiTr(Math.round(t.aci))}° doğrultu`, H.x1, H.y2 + 30, 18, RENK.gri);

  const ad = olayBaslik(veri);
  const toplam = Number.isFinite(dz.toplam) ? dz.toplam : olaylar.length;
  const kesik = toplam > olaylar.length;
  const notMetni = 'Konum ve derinlikler ilk kayıtlardır, değişebilir · halka: ana deprem · eksen: olayların en büyük yayılım doğrultusu' + (kesik ? ` · ilk ${sayiTr(olaylar.length)} olay` : '');
  const bant = {
    sayi: sayiTr(Math.round(med)), birim: 'km',
    baslik: `${ad} · derinlik kesiti`,
    satir1: `Medyan derinlik · %10–%90 aralığı ${sayiTr(Math.round(p10))}–${sayiTr(Math.round(p90))} km`,
    satir2: `${sayiTr(toplam)} artçı${kesik ? ` (ilk ${sayiTr(olaylar.length)} çizildi)` : ''} · doğrultu ${sayiTr(Math.round(t.aci))}° · uzunluk ${sayiTr(Math.round(dMax - dMin))} km`,
  };
  s += not(notMetni) + altBant(bant);
  return { svg: s, uyari: [...bantUyari(bant), ...notUyari(notMetni)], sayi: bant.sayi, birim: 'km', aci: t.aci, medyan: med, n: olaylar.length };
}

/** Kart 10 çizicisi: veri → PNG Buffer. */
export async function kesit(veri) {
  const r = kesitSvg(veri);
  if (r.uyari.length) console.warn('kesit kartı düzen uyarısı:', r.uyari.join(' | '));
  return kart(r.svg);
}
