import { describe, expect, it, vi } from 'vitest';
import sharp from 'sharp';
import { DONEMSEL, donemsel } from '../../scripts/kart/calistir.mjs';
import { aciklama as grAciklama, aylikGr, grDogrusu, grNoktalari, grSvg } from '../../scripts/kart/kartlar/gr.mjs';
import { B_SINIRLAR, SIGMA_ESIK, aciklama as bAciklama, aylikB, bSinif, bSvg } from '../../scripts/kart/kartlar/bharita.mjs';
import { L_SINIRLAR, aciklama as lAciklama, ceyreklikLambda, lambda4, lambdaSinif, lambdaSvg, turkiyeB } from '../../scripts/kart/kartlar/lambdaharita.mjs';
import { SKALA } from '../../scripts/kart/kartlar/izgara.mjs';

const simdi = Date.UTC(2026, 9, 1, 4, 0, 0);   // 1 Ekim 2026 07:00 TSİ → önceki ay Eylül

// Sentetik G–R: N(≥M) = N0·10^(−b(M−Mc)) kutulara bölünür (0,1'lik)
function sentetik(b, mc, n0, mMax = 6.0) {
  const hist = [];
  const kum = (m) => n0 * 10 ** (-b * (m - (mc - 0.05)));
  for (let m = mc; m <= mMax + 1e-9; m = Math.round((m + 0.1) * 10) / 10) {
    const c = Math.round(kum(m - 0.05) - kum(m + 0.05));
    if (c > 0) hist.push([m, c]);
  }
  for (let m = 1.5; m < mc - 1e-9; m = Math.round((m + 0.1) * 10) / 10) hist.push([Math.round(m * 10) / 10, Math.round(0.5 * n0 * 0.1 * (m - 1))]);
  return hist.sort((x, y) => x[0] - y[0]);
}

const grBlok = (ek = {}) => {
  const h = sentetik(1.0, 2.4, 3000);
  return { ay: '2026-09', n: 3000, toplam: h.reduce((t, [, c]) => t + c, 0), mc: 2.4, b: 1.03, sigma: 0.04, dm: 0.1, histogram: h, ...ek };
};

describe('G–R doğrusu', () => {
  it('sentetik b=1: doğru eğimi −b (−1 ± 0,05) ve kümülatif noktaların en küçük kareler eğimi de ≈ −1', () => {
    const blok = grBlok({ b: 1.0 });
    const d = grDogrusu(blok);
    expect(d.egim).toBeCloseTo(-1.0, 6);
    expect((d.y2 - d.y1) / (d.x2 - d.x1)).toBeCloseTo(-1.0, 6);
    const nk = grNoktalari(blok).filter((p) => p.ustu && p.n >= 20);
    const mx = nk.reduce((t, p) => t + p.m, 0) / nk.length, my = nk.reduce((t, p) => t + p.logN, 0) / nk.length;
    const egim = nk.reduce((t, p) => t + (p.m - mx) * (p.logN - my), 0) / nk.reduce((t, p) => t + (p.m - mx) ** 2, 0);
    expect(egim).toBeGreaterThan(-1.05);
    expect(egim).toBeLessThan(-0.95);
  });
  it('doğru Mc kenarında N(≥Mc) noktasından geçer', () => {
    const blok = grBlok();
    const d = grDogrusu(blok);
    const p = grNoktalari(blok).find((q) => q.ustu);
    expect(d.x1).toBeCloseTo(p.m, 6);
    expect(d.y1).toBeCloseTo(p.logN, 6);
  });
  it('kümülatif sayı sondan toplanır', () => {
    const nk = grNoktalari({ ...grBlok(), histogram: [[2.4, 5], [2.5, 3], [2.6, 2]], mc: 2.4 });
    expect(nk.map((p) => p.n)).toEqual([10, 5, 2]);
  });
});

describe('G–R kartı', () => {
  it('SVG: nokta, Mc çizgisi, doğru, sayı ve birim; açıklama sınırı; yasak sözcük yok', () => {
    const r = grSvg(grBlok());
    for (const rol of ['sayi', 'birim', 'baslik', 'not', 'gr-noktalar', 'gr-dogru', 'gr-mc']) expect(r.svg).toContain(`data-rol="${rol}"`);
    expect(r.uyari).toEqual([]);
    const a = grAciklama(grBlok());
    expect(a.length).toBeLessThanOrEqual(1024);
    expect(a).toContain('Eylül 2026');
    expect(a).toContain('1,03');
    expect((a + r.svg).toLocaleLowerCase('tr')).not.toMatch(/tehlike|uyarı/);
  });
  it('1200×800 PNG', async () => {
    const k = await aylikGr({ gr: grBlok() }, { simdi });
    const m = await sharp(k.png).metadata();
    expect([m.width, m.height]).toEqual([1200, 800]);
    expect(k.hedef).toBe('kanal');
  });
  it('veri yok ya da başka ayın bloğu: kart atlanır (null)', async () => {
    expect(await aylikGr({}, { simdi })).toBeNull();
    expect(await aylikGr({ gr: null }, { simdi })).toBeNull();
    const uyar = vi.spyOn(console, 'warn').mockImplementation(() => {});
    expect(await aylikGr({ gr: grBlok({ ay: '2026-07' }) }, { simdi })).toBeNull();
    uyar.mockRestore();
  });
});

const hucre = (anahtar, b, sigma_b, n = 120, lambda = 4.2, mc = 2.8) => ({ anahtar, mc, n, b, sigma_b, lambda });
const hucreVeri = (liste) => ({ hesap: simdi, baslangic: Date.UTC(2018, 0, 1), hucreler: liste });
const ornekHucreler = () => [
  hucre('40_29', 1.12, 0.06, 900, 80, 2.6), hucre('38_27', 0.95, 0.05, 700, 40, 2.6), hucre('37_36', 0.78, 0.2, 55, 2, 3.2),
  hucre('39_40', null, null, 12, 0.5, 3.4), hucre('38_43', 1.31, 0.09, 140, 7, 3.0), hucre('41_33', 1.02, 0.12, 300, 12, 2.8),
];

describe('skalalar', () => {
  it('b sınıfları: sınırlar yukarı sınıfa, 6 sınıf, her sınıfa ayrı renk', () => {
    expect(B_SINIRLAR).toEqual([0.6, 0.8, 1.0, 1.2, 1.4]);
    expect(SKALA).toHaveLength(6);
    expect(new Set(SKALA).size).toBe(6);
    expect([0.59, 0.6, 0.79, 0.8, 0.99, 1.0, 1.19, 1.2, 1.39, 1.4, 2.5].map(bSinif)).toEqual([0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5]);
    expect(SIGMA_ESIK).toBe(0.15);
  });
  it('λ sınıfları logaritmik', () => {
    expect(L_SINIRLAR).toEqual([0.03, 0.1, 0.3, 1, 3]);
    expect([0, 0.029, 0.03, 0.099, 0.1, 0.3, 1, 2.9, 3, 50].map(lambdaSinif)).toEqual([0, 0, 1, 1, 2, 3, 4, 4, 5, 5]);
  });
});

describe('b haritası', () => {
  it('n < 50 hücre boş: çizilmez; σ_b > 0,15 hücre taramalı', () => {
    const r = bSvg(hucreVeri(ornekHucreler()));
    expect(r.cizilen).toBe(5);                 // 39_40 (b yok) çizilmez
    expect(r.taramali).toBe(1);                // 37_36 σ 0,2
    expect(r.svg).toContain('data-rol="hucreler"');
    expect(r.svg).toContain('data-rol="tarama"');
    expect(r.svg).toContain('data-rol="lejant"');
    expect(r.uyari).toEqual([]);
  });
  it('n < 50 olsa bile b alanı doluysa hücre yine boş', () => {
    const r = bSvg(hucreVeri([hucre('38_27', 1.0, 0.1, 49), hucre('40_29', 1.0, 0.1, 50)]));
    expect(r.cizilen).toBe(1);
  });
  it('not "Betimleyici; tahmin değildir." ve Mc aralığı; kırmızı yok; yasak sözcük yok', () => {
    const r = bSvg(hucreVeri(ornekHucreler()));
    expect(r.metin).toContain('Betimleyici; tahmin değildir.');
    const a = bAciklama(hucreVeri(ornekHucreler()));
    expect(a).toContain('Mc');
    expect(a).toContain('n ≥ 50');
    expect(a.length).toBeLessThanOrEqual(1024);
    expect((a + r.svg).toLocaleLowerCase('tr')).not.toMatch(/tehlike|uyarı|#f00|#ff0000|red/);
  });
  it('PNG; hücresiz veri null', async () => {
    const k = await aylikB({ hucreler: hucreVeri(ornekHucreler()) }, { simdi });
    const m = await sharp(k.png).metadata();
    expect([m.width, m.height]).toEqual([1200, 800]);
    expect(await aylikB({ hucreler: hucreVeri([hucre('39_40', null, null, 12)]) }, { simdi })).toBeNull();
    expect(await aylikB({}, { simdi })).toBeNull();
  });
});

describe('λ haritası', () => {
  it('n < 50 ve Mc > 4 hücre boş; kalanlar çizilir', () => {
    const r = lambdaSvg(hucreVeri([...ornekHucreler(), hucre('36_30', null, null, 3, 0), hucre('35_30', 1.0, 0.1, 80, 5, 4.2)]));
    expect(r.cizilen).toBe(5);                 // 39_40 n=12 boş, 36_30 n=3 boş, 35_30 Mc 4,2 boş
    expect(r.svg).toContain('data-rol="lejant"');
    expect(r.metin).toContain('Betimleyici; tahmin değildir.');
    expect(r.metin).toContain("Mw ≥ 4'e çevrilmiş");
  });
  it('Mw ≥ 4 çevirisi: λ·10^(−b(4−Mc)); güvenilmez b yerine Türkiye b', () => {
    expect(lambda4({ lambda: 100, mc: 3, n: 200, b: 1, sigma_b: 0.05 }, 0.9)).toBeCloseTo(10, 9);
    expect(lambda4({ lambda: 100, mc: 3, n: 200, b: 1.3, sigma_b: 0.2 }, 1.0)).toBeCloseTo(10, 9);   // σ_b > 0,15 → Türkiye b
    expect(lambda4({ lambda: 7, mc: 4, n: 60, b: 1, sigma_b: 0.1 }, 1)).toBeCloseTo(7, 9);
    expect(turkiyeB({ turkiyeB: 1.04, hucreler: [] })).toBe(1.04);
    expect(turkiyeB({ hucreler: [hucre('a_b', 1.0, 0.05), hucre('c_d', 1.2, 0.05), hucre('e_f', 0.8, 0.05)] })).toBeCloseTo(1.0, 9);
  });
  it('büyük sayı Türkiye geneli λ(≥4) toplamı', () => {
    const r = lambdaSvg(hucreVeri([hucre('38_27', 1.0, 0.05, 100, 100, 3.0), hucre('40_29', 1.0, 0.05, 100, 200, 3.0)]));
    expect(r.toplam).toBeCloseTo(30, 9);
  });
  it('açıklama ve PNG', async () => {
    const v = { ...hucreVeri(ornekHucreler()), turkiyeB: 1.0 };
    const a = lAciklama(v);
    expect(a.length).toBeLessThanOrEqual(1024);
    expect(a).toContain('Mw ≥ 4');
    expect(a.toLocaleLowerCase('tr')).not.toMatch(/tehlike|uyarı/);
    const k = await ceyreklikLambda({ hucreler: v }, { simdi });
    expect((await sharp(k.png).metadata()).width).toBe(1200);
    expect(await ceyreklikLambda({}, { simdi })).toBeNull();
  });
  it('lejant çizili hücrelerle çakışmaz: hücre olmayan köşeye taşınır', () => {
    const doluSag = [hucre('34_42', 1.0, 0.05, 90, 5), hucre('34_44', 1.0, 0.05, 90, 5), hucre('35_41', 1.0, 0.05, 90, 5)];
    const r = bSvg(hucreVeri(doluSag));
    expect(r.svg).toContain('data-rol="lejant"');
    const m = r.svg.match(/data-rol="lejant"><rect x="([\d.]+)"/);
    expect(Number(m[1])).toBeLessThan(900);   // sağ alt dolu → başka yere
  });
});

describe('dönemsel kayıt', () => {
  it('DONEMSEL: aylikGr, aylikB, ceyreklikLambda kayıtlı', () => {
    for (const t of ['aylikGr', 'aylikB', 'ceyreklikLambda']) expect(typeof DONEMSEL[t]).toBe('function');
  });
  it('donemsel() kanal kartı üretir (kuyruğa yazılır, gönderilir)', async () => {
    const sorgu = vi.fn(async () => ({ degisen: 1 }));
    const k = { gonderiyor: vi.fn(async () => true), bitir: vi.fn(async () => {}), hataYap: vi.fn() };
    const t = { fotograf: vi.fn(async () => ({ mesajId: 7 })) };
    const r = await donemsel('aylikGr', { okuVeri: () => ({ gr: grBlok() }), k, t, db: { sorgu }, simdi, gecikme: 1 });
    expect(r).toEqual({ hedef: 'kanal', mesajId: 7 });
    expect(t.fotograf).toHaveBeenCalledOnce();
  });
});
