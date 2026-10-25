import { describe, expect, it } from 'vitest';
import sharp from 'sharp';
import { artci, artciSvg, beklenenN, bantKirp, yAltSinir } from '../../scripts/kart/kartlar/artci.mjs';
import { ozet, ozetSvg, ozetYaricap } from '../../scripts/kart/kartlar/ozet.mjs';
import { OLAY_CIZICILER } from '../../scripts/kart/calistir.mjs';

const veri = (ek = {}) => ({
  olay: { id: 'x', zaman: Date.UTC(2026, 9, 24, 11, 32, 5), enlem: 38.2, boylam: 38.9, derinlik: 7, mw: 6.0, tur: 'Mw', bolge: 'turkiye', baslik: 'Malatya / Pütürge' },
  artci: {
    satirlar: [{ m: 4, orta: 0.83, alt: 0.4, ust: 0.97 }, { m: 5, orta: 0.21, alt: 0.07, ust: 0.45 }],
    param: { a_ort: -2.42, a_sapma: 0.63, p: 0.98, c: 0.018, b: 1 }, Mana: 6, mc: 2.5, t_simdi_gun: 0.02,
    gozlenen: [{ t_gun: 0.011, mw: 3.4 }, { t_gun: 0.015, mw: 3.1 }, { t_gun: 0.019, mw: 2.2 }],
    ...ek,
  },
});

describe('artçı kartı', () => {
  it('RJ kapalı form Worker paritesi', () => {
    expect(beklenenN(-2.42, 0.98, 0.018, 1, 6, 5, 0, 7)).toBeCloseTo(0.2223, 3);
  });
  it('bant kırpma: üst sınıra kırpılır, alt 0 altına inmez', () => {
    expect(bantKirp(50, 10)).toBe(10);
    expect(bantKirp(-1, 10)).toBe(0);
    expect(bantKirp(4, 10)).toBe(4);
    expect(yAltSinir(3, 0.4)).toBeGreaterThan(0);
  });
  it('büyük sayı ve birim', async () => {
    const r = artciSvg(veri());
    expect(r.sayi).toBe('%21');
    expect(r.birim).toBe('7 günde en az bir M≥5');
    expect(r.yMax).toBeGreaterThanOrEqual(r.gozlenenSon * 1.1 - 1e-9);
    const png = await artci(veri());
    const m = await sharp(png).metadata();
    expect([m.width, m.height]).toEqual([1200, 800]);
  });
  it('gözlenenler şimdiye kadar kırpılır; gözlem yoksa gösterge "gözlenen" yazmaz; şimdi erkense eksen geri çekilir', () => {
    const v = veri({ t_simdi_gun: 0.0014, gozlenen: [{ t_gun: 0.001, mw: 3.5 }, { t_gun: 0.005, mw: 3.5 }] });
    const r = artciSvg(v);
    expect(r.gozlenenSon).toBe(1);
    expect(r.axisBas).toBeCloseTo(0.001, 5);
    expect(r.svg.includes('stroke-dasharray')).toBe(true);
    expect(artciSvg(veri({ gozlenen: [] })).gozlenenVar).toBe(false);
    expect(artciSvg(veri()).gozlenenVar).toBe(true);
  });
  it('gözlem yok / satır yok: çökmez ya da açık hata', async () => {
    await artci(veri({ gozlenen: undefined, t_simdi_gun: undefined }));
    await expect(artci({ olay: veri().olay })).rejects.toThrow(/artci/);
  });
  it('kayıtlı', () => { expect(OLAY_CIZICILER.artci).toBeTypeOf('function'); expect(OLAY_CIZICILER.ozet).toBeTypeOf('function'); });
});

describe('dizi özeti kartı', () => {
  const dizi = {
    id: 'd', ana: { zaman: 1, enlem: 39.24, boylam: 28.18, mw: 3.8 },
    olaylar: [{ zaman: 1, enlem: 39.24, boylam: 28.18, mw: 3.8, derinlik: 8 }, { zaman: 2, enlem: 39.36, boylam: 28.0, mw: 3.1, derinlik: 8 }, { zaman: 3, enlem: 39.1, boylam: 28.4, mw: 3.0, derinlik: 8 }],
  };
  it('ölçek: en az 30 km, en uzak olayın 1,5 katı', () => {
    expect(ozetYaricap(dizi.ana, [{ enlem: 39.24, boylam: 28.18 }])).toBe(30);
    const y = ozetYaricap({ enlem: 39, boylam: 28 }, [{ enlem: 39, boylam: 29 }]);
    expect(y).toBeCloseTo(1.5 * 111.195 * Math.cos((39 * Math.PI) / 180), 0);
  });
  it('çizim', async () => {
    const r = ozetSvg({ olay: { baslik: 'Sındırgı' }, dizi });
    expect(r.sayi).toBe('3');
    expect(ozetSvg({ olay: { il: 'Balıkesir', ilce: 'Sındırgı' }, dizi }).yer).toBe('Balıkesir / Sındırgı');
    expect(ozetSvg({ olay: {}, dizi }).yer).toBe('');
    const m = await sharp(await ozet({ olay: { baslik: 'Sındırgı' }, dizi })).metadata();
    expect([m.width, m.height]).toEqual([1200, 800]);
    await expect(ozet({ olay: {} })).rejects.toThrow(/dizi/);
  });
});
