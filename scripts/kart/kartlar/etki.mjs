// Kart 21: Etki. USGS ShakeMap MMI konturları harita üstünde (Türkiye/yakın: il adlı bölge haritası; dünya: yerel ölçekli
// ülke haritası), varsa ShakeMap'in yüzey kırığı izi. Büyük sayı en yüksek MMI (ShakeMap), satır 1: DYFI ("Did You Feel It?")
// bildirim sayısı. PAGER alarm rengi, kayıp ve ekonomik tahmin YOK. Ürünler olaydan 10–60 dk sonra çıkar: çizici ürünü bulamazsa
// `urun-yok` hatası verir, calistir satırı bekletir (Worker yeniden tetikler, 3 saatte vazgeçer; düz metin yok).
// Veri: USGS (kamu malı). Levha çizgisi çizilmez (atıf gerekmez).
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { RENK, genislik, kart, kisalt, logoKutusu, sayiTr, tarihTr, yazi } from '../cekirdek.mjs';
import { HARITA_G, HARITA_Y, bolgeHaritasi, halka } from '../harita.mjs';
import { altBant, bantUyari, not, notUyari } from '../duzen.mjs';
import { mwBirim, olayBaslik } from './deprem.mjs';

const OLAY_ADRES = 'https://earthquake.usgs.gov/fdsnws/event/1/query';
const ZAMAN_ASIMI_MS = 15_000;
const DERECE_KM = 111.195;
export const NOT_METNI = 'Kaynak: USGS ShakeMap / DYFI (kamu malı); ilk sürümler güncellenir.';

/** Ürün (henüz) alınamadı: satır bekletilir, deneme sayılmaz. */
export class UrunYok extends Error {
  constructor(ayrinti) {
    super(`urun-yok: ${ayrinti}`);
    this.kod = 'urun-yok';
  }
}

async function jsonAl(url, fetchFn) {
  let yanit;
  try {
    yanit = await fetchFn(url, { signal: AbortSignal.timeout(ZAMAN_ASIMI_MS), headers: { accept: 'application/json' } });
  } catch (e) {
    throw new UrunYok(`${url} alınamadı (${e.message})`);
  }
  if (!yanit.ok) throw new UrunYok(`${url} yanıtı ${yanit.status}`);
  try {
    return await yanit.json();
  } catch {
    throw new UrunYok(`${url} çözülemedi`);
  }
}

const cizgiler = (g) => (g?.type === 'LineString' ? [g.coordinates] : g?.type === 'MultiLineString' ? g.coordinates : []);
const halkalar = (g) => (g?.type === 'Polygon' ? g.coordinates : g?.type === 'MultiPolygon' ? g.coordinates.flat() : []);
const nokta = (p) => Number.isFinite(p?.[0]) && Number.isFinite(p?.[1]);

/**
 * USGS olay ürünleri → {konturlar: [{deger, cizgiler: [[[boylam, enlem], ...]]}] (artan MMI), maxMmi, dyfi | null, rupture | null}.
 * ShakeMap ya da konturu yoksa (henüz çıkmadı) UrunYok. DYFI ve yüzey kırığı isteğe bağlıdır.
 */
export async function urunCek(usgsId, { fetchFn = fetch } = {}) {
  const ev = await jsonAl(`${OLAY_ADRES}?eventid=${encodeURIComponent(usgsId)}&format=geojson`, fetchFn);
  const urunler = (ev.features?.[0] ?? ev).properties?.products ?? {};
  const sm = urunler.shakemap?.[0];
  if (!sm) throw new UrunYok('ShakeMap ürünü yok');
  const kUrl = sm.contents?.['download/cont_mmi.json']?.url;
  if (!kUrl) throw new UrunYok('cont_mmi.json yok');
  const kontur = await jsonAl(kUrl, fetchFn);
  const konturlar = (kontur.features ?? [])
    .map((f) => ({ deger: Number(f.properties?.value), cizgiler: cizgiler(f.geometry).map((c) => c.filter(nokta)).filter((c) => c.length > 1) }))
    .filter((k) => Number.isFinite(k.deger) && k.cizgiler.length)
    .sort((a, b) => a.deger - b.deger);
  if (!konturlar.length) throw new UrunYok('MMI konturu boş');

  let rupture = null;
  const rUrl = sm.contents?.['download/rupture.json']?.url;
  if (rUrl) {
    try {
      const r = (await jsonAl(rUrl, fetchFn)).features?.flatMap((f) => halkalar(f.geometry).map((h) => h.filter(nokta))).filter((h) => h.length > 2);
      if (r?.length) rupture = r;
    } catch { /* isteğe bağlı */ }
  }
  const dy = Number(urunler.dyfi?.[0]?.properties?.numResp);
  const mm = Number(sm.properties?.maxmmi);
  return {
    konturlar, rupture,
    dyfi: Number.isFinite(dy) && dy > 0 ? Math.round(dy) : null,
    maxMmi: Number.isFinite(mm) && mm > 0 ? mm : konturlar.at(-1).deger,
  };
}

// ---- harita ----
const ulkeler = JSON.parse(fs.readFileSync(fileURLToPath(new URL('../../../data/harita/ulkeler-dunya.json', import.meta.url)), 'utf8'));
const sar = (x) => ((((x + 180) % 360) + 360) % 360) - 180;

/** Merkez (600, 280), kmYaricap = alanın yarı yüksekliği: yerel eşdikdörtgen, ülke kara parçaları ve ölçek çubuğu (dünya olayları). */
function yerelHarita({ enlem, boylam, kmYaricap }) {
  const pxKm = (HARITA_Y / 2) / kmYaricap;
  const kos = Math.max(0.05, Math.cos((enlem * Math.PI) / 180));
  const px = (lo) => 600 + sar(lo - boylam) * DERECE_KM * kos * pxKm;
  const py = (la) => 280 - (la - enlem) * DERECE_KM * pxKm;
  let d = '';
  for (const u of ulkeler) {
    for (const r of u.r) {
      const xs = [], ys = [];
      for (let i = 0; i < r.length; i += 2) { xs.push(px(r[i])); ys.push(py(r[i + 1])); }
      const dLo = Math.max(...r.filter((_, i) => i % 2 === 0).map((lo) => sar(lo - boylam))) - Math.min(...r.filter((_, i) => i % 2 === 0).map((lo) => sar(lo - boylam)));
      if (dLo > 200) continue; // kutbu / tarih çizgisini saran halka: yerel ölçekte anlamsız
      if (Math.max(...xs) < -40 || Math.min(...xs) > HARITA_G + 40 || Math.max(...ys) < -40 || Math.min(...ys) > HARITA_Y + 40) continue;
      d += xs.map((x, i) => `${i ? 'L' : 'M'}${x.toFixed(1)},${ys[i].toFixed(1)}`).join('') + 'Z';
    }
  }
  const olcekKm = kmYaricap <= 150 ? 50 : kmYaricap <= 400 ? 100 : 200;
  const cubukG = olcekKm * pxKm;
  const zemin = `<rect width="${HARITA_G}" height="${HARITA_Y}" fill="${RENK.deniz}"/>` +
    `<svg x="0" y="0" width="${HARITA_G}" height="${HARITA_Y}" viewBox="0 0 ${HARITA_G} ${HARITA_Y}" overflow="hidden"><path d="${d}" fill="${RENK.kara}" stroke="${RENK.sinir}" stroke-width="1.2"/></svg>` +
    `<rect x="${(1140 - cubukG).toFixed(1)}" y="500" width="${cubukG.toFixed(1)}" height="5" fill="${RENK.murekkep}"/>` +
    yazi(`${olcekKm} km`, 1140, 530, 18, RENK.murekkep, 'end');
  return { px, py, zemin, olcekKm, cubukG };
}

// MMI çizgisi renkleri: değer arttıkça koyulaşan indigo; çizgi kalınlığı da artar (renk körü okuması için).
const RAMPA = [[4, '#a8a2f0'], [5, '#8982e8'], [6, '#6d65de'], [7, '#4f47d3'], [8, '#3d36c9'], [9, '#2a2490'], [10, '#16124f']];
const rampa = (v) => RAMPA.find(([e]) => v < e + 1)?.[1] ?? RAMPA.at(-1)[1];
// MMI < 6: ince ve soluk (gürültülü uzak kuyruk); 6 ve üstü giderek kalınlaşır.
const kalinlik = (v) => (v < 6 ? 1.0 + (v - 4) * 0.15 : 1.9 + Math.min(v - 6, 4) * 0.4).toFixed(2);
const opaklik = (v) => (v < 6 ? 0.55 : 1);
const degerMetni = (v) => sayiTr(v, Number.isInteger(v) ? 0 : 1);

// Konturları sığdıran yarıçap (km): MMI ≥ 5 konturları (yoksa hepsi) ve merkez üssü görünür, kenarlardan %15 pay.
function kmYaricapi(o, konturlar) {
  const secili = konturlar.filter((k) => k.deger >= 5);
  const liste = secili.length ? secili : konturlar;
  const kos = Math.cos((o.enlem * Math.PI) / 180);
  let dy = 0, dx = 0;
  for (const k of liste) {
    for (const c of k.cizgiler) {
      for (const [lo, la] of c) {
        dy = Math.max(dy, Math.abs(la - o.enlem) * DERECE_KM);
        dx = Math.max(dx, Math.abs(sar(lo - o.boylam)) * DERECE_KM * kos);
      }
    }
  }
  return Math.min(900, Math.max(60, Math.max(dy, dx / (600 / 280)) * 1.15));
}

// Douglas–Peucker (piksel uzayında, eps ~1 px): konturdaki ShakeMap gürültüsünü azaltır.
function sadelestir(n, eps) {
  if (n.length < 3) return n;
  const [ax, ay] = n[0], [bx, by] = n.at(-1);
  if (Math.hypot(bx - ax, by - ay) < 1e-6) { // kapalı halka: ilk noktaya en uzak noktadan ikiye böl
    let k = 1;
    for (let i = 2; i < n.length - 1; i++) if (Math.hypot(n[i][0] - ax, n[i][1] - ay) > Math.hypot(n[k][0] - ax, n[k][1] - ay)) k = i;
    return [...sadelestir(n.slice(0, k + 1), eps).slice(0, -1), ...sadelestir(n.slice(k), eps)];
  }
  const dx = bx - ax, dy = by - ay, uz = Math.hypot(dx, dy) || 1e-9;
  let en = 0, i0 = 0;
  for (let i = 1; i < n.length - 1; i++) {
    const d = Math.abs(dy * (n[i][0] - ax) - dx * (n[i][1] - ay)) / uz;
    if (d > en) { en = d; i0 = i; }
  }
  if (en <= eps) return [n[0], n.at(-1)];
  return [...sadelestir(n.slice(0, i0 + 1), eps).slice(0, -1), ...sadelestir(n.slice(i0), eps)];
}

const kesisir = (a, b) => a.x1 < b.x2 && b.x1 < a.x2 && a.y1 < b.y2 && b.y1 < a.y2;

function etiketler(konturlar, px, py, cx, cy, olcek) {
  const logo = logoKutusu();
  const yasak = [
    { ...logo, x2: logo.x2 + 8, y2: 96 },
    { x1: 1140 - Math.max(olcek, 80) - 10, y1: 488, x2: 1170, y2: 545 },
    { x1: 0, y1: 520, x2: 1200, y2: 560 },
    { x1: cx - 26, y1: cy - 26, x2: cx + 26, y2: cy + 26 },
  ];
  const yerlesen = [];
  const cikti = [];
  // tamsayı değerler öncelikli; hepsi ≤ 7 ise yarımlar da etiketlenir
  const tam = konturlar.filter((k) => Number.isInteger(k.deger));
  const adaylar = konturlar.length <= 7 ? konturlar : tam;
  [...adaylar].reverse().forEach((k, sira) => {
    const hedefAci = (-70 + sira * 41) * (Math.PI / 180);
    const noktalar = [];
    for (const c of k.cizgiler) {
      const adim = Math.max(1, Math.floor(c.length / 60));
      for (let i = 0; i < c.length; i += adim) noktalar.push([px(c[i][0]), py(c[i][1])]);
    }
    const metin = degerMetni(k.deger);
    const w = genislik(metin, 17) + 14;
    const aci = ([x, y]) => Math.abs(Math.atan2(Math.sin(Math.atan2(y - cy, x - cx) - hedefAci), Math.cos(Math.atan2(y - cy, x - cx) - hedefAci)));
    const sirali = noktalar.filter(([x, y]) => x > 50 && x < 1150 && y > 110 && y < 505).sort((a, b) => aci(a) - aci(b));
    for (const [x, y] of sirali) {
      const kutu = { x1: x - w / 2, y1: y - 12, x2: x + w / 2, y2: y + 12 };
      if ([...yasak, ...yerlesen].some((r) => kesisir(kutu, r))) continue;
      yerlesen.push({ x1: kutu.x1 - 4, y1: kutu.y1 - 4, x2: kutu.x2 + 4, y2: kutu.y2 + 4 });
      const renk = rampa(k.deger);
      cikti.push({ metin, svg: `<rect x="${kutu.x1.toFixed(1)}" y="${kutu.y1}" width="${w.toFixed(1)}" height="24" rx="12" fill="${RENK.kagit}" fill-opacity="0.95" stroke="${renk}" stroke-width="1.5"/>` + yazi(metin, x, y + 6, 17, RENK.murekkep, 'middle') });
      break;
    }
  });
  return cikti;
}

function baslikMetni(veri) {
  const o = veri.olay;
  const b = olayBaslik(veri);
  const mw = `${mwBirim(o.tur).startsWith('Mw') ? 'Mw' : 'M'} ${sayiTr(o.mw, 1)}`;
  for (const aday of [`${b} · ${mw} · sarsıntı haritası`, `${b} · sarsıntı haritası`, `${b} · ${mw}`, b]) if (genislik(aday, 46) <= 800) return aday;
  return kisalt(b, 46, 800);
}

/** → {svg, uyari, bant, notMetni, etiketler}. urun: urunCek çıktısı. */
export function etkiSvg(veri, urun) {
  const o = veri.olay;
  const kmYaricap = kmYaricapi(o, urun.konturlar);
  const yerel = o.bolge === 'turkiye' || o.bolge === 'yakin';
  const h = yerel ? bolgeHaritasi({ enlem: o.enlem, boylam: o.boylam, kmYaricap: Math.min(700, kmYaricap) }) : yerelHarita({ enlem: o.enlem, boylam: o.boylam, kmYaricap });
  const sar0 = yerel ? (lo) => lo : (lo) => o.boylam + sar(lo - o.boylam); // bölge haritası doğrusal: sarma gerekmez
  const px = (lo) => h.px(sar0(lo)), py = (la) => h.py(la);
  const yol = (c, kapat) => c.map(([lo, la], i) => `${i ? 'L' : 'M'}${px(lo).toFixed(1)},${py(la).toFixed(1)}`).join('') + (kapat ? 'Z' : '');
  const sade = (c) => sadelestir(c.map(([lo, la]) => [px(lo), py(la)]), 1).map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`).join('');
  const cx = px(o.boylam), cy = py(o.enlem);

  let ic = '';
  if (urun.rupture) ic += urun.rupture.map((r) => `<path d="${yol(r, true)}" fill="${RENK.murekkep}" fill-opacity="0.12" stroke="${RENK.murekkep}" stroke-width="1.6" stroke-opacity="0.8"/>`).join('');
  for (const k of urun.konturlar) {
    ic += `<path d="${k.cizgiler.map(sade).join('')}" fill="none" stroke="${rampa(k.deger)}" stroke-opacity="${opaklik(k.deger)}" stroke-width="${kalinlik(k.deger)}" stroke-linejoin="round" stroke-linecap="round"/>`;
  }
  const et = etiketler(urun.konturlar, px, py, cx, cy, h.olcekKm ? (h.cubukG ?? h.olcekKm * h.pxKm) : 80);
  // il adları konturların ÜSTÜNDE, kâğıt rengi halolu (yerel haritada h.zeminAdsiz + adKonum; dünya haritasında il adı yok)
  const adlar = h.adKonum ? h.adKonum.map((a) => {
    const t = yazi(a.ad, a.x + 9, a.y + 6, 20, RENK.gri);
    return `<circle cx="${a.x.toFixed(1)}" cy="${a.y.toFixed(1)}" r="3.5" fill="${RENK.gri}"/>` +
      t.replace('fill="' + RENK.gri + '"', `fill="${RENK.kagit}" stroke="${RENK.kagit}" stroke-width="5" stroke-linejoin="round"`) + t;
  }).join('') : '';
  let s = (h.zeminAdsiz ?? h.zemin) + `<svg x="0" y="0" width="${HARITA_G}" height="${HARITA_Y}" viewBox="0 0 ${HARITA_G} ${HARITA_Y}" overflow="hidden">${ic}</svg>` + adlar;
  s += et.map((e) => e.svg).join('');
  if (cx > 10 && cx < HARITA_G - 10 && cy > 10 && cy < 510) s += halka(cx, cy, 15, 6, RENK.murekkep);

  const bant = {
    sayi: sayiTr(urun.maxMmi, 1).replace(/,0$/, ''),
    birim: 'en yüksek şiddet MMI',
    baslik: baslikMetni(veri),
    satir1: urun.dyfi ? `Did You Feel It? ${sayiTr(urun.dyfi)} bildirim` : 'ShakeMap şiddet konturları (MMI)',
    satir2: tarihTr(o.zaman, { saniye: false }),
  };
  s += `<rect x="44" y="524" width="${(genislik(NOT_METNI, 18) + 24).toFixed(1)}" height="32" rx="8" fill="${RENK.kagit}" fill-opacity="0.88"/>` + not(NOT_METNI) + altBant(bant);
  return { svg: s, uyari: [...bantUyari(bant), ...notUyari(NOT_METNI)], bant, notMetni: NOT_METNI, etiketler: et.map((e) => e.metin) };
}

const kac = (t) => String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

/** Kanal açıklaması: Worker'ın başlık satırı (satir.metin) + "USGS ShakeMap · Did You Feel It? N bildirim" (sayı yoksa yalnız ShakeMap). */
export function aciklamaYap(veri, satir, dyfi) {
  const o = veri.olay;
  const mw = mwBirim(o.tur).startsWith('Mw') ? `Mw ${sayiTr(o.mw, 1)}` : `M ${sayiTr(o.mw, 1)} (yaklaşık)`;
  const ilk = String(satir?.metin ?? '').split('\n')[0] || `🗺 <b>${mw} · ${kac(olayBaslik(veri))} · sarsıntı haritası</b>`;
  return `${ilk}\nUSGS ShakeMap${dyfi ? ` · Did You Feel It? ${sayiTr(dyfi)} bildirim` : ''}`;
}

/**
 * Kart 21 çizicisi: veri (+ satır) → {png, aciklama}. Ürünü USGS'den çeker; yoksa UrunYok fırlatır (urun: sınama için hazır ürün).
 */
export async function etki(veri, satir, { fetchFn = fetch, urun } = {}) {
  let u = urun;
  if (!u) {
    const id = veri.olay?.kaynaklar?.usgs?.id;
    if (!id) throw new Error('etki kartı: olayda USGS kimliği yok');
    u = await urunCek(id, { fetchFn });
  }
  const r = etkiSvg(veri, u);
  if (r.uyari.length) console.warn('etki kartı düzen uyarısı:', r.uyari.join(' | '));
  return { png: await kart(r.svg), aciklama: aciklamaYap(veri, satir, u.dyfi) };
}
