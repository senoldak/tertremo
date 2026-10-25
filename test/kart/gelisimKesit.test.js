import { describe, expect, it } from 'vitest';
import sharp from 'sharp';
import { gelisim, gelisimSvg, bath, guzelAdim } from '../../scripts/kart/kartlar/gelisim.mjs';
import { kesit, kesitSvg, medyan, temelDogrultu } from '../../scripts/kart/kartlar/kesit.mjs';
import { OLAY_CIZICILER } from '../../scripts/kart/calistir.mjs';

const T0 = Date.UTC(2026, 9, 23, 11, 32, 5);
const DK = 60_000;

/** Sentetik dizi: ana Mw 6,1; artçılar Omori benzeri, doğu–batı yayılımlı. */
function veri({ n = 80, mc = 2.0, saat = 24, ek = {} } = {}) {
  const olaylar = [];
  for (let i = 0; i < n; i++) {
    const t = DK * 3 * (1 + i) ** 1.5 * (saat / 24) ** 0.5; // dakika cinsinden büyüyen aralık
    if (t > saat * 60 * DK) break;
    olaylar.push({ zaman: T0 + t, enlem: 39.24 + 0.01 * Math.sin(i), boylam: 28.18 + 0.003 * (i % 40) - 0.06, derinlik: 5 + (i % 9), mw: mc + ((i * 37) % 23) / 10 });
  }
  const ana = { id: 'a', zaman: T0, enlem: 39.24, boylam: 28.18, derinlik: 8, mw: 6.1, tur: 'Mw', bolge: 'turkiye', baslik: 'Balıkesir / Sındırgı' };
  return {
    olay: ana,
    dizi: { id: 'a', ana, olaylar, saat, mc, toplam: olaylar.length },
    artci: { param: { a_ort: -2.42, a_sapma: 0.63, p: 0.98, c: 0.018, b: 1 }, Mana: 6.1, mc },
    ...ek,
  };
}

describe('gelişim kartı (kart 9)', () => {
  it('Båth: ana − 1,2; adım güzel sayı', () => {
    expect(bath(6.1)).toBeCloseTo(4.9, 10);
    expect(guzelAdim(100)).toBe(50);
    expect(guzelAdim(8)).toBe(2);
  });
  it('büyük sayı = toplam artçı; birim M ≥ Mc; en büyük artçı', async () => {
    const v = veri();
    const r = gelisimSvg(v);
    expect(r.sayi).toBe(String(v.dizi.olaylar.length));
    expect(r.birim).toBe('artçı (M ≥ 2,0)');
    expect(r.enBuyuk).toBeCloseTo(Math.max(...v.dizi.olaylar.map((o) => o.mw)), 10);
    expect(r.bath).toBeCloseTo(4.9, 10);
    expect(r.uyari).toEqual([]);
    const m = await sharp(await gelisim(v)).metadata();
    expect([m.width, m.height]).toEqual([1200, 800]);
  });
  it('toplam alanı varsa o yazılır (olay listesi 2000 ile kesilmiş olabilir)', () => {
    const v = veri();
    v.dizi.toplam = 3456;
    expect(gelisimSvg(v).sayi).toBe('3.456');
  });
  it('kesilmiş liste (en eski N olay): toplam ve en_buyuk alanları başlıkta, eğri ilk N olayı belirtir', async () => {
    const v = veri();
    v.dizi.toplam = 2100;
    v.dizi.en_buyuk = 5.0;
    const r = gelisimSvg(v);
    expect(r.sayi).toBe('2.100');
    expect(r.enBuyuk).toBe(5);
    await gelisim(v);
    expect(kesitSvg(v).uyari).toEqual([]);
    await kesit(v);
  });
  it('72 ve 168 saat, artçı yok, model parametresi yok: çökmez', async () => {
    await gelisim(veri({ saat: 72 }));
    await gelisim(veri({ saat: 168, n: 200 }));
    const bos = veri({ n: 0 });
    bos.artci = undefined;
    const r = gelisimSvg(bos);
    expect(r.sayi).toBe('0');
    expect(r.enBuyuk).toBeNull();
    await gelisim(bos);
  });
  it('120 karakterlik başlık düzeni bozmaz (kısaltılır, uyarı verir)', async () => {
    const v = veri();
    v.olay.baslik = 'Çok Uzun Bir Yer Adı '.repeat(6).slice(0, 120);
    const png = await gelisim(v);
    expect((await sharp(png).metadata()).width).toBe(1200);
  });
  it('dizi verisi yoksa açık hata', async () => {
    await expect(gelisim({ olay: veri().olay })).rejects.toThrow(/gelisim/);
  });
});

describe('kesit kartı (kart 10)', () => {
  const nokta = (e, b, z, mw = 3) => ({ enlem: e, boylam: b, derinlik: z, mw });
  it('doğu–batı dizilmiş olaylar → doğrultu ≈ 90°', () => {
    const l = Array.from({ length: 30 }, (_, i) => nokta(39.0 + 0.0005 * Math.sin(i), 28 + 0.01 * i, 8));
    expect(temelDogrultu(l).aci).toBeCloseTo(90, 0);
  });
  it('kuzey–güney → ≈ 0°/180°; KD–GB (45°) → ≈ 45°', () => {
    const ns = Array.from({ length: 30 }, (_, i) => nokta(38 + 0.01 * i, 28, 8));
    const a = temelDogrultu(ns).aci;
    expect(Math.min(a, 180 - a)).toBeLessThan(1);
    const kd = Array.from({ length: 30 }, (_, i) => nokta(38 + 0.01 * i, 28 + (0.01 * i) / Math.cos((38.15 * Math.PI) / 180), 8));
    expect(temelDogrultu(kd).aci).toBeCloseTo(45, 0);
  });
  it('eksen boyunca mesafe ortalamada sıfır, uzunluk km', () => {
    const l = Array.from({ length: 11 }, (_, i) => nokta(39, 28 + 0.01 * i, 8));
    const t = temelDogrultu(l);
    expect(t.d.reduce((a, b) => a + b, 0)).toBeCloseTo(0, 6);
    expect(Math.max(...t.d) - Math.min(...t.d)).toBeCloseTo(0.1 * 111.195 * Math.cos((39 * Math.PI) / 180), 1);
  });
  it('medyan derinlik', () => {
    expect(medyan([1, 2, 3, 10])).toBe(2.5);
    expect(medyan([5])).toBe(5);
  });
  it('büyük sayı = medyan derinlik km; PNG 1200×800', async () => {
    const v = veri();
    const r = kesitSvg(v);
    expect(r.birim).toBe('km');
    expect(r.sayi).toBe(String(Math.round(medyan(v.dizi.olaylar.map((o) => o.derinlik)))));
    expect(r.aci).toBeGreaterThan(60);
    expect(r.aci).toBeLessThan(120);
    expect(r.uyari).toEqual([]);
    const m = await sharp(await kesit(v)).metadata();
    expect([m.width, m.height]).toEqual([1200, 800]);
  });
  it('tek derinlik, ana derinliği yok, çok az olay', async () => {
    const v = veri();
    v.dizi.olaylar = v.dizi.olaylar.map((o) => ({ ...o, derinlik: 10 }));
    delete v.dizi.ana.derinlik;
    await kesit(v);
    v.dizi.olaylar = v.dizi.olaylar.slice(0, 2);
    await expect(kesit(v)).rejects.toThrow(/en az 3/);
  });
});

it('kayıtlı', () => {
  expect(OLAY_CIZICILER.gelisim).toBeTypeOf('function');
  expect(OLAY_CIZICILER.kesit).toBeTypeOf('function');
});
