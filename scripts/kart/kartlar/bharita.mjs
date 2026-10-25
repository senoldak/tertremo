// Kart 15 — Türkiye b-değeri haritası (aylık). Veri: hesap/.onbellek/kart-veri.json → hucreler (hesap/kartblok.py; hucre tablosuyla
// aynı değerler). Literatür korkulukları (Marzocchi vd. 2019, GJI, doi:10.1093/gji/ggz541): hücrede Mc üstünde n ≥ 50 olay yoksa
// hücre BOŞ; σ_b (Shi–Bolt) > 0,15 hücre çizgili (belirsiz); her hücrenin kendi Mc'si lejantta/altbantta belirtilir.
// Renk: tek tonlu indigo skala (tehlike çağrışımı yok).
import { kart, sayiTr } from '../cekirdek.mjs';
import { altBant, bantUyari, not, notUyari } from '../duzen.mjs';
import { turkiyeHucreleri } from '../turkiye.mjs';
import { hucreHaritasi, lejant, mcAraligi, siniflayici, taze, yilAraligi } from './izgara.mjs';

export const B_SINIRLAR = [0.6, 0.8, 1.0, 1.2, 1.4];
export const SIGMA_ESIK = 0.15;
export const bSinif = siniflayici(B_SINIRLAR);
const ETIKETLER = ['<0,6', '0,6–0,8', '0,8–1,0', '1,0–1,2', '1,2–1,4', '≥1,4'];
const NOT = 'Betimleyici; tahmin değildir.';
export const PATLATMA_NOTU = 'Olası patlatma kaynaklı küçük olaylar ayıklandı.';

const gecerli = (h) => h.n >= 50 && Number.isFinite(h.b);
const ortanca = (d) => { const s = [...d].sort((a, b) => a - b); return s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2; };

/** → {svg, uyari, cizilen, taramali, metin}. */
export function bSvg(v) {
  const tr = turkiyeHucreleri(v.hucreler);
  const dolu = tr.filter(gecerli);
  const h = hucreHaritasi(tr, {
    sinif: (x) => (gecerli(x) ? bSinif(x.b) : null),
    etiket: (x) => sayiTr(x.b, 2),
    tarama: (x) => x.sigma_b > SIGMA_ESIK,
  });
  const metin = `${NOT} Her hücre en az 50 olay; Mc hücre başına değişir.${v.patlatmaAyiklandi ? ' ' + PATLATMA_NOTU : ''}`;
  const bant = {
    sayi: dolu.length ? sayiTr(ortanca(dolu.map((x) => x.b)), 2) : '—', birim: 'ortanca b-değeri',
    baslik: 'Türkiye b-değeri haritası',
    satir1: `Türkiye (kıyıdan 30 km) · ${yilAraligi(v)} · ${h.cizilen} hücre · Mc ${mcAraligi(dolu, sayiTr)}`,
    satir2: `Çizgili: σ_b > 0,15, belirsiz · σ_b: Shi–Bolt`,
  };
  const svg = h.zemin + h.katman +
    lejant('b-değeri', ETIKETLER, { taramaMetni: 'σ_b > 0,15 (belirsiz)', kutular: h.kutular }) + not(metin) + altBant(bant);
  return { svg, uyari: [...bantUyari(bant), ...notUyari(metin)], cizilen: h.cizilen, taramali: h.taramali, metin };
}

/** Telegram açıklaması (HTML, ≤ 1024). */
export function aciklama(v) {
  const dolu = turkiyeHucreleri(v.hucreler).filter(gecerli);
  const belirsiz = dolu.filter((x) => x.sigma_b > SIGMA_ESIK).length;
  const a = [
    `<b>Türkiye b-değeri haritası</b> · ${yilAraligi(v)}`,
    `b-değeri, küçük depremlerin büyüklere oranını anlatan bir sayıdır; yüksek b küçük depremlerin payının görece fazla olduğunu gösterir. ` +
    `Harita, Türkiye'nin (kıyıdan 30 km) 1° hücrelere bölünmüş kataloğunu (EMSC) gösterir; ortanca b ${sayiTr(ortanca(dolu.map((x) => x.b)), 2)}.`,
    `Yalnız Mc'nin üstünde en az 50 olayı olan hücreler çizilir (n ≥ 50; ${dolu.length} hücre), diğerleri boştur. Her hücrenin Mc değeri farklıdır (${mcAraligi(dolu, sayiTr)}). ` +
    `Çizgili ${belirsiz} hücrenin σ_b değeri 0,15'ten büyük: belirsiz.`,
    `Betimleyici; tahmin değildir. Yöntem: Aki–Utsu b, Shi–Bolt σ_b; küçük örnekte b değişimlerini yanlış okumamak için eşikler Marzocchi vd. 2019'a göre.${v.patlatmaAyiklandi ? ' ' + PATLATMA_NOTU : ''}`,
  ].join('\n\n');
  return a.length > 1024 ? a.slice(0, 1020).replace(/<[^>]*$/, '') + '…' : a;
}

/** Dönemsel üretici: veri yok / hücre yok / önbellek eski ise null. */
export async function aylikB(kartVeri, { simdi = Date.now() } = {}) {
  const v = kartVeri?.hucreler;
  if (!v?.hucreler?.some(gecerli)) return null;
  if (!taze(v.hesap, simdi)) { console.warn('b haritası: önbellek eski, kart atlandı'); return null; }
  const r = bSvg(v);
  if (r.uyari.length) console.warn('b haritası düzen uyarısı:', r.uyari.join(' | '));
  return { png: await kart(r.svg), aciklama: aciklama(v), hedef: 'kanal' };
}
