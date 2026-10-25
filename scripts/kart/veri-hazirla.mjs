// Harita verisini hazırlar (bir kez çalışır, çıktı kommitlenir; ham indirmeler kommitlenmez).
// Kullanım: node scripts/kart/veri-hazirla.mjs <ham-klasör>   (klasör yoksa oluşturulur, dosyalar yoksa indirilir)
// Ek: --tarihte-bugun → USGS FDSN'den data/tarihte-bugun.json (yalnız bunu üretir).
// Çıktı: data/harita/{ulkeler-bolge,ulkeler-dunya,iller,levhalar}.json + kaynak.txt
// Halkalar düz sayı dizisidir: [boylam, enlem, boylam, enlem, ...].
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const CIKTI = fileURLToPath(new URL('../../data/harita/', import.meta.url));
const NE = 'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/';
const KAYNAKLAR = {
  'ne_10m_admin_0_countries.geojson': NE + 'ne_10m_admin_0_countries.geojson',
  'ne_50m_admin_0_countries.geojson': NE + 'ne_50m_admin_0_countries.geojson',
  'ne_10m_admin_1_states_provinces.geojson': NE + 'ne_10m_admin_1_states_provinces.geojson',
  'PB2002_boundaries.json': 'https://raw.githubusercontent.com/fraxen/tectonicplates/master/GeoJSON/PB2002_boundaries.json',
};

const USGS_ADRES = 'https://earthquake.usgs.gov/fdsnws/event/1/query';
const TR_KUTU = { enAz: 35.5, enCok: 42.5, boyAz: 25.5, boyCok: 45 };

const rad = (d) => (d * Math.PI) / 180;
const mesafe = (la1, lo1, la2, lo2) => {
  const a = Math.sin(rad(la2 - la1) / 2) ** 2 + Math.cos(rad(la1)) * Math.cos(rad(la2)) * Math.sin(rad(lo2 - lo1) / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(a));
};
// Düz halka [lo, la, lo, la, ...] içinde nokta mı (ışın yöntemi).
const icinde = (lo, la, h) => {
  let ic = false;
  for (let i = 0, j = h.length - 2; i < h.length; j = i, i += 2) {
    const xi = h[i], yi = h[i + 1], xj = h[j], yj = h[j + 1];
    if (yi > la !== yj > la && lo < ((xj - xi) * (la - yi)) / (yj - yi) + xi) ic = !ic;
  }
  return ic;
};

const enYakin = (lo, la, halkalar) => {
  let en = Infinity;
  for (const h of halkalar) for (let i = 0; i < h.length; i += 2) en = Math.min(en, mesafe(la, lo, h[i + 1], h[i]));
  return en;
};

/**
 * Yer adı. girdi: {iller: iller.json, ulkeler: ulkeler-bolge.json (iso, ad, r)}.
 * Türkiye içinde: içinde olduğu il (yoksa sınıra en yakın il). Başka ülkede: ülke adı (Türkçe).
 * Denizde: kıyıya ≤ 15 km ise o il; en yakın kıyı Türk iliyse (≤ 100 km) "<İl> açıkları", başka ülkenin kıyısıysa (ya da 100 km'den uzaksa) en yakın ülke "<Ülke> açıkları".
 */
export function yerAdi(boylam, enlem, { iller, ulkeler }) {
  const il = iller.find((x) => x.r.some((h) => icinde(boylam, enlem, h)));
  const ulke = ulkeler.find((u) => u.r.some((h) => icinde(boylam, enlem, h)));
  const enYakinIl = () => iller.map((x) => [x.ad, enYakin(boylam, enlem, x.r)]).sort((p, q) => p[1] - q[1])[0];
  if (il) return il.ad;
  if (ulke && ulke.iso === 'TUR') return enYakinIl()[0];
  if (ulke) return ulke.ad;
  const [ilAd, ilKm] = enYakinIl();
  if (ilKm <= 15) return ilAd;   // körfez/kıyı: sadeleştirilmiş sınırın dışına taşan kıyı noktası
  const u = ulkeler.filter((x) => x.iso !== 'TUR').map((x) => [x.ad, enYakin(boylam, enlem, x.r)]).sort((p, q) => p[1] - q[1])[0];
  if (u && u[1] < ilKm) return `${u[0]} açıkları`;   // en yakın kıyı başka ülkenin
  if (ilKm <= 100) return `${ilAd} açıkları`;
  return u ? `${u[0]} açıkları` : 'Türkiye çevresi';
}

const TSI = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Istanbul', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
/** ms → Türkiye yerel tarih/saati (Europe/Istanbul, tarihsel ofsetler dahil): {t: 'YYYY-AA-GG', s: 'SS:DD'}. */
export function yerelZaman(ms) {
  const p = Object.fromEntries(TSI.formatToParts(new Date(ms)).map((x) => [x.type, x.value]));
  return { t: `${p.year}-${p.month}-${p.day}`, s: `${p.hour}:${p.minute}` };
}
/** USGS GeoJSON özelliği → {t, s (Türkiye yerel saati), enlem, boylam, mw, yer}. */
export function kayitDonustur(f, harita) {
  const [boylam, enlem] = f.geometry.coordinates;
  return {
    ...yerelZaman(f.properties.time),
    enlem: yuvarla(enlem, 2), boylam: yuvarla(boylam, 2), mw: yuvarla(f.properties.mag, 1), yer: yerAdi(boylam, enlem, harita),
  };
}

/** USGS FDSN (kamu malı): 1900–bugün, Türkiye çevresi kutusu, M ≥ 6 → data/tarihte-bugun.json. */
async function tarihteBugunHazirla() {
  const harita = { iller: JSON.parse(fs.readFileSync(path.join(CIKTI, 'iller.json'), 'utf8')), ulkeler: JSON.parse(fs.readFileSync(path.join(CIKTI, 'ulkeler-bolge.json'), 'utf8')) };
  const q = new URLSearchParams({
    format: 'geojson', starttime: '1900-01-01', endtime: new Date().toISOString().slice(0, 10), minmagnitude: '6',
    minlatitude: TR_KUTU.enAz, maxlatitude: TR_KUTU.enCok, minlongitude: TR_KUTU.boyAz, maxlongitude: TR_KUTU.boyCok,
    orderby: 'time-asc', limit: '20000',
  });
  const r = await fetch(`${USGS_ADRES}?${q}`);
  if (!r.ok) throw new Error(`USGS: ${r.status}`);
  const kayit = (await r.json()).features.map((f) => kayitDonustur(f, harita));
  const s = JSON.stringify(kayit);
  fs.writeFileSync(path.join(CIKTI, '..', 'tarihte-bugun.json'), s);
  console.log('tarihte-bugun.json', kayit.length, 'kayıt', (s.length / 1024).toFixed(0), 'KB');
}

const BOLGE_KUTU = { d1: 19, d2: 50, k1: 30, k2: 47 };
const DERECE_KM = 111.195;

/** Douglas–Peucker (yinelemesiz). tol: derece; boylam enleme göre ölçeklenir. */
export function sadelestir(nok, tol, kos = 1) {
  if (nok.length <= 2) return nok;
  const tut = new Uint8Array(nok.length);
  tut[0] = tut[nok.length - 1] = 1;
  const yigin = [[0, nok.length - 1]];
  while (yigin.length) {
    const [a, b] = yigin.pop();
    const [ax, ay] = [nok[a][0] * kos, nok[a][1]];
    const [bx, by] = [nok[b][0] * kos, nok[b][1]];
    const dx = bx - ax, dy = by - ay, uz = Math.hypot(dx, dy);
    let en = -1, ei = -1;
    for (let i = a + 1; i < b; i++) {
      const px = nok[i][0] * kos - ax, py = nok[i][1] - ay;
      const s = uz === 0 ? Math.hypot(px, py) : Math.abs(px * dy - py * dx) / uz;
      if (s > en) (en = s), (ei = i);
    }
    if (en > tol) (tut[ei] = 1), yigin.push([a, ei], [ei, b]);
  }
  return nok.filter((_, i) => tut[i]);
}

const alan = (h) => { let s = 0; for (let i = 0, n = h.length; i < n; i++) { const [x1, y1] = h[i], [x2, y2] = h[(i + 1) % n]; s += x1 * y2 - x2 * y1; } return s / 2; };
const kutu = (h) => ({ d1: Math.min(...h.map((p) => p[0])), d2: Math.max(...h.map((p) => p[0])), k1: Math.min(...h.map((p) => p[1])), k2: Math.max(...h.map((p) => p[1])) });
const kesisir = (a, b) => a.d1 <= b.d2 && b.d1 <= a.d2 && a.k1 <= b.k2 && b.k1 <= a.k2;
const yuvarla = (s, b) => Math.round(s * 10 ** b) / 10 ** b;
const duz = (h, b) => h.flatMap(([x, y]) => [yuvarla(x, b), yuvarla(y, b)]);
const dis = (geo) => (geo.type === 'Polygon' ? [geo.coordinates] : geo.coordinates).map((p) => p[0]); // yalnız dış halkalar

function halkalar(geo, { tolKm, basamak, enAz, filtre }) {
  const sonuc = [];
  for (const h of dis(geo)) {
    if (filtre && !kesisir(kutu(h), filtre)) continue;
    if (Math.abs(alan(h)) < enAz) continue;
    const s = sadelestir(h, tolKm / DERECE_KM, Math.cos((39 * Math.PI) / 180));
    if (s.length >= 4) sonuc.push(duz(s, basamak));
  }
  return sonuc;
}

function agirlikMerkezi(flat) {
  const n = flat.length / 2;
  let a = 0, cx = 0, cy = 0;
  for (let i = 0; i < n; i++) {
    const x1 = flat[2 * i], y1 = flat[2 * i + 1], x2 = flat[2 * ((i + 1) % n)], y2 = flat[2 * ((i + 1) % n) + 1];
    const c = x1 * y2 - x2 * y1;
    a += c; cx += (x1 + x2) * c; cy += (y1 + y2) * c;
  }
  return [yuvarla(cx / (3 * a), 2), yuvarla(cy / (3 * a), 2)];
}

async function hamDosya(klasor, ad) {
  const yol = path.join(klasor, ad);
  if (!fs.existsSync(yol)) {
    const r = await fetch(KAYNAKLAR[ad]);
    if (!r.ok) throw new Error(`${ad}: ${r.status}`);
    fs.writeFileSync(yol, Buffer.from(await r.arrayBuffer()));
  }
  return JSON.parse(fs.readFileSync(yol, 'utf8'));
}

const yaz = (ad, veri) => {
  const s = JSON.stringify(veri);
  fs.writeFileSync(path.join(CIKTI, ad), s);
  console.log(ad, (s.length / 1024).toFixed(0), 'KB');
};

async function main() {
  if (process.argv.includes('--tarihte-bugun')) return tarihteBugunHazirla();
  const klasor = path.resolve(process.argv.slice(2).find((a) => !a.startsWith('--')) ?? 'ham-harita');
  fs.mkdirSync(klasor, { recursive: true });
  fs.mkdirSync(CIKTI, { recursive: true });

  const u10 = await hamDosya(klasor, 'ne_10m_admin_0_countries.geojson');
  const bolge = [];
  for (const f of u10.features) {
    const r = halkalar(f.geometry, { tolKm: 1, basamak: 3, enAz: 0.0002, filtre: BOLGE_KUTU });
    if (r.length) bolge.push({ iso: f.properties.ADM0_A3, ad: f.properties.NAME_TR, r });
  }
  yaz('ulkeler-bolge.json', bolge);

  const u50 = await hamDosya(klasor, 'ne_50m_admin_0_countries.geojson');
  const dunya = [];
  for (const f of u50.features) {
    const r = halkalar(f.geometry, { tolKm: 10, basamak: 2, enAz: 0.02 });
    if (r.length) dunya.push({ iso: f.properties.ADM0_A3, ad: f.properties.NAME_TR, r });
  }
  yaz('ulkeler-dunya.json', dunya);

  const il = await hamDosya(klasor, 'ne_10m_admin_1_states_provinces.geojson');
  const iller = [];
  for (const f of il.features.filter((x) => x.properties.adm0_a3 === 'TUR')) {
    const r = halkalar(f.geometry, { tolKm: 1, basamak: 3, enAz: 0.0002 });
    const enBuyuk = r.reduce((a, b) => (b.length > a.length ? b : a));
    iller.push({ ad: f.properties.name_tr || f.properties.name, m: agirlikMerkezi(enBuyuk), r });
  }
  yaz('iller.json', iller);

  const pb = await hamDosya(klasor, 'PB2002_boundaries.json');
  const levhalar = pb.features
    .filter((f) => f.geometry.type === 'LineString')
    .map((f) => ({ ad: f.properties.Name, r: duz(sadelestir(f.geometry.coordinates, 0.05), 2) }));
  yaz('levhalar.json', levhalar);

  fs.writeFileSync(path.join(CIKTI, 'kaynak.txt'), KAYNAK_METNI);
  const toplam = fs.readdirSync(CIKTI).reduce((t, d) => t + fs.statSync(path.join(CIKTI, d)).size, 0);
  console.log('toplam', (toplam / 1024).toFixed(0), 'KB');
  if (toplam > 2 * 1024 * 1024) throw new Error('data/harita 2 MB sınırını aştı');
}

const KAYNAK_METNI = `Harita verisi kaynakları (scripts/kart/veri-hazirla.mjs ile üretildi; ham indirmeler kommitlenmez)

ulkeler-bolge.json  Natural Earth 1:10m ülke sınırları (ne_10m_admin_0_countries), kutu 19-50 D / 30-47 K,
                    Douglas-Peucker ile ~1 km sadeleştirilmiş. Alanlar: iso (ADM0_A3), ad (NAME_TR).
ulkeler-dunya.json  Natural Earth 1:50m ülke sınırları (ne_50m_admin_0_countries), ~10 km sadeleştirilmiş.
iller.json          Natural Earth 1:10m birinci düzey idari bölümler (ne_10m_admin_1_states_provinces), yalnız Türkiye,
                    ~1 km sadeleştirilmiş; m = yazı yeri (en büyük halkanın ağırlık merkezi).
                    Kaynak: https://github.com/nvkelso/natural-earth-vector (geojson/)
                    Lisans: Natural Earth kamu malıdır (public domain), atıf zorunlu değildir.
                    https://www.naturalearthdata.com/about/terms-of-use/

levhalar.json       PB2002 levha sınırları (GeoJSON/PB2002_boundaries.json), ~5 km sadeleştirilmiş.
                    Özgün veri: Bird, P. (2003), An updated digital model of plate boundaries,
                    Geochemistry, Geophysics, Geosystems, 4(3), 1027, doi:10.1029/2001GC000252.
                    GeoJSON dönüşümü: Hugo Ahlenius (Nordpil) ve csterling, https://github.com/fraxen/tectonicplates
                    Lisans: Open Data Commons Attribution License (ODC-By) 1.0,
                    https://opendatacommons.org/licenses/by/1-0/ ; depodaki LICENSE.md
                    Atıf: Bird (2003); Hugo Ahlenius, Nordpil.

Halkalar düz sayı dizisidir: [boylam, enlem, boylam, enlem, ...]. Yalnız dış halkalar saklanır.
`;

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) await main();
