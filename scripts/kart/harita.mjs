// Kart haritaları: Türkiye çevresi (sabit kutu), bölge (il sınırları + il adları + ölçek) ve dünya (eşdikdörtgen).
// Hepsi {zemin, px, py, ...} döndürür: zemin = 1200×560 alanın SVG'si, px/py = boylam/enlem → piksel.
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { RENK, genislik, yazi, logoKutusu } from './cekirdek.mjs';

const VERI = fileURLToPath(new URL('../../data/harita/', import.meta.url));
const onbellek = {};
const yukle = (ad) => (onbellek[ad] ??= JSON.parse(fs.readFileSync(VERI + ad, 'utf8')));

export const HARITA_G = 1200;
export const HARITA_Y = 560;
const DERECE_KM = 111.195;

/** PB2002 çizgisi çizen her kart bu atfı taşımalıdır (ODC-By). */
export const LEVHA_ATIF = 'Levha sınırları: Bird (2003), ODC-By';

/** Odak halkası (merkez üssü): dış yarıçap r, kalınlık k, ortada nokta. */
export function halka(cx, cy, r, k, renk) {
  return `<circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="${(r - k / 2).toFixed(1)}" fill="none" stroke="${renk}" stroke-width="${k}"/>` +
    `<circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="${(k * 0.75).toFixed(1)}" fill="${renk}"/>`;
}

const yol = (flat, px, py) => {
  let d = '';
  for (let i = 0; i < flat.length; i += 2) d += `${i ? 'L' : 'M'}${px(flat[i]).toFixed(1)},${py(flat[i + 1]).toFixed(1)}`;
  return d + 'Z';
};
// Halka görünür alana değiyorsa yol verisi, değilse boş.
const gorunur = (flat, px, py, pay = 40) => {
  let x1 = Infinity, x2 = -Infinity, y1 = Infinity, y2 = -Infinity;
  for (let i = 0; i < flat.length; i += 2) {
    const x = px(flat[i]), y = py(flat[i + 1]);
    x1 = Math.min(x1, x); x2 = Math.max(x2, x); y1 = Math.min(y1, y); y2 = Math.max(y2, y);
  }
  return x2 >= -pay && x1 <= HARITA_G + pay && y2 >= -pay && y1 <= HARITA_Y + pay;
};
const yollar = (ulkeler, px, py) => ulkeler.flatMap((u) => u.r.filter((r) => gorunur(r, px, py)).map((r) => yol(r, px, py))).join('');
const kirp = (ic) => `<svg x="0" y="0" width="${HARITA_G}" height="${HARITA_Y}" viewBox="0 0 ${HARITA_G} ${HARITA_Y}" overflow="hidden">${ic}</svg>`;

/** Türkiye çevresi: sabit kutu 24,2–46,2 D / üst 43,4 K, boylam ölçeği cos 39°. */
export function turkiyeCevresi() {
  const d1 = 24.2, d2 = 46.2, kMax = 43.4;
  const k = HARITA_G / (d2 - d1);
  const kos = Math.cos((39 * Math.PI) / 180);
  const px = (lo) => (lo - d1) * k * kos + (HARITA_G - (d2 - d1) * k * kos) / 2;
  const py = (la) => (kMax - la) * k;
  const ulkeler = yukle('ulkeler-bolge.json');
  const zemin = `<rect width="${HARITA_G}" height="${HARITA_Y}" fill="${RENK.deniz}"/>` + kirp(
    `<path d="${yollar(ulkeler.filter((u) => u.iso !== 'TUR'), px, py)}" fill="${RENK.komsu}" stroke="${RENK.cizgi}" stroke-width="1"/>` +
    `<path d="${yollar(ulkeler.filter((u) => u.iso === 'TUR'), px, py)}" fill="${RENK.kara}" stroke="${RENK.sinir}" stroke-width="1.6"/>`);
  return { px, py, zemin, kmPx: (km) => (km / DERECE_KM) * k * kos };
}

const kesisir = (a, b) => a.x1 < b.x2 && b.x1 < a.x2 && a.y1 < b.y2 && b.y1 < a.y2;

/**
 * Bölge haritası: (enlem, boylam) merkezde (600, 280); kmYaricap = alanın yarı yüksekliği (280 px) kaç km'ye denk.
 * İl sınırları, il adları (çakışanlar atılır) ve sağ altta 50 km (yarıçap ≤ 150) ya da 100 km ölçek çubuğu çizer.
 */
export function bolgeHaritasi({ enlem, boylam, kmYaricap }) {
  const pxKm = (HARITA_Y / 2) / kmYaricap;
  const kos = Math.cos((enlem * Math.PI) / 180);
  const px = (lo) => 600 + (lo - boylam) * DERECE_KM * kos * pxKm;
  const py = (la) => 280 - (la - enlem) * DERECE_KM * pxKm;
  const ulkeler = yukle('ulkeler-bolge.json');
  const iller = yukle('iller.json');
  const olcekKm = kmYaricap <= 150 ? 50 : 100;
  const cubukG = olcekKm * pxKm;

  // İl adları: büyük (çok halkalı) iller önce; logo levhası, ölçek çubuğu ve kenarlarla ya da birbiriyle çakışan atılır.
  const yasak = [{ ...logoKutusu(), x2: logoKutusu().x2 + 8, y2: 96 }, { x1: 1140 - Math.max(cubukG, 80) - 8, y1: 488, x2: 1160, y2: 540 }];
  const yerlesen = [];
  const etiketler = [];
  const adKonum = [];
  let yazilar = '';
  for (const il of iller) {
    const x = px(il.m[0]), y = py(il.m[1]);
    const g = genislik(il.ad, 20);
    const kutu = { x1: x - 8, y1: y - 18, x2: x + 12 + g, y2: y + 10 };
    if (kutu.x1 < 24 || kutu.x2 > 1176 || kutu.y1 < 24 || kutu.y2 > 524) continue;
    if ([...yasak, ...yerlesen].some((o) => kesisir(kutu, o))) continue;
    yerlesen.push(kutu);
    etiketler.push(il.ad);
    adKonum.push({ ad: il.ad, x, y });
    yazilar += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3.5" fill="${RENK.gri}"/>` + yazi(il.ad, x + 9, y + 6, 20, RENK.gri);
  }

  const turSiniri = yollar(ulkeler.filter((u) => u.iso === 'TUR'), px, py);
  const govde = `<rect width="${HARITA_G}" height="${HARITA_Y}" fill="${RENK.deniz}"/>` + kirp(
    `<path d="${yollar(ulkeler.filter((u) => u.iso !== 'TUR'), px, py)}" fill="${RENK.komsu}" stroke="${RENK.cizgi}" stroke-width="1"/>` +
    `<path d="${yollar(iller, px, py)}" fill="${RENK.kara}" stroke="${RENK.ince}" stroke-width="1.2"/>` +
    `<path d="${turSiniri}" fill="none" stroke="${RENK.sinir}" stroke-width="1.6"/>`);
  const olcek = `<rect x="${(1140 - cubukG).toFixed(1)}" y="500" width="${cubukG.toFixed(1)}" height="5" fill="${RENK.murekkep}"/>` +
    yazi(`${olcekKm} km`, 1140, 530, 18, RENK.murekkep, 'end');
  const zemin = govde + yazilar + olcek;
  // zeminAdsiz + adKonum: il adlarını üst katmanda (ör. halolu) yeniden çizmek isteyen kartlar için
  return { px, py, zemin, zeminAdsiz: govde + olcek, adKonum, pxKm, olcekKm, etiketler, kmPx: (km) => km * pxKm };
}

const sar = (x) => ((((x + 180) % 360) + 360) % 360) - 180; // [-180, 180)

/**
 * Dünya haritası: eşdikdörtgen (enlem 84 K – 84 G), boylamMerkez kartın ortasında (x = 600).
 * Merkezden ±180° uzaktaki kesim çizgisini geçen ülkeler atılmaz: halka açılarak sürekli çizilir,
 * her iki yana kaydırılmış kopyalarıyla alan doldurulur (Antarktika gibi kutbu saran halkalar kutuptan kapatılır).
 */
export function dunyaHaritasi({ boylamMerkez, levha = false }) {
  const W = HARITA_G;
  const px = (lo) => 600 + (sar(lo - boylamMerkez) / 360) * W;
  const py = (la) => ((84 - Math.max(-84, Math.min(84, la))) / 168) * HARITA_Y;
  // Halkayı sürekli x'e açar: ardışık noktalar arası boylam farkı en kısa yoldan. kisitli: enlem 84 sınırına sıkışan nokta.
  const ac = (flat) => {
    const nok = [];
    const ekle = (x, la) => nok.push({ x, y: py(la), k: Math.abs(la) >= 84 });
    let x = (sar(flat[0] - boylamMerkez) / 360) * W + 600;
    ekle(x, flat[1]);
    for (let i = 2; i < flat.length; i += 2) {
      x += (sar(flat[i] - flat[i - 2]) / 360) * W;
      ekle(x, flat[i + 1]);
    }
    return nok;
  };
  const nokta = (n, kay, i) => `${i ? 'L' : 'M'}${(n.x + kay).toFixed(1)},${n.y.toFixed(1)}`;
  // dolgu: kutbu saran halka kutuptan kapatılır (yalnız dolgu için); cizgi: yalnız özgün kıyı, kenara sıkışmış parçalar çizilmez.
  const cizim = (halkalar, kapali) => {
    let dolgu = '', cizgi = '';
    for (const flat of halkalar) {
      const nok = ac(flat);
      const kutup = kapali && Math.abs(nok.at(-1).x - nok[0].x) > W / 2;
      const dnok = kutup ? [...nok, { x: nok.at(-1).x, y: flat[1] < 0 ? HARITA_Y : 0 }, { x: nok[0].x, y: flat[1] < 0 ? HARITA_Y : 0 }] : nok;
      const x1 = Math.min(...nok.map((n) => n.x)), x2 = Math.max(...nok.map((n) => n.x));
      for (const kay of [-W, 0, W]) {
        if (x2 + kay < 0 || x1 + kay > W) continue;
        dolgu += dnok.map((n, i) => nokta(n, kay, i)).join('') + (kapali ? 'Z' : '');
        let acik = false;
        nok.forEach((n, i) => {
          if (i && n.k && nok[i - 1].k) return void (acik = false);
          cizgi += (acik ? 'L' : 'M') + `${(n.x + kay).toFixed(1)},${n.y.toFixed(1)}`;
          acik = true;
        });
        if (kapali && !kutup) cizgi += 'Z';
      }
    }
    return { dolgu, cizgi };
  };
  const ulkeler = yukle('ulkeler-dunya.json');
  const u = cizim(ulkeler.flatMap((x) => x.r), true);
  let ic = `<path d="${u.dolgu}" fill="${RENK.komsu}" stroke="none"/><path data-rol="kiyi" d="${u.cizgi}" fill="none" stroke="${RENK.cizgi}" stroke-width="0.6"/>`;
  if (levha) ic += `<path d="${cizim(yukle('levhalar.json').map((l) => l.r), false).cizgi}" fill="none" stroke="${RENK.sinir}" stroke-width="1.2"/>`;
  const zemin = `<rect width="${W}" height="${HARITA_Y}" fill="${RENK.deniz}"/>` + kirp(ic);
  return { px, py, zemin, kiyi: u.cizgi, atif: levha ? LEVHA_ATIF : '' };
}

/**
 * Türkiye il haritası (sol 790 px, il bazında renklendirme): ilDolgu(ilAdı) → renk | null (varsayılan kara rengi).
 * Çizim: 24,9–45,6 D aralığı, sabit çerçeve; px/py yalnız bu alan içinde geçerlidir.
 */
export function ilRenkliHarita(ilDolgu, { w = 790 } = {}) {
  const pxDer = 49, kos = Math.cos((39 * Math.PI) / 180);
  const px = (lo) => 395 + (lo - 35.25) * pxDer * kos;
  const py = (la) => 318 - (la - 39.0) * pxDer;
  const ulkeler = yukle('ulkeler-bolge.json');
  const iller = yukle('iller.json');
  const gor = (flat) => { // yalnız alana değen halkalar
    for (let i = 0; i < flat.length; i += 2) {
      const x = px(flat[i]), y = py(flat[i + 1]);
      if (x > -60 && x < w + 60 && y > -60 && y < HARITA_Y + 60) return true;
    }
    return false;
  };
  const yollar2 = (liste) => liste.flatMap((u) => u.r.filter(gor).map((r) => yol(r, px, py))).join('');
  let ic = `<rect width="${w}" height="${HARITA_Y}" fill="${RENK.deniz}"/>` +
    `<path d="${yollar2(ulkeler.filter((u) => u.iso !== 'TUR'))}" fill="${RENK.komsu}" stroke="${RENK.cizgi}" stroke-width="1"/>`;
  for (const il of iller) ic += `<path d="${yollar2([il])}" fill="${ilDolgu(il.ad) ?? RENK.kara}" stroke="${RENK.ince}" stroke-width="1"/>`;
  ic += `<path d="${yollar2(ulkeler.filter((u) => u.iso === 'TUR'))}" fill="none" stroke="${RENK.sinir}" stroke-width="1.6"/>`;
  return { px, py, w, zemin: `<svg x="0" y="0" width="${w}" height="${HARITA_Y}" viewBox="0 0 ${w} ${HARITA_Y}" overflow="hidden">${ic}</svg>` };
}
