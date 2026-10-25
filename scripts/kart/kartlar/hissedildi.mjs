// Kart 2: Nerelerde hissedildi. Sol: il il renklendirilmiş Türkiye haritası (il merkezinde tahmini MMI);
// sağ: en yüksek 10 il çubuğu ve renk lejandı. Büyük sayı: MMI ≥ 2,5 (yuvarlanınca III, "zayıf") olan il sayısı.
// Sınıf kenarları USGS MMI sözcüklerine göre x,5'te (tam sayı sınıfı sürekli değerin yuvarlanmasıdır): II–III zayıf, IV hafif, V orta, VI güçlü, VII+ çok güçlü.
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { RENK, genislik, kart, kisalt, sayiTr, tarihTr, yazi } from '../cekirdek.mjs';
import { ilRenkliHarita, halka } from '../harita.mjs';
import { mmi, mesafeKm } from '../ipe.mjs';
import { altBant, bantUyari, not, notUyari } from '../duzen.mjs';
import { olayBaslik, mwBirim } from './deprem.mjs';

const RENKLER = ['#e6e4f6', '#c9c5ef', '#9e98e2', '#6b64d4', '#3d36c9'];
const ETIKET = ['II–III', 'IV', 'V', 'VI', 'VII+'];
const iller = JSON.parse(fs.readFileSync(fileURLToPath(new URL('../../../data/harita/iller.json', import.meta.url)), 'utf8'));

const sinif = (v) => (v >= 6.5 ? 4 : v >= 5.5 ? 3 : v >= 4.5 ? 2 : v >= 3.5 ? 1 : v >= 1.5 ? 0 : -1);
const ESIK_SAYI = 2.5; // büyük sayıya giren en düşük MMI (yuvarlanınca III)
// "Elâzığ" / "Elazığ" gibi yazım farklarını eşler.
const anahtar = (ad) => String(ad).toLocaleLowerCase('tr-TR').replace(/â/g, 'a').replace(/î/g, 'i').replace(/û/g, 'u');

/** Worker listesi yoksa: 81 il merkezinde Allen 2012 ile [{ad, mmi, sigma}] (il.m = [boylam, enlem]). */
export function ilSiddetleriHesapla({ enlem, boylam, derinlik, mw }) {
  return iller.map((il) => {
    const s = mmi({ mw, derinlik, mesafeKm: mesafeKm(enlem, boylam, il.m[1], il.m[0]) });
    return { ad: il.ad, mmi: s.mmi, sigma: s.sigma };
  });
}

/** En yüksek 10 il (azalan MMI, eşitlikte ada göre). */
export function ilSirala(liste) {
  return [...liste].filter((i) => Number.isFinite(i.mmi)).sort((a, b) => b.mmi - a.mmi || a.ad.localeCompare(b.ad, 'tr')).slice(0, 10);
}

function baslikMetni(veri) {
  const o = veri.olay;
  const tam = olayBaslik(veri);
  const kisa = (o.baslik ?? veri.baslik) ? tam : o.bolge !== 'dunya' && o.ilce ? o.ilce : o.bolge !== 'dunya' && o.il ? o.il : tam;
  const mw = `${mwBirim(o.tur).startsWith('Mw') ? 'Mw' : 'M'} ${sayiTr(o.mw, 1)}`;
  for (const aday of [`${kisa} ${mw} · nerelerde hissedildi`, `${kisa} ${mw} · hissedilme`, `${kisa} · nerelerde hissedildi`, 'Nerelerde hissedildi']) {
    if (genislik(aday, 46) <= 800) return aday;
  }
  return 'Nerelerde hissedildi';
}

/** → {svg, uyari, sayi}. */
export function hissedildiSvg(veri) {
  const o = veri.olay;
  const liste = Array.isArray(veri.siddetIller) && veri.siddetIller.length
    ? veri.siddetIller
    : veri.siddetIller ? [] : ilSiddetleriHesapla(o);
  const byAd = new Map(liste.map((i) => [anahtar(i.ad), i]));
  const dolgu = (ad) => {
    const k = sinif(byAd.get(anahtar(ad))?.mmi);
    return k < 0 ? null : RENKLER[k];
  };
  const m = ilRenkliHarita(dolgu);
  let s = m.zemin;
  const cx = m.px(o.boylam), cy = m.py(o.enlem);
  if (cx > 10 && cx < m.w - 10 && cy > 10 && cy < 550) s += halka(cx, cy, 13, 5, RENK.murekkep);

  // sağ sütun
  s += `<rect x="790" y="0" width="410" height="560" fill="${RENK.kagit}"/><line x1="790" x2="790" y1="0" y2="560" stroke="${RENK.cizgi}"/>`;
  s += yazi('En yüksek 10 il', 820, 62, 22, RENK.murekkep) + yazi('medyan MMI', 1170, 62, 18, RENK.gri, 'end');
  const ilk = ilSirala(liste);
  const bx = 990, bw = 130;
  if (!ilk.length) s += yazi('İl merkezlerinde hissedilme yok', 820, 110, 20, RENK.gri);
  ilk.forEach((x, i) => {
    const y = 104 + i * 34;
    s += yazi(kisalt(x.ad, 20, 162), 820, y + 7, 20, RENK.murekkep);
    s += `<rect x="${bx}" y="${y - 11}" width="${bw}" height="20" fill="${RENK.ince}" fill-opacity="0.5"/>`;
    s += `<rect x="${bx}" y="${y - 11}" width="${((x.mmi / 8) * bw).toFixed(1)}" height="20" fill="${RENKLER[Math.max(0, sinif(x.mmi))]}"/>`;
    s += yazi(sayiTr(x.mmi, 1), 1170, y + 7, 20, RENK.murekkep, 'end');
  });
  s += yazi('MMI · il merkezinde tahmini şiddet', 820, 456, 18, RENK.gri);
  ETIKET.forEach((e, i) => {
    const x = 820 + i * 70;
    s += `<rect x="${x}" y="468" width="56" height="18" fill="${RENKLER[i]}" stroke="${RENK.cizgi}"/>` + yazi(e, x + 28, 508, 16, RENK.gri, 'middle');
  });

  const notMetni = 'Allen ve ark. (2012) hiposantral şiddet bağıntısı · il merkezleri · ölçülmüş değil';
  const sayi = liste.filter((i) => i.mmi >= ESIK_SAYI).length;
  let satir1 = ilk.length ? 'En yüksek: ' + ilk.slice(0, 3).map((x) => `${x.ad} ${sayiTr(x.mmi, 1)}`).join(' · ') : 'MMI 2,5\'e ulaşan il yok';
  if (genislik(satir1, 28) > 800 && ilk.length > 2) satir1 = 'En yüksek: ' + ilk.slice(0, 2).map((x) => `${x.ad} ${sayiTr(x.mmi, 1)}`).join(' · ');
  const bant = {
    sayi: String(sayi), birim: 'ilde hissedilir', baslik: baslikMetni(veri), satir1,
    satir2: 'MMI ≥ 2,5: zayıf hissedilir · ' + tarihTr(o.zaman, { saniye: false }),
  };
  s += not(notMetni) + altBant(bant);
  return { svg: s, uyari: [...bantUyari(bant), ...notUyari(notMetni)], sayi };
}

/** Kart 2 çizicisi: veri → PNG Buffer. */
export async function hissedildi(veri) {
  const r = hissedildiSvg(veri);
  if (r.uyari.length) console.warn('hissedildi kartı düzen uyarısı:', r.uyari.join(' | '));
  return kart(r.svg);
}
