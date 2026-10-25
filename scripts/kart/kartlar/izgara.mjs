// Dönemsel kartlar için ortak yardımcılar: 1° hücre ızgarası (Türkiye çevresi haritası üstünde), sıralı indigo skala,
// lejant, ay yazımı. Renk skalası tek tonlu (açıktan koyuya), renk körlüğüne uygun; kırmızı yok, tehlike çağrışımı yok.
import { RENK, genislik, yazi } from '../cekirdek.mjs';
import { HARITA_G, HARITA_Y, turkiyeCevresi } from '../harita.mjs';

/** Sıralı indigo skala: açık → koyu, luminans tek yönlü. */
export const SKALA = ['#e4e2f6', '#c4c0ee', '#9a93e2', '#6c64d6', '#3d36c9', '#241f86'];
const YAZI_BEYAZ = [false, false, false, true, true, true];

const rol = (ad, ic) => `<g data-rol="${ad}">${ic}</g>`;
const AYLAR = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'];

/** Artan sınırlara göre sınıf sıra numarası: değer ≥ sınır ise bir üst sınıf. */
export const siniflayici = (sinirlar) => (v) => sinirlar.filter((s) => v >= s).length;

/** "2026-09" → "Eylül 2026". */
export const ayYazi = (ay) => { const [y, a] = ay.split('-').map(Number); return `${AYLAR[a - 1]} ${y}`; };

/** simdi (UTC ms) için önceki takvim ayı, Türkiye yerel saatiyle: "YYYY-AA" (hesap/kartblok.py ay_araligi ile aynı). */
export function oncekiAy(simdi) {
  const d = new Date(simdi + 3 * 3600 * 1000);
  const y = d.getUTCMonth() === 0 ? d.getUTCFullYear() - 1 : d.getUTCFullYear();
  const a = d.getUTCMonth() === 0 ? 12 : d.getUTCMonth();
  return `${y}-${String(a).padStart(2, '0')}`;
}

/** Önbellek bloğu `en çok gun` günden eskiyse false (gece hesabı aksamış). */
export const taze = (hesap, simdi, gun = 5) => Number.isFinite(hesap) && simdi - hesap <= gun * 86_400_000;

/**
 * Hücre katmanı (Türkiye çevresi haritası üstünde). hucreler: [{anahtar:'38_27', ...}];
 * sinif(h) → 0..5 ya da null (boş bırak); etiket(h) → hücre içi küçük yazı; tarama(h) → true ise çizgili (belirsiz).
 * → {zemin, katman, cizilen, taramali}
 */
export function hucreHaritasi(hucreler, { sinif, etiket, tarama = () => false }) {
  const m = turkiyeCevresi();
  let hucreSvg = '', taramaSvg = '', yaziSvg = '';
  let cizilen = 0, taramali = 0;
  const kutular = [];
  for (const h of hucreler) {
    const s = sinif(h);
    if (s === null || s === undefined) continue;
    const [la, lo] = h.anahtar.split('_').map(Number);
    const x1 = m.px(lo), x2 = m.px(lo + 1), y1 = m.py(la + 1), y2 = m.py(la);
    kutular.push({ x1, y1, x2, y2 });
    hucreSvg += `<rect x="${x1.toFixed(1)}" y="${y1.toFixed(1)}" width="${(x2 - x1).toFixed(1)}" height="${(y2 - y1).toFixed(1)}" fill="${SKALA[s]}" fill-opacity="0.9" stroke="${RENK.kagit}" stroke-width="1" stroke-opacity="0.7"/>`;
    if (tarama(h)) {
      taramali++;
      taramaSvg += `<rect x="${x1.toFixed(1)}" y="${y1.toFixed(1)}" width="${(x2 - x1).toFixed(1)}" height="${(y2 - y1).toFixed(1)}" fill="url(#tarama)"/>`;
    }
    const t = etiket(h);
    if (t && genislik(t, 15) <= x2 - x1 - 4) yaziSvg += yazi(t, (x1 + x2) / 2, (y1 + y2) / 2 + 5, 15, YAZI_BEYAZ[s] ? '#ffffff' : RENK.murekkep, 'middle');
    cizilen++;
  }
  const tanim = `<defs><pattern id="tarama" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="7" height="7" fill="none"/><line x1="0" y1="0" x2="0" y2="7" stroke="${RENK.murekkep}" stroke-width="2" stroke-opacity="0.45"/></pattern></defs>`;
  const katman = `<svg x="0" y="0" width="${HARITA_G}" height="${HARITA_Y}" viewBox="0 0 ${HARITA_G} ${HARITA_Y}" overflow="hidden">${tanim}${rol('hucreler', hucreSvg)}${rol('tarama', taramaSvg)}</svg>` + rol('hucre-etiket', yaziSvg);
  return { zemin: m.zemin, katman, cizilen, taramali, kutular };
}

/**
 * Lejant (kâğıt levha): başlık, 6 renk kutusu + etiket, isteğe bağlı çizgili örnek + açıklama.
 * Yer: sağ alt, sol alt, sağ üst adaylarından çizili hücrelerle en az kesişen (kutular: hucreHaritasi().kutular).
 */
export function lejant(baslik, etiketler, { taramaMetni = null, kutular = [] } = {}) {
  const kutuG = 66, ara = 4, kolon = 3;
  const gen = kolon * (kutuG + ara) - ara;
  const h = taramaMetni ? 154 : 128;
  const adaylar = [];
  for (let x0 = 1160 - gen; x0 >= 72; x0 -= 40) adaylar.push({ x0, y0: 528 - h });
  adaylar.push({ x0: 1160 - gen, y0: 44 }, { x0: 1160 - gen - 240, y0: 44 }, { x0: 72, y0: 100 });
  const kes = (a) => kutular.filter((k) => k.x1 < a.x0 + gen + 14 && k.x2 > a.x0 - 14 && k.y1 < a.y0 + h && k.y2 > a.y0 - 6).length;
  const { x0, y0 } = adaylar.map((a) => ({ ...a, k: kes(a) })).reduce((en, a) => (a.k < en.k ? a : en));
  let s = `<rect x="${x0 - 14}" y="${y0 - 6}" width="${gen + 28}" height="${h + 6}" rx="8" fill="${RENK.kagit}" fill-opacity="0.97"/>`;
  s += yazi(baslik, x0, y0 + 20, 18, RENK.gri);
  etiketler.forEach((e, i) => {
    const x = x0 + (i % kolon) * (kutuG + ara), ys = y0 + 30 + Math.floor(i / kolon) * 48;
    s += `<rect x="${x}" y="${ys}" width="${kutuG}" height="14" fill="${SKALA[i]}"/>` + yazi(e, x + kutuG / 2, ys + 34, 15, RENK.gri, 'middle');
  });
  if (taramaMetni) {
    const ys = y0 + 30 + 96;
    s += `<rect x="${x0}" y="${ys}" width="30" height="14" fill="${SKALA[2]}"/><rect x="${x0}" y="${ys}" width="30" height="14" fill="url(#tarama)"/>` +
      yazi(taramaMetni, x0 + 40, ys + 13, 15, RENK.gri);
  }
  return rol('lejant', s);
}

/** Hücre listesinden Mc aralığı metni: "2,6" ya da "2,6–3,4". */
export function mcAraligi(hucreler, bicim) {
  const mc = hucreler.map((h) => h.mc).filter(Number.isFinite);
  if (!mc.length) return '—';
  const a = Math.min(...mc), b = Math.max(...mc);
  return a === b ? bicim(a, 1) : `${bicim(a, 1)}–${bicim(b, 1)}`;
}

export const yilAraligi = (v) => {
  const a = new Date(v.baslangic).getUTCFullYear(), b = new Date(v.hesap + 3 * 3600 * 1000).getUTCFullYear();
  return a === b ? String(a) : `${a}–${b}`;
};
