import { describe, expect, it } from 'vitest';
import sharp from 'sharp';
import { kaynaklarSvg, kaynaklar, kaynakListesi, farklar } from '../../scripts/kart/kartlar/kaynaklar.mjs';
import { enerjiSvg, enerji, enerjiJ, m4Esdeger, oranMetni, jouleMetni, toplamEnerji, enerji12AyHesapla } from '../../scripts/kart/kartlar/enerji.mjs';
import { OLAY_CIZICILER } from '../../scripts/kart/calistir.mjs';

const zaman = Date.UTC(2026, 9, 24, 11, 32, 5);
const olay = (ek = {}) => ({
  id: 'x', zaman, enlem: 38.245, boylam: 38.905, derinlik: 7, mw: 5.9, tur: 'Mw', kaynak: 'afad', bolge: 'turkiye', baslik: 'Malatya / Pütürge',
  kaynaklar: {
    afad: { id: '1', buyukluk: 5.9, tur: 'Mw', mw: 5.9, enlem: 38.245, boylam: 38.905, derinlik: 7 },
    kandilli: { id: '2', buyukluk: 5.4, tur: 'ML', mw: 5.4, enlem: 38.31, boylam: 38.99, derinlik: 5 },
    emsc: { id: '3', buyukluk: 5.7, tur: 'Mw', mw: 5.7, enlem: 38.2, boylam: 38.85 },
  }, ...ek,
});

describe('enerji hesabı', () => {
  it('Mw 6,0 = 1.000 tane M4; Mw 4 = 1; +1 büyüklük ≈ 31,62', () => {
    expect(m4Esdeger(6)).toBeCloseTo(1000, 9);
    expect(Math.round(m4Esdeger(6))).toBe(1000);
    expect(m4Esdeger(4)).toBe(1);
    expect(m4Esdeger(5) / m4Esdeger(4)).toBeCloseTo(31.6228, 3);
  });
  it('E = 10^(1,5Mw+4,8) J', () => {
    expect(Math.log10(enerjiJ(6))).toBeCloseTo(13.8, 9);
    expect(jouleMetni(enerjiJ(7))).toBe('2,0 × 10^15 J');
  });
  it('12 aylık oran: yüzde ve kat', () => {
    expect(oranMetni(1e14, 1e15)).toBe('%10');
    expect(oranMetni(1e13, 1e15)).toBe('%1,0');
    expect(oranMetni(3.5e15, 1e15)).toBe('3,5 kat');
    expect(oranMetni(1e15, 0)).toBeNull();
    expect(oranMetni(1e15, null)).toBeNull();
  });
  it('toplamEnerji: kutu başına adet × enerji', () => {
    const e = toplamEnerji([{ k: 80, n: 2 }, { k: 100, n: 1 }]); // Mw 4 ×2 + Mw 5 ×1
    expect(e).toBeCloseTo(2 * enerjiJ(4) + enerjiJ(5), 0);
  });
  it('D1 sorgusu: katalog=tr, son 365 gün, tek sorgu; hata atar', async () => {
    const cagri = [];
    const db = { async sorgu(sql, p) { cagri.push([sql, p]); return { satirlar: [{ k: 80, n: 10 }], degisen: 0 }; } };
    const simdi = Date.UTC(2026, 9, 24);
    const t = await enerji12AyHesapla({ db, simdi });
    expect(t).toBeCloseTo(10 * enerjiJ(4), -5);
    expect(cagri).toHaveLength(1);
    expect(cagri[0][1]).toEqual(['tr', simdi - 365 * 86_400_000]);
    expect(cagri[0][0]).toMatch(/katalog = \?/);
    await expect(enerji12AyHesapla({ db: { sorgu: async () => { throw new Error('düştü'); } } })).rejects.toThrow('düştü');
  });
});

describe('enerji kartı', () => {
  it('sayı ×N, birim M4 eşdeğeri; oranlı ve oransız çizilir', async () => {
    const o = { olay: olay({ mw: 6.0 }) };
    const r = enerjiSvg(o, { toplam12: 5e15 });
    expect(r.n).toBeCloseTo(1000, 6);
    expect(r.oran).toBe('%1,3');
    expect(r.uyari).toEqual([]);
    expect(enerjiSvg(o).oran).toBeNull();
    const png = await enerji(o, null, { toplam12: null });
    const m = await sharp(png).metadata();
    expect([m.width, m.height]).toEqual([1200, 800]);
  });
  it('120 karakterlik başlıkta kısaltma uyarısı, taşma yok', () => {
    const r = enerjiSvg({ olay: olay({ mw: 7.8, baslik: 'Çok uzun bir yer adı '.repeat(6).slice(0, 120) }) });
    expect(r.uyari.some((u) => u.startsWith('baslik kısaltıldı'))).toBe(true);
  });
  it('mw yoksa net hata', () => {
    expect(() => enerjiSvg({ olay: olay({ mw: null }) })).toThrow('olay.mw');
  });
});

describe('kaynaklar kartı', () => {
  it('ΔM: en büyük büyüklük farkı; konum farkı km', () => {
    const l = kaynakListesi(olay());
    expect(l.map((s) => s.ad)).toEqual(['AFAD', 'Kandilli', 'EMSC']);
    const f = farklar(l);
    expect(f.dM).toBeCloseTo(0.5, 9);
    expect(f.km).toBeGreaterThan(5);
    expect(f.km).toBeLessThan(20);
  });
  it('konumsuz kaynaklarla çökmez; çizer', async () => {
    const o = olay({ kaynaklar: { afad: { buyukluk: 4.6, tur: 'Mw' }, kandilli: { buyukluk: 4.0, tur: 'ML' } }, mw: 4.6 });
    const r = kaynaklarSvg({ olay: o });
    expect(r.dM).toBeCloseTo(0.6, 9);
    expect(r.km).toBeNull();
    expect(r.uyari).toEqual([]);
    const m = await sharp(await kaynaklar({ olay: o })).metadata();
    expect([m.width, m.height]).toEqual([1200, 800]);
  });
  it('tek kaynakla anlamsız: net hata', () => {
    expect(() => kaynaklarSvg({ olay: olay({ kaynaklar: { afad: { buyukluk: 5 } } }) })).toThrow('en az iki kaynak');
  });
  it('120 karakterlik başlık: kısaltılır', () => {
    const r = kaynaklarSvg({ olay: olay({ baslik: 'x'.repeat(120) }) });
    expect(r.uyari.some((u) => u.startsWith('baslik kısaltıldı'))).toBe(true);
  });
});

describe('kayıt', () => {
  it('OLAY_CIZICILER kaynaklar ve enerji türlerini içerir', () => {
    expect(typeof OLAY_CIZICILER.kaynaklar).toBe('function');
    expect(typeof OLAY_CIZICILER.enerji).toBe('function');
  });
});

describe('kaynaklar ham değer etiketi', () => {
  it('ham büyüklük + kendi türü; yoksa mw "(Mw)"; ΔM mw üzerinden', () => {
    const o = olay({ kaynaklar: {
      afad: { buyukluk: 4.6, tur: 'Mw', mw: 4.6 },
      kandilli: { buyukluk: 4.4, tur: 'ML', mw: 4.1 },
      emsc: { mw: 4.5 },
    } });
    const l = kaynakListesi(o);
    expect(l.map((s) => [s.ham, s.hamTur])).toEqual([[4.6, 'Mw'], [4.4, 'ML'], [4.5, '(Mw)']]);
    const r = kaynaklarSvg({ olay: o });
    expect(r.dM).toBeCloseTo(0.5, 9);
    expect(r.uyari).toEqual([]);
  });
});
