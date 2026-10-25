// Kart 20 — Haftalık deprem olasılığı (ETAS, deneysel). Veri: hesap/.onbellek/kart-veri.json → etas
// (hesap/etas.py) ve etasDogrulama (hesap/dogrulama.py). Yayın kapısı geçmeden (doğrulama + 8 hafta gizli kayıt)
// kart yalnız sahibin özel sohbetine gider ve "deneysel — doğrulama sürüyor" etiketi taşır.
// Kullanım: node scripts/kart/kartlar/etasHaftalik.mjs <kart-veri.json> <çıktı.png>  → stdout: {hedef, aciklama}
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { RENK, altBant, genislik, kart, not, yazi } from '../cekirdek.mjs';
import { turkiyeCevresi } from '../harita.mjs';

const VERI = fileURLToPath(new URL('../../../data/', import.meta.url));
const AYLAR = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'];
const KURAL = 'github.com/senoldak/tertremo/blob/main/docs/etas-on-kayit.md';
const ETIKET = 'deneysel — doğrulama sürüyor';
const ETIKET_RED = 'deneysel — doğrulamadan geçemedi';
// Doğrulama kesin olarak geçmediyse (gecti === false) etiket bunu söyler; geçmediği sürece kart kanala gitmez.
const etiketMetni = (e) => (e?.kapi?.gecti === false ? ETIKET_RED : ETIKET);
const NOT = 'Olasılık tahminidir; deprem tahmini değildir. ETAS (Mizrahi vd. 2021) · Mw ≥ 6 değeri doğrulanmamış';
// Sıralı indigo tonları (açıktan koyuya); sınırlar P(≥1 Mw ≥ 5, 7 gün)
const SINIFLAR = [
  { ust: 0.01, renk: '#e4e2f6', ad: '<%1' },
  { ust: 0.02, renk: '#c4c0ee', ad: '%1–2' },
  { ust: 0.05, renk: '#9a93e2', ad: '%2–5' },
  { ust: 0.1, renk: '#6c64d6', ad: '%5–10' },
  { ust: Infinity, renk: RENK.indigo, ad: '≥%10' },
];

let onbellek;
function harita() {
  if (onbellek) return onbellek;
  const tanim = JSON.parse(fs.readFileSync(VERI + 'bolgeler.json', 'utf8'));
  const iller = JSON.parse(fs.readFileSync(VERI + 'harita/iller.json', 'utf8'));
  const ilBolge = new Map();
  for (const b of tanim.bolgeler) for (const il of b.iller) ilBolge.set(il, b.ad);
  onbellek = { tanim, iller, ilBolge };
  return onbellek;
}

/** Olasılık → "%18", "<%1", ">%99" (tam yüzde). */
export function yuzde(p) {
  if (p === null || p === undefined || !Number.isFinite(p)) return '—';
  if (p < 0.01) return '<%1';
  if (p >= 0.995) return '>%99';
  return '%' + Math.round(p * 100);
}

const tsi = (ms) => new Date(ms + 3 * 3600 * 1000);
/** Pencere (UTC ms) → "24–31 Ekim 2026" ya da "28 Ekim – 4 Kasım 2026" (TSİ). */
export function aralikTr(bas, bit) {
  const a = tsi(bas), b = tsi(bit);
  if (a.getUTCFullYear() !== b.getUTCFullYear()) {
    return `${a.getUTCDate()} ${AYLAR[a.getUTCMonth()]} ${a.getUTCFullYear()} – ${b.getUTCDate()} ${AYLAR[b.getUTCMonth()]} ${b.getUTCFullYear()}`;
  }
  if (a.getUTCMonth() !== b.getUTCMonth()) {
    return `${a.getUTCDate()} ${AYLAR[a.getUTCMonth()]} – ${b.getUTCDate()} ${AYLAR[b.getUTCMonth()]} ${b.getUTCFullYear()}`;
  }
  return `${a.getUTCDate()}–${b.getUTCDate()} ${AYLAR[b.getUTCMonth()]} ${b.getUTCFullYear()}`;
}

const etasMi = (e) => e?.mod === 'etas';
const yayin = (e) => e?.kapi?.yayin === true;
const deger = (e, k) => (etasMi(e) ? k.p5 : k.norm5);

/** Gönderim hedefi: yalnız kapı açıkken kanal, aksi halde sahibin özel sohbeti. */
export function hedef(kartVeri) {
  return yayin(kartVeri?.etas) ? 'kanal' : 'ozel';
}

const sinavSatiri = (e) => (e?.ileri ? `İleriye dönük sınavda: ${e.ileri.hafta}/${e.ileri.hedef ?? 52} hafta` : null);

/** Kart alt notu (kısaltılmadan). Sınav satırı varsa ETAS atfı yerine o girer (kart tek satır). */
export function notMetni(e) {
  const dogrulama = yayin(e) ? 'doğrulamadan geçti' : e.kapi?.gecti === false ? 'doğrulamadan geçemedi' : 'doğrulama sürüyor';
  const sinav = sinavSatiri(e);
  return sinav ? `Olasılık tahminidir; deprem tahmini değildir. ${sinav} · ${dogrulama}` : `${NOT} · ${dogrulama}`;
}

/** Telegram açıklaması (HTML, ≤ 1024). */
export function aciklama(kartVeri) {
  const e = kartVeri.etas;
  const t = e.turkiye;
  const satirlar = [];
  if (!yayin(e)) satirlar.push(`<i>${etiketMetni(e)}</i>`);
  satirlar.push(`<b>Haftalık deprem olasılığı (deneysel)</b> — ${aralikTr(e.baslangic, e.bitis)}`);
  if (etasMi(e)) {
    satirlar.push(`Türkiye ve çevresinde önümüzdeki 7 günde en az bir Mw 5 ve üzeri deprem olma olasılığı: ` +
      `<b>${yuzde(t.p5)}</b> (olağan hafta: ${yuzde(t.norm5)}). ` +
      `Mw 6 ve üzeri: ${yuzde(t.p6)} (olağan: ${yuzde(t.norm6)}; doğrulanmamış model çıktısı).`);
    satirlar.push('Bölgeler (Mw ≥ 5): ' + e.bolgeler.map((b) => `${b.ad} ${yuzde(b.p5)} (olağan ${yuzde(b.norm5)})`).join(' · '));
  } else {
    satirlar.push(`ETAS modeli ${e.neden || 'bu hafta model güncellenemedi'}. Olağan bir haftada Türkiye ve çevresinde ` +
      `en az bir Mw 5 ve üzeri deprem olasılığı: <b>${yuzde(t.norm5)}</b>; Mw 6 ve üzeri: ${yuzde(t.norm6)}.`);
    satirlar.push('Bölgeler, olağan hafta (Mw ≥ 5): ' + e.bolgeler.map((b) => `${b.ad} ${yuzde(b.norm5)}`).join(' · '));
  }
  const sinav = sinavSatiri(e);
  satirlar.push('Bu bir tahmin değil, istatistiksel olasılıktır; deprem zamanı ve yeri önceden bilinemez. ' +
    (sinav ? '' : 'Model son depremlerin artçı etkisini hesaba katar (ETAS). Olağan hafta: zamandan bağımsız Poisson. ') +
    'Resmî bilgi için AFAD.');
  if (sinav) satirlar.push(`${sinav} (kurallar: ${KURAL})`);
  const ozet = kartVeri.etasDogrulama?.ozet ?? e.kapi?.ozet;
  const ek = ozet && ozet !== 'doğrulama yapılmadı' ? ` (${ozet})` : '';
  if (yayin(e)) satirlar.push(`Doğrulama: ${ozet ?? 'geçti'}`);
  else if (e.kapi?.gecti === false) satirlar.push(`Doğrulama: geçemedi${ek}`);
  else if (e.kapi?.gecti === true) satirlar.push(`Doğrulama: geçti; ileriye dönük gizli kayıt ${e.kapi.gizliHafta ?? 0}/8 hafta${ek}`);
  else satirlar.push(`Doğrulama: sürüyor${ek}`);
  let metin = satirlar.join('\n\n');
  if (metin.length > 1024) metin = metin.slice(0, 1020).replace(/<[^>]*$/, '') + '…';
  return metin;
}

const sinif = (p) => SINIFLAR.find((s) => p < s.ust) ?? SINIFLAR.at(-1);
const halkaYol = (r, px, py) => {
  let d = '';
  for (let i = 0; i < r.length; i += 2) d += `${i ? 'L' : 'M'}${px(r[i]).toFixed(1)},${py(r[i + 1]).toFixed(1)}`;
  return d + 'Z';
};
const rol = (ad, ic) => `<g data-rol="${ad}">${ic}</g>`;

/** Kart SVG'si (logo hariç; kart() ekler). */
export function etasSvg(e) {
  const { tanim, iller, ilBolge } = harita();
  const t = turkiyeCevresi();
  const bolge = new Map(e.bolgeler.map((b) => [b.ad, b]));
  // İller bölge rengiyle (kenar aynı renk: bölge içi il sınırları kaybolur)
  let iller_svg = '';
  const etiketYer = new Map();
  for (const il of iller) {
    const ad = ilBolge.get(il.ad);
    const b = bolge.get(ad);
    if (!b) continue;
    const renk = sinif(deger(e, b) ?? 0).renk;
    iller_svg += `<path d="${il.r.map((r) => halkaYol(r, t.px, t.py)).join('')}" fill="${renk}" stroke="${renk}" stroke-width="0.8"/>`;
    const y = etiketYer.get(ad) ?? { x: 0, y: 0, n: 0 };
    etiketYer.set(ad, { x: y.x + il.m[0], y: y.y + il.m[1], n: y.n + 1 });
  }
  // Bölge etiketleri: ad (18 px gri) + yüzde (28 px), kâğıt levha üstünde
  let etiketler = '';
  for (const b of tanim.bolgeler) {
    const y = etiketYer.get(b.ad);
    const v = bolge.get(b.ad);
    if (!y || !v) continue;
    const x = t.px(y.x / y.n), yy = t.py(y.y / y.n);
    const ad = b.ad === 'Güneydoğu Anadolu' ? 'Güneydoğu' : b.ad;
    const deg = yuzde(deger(e, v));
    // ETAS modunda her bölge yüzdesinin altında olağan hafta değeri (küçük gri satır)
    const olagan = etasMi(e) ? `olağan ${yuzde(v.norm5)}` : null;
    const g = Math.max(genislik(ad, 18), genislik(deg, 28), olagan ? genislik(olagan, 16) : 0) + 16;
    const h = olagan ? 74 : 56;
    etiketler += `<rect x="${(x - g / 2).toFixed(1)}" y="${(yy - 24).toFixed(1)}" width="${g.toFixed(1)}" height="${h}" rx="8" fill="${RENK.kagit}" fill-opacity="0.88"/>` +
      yazi(ad, x, yy - 6, 18, RENK.gri, 'middle') + yazi(deg, x, yy + 24, 28, RENK.murekkep, 'middle') +
      (olagan ? rol('bolge-olagan', yazi(olagan, x, yy + 43, 16, RENK.gri, 'middle')) : '');
  }
  // Lejant (sağ alt)
  let lejant = yazi(etasMi(e) ? 'P(≥ 1 Mw ≥ 5, 7 gün)' : 'Olağan hafta, Mw ≥ 5', 1160, 470, 18, RENK.gri, 'end');
  const kutuG = 52;
  SINIFLAR.forEach((s, i) => {
    const x = 1160 - (SINIFLAR.length - i) * (kutuG + 4);
    lejant += `<rect x="${x}" y="482" width="${kutuG}" height="14" fill="${s.renk}"/>` + yazi(s.ad, x + kutuG / 2, 518, 16, RENK.gri, 'middle');
  });
  lejant = `<rect x="${1160 - SINIFLAR.length * (kutuG + 4) - 12}" y="448" width="${SINIFLAR.length * (kutuG + 4) + 24}" height="80" rx="8" fill="${RENK.kagit}" fill-opacity="0.88"/>` + lejant;
  // Deneysel etiketi (sağ üst)
  let etiket = '';
  if (!yayin(e)) {
    const metin = etiketMetni(e);
    const g = genislik(metin, 22) + 28;
    etiket = rol('etiket', `<rect x="${(1172 - g).toFixed(1)}" y="28" width="${g.toFixed(1)}" height="40" rx="10" fill="${RENK.kagit}" fill-opacity="0.94" stroke="${RENK.indigo}" stroke-width="2"/>` +
      yazi(metin, 1158, 56, 22, RENK.indigo, 'end'));
  }
  const tr = e.turkiye;
  const aralik = aralikTr(e.baslangic, e.bitis);
  const bant = etasMi(e)
    ? altBant({ sayi: yuzde(tr.p5), birim: '7 günde Mw ≥ 5', baslik: 'Haftalık deprem olasılığı (deneysel)',
      satir1: `Türkiye ve çevresi · olağan hafta ${yuzde(tr.norm5)}`,
      satir2: `${aralik} · Mw ≥ 6: ${yuzde(tr.p6)} (olağan ${yuzde(tr.norm6)})` })
    : altBant({ sayi: yuzde(tr.norm5), birim: '7 günde Mw ≥ 5', baslik: 'Haftalık deprem olasılığı (deneysel)',
      satir1: 'Model bu hafta güncellenemedi · olağan hafta değeri',
      satir2: `${aralik} · Mw ≥ 6: ${yuzde(tr.norm6)} (olağan)` });
  return t.zemin + rol('bolgeler', iller_svg) + etiketler + rol('lejant', lejant) + etiket + not(notMetni(e)) + bant;
}

/** kart-veri.json içeriği → {png, aciklama, hedef}. */
export async function etasHaftalik(kartVeri) {
  if (!kartVeri?.etas) throw new Error('kart-veri.json içinde etas yok');
  return { png: await kart(etasSvg(kartVeri.etas)), aciklama: aciklama(kartVeri), hedef: hedef(kartVeri) };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [girdi, cikti] = process.argv.slice(2);
  if (!girdi || !cikti) {
    console.error('Kullanım: node scripts/kart/kartlar/etasHaftalik.mjs <kart-veri.json> <çıktı.png>');
    process.exit(2);
  }
  const k = await etasHaftalik(JSON.parse(fs.readFileSync(girdi, 'utf8')));
  fs.mkdirSync(path.dirname(path.resolve(cikti)), { recursive: true });
  fs.writeFileSync(cikti, k.png);
  console.log(JSON.stringify({ hedef: k.hedef, aciklama: k.aciklama }));
}
