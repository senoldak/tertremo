// Kart 4: Levha sınırı. Merkez üssü ortada, ±25° enlemlik pencere (50° = 560 px; boylam cos enlem ile ölçeklenir);
// Yalnız PB2002 verisinin kendisinde dalma-batma diye işaretli sınırlar (adda "/" ya da "\\") dişli çizilir ve türü yazılır;
// dişler üstte kalan levha tarafındadır ("/" için çizim yönünün solunda, "\\" için sağında). Diğer bütün sınırlar düz çizgidir,
// türüne dair iddia yoktur (veride tür bilgisi yok). Kaynak: Bird (2003).
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { RENK, genislik, kart, sayiTr, tarihTr } from '../cekirdek.mjs';
import { HARITA_G, HARITA_Y, LEVHA_ATIF, halka } from '../harita.mjs';
import { mesafeKm } from '../ipe.mjs';
import { altBant, bantUyari, not, notUyari } from '../duzen.mjs';
import { mwBirim, olayBaslik } from './deprem.mjs';

const VERI = fileURLToPath(new URL('../../../data/harita/', import.meta.url));
const oku = (ad) => JSON.parse(fs.readFileSync(VERI + ad, 'utf8'));
const ulkeler = oku('ulkeler-dunya.json');
const levhalar = oku('levhalar.json');

const R = 15;
const KY = HARITA_Y / 50; // px / derece enlem
const DERECE_KM = 111.195;
const sar = (x) => ((((x + 180) % 360) + 360) % 360) - 180;

const LEVHA_AD = {
  PA: 'Pasifik', NA: 'Kuzey Amerika', SA: 'Güney Amerika', EU: 'Avrasya', AF: 'Afrika', AN: 'Antarktika', AU: 'Avustralya',
  IN: 'Hint', AR: 'Arap', NZ: 'Nazca', CO: 'Cocos', CA: 'Karayip', PS: 'Filipin Denizi', OK: 'Ohotsk', AM: 'Amur',
  YA: 'Yangtze', SU: 'Sunda', JF: 'Juan de Fuca', SO: 'Somali', SC: 'Scotia', KE: 'Kermadec', TO: 'Tonga', AT: 'Anadolu',
  CL: 'Caroline', MA: 'Mariana', SS: 'Solomon Denizi', NH: 'Yeni Hebridler', TI: 'Timor', BS: 'Banda Denizi', WL: 'Woodlark',
};

/** PB2002 adı → {tur: 'yakinsak' (dalma-batma) | 'diger', ustte: 'sol' | 'sag'}. */
export function sinirTuru(ad) {
  if (ad.includes('/')) return { tur: 'yakinsak', ustte: 'sol' };
  if (ad.includes('\\')) return { tur: 'yakinsak', ustte: 'sag' };
  return { tur: 'diger' };
}
const SINIRLAR = levhalar.map((l) => ({ ...l, ...sinirTuru(l.ad) }));

/** "PA/OK" → "Pasifik–Ohotsk" (bilinmeyen kod olduğu gibi). */
export function sinirAdi(ad) {
  const m = /^([A-Z]{2})[-/\\]([A-Z]{2})$/.exec(ad);
  return m ? `${LEVHA_AD[m[1]] ?? m[1]}–${LEVHA_AD[m[2]] ?? m[2]}` : ad;
}

/** En yakın PB2002 parçası → {km, tur, ad, nokta, dalma}; dalma = en yakın dalma-batma parçası (aynı alanlar) ya da null. */
export function enYakinSinir(enlem, boylam) {
  let en = null, dalma = null;
  for (const s of SINIRLAR) {
    const r = s.r;
    for (let i = 0; i + 3 < r.length; i += 2) {
      const la1 = r[i + 1], la2 = r[i + 3];
      const kos = Math.cos(((la1 + la2 + 2 * enlem) / 4 * Math.PI) / 180);
      const ax = sar(r[i] - boylam) * kos, ay = la1 - enlem;
      const bx = ax + sar(r[i + 2] - r[i]) * kos, by = la2 - enlem;
      const dx = bx - ax, dy = by - ay, uz = dx * dx + dy * dy;
      const t = uz ? Math.max(0, Math.min(1, -(ax * dx + ay * dy) / uz)) : 0;
      const lo = boylam + (ax + t * dx) / kos, la = enlem + ay + t * dy;
      const km = mesafeKm(enlem, boylam, la, sar(lo));
      const k = { km, tur: s.tur, ad: s.ad, nokta: [sar(lo), la] };
      if (!en || km < en.km) en = k;
      if (s.tur === 'yakinsak' && (!dalma || km < dalma.km)) dalma = k;
    }
  }
  return { ...en, dalma };
}

/** Yazıda kullanılacak sınır: dalma-batma parçası en yakının max(1,5×, +75 km) toleransı içindeyse o, değilse tür iddiasız en yakın. */
export function yaziSiniri(en) {
  const d = en.dalma;
  return d && d.km <= Math.max(1.5 * en.km, en.km + 75) ? { ...d, dalmaBatma: true } : { ...en, dalmaBatma: false };
}

/** Pencere projeksiyonu: merkez üssü x = 600; enlem 62° ile sınırlı pencere merkezi (kutuplarda pencere kayar). */
function pencere(enlem, boylam) {
  const mer = Math.max(-62, Math.min(62, enlem));
  const kx = KY * Math.cos((mer * Math.PI) / 180);
  return { kx, W: 360 * kx, px: (lo) => 600 + sar(lo - boylam) * kx, py: (la) => 280 - (la - mer) * KY, mer };
}

// Halkayı sürekli x'e açar (±180° geçişinde kopmaz).
function ac(flat, p, boylam) {
  const n = [];
  let x = p.px(flat[0]);
  n.push([x, p.py(flat[1])]);
  for (let i = 2; i < flat.length; i += 2) {
    x += sar(flat[i] - flat[i - 2]) * p.kx;
    n.push([x, p.py(flat[i + 1])]);
  }
  return n;
}
const kopyalar = (nok, W) => {
  const x1 = Math.min(...nok.map((n) => n[0])), x2 = Math.max(...nok.map((n) => n[0]));
  return [-W, 0, W].filter((k) => x2 + k >= -20 && x1 + k <= HARITA_G + 20);
};
const yolDizi = (nok, kay) => nok.map((n, i) => `${i ? 'L' : 'M'}${(n[0] + kay).toFixed(1)},${n[1].toFixed(1)}`).join('');

function karalar(p, boylam) {
  let d = '', k = '';
  for (const u of ulkeler) {
    for (const flat of u.r) {
      const nok = ac(flat, p, boylam);
      const kutup = Math.abs(nok.at(-1)[0] - nok[0][0]) > p.W / 2;
      const dolgu = kutup ? [...nok, [nok.at(-1)[0], flat[1] < 0 ? 700 : -140], [nok[0][0], flat[1] < 0 ? 700 : -140]] : nok;
      for (const kay of kopyalar(nok, p.W)) {
        d += yolDizi(dolgu, kay) + 'Z';
        k += yolDizi(nok, kay) + (kutup ? '' : 'Z');
      }
    }
  }
  return `<path d="${d}" fill="${RENK.komsu}" stroke="none"/><path d="${k}" fill="none" stroke="${RENK.cizgi}" stroke-width="0.7"/>`;
}

// Dişli çizgi: yol boyunca 26 px'te bir, üstte kalan taraf yönünde üçgen diş.
function disler(nok, kay, ustte) {
  let s = '', kalan = 10;
  for (let i = 1; i < nok.length; i++) {
    const [x1, y1] = nok[i - 1], [x2, y2] = nok[i];
    const uz = Math.hypot(x2 - x1, y2 - y1);
    if (!uz) continue;
    const ux = (x2 - x1) / uz, uy = (y2 - y1) / uz;
    let nx = uy, ny = -ux; // coğrafi sol (ekranda)
    if (ustte === 'sag' || (ustte === 'kuzey' && ny > 0)) { nx = -nx; ny = -ny; }
    let t = kalan;
    for (; t < uz; t += 26) {
      const cx = x1 + ux * t + kay, cy = y1 + uy * t;
      if (cx < -12 || cx > HARITA_G + 12 || cy < -12 || cy > HARITA_Y + 12) continue;
      s += `M${(cx - ux * 6).toFixed(1)},${(cy - uy * 6).toFixed(1)}L${(cx + nx * 10).toFixed(1)},${(cy + ny * 10).toFixed(1)}L${(cx + ux * 6).toFixed(1)},${(cy + uy * 6).toFixed(1)}Z`;
    }
    kalan = t - uz;
  }
  return s;
}

function sinirlar(p, boylam) {
  let duz = '', dis = '';
  for (const s of SINIRLAR) {
    const nok = ac(s.r, p, boylam);
    for (const kay of kopyalar(nok, p.W)) {
      const yol = yolDizi(nok, kay);
      duz += yol;
      if (s.tur === 'yakinsak') dis += disler(nok, kay, s.ustte);
    }
  }
  return `<path d="${duz}" fill="none" stroke="${RENK.murekkep}" stroke-width="2" stroke-linejoin="round"/>` +
    `<path d="${dis}" fill="${RENK.murekkep}" stroke="none"/>`;
}

/** → {svg, uyari, merkez, enYakin, satir1, satir2, not}. */
export function levhaSvg(veri) {
  const o = veri.olay;
  const p = pencere(o.enlem, o.boylam);
  const cx = 600, cy = p.py(o.enlem);
  const en = enYakinSinir(o.enlem, o.boylam);
  const nx = p.px(en.nokta[0]), ny = p.py(en.nokta[1]);
  const kes = (ic) => `<svg x="0" y="0" width="${HARITA_G}" height="${HARITA_Y}" viewBox="0 0 ${HARITA_G} ${HARITA_Y}" overflow="hidden">${ic}</svg>`;
  let s = `<rect width="${HARITA_G}" height="${HARITA_Y}" fill="${RENK.deniz}"/>` + kes(karalar(p, o.boylam) + sinirlar(p, o.boylam));
  // En yakın sınır noktası: ince kesik çizgi ve küçük işaret.
  if (Math.hypot(nx - cx, ny - cy) > R + 6) {
    s += kes(`<line x1="${cx}" y1="${cy.toFixed(1)}" x2="${nx.toFixed(1)}" y2="${ny.toFixed(1)}" stroke="${RENK.indigo}" stroke-width="2" stroke-dasharray="7 6"/>` +
      `<circle cx="${nx.toFixed(1)}" cy="${ny.toFixed(1)}" r="6" fill="${RENK.kagit}" stroke="${RENK.indigo}" stroke-width="3"/>`);
  }
  s += halka(cx, cy, R, 6, RENK.indigo);
  const notMetni = `Dişli çizgi: dalma-batma sınırı (dişler üstte kalan levhaya bakar) · ${LEVHA_ATIF}`;
  const ys = yaziSiniri(en);
  const km = ys.km < 10 ? 'sınırın üzerinde' : `${sayiTr(Math.round(ys.km))} km`;
  const derinlik = Number.isFinite(o.derinlik) ? `Derinlik ${sayiTr(Math.round(o.derinlik))} km · ` : '';
  const bant = {
    sayi: sayiTr(o.mw, 1), birim: mwBirim(o.tur), baslik: olayBaslik(veri),
    satir1: ys.dalmaBatma ? `${sinirAdi(ys.ad)} · dalma-batma sınırı · ${km}` : `${sinirAdi(ys.ad)} levha sınırı · ${km}`, satir2: derinlik + tarihTr(o.zaman),
  };
  s += `<rect x="44" y="524" width="${(genislik(notMetni, 18) + 24).toFixed(1)}" height="32" rx="8" fill="${RENK.kagit}" fill-opacity="0.88"/>` + not(notMetni) + altBant(bant);
  return { svg: s, uyari: [...bantUyari(bant), ...notUyari(notMetni)], merkez: { cx, cy }, enYakin: en, satir1: bant.satir1, satir2: bant.satir2, not: notMetni };
}

/** Kart 4 çizicisi: veri → PNG Buffer. */
export async function levha(veri) {
  const r = levhaSvg(veri);
  if (r.uyari.length) console.warn('levha kartı düzen uyarısı:', r.uyari.join(' | '));
  return kart(r.svg);
}
