// Kart 13 — Haftalık. Geçen haftanın (pazartesi 00:00 – pazar 24:00 TSİ) Türkiye kataloğu Mw ≥ 3 depremleri: Türkiye çevresi haritası,
// günlük sayı çubukları, toplam enerji eşdeğeri (Gutenberg–Richter; tek bir Mw'ye çevrilmiş toplam). Hafta boşsa "kaydedilmedi" kartı.
import { RENK, kart, sayiTr, yazi } from '../cekirdek.mjs';
import { turkiyeCevresi } from '../harita.mjs';
import { altBant, bantUyari, not, notUyari } from '../duzen.mjs';
import { GUN_MS, aralikYazi, esdegerMw, gunAdi, gunAy, jouleYazi, kac, kisalt1024, mwYazi, noktalar, olayAdi, toplamJ, trOlaylari, tsiGunBasi } from './donem.mjs';

export const ESIK = 3;
const NOT = 'Türkiye kataloğu · Mw ≥ 3 · enerji: log10 E = 1,5 Mw + 4,8 (ortalama bağıntı) · halka: haftanın en büyüğü';

/** Hafta penceresi: [bas, bit) = son tamamlanan 7 TSİ günü (bit = bugünün 00:00'ı). */
export const hafta = (simdi) => { const bit = tsiGunBasi(simdi); return { bas: bit - 7 * GUN_MS, bit }; };

/** Olaylar → günlük sayılar [{gun (ms), sayi, enBuyuk}] (7 gün). */
export function gunluk7(olaylar, bas) {
  const g = Array.from({ length: 7 }, (_, i) => ({ gun: bas + i * GUN_MS, sayi: 0, enBuyuk: null }));
  for (const o of olaylar) {
    const i = Math.floor((o.zaman - bas) / GUN_MS);
    if (i < 0 || i > 6) continue;
    g[i].sayi++;
    g[i].enBuyuk = Math.max(g[i].enBuyuk ?? -Infinity, o.mw);
  }
  return g;
}

/** Olaylar → {toplam, enerji (J), esdeger (Mw), en}. Boşsa enerji 0, esdeger null. */
export function ozetle(olaylar) {
  const enerji = toplamJ(olaylar.map((o) => o.mw));
  return { toplam: olaylar.length, enerji, esdeger: olaylar.length ? esdegerMw(enerji) : null, en: olaylar[0] ?? null };
}

/** Telegram açıklaması (HTML, ≤ 1024). */
export function aciklama(olaylar, bas, bit) {
  const ust = `📊 <b>Haftalık · ${aralikYazi(bas, bit)}</b>`;
  if (!olaylar.length) return kisalt1024(`${ust}\nBu hafta Türkiye ve çevresinde Mw ≥ 3 deprem kaydedilmedi.`);
  const z = ozetle(olaylar);
  const g = gunluk7(olaylar, bas);
  const yogun = [...g].sort((a, b) => b.sayi - a.sayi || a.gun - b.gun)[0];
  const satirlar = [
    ust,
    `Mw ≥ 3: ${z.toplam} deprem · en büyüğü ${mwYazi(z.en)} (${kac(olayAdi(z.en))}, ${gunAy(z.en.zaman)})`,
    `En çok deprem: ${gunAdi(yogun.gun)} ${gunAy(yogun.gun)}, ${yogun.sayi}`,
    `Toplam enerji ${jouleYazi(z.enerji)}; tek bir depreme çevrilirse yaklaşık Mw ${sayiTr(z.esdeger, 1)}.`,
  ];
  return kisalt1024(satirlar.join('\n'));
}

// Sağ alttaki çubuk paneli (kâğıt levha) — yalnız Suriye/Irak üstüne düşer, Türkiye'yi örtmez.
const PX = 740, PY = 392, PG = 430, PY2 = 536;
function cubuklar(g) {
  const enCok = Math.max(1, ...g.map((x) => x.sayi));
  const tabanY = PY2 - 38, yuk = tabanY - (PY + 64);
  const adim = (PG - 40) / 7, bw = adim * 0.62;
  let s = `<rect x="${PX}" y="${PY}" width="${PG}" height="${PY2 - PY}" rx="10" fill="${RENK.kagit}" fill-opacity="0.94"/>`;
  s += yazi('Günlük deprem sayısı', PX + 20, PY + 28, 20, RENK.gri);
  const enGun = g.reduce((a, b) => (b.sayi > a.sayi ? b : a), g[0]);
  g.forEach((x, i) => {
    const cx = PX + 20 + adim * i + adim / 2;
    const h = x.sayi ? Math.max(4, (x.sayi / enCok) * yuk) : 2;
    const renk = x.sayi && x === enGun ? RENK.indigo : x.sayi ? RENK.sinir : RENK.ince;
    s += `<rect x="${(cx - bw / 2).toFixed(1)}" y="${(tabanY - h).toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}" rx="3" fill="${renk}"/>`;
    s += yazi(String(x.sayi), cx, tabanY - h - 6, 18, RENK.murekkep, 'middle');
    s += yazi(gunAdi(x.gun), cx, PY2 - 14, 18, RENK.gri, 'middle');
  });
  return s;
}

/** → {svg, uyari}. */
export function haftalikSvg(olaylar, bas, bit) {
  const m = turkiyeCevresi();
  const z = ozetle(olaylar);
  const g = gunluk7(olaylar, bas);
  const bos = !olaylar.length;
  const bant = bos
    ? { sayi: '0', birim: 'deprem · Mw ≥ 3', baslik: `Haftalık · ${aralikYazi(bas, bit)}`, satir1: 'Bu hafta Mw ≥ 3 deprem kaydedilmedi', satir2: 'Türkiye ve yakın çevresi' }
    : {
      sayi: sayiTr(z.toplam), birim: 'deprem · Mw ≥ 3', baslik: `Haftalık · ${aralikYazi(bas, bit)}`,
      satir1: `En büyüğü ${mwYazi(z.en)} · ${olayAdi(z.en)} · ${gunAy(z.en.zaman)}`,
      satir2: `Toplam enerji ${jouleYazi(z.enerji)} · tek depremle yaklaşık Mw ${sayiTr(z.esdeger, 1)}`,
    };
  const svg = m.zemin + noktalar(m, olaylar, { esik: ESIK }) + cubuklar(g) + not(NOT) + altBant(bant);
  return { svg, uyari: [...bantUyari(bant), ...notUyari(NOT)] };
}

/** Dönemsel üretici: (kartVeri, {simdi, db}) → {png, aciklama, hedef: 'kanal'}. Boş hafta da kart olur. */
export async function haftalik(_kartVeri, { simdi = Date.now(), db } = {}) {
  const d1 = db ?? (await import('../d1.mjs'));
  const { bas, bit } = hafta(simdi);
  const olaylar = await trOlaylari(d1, bas, bit, ESIK);
  const r = haftalikSvg(olaylar, bas, bit);
  if (r.uyari.length) console.warn('haftalık kart düzen uyarısı:', r.uyari.join(' | '));
  return { png: await kart(r.svg), aciklama: aciklama(olaylar, bas, bit), hedef: 'kanal' };
}
