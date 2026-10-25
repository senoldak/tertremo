// Kart 9: Dizi gelişimi (24 / 72 / 168. saat). Üstte büyüklük–log zaman saçılımı (en büyük artçı halka, Båth çizgisi
// Mana − 1,2); altta gözlenen kümülatif artçı sayısı ile Reasenberg–Jones medyan eğrisi. Büyük sayı: toplam artçı.
import { RENK, kart, sayiTr, yazi } from '../cekirdek.mjs';
import { altBant, bantUyari, not, notUyari } from '../duzen.mjs';
import { halka } from '../harita.mjs';
import { olayBaslik } from './deprem.mjs';
import { beklenenN } from './artci.mjs';

const GUN_DK = 1440;
const T_MIN = 1 / GUN_DK; // 1 dakika (gün)
const X1 = 120, X2 = 1130;
const A = { y1: 134, y2: 300 }; // büyüklük–zaman
const B = { y1: 372, y2: 498 }; // kümülatif
const TIKLAR = [[1, '1 dk'], [10, '10 dk'], [60, '1 sa'], [360, '6 sa'], [1440, '1 gün'], [4320, '3 gün'], [10080, '7 gün']];

const R = (x) => x.toFixed(1);

/** Båth yasası: en büyük artçı ≈ ana şok − 1,2. */
export const bath = (Mana) => Mana - 1.2;

/** Güzel eksen adımı (≈ 4 aralık). */
export function guzelAdim(tepe) {
  const ham = Math.max(tepe, 1e-9) / 4;
  const us = 10 ** Math.floor(Math.log10(ham));
  const f = ham / us;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * us;
}

/** → {svg, uyari, sayi, birim, toplam, enBuyuk, bath, medyan}. */
export function gelisimSvg(veri) {
  const d = veri.dizi;
  const ana = d?.ana;
  if (!d || !ana || !Number.isFinite(ana.zaman)) throw new Error('gelisim verisi yok (veri.dizi.ana/olaylar)');
  const prm = veri.artci?.param;
  const Mana = Number.isFinite(veri.artci?.Mana) ? veri.artci.Mana : ana.mw;
  const mc = Number.isFinite(d.mc) ? d.mc : Number.isFinite(veri.artci?.mc) ? veri.artci.mc : 2;
  const saat = Number.isFinite(d.saat) ? d.saat : 24;
  const tSon = saat * 60; // dakika
  const olaylar = (d.olaylar ?? [])
    .filter((e) => Number.isFinite(e.zaman) && Number.isFinite(e.mw) && e.zaman > ana.zaman)
    .map((e) => ({ t: Math.max((e.zaman - ana.zaman) / 60000, 1), mw: e.mw }))
    .filter((e) => e.t <= tSon * 1.0001)
    .sort((a, b) => a.t - b.t);
  const toplam = Number.isFinite(d.toplam) ? d.toplam : olaylar.length;
  const cizilenEn = olaylar.length ? Math.max(...olaylar.map((e) => e.mw)) : null;
  const enBuyuk = Number.isFinite(d.en_buyuk) ? d.en_buyuk : cizilenEn;
  const kesik = toplam > olaylar.length; // Worker en eski 2000 olayı gönderir: eğri ilk N olayı gösterir
  const bt = bath(Mana);

  const lx = (dk) => X1 + ((Math.log10(dk) - Math.log10(1)) / (Math.log10(tSon) - Math.log10(1))) * (X2 - X1);
  let s = '';
  // ---- A: büyüklük–zaman
  const yMin = Math.floor(mc);
  const yMax = Math.max(Math.ceil(Math.max(bt, enBuyuk ?? 0) + 0.3), yMin + 2);
  const ay = (m) => A.y2 - ((m - yMin) / (yMax - yMin)) * (A.y2 - A.y1);
  s += `<rect x="${X1}" y="${A.y1}" width="${X2 - X1}" height="${A.y2 - A.y1}" fill="${RENK.kara}" stroke="${RENK.ince}"/>`;
  for (let m = yMin; m <= yMax; m++) {
    s += `<line x1="${X1}" x2="${X2}" y1="${R(ay(m))}" y2="${R(ay(m))}" stroke="${RENK.ince}"/>` + yazi(String(m), X1 - 12, ay(m) + 6, 18, RENK.gri, 'end');
  }
  const tikli = TIKLAR.filter(([dk]) => dk <= tSon * 1.0001);
  for (const [dk] of tikli) s += `<line x1="${R(lx(dk))}" x2="${R(lx(dk))}" y1="${A.y1}" y2="${B.y2}" stroke="${RENK.ince}"/>`;
  s += yazi('Artçı büyüklüğü (Mw) — ana depremden bu yana geçen süre (log)', X1, A.y1 - 14, 20, RENK.murekkep);
  // Båth çizgisi
  if (bt >= yMin && bt <= yMax) {
    s += `<line x1="${X1}" x2="${X2}" y1="${R(ay(bt))}" y2="${R(ay(bt))}" stroke="${RENK.gri}" stroke-width="2" stroke-dasharray="8 6"/>` +
      yazi(`Båth beklentisi Mw ${sayiTr(bt, 1)}`, X2 - 10, ay(bt) - 8, 18, RENK.gri, 'end');
  }
  let daireler = '';
  for (const e of olaylar) {
    const r = Math.min(9, 2.5 + Math.max(0, e.mw - mc) * 1.8);
    daireler += `<circle cx="${R(lx(e.t))}" cy="${R(ay(Math.min(e.mw, yMax)))}" r="${R(r)}" fill="${RENK.indigo}" fill-opacity="0.3" stroke="${RENK.indigo}" stroke-width="1"/>`;
  }
  s += daireler;
  if (cizilenEn != null) {
    const e = olaylar.find((o) => o.mw === cizilenEn);
    const ex = lx(e.t), ey = ay(Math.min(e.mw, yMax));
    s += halka(ex, ey, 12, 4, RENK.indigo);
    const solda = ex > X1 + 330;
    s += yazi(`${kesik ? 'ilk olaylarda en büyük' : 'en büyük artçı'} Mw ${sayiTr(cizilenEn, 1)}`, solda ? ex - 18 : ex + 18, ey + 6, 18, RENK.murekkep, solda ? 'end' : 'start');
  }

  // ---- B: kümülatif
  let med = null;
  const f = (t) => (prm ? beklenenN(prm.a_ort, prm.p, prm.c, prm.b, Mana, mc, 0, t / GUN_DK) : null);
  if (prm) med = f(tSon);
  const gTop = olaylar.length;
  const tepeHam = Math.max(gTop, Number.isFinite(med) ? med : 0, 1) * 1.1;
  const adim = guzelAdim(tepeHam);
  const tepe = Math.ceil(tepeHam / adim - 1e-9) * adim;
  const by = (n) => B.y2 - (Math.min(n, tepe) / tepe) * (B.y2 - B.y1);
  s += `<rect x="${X1}" y="${B.y1}" width="${X2 - X1}" height="${B.y2 - B.y1}" fill="${RENK.kara}" stroke="${RENK.ince}"/>`;
  for (let v = 0; v <= tepe + 1e-9; v += adim) {
    s += `<line x1="${X1}" x2="${X2}" y1="${R(by(v))}" y2="${R(by(v))}" stroke="${RENK.ince}"/>` + yazi(sayiTr(v, adim < 1 ? 1 : 0), X1 - 12, by(v) + 6, 18, RENK.gri, 'end');
  }
  for (const [dk, e] of tikli) s += yazi(e, Math.min(lx(dk), X2 - 14), B.y2 + 26, 18, RENK.gri, 'middle');
  s += yazi(`Birikimli artçı sayısı (M ≥ ${sayiTr(mc, 1)})`, X1, B.y1 - 14, 20, RENK.murekkep);
  if (prm) {
    const ts = Array.from({ length: 121 }, (_, i) => 1 * (tSon / 1) ** (i / 120));
    s += `<path d="${ts.map((t, i) => `${i ? 'L' : 'M'}${R(lx(t))},${R(by(f(t)))}`).join('')}" fill="none" stroke="${RENK.indigo}" stroke-width="3.5"/>`;
  }
  if (gTop) {
    let p = `M${R(lx(1))},${R(by(0))}`;
    olaylar.forEach((e, i) => { p += `L${R(lx(e.t))},${R(by(i))}L${R(lx(e.t))},${R(by(i + 1))}`; });
    if (!kesik) p += `L${R(lx(tSon))},${R(by(gTop))}`;
    s += `<path d="${p}" fill="none" stroke="${RENK.murekkep}" stroke-width="2.5"/>`;
  }
  if (kesik) s += yazi(`eğri ilk ${sayiTr(olaylar.length)} olayı gösterir`, X2 - 10, B.y2 - 12, 18, RENK.gri, 'end');
  const gx = X1 + 16, gy = B.y1 + 28;
  s += `<line x1="${gx}" x2="${gx + 30}" y1="${gy - 6}" y2="${gy - 6}" stroke="${RENK.murekkep}" stroke-width="2.5"/>` + yazi('gözlenen', gx + 40, gy, 18, RENK.murekkep);
  if (prm) s += `<line x1="${gx + 160}" x2="${gx + 190}" y1="${gy - 6}" y2="${gy - 6}" stroke="${RENK.indigo}" stroke-width="3.5"/>` + yazi('model (medyan)', gx + 200, gy, 18, RENK.murekkep);

  const ad = olayBaslik(veri);
  const sure = saat === 24 ? '24 saat' : `${saat / 24} gün`;
  const notMetni = kesik ? 'Model eğrisi geçmişle karşılaştırmadır, tahmin değildir (Reasenberg–Jones 1989) · eğri ilk olayları gösterir' : 'Model eğrisi geçmişle karşılaştırmadır, tahmin değildir (Reasenberg–Jones 1989; Båth yasası) · ilk kayıtlar eksik olabilir';
  const bant = {
    sayi: sayiTr(toplam), birim: `artçı (M ≥ ${sayiTr(mc, 1)})`,
    baslik: `${ad} dizisi · ${sure}`,
    satir1: enBuyuk != null ? `En büyük artçı Mw ${sayiTr(enBuyuk, 1)} · Båth beklentisi Mw ${sayiTr(bt, 1)}` : `Båth beklentisi Mw ${sayiTr(bt, 1)} · artçı kaydı yok`,
    satir2: Number.isFinite(med) ? `Gözlenen ${sayiTr(toplam)} · model medyanı ${sayiTr(Math.round(med))}` : `Ana deprem Mw ${sayiTr(Mana, 1)}`,
  };
  s += not(notMetni) + altBant(bant);
  return { svg: s, uyari: [...bantUyari(bant), ...notUyari(notMetni)], sayi: bant.sayi, birim: bant.birim, toplam, enBuyuk, bath: bt, medyan: med };
}

/** Kart 9 çizicisi: veri → PNG Buffer. */
export async function gelisim(veri) {
  const r = gelisimSvg(veri);
  if (r.uyari.length) console.warn('gelişim kartı düzen uyarısı:', r.uyari.join(' | '));
  return kart(r.svg);
}
