// Kart 19 — Uzun dönem deprem olasılığı (aylık). Veri: hesap/.onbellek/kart-veri.json → uzunDonem (hesap/olasilik.py):
// Mw ≥ 6–7: USGS 1964/1918– uzun kayıt, Gardner–Knopoff ile ayıklanmış doğrudan sayım; Mw 5: EMSC 2018– (en yakın komşu, G–R uzatma);
// zamandan bağımsız Poisson, bootstrap %10–%90. KAMUYA AÇIK KART bölge bazında yüzde GÖSTERMEZ (belirli bir yer için tahmin/alarm
// okunabilir): harita gerçekleşmiş bağımsız Mw ≥ 6 merkez üslerini çizer. Bölge değerleri yalnız kart-veri.json'da (uzunDonem.bolgeler).
// Sağda Türkiye geneli 1/10/50 yıl × Mw ≥ 5/6/7 tablosu. Deprem tahmini değildir.
import { RENK, genislik, kart, sayiTr, yazi } from '../cekirdek.mjs';
import { altBant, bantUyari, not, notUyari } from '../duzen.mjs';
import { ilRenkliHarita } from '../harita.mjs';
import { taze } from './izgara.mjs';
import { yuzde } from './etasHaftalik.mjs';

/** Panel notu (16 px satırlar): hangi satır hangi katalogtan. */
export const KATALOG_SATIR = ['Mw ≥ 6–7: USGS 1964/1918– kataloğu;', 'Mw 5: EMSC 2018–. Kümelenmiş olaylar', 'ayıklanmış (Gardner–Knopoff / yakın komşu).'];
export const KATALOG_NOTU = 'Mw ≥ 6–7: USGS 1964/1918– kataloğu; Mw 5: EMSC 2018–';
export const TURKIYE_AD = 'Türkiye (kıyıdan 30 km dahil)';
const NOT = 'Olasılık hesabıdır; depremin yeri ve zamanı önceden bilinemez. Zamandan bağımsız Poisson modeli.';
const T_LISTE = [1, 10, 50];
const M_LISTE = [5, 6, 7];
const rol = (ad, ic) => `<g data-rol="${ad}">${ic}</g>`;

const tam = (p) => Math.round(Math.min(1, Math.max(0, p)) * 100);
/** [alt, üst] → "%81–%93" (tam yüzde; uç değerler %0 / %100 olabilir). */
export const aralikYazi = (a, u) => `%${tam(a)}–%${tam(u)}`;
const deg = (blok, T, M) => blok.olasilik?.[T]?.[M];

const BAS_YIL = (b) => b.uzunKatalog.bas6;
const SON_YIL = (b) => new Date(b.hesap + 3 * 3600 * 1000).getUTCFullYear();

/** Gerçekleşmiş bağımsız merkez üsleri: Mw ≥ 6 küçük nokta, Mw ≥ 7 büyük halka (haritada px/py ile). */
function olaylar(b, h) {
  let k6 = '', k7 = '';
  const liste = [...(b.uzunKatalog.olaylar ?? [])].sort((p, q) => p[2] - q[2]);
  for (const [la, lo, mw] of liste) {
    const x = h.px(lo).toFixed(1), y = h.py(la).toFixed(1);
    if (mw >= 7 - 1e-9) k7 += `<circle cx="${x}" cy="${y}" r="11" fill="${RENK.indigo}" fill-opacity="0.2" stroke="${RENK.indigo}" stroke-width="3"/>`;
    else k6 += `<circle cx="${x}" cy="${y}" r="5.5" fill="${RENK.indigo}" fill-opacity="0.65" stroke="${RENK.kagit}" stroke-width="1.5"/>`;
  }
  return `<svg x="0" y="0" width="790" height="560" viewBox="0 0 790 560" overflow="hidden">${k6}${k7}</svg>`;
}

const LEJANT_BASLIK = (b) => `Bağımsız Mw ≥ 6 depremler, ${BAS_YIL(b)}–${SON_YIL(b)} (USGS)`;
function lejant(b) {
  const g = Math.max(genislik(LEJANT_BASLIK(b), 17), 250) + 28;
  return rol('lejant', `<rect x="24" y="460" width="${g.toFixed(1)}" height="68" rx="8" fill="${RENK.kagit}" fill-opacity="0.95"/>` +
    yazi(LEJANT_BASLIK(b), 38, 484, 17, RENK.murekkep) +
    `<circle cx="48" cy="509" r="5.5" fill="${RENK.indigo}" fill-opacity="0.65"/>` + yazi('Mw ≥ 6', 62, 515, 16, RENK.gri) +
    `<circle cx="160" cy="509" r="11" fill="${RENK.indigo}" fill-opacity="0.2" stroke="${RENK.indigo}" stroke-width="3"/>` + yazi(`Mw ≥ 7 (1918–)`, 180, 515, 16, RENK.gri));
}

/** → {svg, uyari, bant, metin, tablo}: tablo = Türkiye 1/10/50 yıl satırları × Mw ≥ 5/6/7 (yüzde metni). */
export function uzunDonemSvg(b) {
  const h = ilRenkliHarita(() => null, { w: 790 });

  // Sağ panel: Türkiye geneli tablosu
  const tr = b.turkiye;
  const tablo = T_LISTE.map((T) => M_LISTE.map((M) => { const v = deg(tr, T, M); return v ? yuzde(v[0]) : '—'; }));
  const kolon = [940, 1030, 1120];
  let panel = yazi(TURKIYE_AD, 830, 76, 21, RENK.murekkep) +
    yazi('en az bir deprem olasılığı', 830, 104, 18, RENK.gri);
  M_LISTE.forEach((M, i) => { panel += yazi(`Mw ≥ ${M}`, kolon[i], 160, 19, RENK.gri, 'middle'); });
  panel += `<line x1="830" y1="172" x2="1165" y2="172" stroke="${RENK.cizgi}" stroke-width="1.5"/>`;
  T_LISTE.forEach((T, r) => {
    const y = 218 + r * 58;
    panel += yazi(`${T} yıl`, 830, y, 22, RENK.gri);
    tablo[r].forEach((t, i) => { panel += yazi(t, kolon[i], y, 28, T === 10 && M_LISTE[i] === 6 ? RENK.indigo : RENK.murekkep, 'middle'); });
    panel += `<line x1="830" y1="${y + 20}" x2="1165" y2="${y + 20}" stroke="${RENK.ince}" stroke-width="1"/>`;
  });
  panel += rol('katalog-notu', KATALOG_SATIR.map((t, i) => yazi(t, 830, 392 + i * 20, 16, RENK.gri)).join('')) +
    rol('gecmis-notu', yazi('Harita geçmiş kaydı gösterir;', 830, 484, 18, RENK.murekkep) + yazi('gelecekteki yer ve zamanı değil.', 830, 508, 18, RENK.murekkep));

  const t1 = deg(tr, 1, 6);
  const bant = {
    sayi: t1 ? yuzde(t1[0]) : '—', birim: '1 yılda Mw ≥ 6, Türkiye',
    baslik: 'Uzun dönem deprem olasılığı',
    satir1: t1 ? `Aralık ${aralikYazi(t1[1], t1[2])} · USGS ${b.uzunKatalog.bas6}–${new Date(b.hesap + 3 * 3600 * 1000).getUTCFullYear()}, ${b.turkiye.n6} olay` : 'USGS uzun katalog',
    satir2: 'Kümelenmiş olaylar ayıklanmış (Gardner–Knopoff)',
  };
  const svg = h.zemin + rol('olaylar', olaylar(b, h)) + lejant(b) + rol('tablo', panel) + not(NOT) + altBant(bant);
  return { svg, uyari: [...bantUyari(bant), ...notUyari(NOT)], bant, metin: NOT, tablo };
}

/** Telegram açıklaması (HTML, ≤ 1024). */
export function aciklama(b) {
  const t = b.turkiye;
  const satir = (T) => `${T} yıl: Mw ≥ 5 ${yuzde(deg(t, T, 5)?.[0])} · Mw ≥ 6 ${yuzde(deg(t, T, 6)?.[0])} · Mw ≥ 7 ${yuzde(deg(t, T, 7)?.[0])}`;
  const a = [
    '<b>Uzun dönem deprem olasılığı</b>',
    `${TURKIYE_AD}: kayıttan hesaplanan hıza göre, belirtilen sürede en az bir deprem olma olasılığı:\n${satir(1)}\n${satir(10)}\n${satir(50)}`,
    `Harita, ${BAS_YIL(b)}–${SON_YIL(b)} arasında kaydedilen bağımsız Mw ≥ 6 depremlerin merkez üslerini gösterir (büyük halka: Mw ≥ 7); geçmiş kaydı gösterir, gelecekteki yer ve zamanı göstermez.`,
    `${KATALOG_NOTU}. Kümelenme ayıklandı: Mw ≥ 6–7 bağımsız ana depremler (Gardner–Knopoff; Türkiye'de ${b.turkiye.n6} Mw ≥ 6, ${b.turkiye.n7} Mw ≥ 7 olay; tamlık: Michael 2014), Mw 5 en yakın komşu (Mc ${sayiTr(b.mc, 1)}, b ${sayiTr(t.b, 2)}). Zamandan bağımsız Poisson; aralık %10–%90 (yeniden örnekleme).`,
    'Olasılık hesabıdır; depremin yeri ve zamanı önceden bilinemez.',
  ].join('\n\n');
  return a.length > 1024 ? a.slice(0, 1020).replace(/<[^>]*$/, '') + '…' : a;
}

/** Dönemsel üretici: veri yok / önbellek eski ise null. */
export async function uzunDonem(kartVeri, { simdi = Date.now() } = {}) {
  const b = kartVeri?.uzunDonem;
  if (!b?.turkiye?.olasilik) return null;
  if (!taze(b.hesap, simdi)) { console.warn('uzun dönem kartı: önbellek eski, kart atlandı'); return null; }
  const r = uzunDonemSvg(b);
  if (r.uyari.length) console.warn('uzun dönem kartı düzen uyarısı:', r.uyari.join(' | '));
  return { png: await kart(r.svg), aciklama: aciklama(b), hedef: 'kanal' };
}
