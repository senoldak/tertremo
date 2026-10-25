// Kart 5: Kaynaklar. Aynı depremi veren kurumların büyüklük ve konum farkı: bölge haritasında her kaynağın konumu
// (indigo/gri tonlarıyla, etiketli), sağ üstte kaynak listesi. Büyük sayı: en büyük büyüklük farkı (ΔM).
import { RENK, genislik, kart, sayiTr, tarihTr, yazi } from '../cekirdek.mjs';
import { bolgeHaritasi } from '../harita.mjs';
import { mesafeKm } from '../ipe.mjs';
import { altBant, bantUyari, not, notUyari } from '../duzen.mjs';
import { olayBaslik } from './deprem.mjs';

const AD = { afad: 'AFAD', kandilli: 'Kandilli', emsc: 'EMSC', usgs: 'USGS' };
const TON = { afad: RENK.indigo, kandilli: '#6b64d4', emsc: RENK.gri, usgs: RENK.murekkep };
const BIRIM_UZUN = "büyüklük farkı (Mw'ye çevrilmiş)";
const SIRA = ['afad', 'kandilli', 'emsc', 'usgs'];

const sayisal = (x) => typeof x === 'number' && Number.isFinite(x);
const mwDeger = (k) => (sayisal(k.mw) ? k.mw : sayisal(k.buyukluk) ? k.buyukluk : null);

/** Veriden kaynak listesi: [{ad, anahtar, m, tur, derinlik, enlem, boylam}] (büyüklüğü olmayanlar atılır). */
export function kaynakListesi(o) {
  const k = o.kaynaklar ?? {};
  const anahtarlar = [...SIRA.filter((a) => k[a]), ...Object.keys(k).filter((a) => !SIRA.includes(a))];
  return anahtarlar.map((a) => ({ a, v: k[a] })).filter(({ v }) => v && typeof v === 'object').map(({ a, v }) => ({
    anahtar: a, ad: AD[a] ?? String(a).toUpperCase(), m: mwDeger(v),
    // Ham değer kendi türüyle; ham büyüklük yoksa dönüştürülmüş Mw "(Mw)" ile
    ham: sayisal(v.buyukluk) ? v.buyukluk : mwDeger(v), hamTur: sayisal(v.buyukluk) ? (v.tur ?? 'M') : '(Mw)',
    derinlik: sayisal(v.derinlik) ? v.derinlik : null,
    enlem: sayisal(v.enlem) ? v.enlem : null, boylam: sayisal(v.boylam) ? v.boylam : null,
  })).filter((s) => s.m != null);
}

/** En büyük büyüklük farkı ve en büyük konum farkı (km; konumu olan kaynaklar arasında, yoksa null). */
export function farklar(liste) {
  const ms = liste.map((s) => s.m);
  const dM = ms.length >= 2 ? Math.max(...ms) - Math.min(...ms) : 0;
  const k = liste.filter((s) => s.enlem != null && s.boylam != null);
  let km = null;
  for (let i = 0; i < k.length; i++) for (let j = i + 1; j < k.length; j++) km = Math.max(km ?? 0, mesafeKm(k[i].enlem, k[i].boylam, k[j].enlem, k[j].boylam));
  return { dM, km };
}

const kesisir = (a, b) => a.x1 < b.x2 && b.x1 < a.x2 && a.y1 < b.y2 && b.y1 < a.y2;
const etiket = (s) => `${s.ad} ${sayiTr(s.ham, 1)} ${s.hamTur}`;

/** → {svg, uyari, dM, km}. */
export function kaynaklarSvg(veri) {
  const o = veri.olay;
  const liste = kaynakListesi(o);
  if (liste.length < 2) throw new Error('kaynaklar kartı: en az iki kaynak gerekir');
  const { dM, km } = farklar(liste);

  // Konumsuz kaynak: yalnız tercih edilen kaynak olayın konumunda çizilir.
  const konumlu = liste.map((s) => (s.enlem != null ? s : s.anahtar === o.kaynak && sayisal(o.enlem) ? { ...s, enlem: o.enlem, boylam: o.boylam } : s));
  const cizilen = konumlu.filter((s) => s.enlem != null && s.boylam != null);
  const mrk = cizilen.length ? cizilen : [{ enlem: o.enlem, boylam: o.boylam }];
  const mEnlem = mrk.reduce((t, s) => t + s.enlem, 0) / mrk.length;
  const mBoylam = mrk.reduce((t, s) => t + s.boylam, 0) / mrk.length;
  const yayilim = Math.max(0, ...mrk.map((s) => mesafeKm(mEnlem, mBoylam, s.enlem, s.boylam)));
  const m = bolgeHaritasi({ enlem: mEnlem, boylam: mBoylam, kmYaricap: Math.min(500, Math.max(25, yayilim * 3)) });
  let s = m.zemin;

  // Kaynak listesi paneli (sağ üst)
  const satirH = 34, pw = 320, ph = 52 + liste.length * satirH, px0 = 1160 - pw, py0 = 28;
  const yasak = [{ x1: 24, y1: 24, x2: 360, y2: 100 }, { x1: px0 - 6, y1: py0 - 6, x2: 1176, y2: py0 + ph + 6 }, { x1: 900, y1: 480, x2: 1176, y2: 545 }];
  const yerlesen = [];

  let nokta = '', yaziKatman = '';
  cizilen.forEach((k) => {
    const x = m.px(k.boylam), y = m.py(k.enlem);
    const ton = TON[k.anahtar] ?? RENK.gri;
    nokta += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="9" fill="${ton}" fill-opacity="0.9" stroke="${RENK.kagit}" stroke-width="2.5"/>`;
    yerlesen.push({ x1: x - 11, y1: y - 11, x2: x + 11, y2: y + 11 });
  });
  cizilen.forEach((k) => {
    const x = m.px(k.boylam), y = m.py(k.enlem);
    const g = genislik(etiket(k), 20);
    const adaylar = [[16, -2], [16, 24], [16, -26], [-16 - g, -2], [-16 - g, 24], [-16 - g, -26], [-g / 2, -22], [-g / 2, 36]];
    for (const [dx, dy] of adaylar) {
      const kutu = { x1: x + dx - 5, y1: y + dy - 17, x2: x + dx + g + 5, y2: y + dy + 8 };
      if (kutu.x1 < 24 || kutu.x2 > 1176 || kutu.y1 < 24 || kutu.y2 > 540) continue;
      if ([...yasak, ...yerlesen].some((r) => kesisir(kutu, r))) continue;
      yerlesen.push(kutu);
      yaziKatman += `<rect x="${kutu.x1.toFixed(1)}" y="${kutu.y1.toFixed(1)}" width="${(kutu.x2 - kutu.x1).toFixed(1)}" height="${(kutu.y2 - kutu.y1 + 2).toFixed(1)}" rx="5" fill="${RENK.kagit}" fill-opacity="0.9"/>` +
        yazi(etiket(k), x + dx, y + dy, 20, TON[k.anahtar] ?? RENK.murekkep);
      break; // yer yoksa harita etiketi atlanır; kaynak listesinde zaten var
    }
  });
  s += nokta + yaziKatman;

  s += `<rect x="${px0}" y="${py0}" width="${pw}" height="${ph}" rx="10" fill="${RENK.kagit}" fill-opacity="0.94"/>`;
  s += yazi('Kaynaklar', px0 + 20, py0 + 34, 20, RENK.gri);
  liste.forEach((k, i) => {
    const y = py0 + 52 + i * satirH + 20;
    s += `<circle cx="${px0 + 28}" cy="${y - 7}" r="8" fill="${TON[k.anahtar] ?? RENK.gri}"/>`;
    s += yazi(k.ad, px0 + 46, y, 20, RENK.murekkep);
    s += yazi(`${sayiTr(k.ham, 1)} ${k.hamTur}`, px0 + pw - 18, y, 20, RENK.murekkep, 'end');
  });

  const konumVar = cizilen.length >= 2;
  const notMetni = konumVar ? 'Her kurum depremi kendi ölçümüyle konumlandırır · noktalar kaynakların bildirdiği merkez üstleri' : 'Kaynakların bildirdiği büyüklükler · konum bilgisi tüm kaynaklarda yok';
  const bant = {
    sayi: sayiTr(dM, 1), birim: genislik(BIRIM_UZUN, 26) <= 284 ? BIRIM_UZUN : 'Mw farkı', baslik: olayBaslik(veri), satir1: liste.map(etiket).join(' · '),
    satir2: (km != null ? `Konum farkı en çok ${sayiTr(km < 10 ? km : Math.round(km), km < 10 ? 1 : 0)} km · ` : '') + tarihTr(o.zaman, { saniye: false }),
  };
  s += not(notMetni) + altBant(bant);
  return { svg: s, uyari: [...bantUyari(bant), ...notUyari(notMetni)], dM, km };
}

/** Kart 5 çizicisi: veri → PNG Buffer. */
export async function kaynaklar(veri) {
  const r = kaynaklarSvg(veri);
  if (r.uyari.length) console.warn('kaynaklar kartı düzen uyarısı:', r.uyari.join(' | '));
  return kart(r.svg);
}
