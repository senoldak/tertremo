// Kart 14 — Aylık Gutenberg–Richter. Veri: hesap/.onbellek/kart-veri.json → gr (hesap/kartblok.py: son 12 ayın Türkiye kataloğu (başlıkta bitiş ayı),
// 0,1'lik kutular, Mc = katalog tamlığı (MBS), b = Aki–Utsu, σ_b = Shi–Bolt). Grafik: kümülatif log N – M noktaları, Mc dikey çizgisi, Aki–Utsu doğrusu
// (N(≥Mc) noktasından geçen, eğimi −b). Büyük sayı b, birim "b-değeri (± σ)".
import { RENK, genislik, kart, sayiTr, yazi } from '../cekirdek.mjs';
import { altBant, bantUyari, not, notUyari } from '../duzen.mjs';
import { ayYazi, oncekiAy } from './izgara.mjs';

const NOT = 'Betimleyici; tahmin değildir. Kaynak: EMSC kataloğu';
// Çizim alanı (harita alanı y 0–560; logo sol üstte y 28–86)
const X0 = 124, X1 = 1140, Y0 = 128, Y1 = 470;
const rol = (ad, ic) => `<g data-rol="${ad}">${ic}</g>`;

/** Kümülatif noktalar: x = kutunun alt kenarı (m − dm/2), n = N(≥ o kenar), logN, ustu = Mc ve üstü. */
export function grNoktalari(blok) {
  const dm = blok.dm ?? 0.1;
  const h = [...blok.histogram].sort((a, b) => a[0] - b[0]);
  let toplam = 0;
  const sonuc = [];
  for (let i = h.length - 1; i >= 0; i--) {
    toplam += h[i][1];
    sonuc.push({ m: h[i][0] - dm / 2, n: toplam, logN: Math.log10(toplam), ustu: h[i][0] >= blok.mc - 1e-9 });
  }
  return sonuc.reverse();
}

/** Aki–Utsu doğrusu: Mc kenarındaki N(≥Mc) noktasından, eğim −b, N = 1'e (log 0) ya da son büyüklüğe kadar. */
export function grDogrusu(blok) {
  const p = grNoktalari(blok).find((q) => q.ustu);
  const son = Math.max(...blok.histogram.map(([m]) => m)) + (blok.dm ?? 0.1) / 2;
  const x2 = Math.min(son, p.m + p.logN / blok.b);
  return { x1: p.m, y1: p.logN, x2, y2: p.logN - blok.b * (x2 - p.m), egim: -blok.b };
}

/** → {svg, uyari}. */
export function grSvg(blok) {
  const nk = grNoktalari(blok);
  const d = grDogrusu(blok);
  const xmin = Math.floor(nk[0].m), xmax = Math.ceil(nk.at(-1).m + 0.1);
  const ymax = Math.max(1, Math.ceil(Math.log10(nk[0].n) + 0.05));
  const px = (m) => X0 + ((m - xmin) / (xmax - xmin)) * (X1 - X0);
  const py = (l) => Y1 - (l / ymax) * (Y1 - Y0);

  let izgara = '';
  for (let m = xmin; m <= xmax; m++) {
    izgara += `<line x1="${px(m).toFixed(1)}" y1="${Y0}" x2="${px(m).toFixed(1)}" y2="${Y1}" stroke="${RENK.ince}" stroke-width="1"/>` + yazi(String(m), px(m), Y1 + 26, 17, RENK.gri, 'middle');
  }
  for (let l = 0; l <= ymax; l++) {
    const bin = sayiTr(10 ** l);
    izgara += `<line x1="${X0}" y1="${py(l).toFixed(1)}" x2="${X1}" y2="${py(l).toFixed(1)}" stroke="${RENK.ince}" stroke-width="1"/>` + yazi(bin, X0 - 12, py(l) + 6, 17, RENK.gri, 'end');
  }
  izgara += `<line x1="${X0}" y1="${Y1}" x2="${X1}" y2="${Y1}" stroke="${RENK.sinir}" stroke-width="1.6"/><line x1="${X0}" y1="${Y0}" x2="${X0}" y2="${Y1}" stroke="${RENK.sinir}" stroke-width="1.6"/>`;
  izgara += yazi('Büyüklük (Mw)', (X0 + X1) / 2, Y1 + 54, 18, RENK.gri, 'middle') + yazi('Kümülatif deprem sayısı N (≥ Mw)', X0, Y0 - 20, 18, RENK.gri);

  const mcX = px(d.x1);
  const mc = rol('gr-mc', `<line x1="${mcX.toFixed(1)}" y1="${Y0}" x2="${mcX.toFixed(1)}" y2="${Y1}" stroke="${RENK.gri}" stroke-width="2" stroke-dasharray="7 6"/>` +
    yazi(`Mc ${sayiTr(blok.mc, 1)}`, mcX + 10, Y0 + 22, 20, RENK.gri));
  let nokta = '';
  for (const p of nk) {
    nokta += `<circle cx="${px(p.m).toFixed(1)}" cy="${py(p.logN).toFixed(1)}" r="4.5" fill="${p.ustu ? RENK.indigo : RENK.gri}" fill-opacity="${p.ustu ? 0.95 : 0.55}"/>`;
  }
  const dogru = rol('gr-dogru', `<line x1="${px(d.x1).toFixed(1)}" y1="${py(d.y1).toFixed(1)}" x2="${px(d.x2).toFixed(1)}" y2="${py(d.y2).toFixed(1)}" stroke="${RENK.murekkep}" stroke-width="2.6"/>`);
  const etiket = `b = ${sayiTr(blok.b, 2)}`;
  const ex = Math.min(px((d.x1 + d.x2) / 2) + 14, X1 - genislik(etiket, 22) - 6);
  const dogruEtiket = yazi(etiket, ex, py((d.y1 + d.y2) / 2) - 16, 22, RENK.murekkep);

  const bant = {
    sayi: sayiTr(blok.b, 2), birim: `b-değeri (± ${sayiTr(blok.sigma, 2)})`,
    baslik: `Gutenberg–Richter · ${ayYazi(blok.ay)}`,
    satir1: `Türkiye ve çevresi · ${sayiTr(blok.n)} deprem · son 12 ay, Mw ≥ ${sayiTr(blok.mc, 1)}`,
    satir2: `Mc ${sayiTr(blok.mc, 1)} (MBS, katalog tamlığı) · artçılar ayıklanmadı`,
  };
  const svg = izgara + mc + rol('gr-noktalar', nokta) + dogru + dogruEtiket + not(NOT) + altBant(bant);
  return { svg, uyari: [...bantUyari(bant), ...notUyari(NOT)] };
}

/** Telegram açıklaması (HTML, ≤ 1024). */
export function aciklama(blok) {
  const a = [
    `<b>Gutenberg–Richter b-değeri</b> · ${ayYazi(blok.ay)}`,
    `Türkiye ve çevresinde ${ayYazi(blok.ay)} ayına kadarki son 12 ayda kaydedilen ${sayiTr(blok.toplam)} depremin büyüklük dağılımı: tamlık büyüklüğü (Mc) ${sayiTr(blok.mc, 1)}, ` +
    `bu büyüklüğün üstünde ${sayiTr(blok.n)} deprem. b-değeri <b>${sayiTr(blok.b, 2)}</b> (± ${sayiTr(blok.sigma, 2)}).`,
    'b-değeri, küçük depremlerin büyüklere oranını anlatır; Mc altı kayıtlar eksik olduğundan b yalnız Mc ve üstüyle hesaplanır. Artçılar ayıklanmamıştır.',
    'Betimleyici; tahmin değildir. Yöntem: Aki–Utsu b, Shi–Bolt σ_b, Mc: MBS (katalog tamlığı). Veri: EMSC.',
  ].join('\n\n');
  return a.length > 1024 ? a.slice(0, 1020).replace(/<[^>]*$/, '') + '…' : a;
}

/** Dönemsel üretici: önceki ayın bloğu yoksa (n < 50, önbellek başka ayda) null. */
export async function aylikGr(kartVeri, { simdi = Date.now() } = {}) {
  const blok = kartVeri?.gr;
  if (!blok) return null;
  if (blok.ay !== oncekiAy(simdi)) { console.warn(`G–R kartı: önbellekte ${blok.ay} var, ${oncekiAy(simdi)} bekleniyordu; kart atlandı`); return null; }
  const r = grSvg(blok);
  if (r.uyari.length) console.warn('G–R kartı düzen uyarısı:', r.uyari.join(' | '));
  return { png: await kart(r.svg), aciklama: aciklama(blok), hedef: 'kanal' };
}
