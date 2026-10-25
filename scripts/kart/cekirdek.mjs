// tertremo kartlarının ortak çizim çekirdeği: renkler, yazı (Manrope Bold, harfler yol), alt bant, logo levhası, not,
// Türkçe sayı/tarih biçimi ve SVG'yi 1200×800 PNG'ye çeviren kart().
import sharp from 'sharp';
import { YAZI, logoYazisi } from '../kimlik.mjs';

export const RENK = {
  kagit: '#f5f4ef', murekkep: '#16181d', indigo: '#3d36c9', indigoKoyu: '#8f88ff', gri: '#6b6a64',
  deniz: '#dfe3e6', kara: '#fbfaf6', komsu: '#efede6', cizgi: '#c9c5b8', ince: '#d9d6cc', sinir: '#a9a596',
};

export const G = 1200;
export const Y = 800;
const SAG_X = 360; // sağ sütun başlangıcı
const SAG_ENGENIS = 800; // 360–1160
const SOL_X = 56;
const SOL_ENGENIS = 284; // 56–340

export const genislik = (metin, boy) => YAZI.getAdvanceWidth(metin, boy);

/** Yazıyı yol olarak çizer. taban = yazı tabanının y'si; hiza: start | middle | end. */
export function yazi(metin, x, taban, boy, renk, hiza = 'start') {
  const g = genislik(metin, boy);
  const x0 = hiza === 'end' ? x - g : hiza === 'middle' ? x - g / 2 : x;
  return `<path d="${YAZI.getPath(metin, x0, taban, boy).toPathData(1)}" fill="${renk}"/>`;
}

/** Metni enGenis px'e sığacak biçimde "…" ile keser (sondaki boşluk atılır). */
export function kisalt(metin, boy, enGenis) {
  if (genislik(metin, boy) <= enGenis) return metin;
  const harfler = [...metin];
  while (harfler.length) {
    harfler.pop();
    const aday = harfler.join('').trimEnd() + '…';
    if (genislik(aday, boy) <= enGenis) return aday;
  }
  return '';
}

const rol = (ad, ic) => `<g data-rol="${ad}">${ic}</g>`;

const LOGO_X = 44, LOGO_TABAN = 70, LOGO_BOY = 34;
/** Logo levhasının kutusu (kâğıt levha, sol üst). */
export function logoKutusu() {
  const l = logoYazisi(LOGO_X, LOGO_TABAN, LOGO_BOY, RENK.murekkep, RENK.indigo);
  return { x1: 28, y1: 28, x2: 28 + l.genislik + 32, y2: 86 };
}

/** Logo: kâğıt levha (0,94 opaklık, köşe 10) üstünde logo yazısı; harita ne olursa olsun okunur. */
export function logoLevha() {
  const l = logoYazisi(LOGO_X, LOGO_TABAN, LOGO_BOY, RENK.murekkep, RENK.indigo);
  return `<rect x="28" y="28" width="${(l.genislik + 32).toFixed(1)}" height="58" rx="10" fill="${RENK.kagit}" fill-opacity="0.94"/>` + l.ic;
}

/** Alt bant (y 560–800): üstte 6 px indigo çizgi, solda büyük sayı + altında birim, sağda başlık ve iki satır. */
export function altBant({ sayi, birim, baslik, satir1, satir2 }) {
  let boy = 112;
  const g = genislik(sayi, boy);
  if (g > SOL_ENGENIS) boy = Math.floor((112 * SOL_ENGENIS) / g);
  return `<rect x="0" y="560" width="${G}" height="240" fill="${RENK.kagit}"/><rect x="0" y="560" width="${G}" height="6" fill="${RENK.indigo}"/>` +
    rol('sayi', yazi(sayi, SOL_X, 690, boy, RENK.murekkep)) +
    rol('birim', yazi(kisalt(birim, 26, SOL_ENGENIS), SOL_X + 2, 745, 26, RENK.gri)) +
    rol('baslik', yazi(kisalt(baslik, 46, SAG_ENGENIS), SAG_X, 640, 46, RENK.murekkep)) +
    rol('satir1', yazi(kisalt(satir1, 28, SAG_ENGENIS), SAG_X, 690, 28, RENK.gri)) +
    rol('satir2', yazi(kisalt(satir2, 28, SAG_ENGENIS), SAG_X, 735, 28, RENK.gri));
}

/** Harita alanının altındaki küçük not (y 548, 18 px gri). */
export function not(metin) {
  return rol('not', yazi(kisalt(metin, 18, G - 2 * SOL_X), SOL_X, 548, 18, RENK.gri));
}

/** İç SVG (harita/grafik + alt bant) → 1200×800 PNG. Logo en üste otomatik eklenir (logo: false ile kapatılır). */
export async function kart(icSvg, { logo = true } = {}) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${G}" height="${Y}" viewBox="0 0 ${G} ${Y}"><rect width="${G}" height="${Y}" fill="${RENK.kagit}"/>${icSvg}${logo ? logoLevha() : ''}</svg>`;
  return sharp(Buffer.from(svg)).png().toBuffer();
}

/** Türkçe sayı: virgül ondalık, nokta binlik, gerçek eksi (−); eksi sıfır yazılmaz. */
export function sayiTr(x, basamak = 0) {
  const s = Math.abs(x).toFixed(basamak);
  const eksi = x < 0 && Number(s) !== 0;
  let [tam, kesir] = s.split('.');
  tam = tam.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  return (eksi ? '−' : '') + tam + (kesir ? ',' + kesir : '');
}

const AYLAR = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'];
const iki = (n) => String(n).padStart(2, '0');

/** ms (UTC epoch) → "24 Ekim 2026 · 14:32:05 TSİ" (TSİ = UTC+3, yaz saati yok). saniye: false ile "14:32". */
export function tarihTr(ms, { saniye = true } = {}) {
  const d = new Date(ms + 3 * 3600 * 1000);
  const saat = `${iki(d.getUTCHours())}:${iki(d.getUTCMinutes())}${saniye ? ':' + iki(d.getUTCSeconds()) : ''}`;
  return `${d.getUTCDate()} ${AYLAR[d.getUTCMonth()]} ${d.getUTCFullYear()} · ${saat} TSİ`;
}
