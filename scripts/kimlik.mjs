// tertremo kimliğinin çizim yardımcıları: renkler, yazı tipi, glif yolu olarak logo yazısı ve odak halkası.
// SVG'ler yazı tipi gerektirmez (her harf yol olarak çizilir); logo paketi ve ileride kart çizicisi birlikte kullanır.
import { fileURLToPath } from 'node:url';
import opentype from 'opentype.js';

export const RENK = { indigo: '#3d36c9', indigoKoyu: '#8f88ff', murekkep: '#16181d', kagit: '#f5f4ef' };

export const YAZI = opentype.loadSync(fileURLToPath(new URL('../brand/yazi/Manrope-Bold.ttf', import.meta.url)));
const ARALIK = -0.033; // logodaki harf aralığı (em)

// 'o' glifinin dış ve iç konturu: halka onun yerine, aynı dış ölçü ve aynı kalınlıkla oturur.
function oOlculeri() {
  const yollar = [];
  let cur = [];
  for (const k of YAZI.charToGlyph('o').path.commands) {
    if (k.type === 'M' && cur.length) yollar.push(cur), (cur = []);
    cur.push(k);
  }
  yollar.push(cur);
  const kutu = (y) => {
    const xs = y.filter((k) => 'x' in k).map((k) => k.x);
    const ys = y.filter((k) => 'y' in k).map((k) => k.y);
    return { x1: Math.min(...xs), x2: Math.max(...xs), y1: Math.min(...ys), y2: Math.max(...ys) };
  };
  const [dis, ic] = yollar.filter((y) => y.length > 1).map(kutu).sort((a, b) => b.x2 - b.x1 - (a.x2 - a.x1));
  return { dis, kalinlik: ((ic.x1 - dis.x1) + (dis.x2 - ic.x2)) / 2 };
}
export const O = oOlculeri();

/** Odak halkası: merkez (cx, cy), dış yarıçap r, kalınlık k; ortada nokta. */
export function halka(cx, cy, r, k, renk) {
  const nokta = k * 0.5;
  return `<circle cx="${cx.toFixed(2)}" cy="${cy.toFixed(2)}" r="${(r - k / 2).toFixed(2)}" fill="none" stroke="${renk}" stroke-width="${k.toFixed(2)}"/>` +
    `<circle cx="${cx.toFixed(2)}" cy="${cy.toFixed(2)}" r="${nokta.toFixed(2)}" fill="${renk}"/>`;
}

/** Logo yazısı: "tertrem" glif yolu + son "o" yerine odak halkası. boy = em boyu (px); taban = yazı tabanının y'si. */
export function logoYazisi(x, taban, boy, renk, vurgu) {
  const o = boy / YAZI.unitsPerEm;
  let d = '';
  let imlec = x;
  for (const h of 'tertrem') {
    const g = YAZI.charToGlyph(h);
    d += g.getPath(imlec, taban, boy).toPathData(2);
    imlec += g.advanceWidth * o + ARALIK * boy;
  }
  const og = YAZI.charToGlyph('o');
  const { dis, kalinlik } = O;
  const r = (Math.max(dis.x2 - dis.x1, dis.y2 - dis.y1) / 2) * o; // halka gözde o'dan küçük görünmesin
  const cx = imlec + ((dis.x1 + dis.x2) / 2) * o;
  const cy = taban - ((dis.y1 + dis.y2) / 2) * o;
  // Renkli halka gözde harflerden ağır durur: kalınlık o’nunkinden %12 ince.
  const ic = `<path d="${d}" fill="${renk}"/>` + halka(cx, cy, r, kalinlik * o * 0.88, vurgu);
  return { ic, genislik: imlec + og.advanceWidth * o - x };
}

export const svg = (g, y, ic, zemin) =>
  `<svg xmlns="http://www.w3.org/2000/svg" width="${g.toFixed(0)}" height="${y.toFixed(0)}" viewBox="0 0 ${g.toFixed(2)} ${y.toFixed(2)}">` +
  (zemin ? `<rect width="100%" height="100%" fill="${zemin}"/>` : '') + ic + '</svg>';
