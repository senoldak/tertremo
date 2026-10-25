// Kart 16 — Arka plan deprem hızı (λ) haritası (çeyreklik). Veri: kart-veri.json → hucreler (hucre tablosundaki λ ile aynı):
// kümelenmesi ayrılmış (en yakın komşu) olaylar, hücrenin kendi Mc'sinin üstünde, yılda kaç olay. Hücreler kıyaslanabilsin diye
// hepsi ORTAK eşiğe (Mw ≥ 4,0) çevrilir: λ(≥4) = λ(≥Mc)·10^(−b(4−Mc)), b = hücrenin kendi b'si yalnız n ≥ 50 ve σ_b ≤ 0,15 ise,
// yoksa Türkiye b'si. Hücre Mc'si katalog tamlığının altına inmez (hesap/hucre.py); hücrede Mc üstü n ≥ 10 olay yoksa ya da Mc > 4 ise boş. Tek tonlu indigo skala.
import { kart, sayiTr } from '../cekirdek.mjs';
import { altBant, bantUyari, not, notUyari } from '../duzen.mjs';
import { hucreHaritasi, lejant, siniflayici, taze, yilAraligi } from './izgara.mjs';

export const M_ORTAK = 4.0;
export const L_SINIRLAR = [0.03, 0.1, 0.3, 1, 3];
export const lambdaSinif = siniflayici(L_SINIRLAR);
const ETIKETLER = ['<0,03', '0,03–0,1', '0,1–0,3', '0,3–1', '1–3', '≥3'];
export const N_LAMBDA_EN_AZ = 10;
const NOT = "Betimleyici; tahmin değildir. Mw ≥ 4'e çevrilmiş: hücre b'si (n ≥ 50), yoksa Türkiye b'si.";
const SIGMA_ESIK = 0.15;

const ortanca = (d) => { const s = [...d].sort((a, b) => a - b); return s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2; };
const guvenilirB = (h) => h.n >= 50 && Number.isFinite(h.b) && !(h.sigma_b > SIGMA_ESIK);
/** Türkiye b'si: bloktaki turkiyeB, yoksa güvenilir hücre b'lerinin ortancası, yoksa 1. */
export function turkiyeB(v) {
  if (Number.isFinite(v.turkiyeB)) return v.turkiyeB;
  const b = v.hucreler.filter(guvenilirB).map((h) => h.b);
  return b.length ? ortanca(b) : 1;
}
const gecerli = (h) => h.n >= N_LAMBDA_EN_AZ && Number.isFinite(h.lambda) && h.lambda > 0 && Number.isFinite(h.mc) && h.mc <= M_ORTAK + 1e-9;
/** λ(≥ Mw 4,0), yıl başına. */
export const lambda4 = (h, bTr) => h.lambda * 10 ** (-(guvenilirB(h) ? h.b : bTr) * (M_ORTAK - h.mc));
const lamYazi = (l) => sayiTr(l, l < 1 ? 2 : l < 10 ? 1 : 0);

/** Çizilecek hücreler + λ(≥4) değerleri. */
function hazirla(v) {
  const bTr = turkiyeB(v);
  const dolu = v.hucreler.filter(gecerli).map((h) => ({ ...h, l4: lambda4(h, bTr) }));
  return { dolu, toplam: dolu.reduce((t, h) => t + h.l4, 0) };
}

/** → {svg, uyari, cizilen, metin, toplam}. */
export function lambdaSvg(v) {
  const { dolu, toplam } = hazirla(v);
  const h = hucreHaritasi(dolu, { sinif: (x) => lambdaSinif(x.l4), etiket: (x) => lamYazi(x.l4) });
  const bant = {
    sayi: dolu.length ? lamYazi(toplam) : '—', birim: 'olay/yıl · Mw ≥ 4',
    baslik: 'Arka plan deprem hızı haritası',
    satir1: `${yilAraligi(v)} · ${h.cizilen} hücre (1°, n ≥ 10) · Mw ≥ 4'e çevrilmiş`,
    satir2: 'Sayı: haritadaki hücrelerin toplamı · kümelenme ayıklanmış',
  };
  const svg = h.zemin + h.katman + lejant("olay / yıl, Mw ≥ 4'e çevrilmiş", ETIKETLER, { kutular: h.kutular }) + not(NOT) + altBant(bant);
  return { svg, uyari: [...bantUyari(bant), ...notUyari(NOT)], cizilen: h.cizilen, metin: NOT, toplam };
}

/** Telegram açıklaması (HTML, ≤ 1024). */
export function aciklama(v) {
  const { dolu, toplam } = hazirla(v);
  const en = dolu.length ? dolu.reduce((a, b) => (b.l4 > a.l4 ? b : a)) : null;
  const [la, lo] = en ? en.anahtar.split('_').map(Number) : [0, 0];
  const a = [
    `<b>Arka plan deprem hızı haritası</b> · ${yilAraligi(v)}`,
    `Harita, 1° hücrelerde yılda kaç bağımsız depremin (Mw ≥ 4) beklendiğini kayıttan gösterir. Artçılar ve kümelenmiş olaylar en yakın komşu yöntemiyle ayıklanmıştır. ` +
    `Her hücrenin tamlık büyüklüğü (Mc) farklı olduğundan sayılar Gutenberg–Richter ile ortak eşiğe (Mw ≥ 4) çevrilmiştir: Mc üstünde en az 50 olayı olan hücrelerde hücrenin kendi b'si, daha azında Türkiye b'si kullanılır. Mc üstünde en az 10 olayı olan ${dolu.length} hücre çizilir.` +
    (en ? ` Çizilen hücrelerin toplamı yılda ${lamYazi(toplam)} olay; en yoğun hücre ${la}–${la + 1}° K, ${lo}–${lo + 1}° D (yılda ${lamYazi(en.l4)}).` : ''),
    'Betimleyici; tahmin değildir.',
  ].join('\n\n');
  return a.length > 1024 ? a.slice(0, 1020).replace(/<[^>]*$/, '') + '…' : a;
}

/** Dönemsel üretici: çizilecek hücre yok / önbellek eski ise null. */
export async function ceyreklikLambda(kartVeri, { simdi = Date.now() } = {}) {
  const v = kartVeri?.hucreler;
  if (!v?.hucreler?.some(gecerli)) return null;
  if (!taze(v.hesap, simdi)) { console.warn('λ haritası: önbellek eski, kart atlandı'); return null; }
  const r = lambdaSvg(v);
  if (r.uyari.length) console.warn('λ haritası düzen uyarısı:', r.uyari.join(' | '));
  return { png: await kart(r.svg), aciklama: aciklama(v), hedef: 'kanal' };
}
