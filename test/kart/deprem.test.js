import { describe, expect, it } from 'vitest';
import sharp from 'sharp';
import { halkaYaricapi, mmi } from '../../scripts/kart/ipe.mjs';
import { depremSvg, deprem, olayBaslik, mwBirim } from '../../scripts/kart/kartlar/deprem.mjs';
import { hissedildi, hissedildiSvg, ilSirala, ilSiddetleriHesapla } from '../../scripts/kart/kartlar/hissedildi.mjs';
import { OLAY_CIZICILER } from '../../scripts/kart/calistir.mjs';

const kaynaklar = { afad: { buyukluk: 4.6 }, kandilli: { buyukluk: 4.4 } };
const olay = (ek = {}) => ({
  id: 'x', zaman: Date.UTC(2026, 9, 24, 11, 32, 5), enlem: 38.245, boylam: 38.905, derinlik: 7, mw: 4.6, tur: 'Mw',
  yer: 'PÜTÜRGE (MALATYA)', il: 'Malatya', ilce: 'Pütürge', bolge: 'turkiye', kaynaklar, ...ek,
});

describe('IPE (Allen 2012) parite', () => {
  it('Worker siddet.js ile aynı değerler', () => {
    expect(mmi({ mw: 4.0, derinlik: 10, mesafeKm: 20 }).mmi).toBeCloseTo(3.4401, 4);
    expect(mmi({ mw: 5.5, derinlik: 10, mesafeKm: 100 }).mmi).toBeCloseTo(3.5293, 4);
    expect(mmi({ mw: 7.8, derinlik: 10, mesafeKm: 50 }).mmi).toBeCloseTo(7.9025, 4);
    expect(mmi({ mw: 7.8, derinlik: 10, mesafeKm: 1200 }).mmi).toBeCloseTo(3.3111, 4);
  });
  it('halkaYaricapi: yarıçapta MMI eşiğe eşit, eşik ulaşılmazsa 0', () => {
    const r = halkaYaricapi(5.5, 10, 4);
    expect(r).toBeGreaterThan(10);
    expect(mmi({ mw: 5.5, derinlik: 10, mesafeKm: r }).mmi).toBeCloseTo(4, 2);
    expect(halkaYaricapi(2.0, 10, 4)).toBe(0);
    expect(halkaYaricapi(5.5, 10, 2)).toBeGreaterThan(halkaYaricapi(5.5, 10, 3));
  });
});

describe('deprem kartı', () => {
  it('başlık: il / ilçe; dünyada yer; veri.baslik öncelikli', () => {
    expect(olayBaslik({ olay: olay() })).toBe('Malatya / Pütürge');
    expect(olayBaslik({ olay: olay({ il: null, ilce: null, bolge: 'dunya', yer: 'Yunanistan' }) })).toBe('Yunanistan');
    expect(olayBaslik({ baslik: 'Özel', olay: olay() })).toBe('Özel');
    expect(olayBaslik({ olay: olay({ baslik: 'Yeni Zelanda açıkları', bolge: 'dunya', yer: 'KERMADEC ISLANDS' }) })).toBe('Yeni Zelanda açıkları');
  });
  it('Mw / yaklaşık M birimi', () => {
    expect(mwBirim('Mw')).toBe('Mw');
    expect(mwBirim('ML')).toBe('Mw');
    expect(mwBirim('mb')).toBe('M (mb, yaklaşık)');
    expect(mwBirim('M')).toBe('M (yaklaşık)');
  });
  it('düzen çakışması yok, sayı ve başlık kısaltılmaz', () => {
    const r = depremSvg({ olay: olay() });
    expect(r.uyari).toEqual([]);
    expect(r.svg).toContain('data-rol="sayi"');
  });
  it('1200×800 PNG; yakın çevre dışı ve çok küçük/büyük olaylarda hata vermez', async () => {
    for (const o of [olay(), olay({ bolge: 'yakin', enlem: 35.2, boylam: 25.5, il: null, ilce: null, yer: 'Girit açıkları', mw: 5.8 }),
      olay({ mw: 2.1 }), olay({ mw: 7.4, derinlik: 15 }), olay({ tur: 'mb', kaynaklar: { usgs: { buyukluk: 4.6 } } })]) {
      const png = await deprem({ olay: o });
      const m = await sharp(png).metadata();
      expect([m.width, m.height]).toEqual([1200, 800]);
    }
  });
  it('olay kuyruğu çizicisi kayıtlı', () => {
    expect(typeof OLAY_CIZICILER.deprem).toBe('function');
    expect(typeof OLAY_CIZICILER.hissedildi).toBe('function');
  });
});

describe('hissedildi kartı', () => {
  it('ilSirala: en yüksek 10 il, azalan, eşitlikte ada göre', () => {
    const iller = Array.from({ length: 15 }, (_, i) => ({ ad: 'İl' + String.fromCharCode(65 + i), mmi: 2 + i * 0.2 }));
    const s = ilSirala(iller);
    expect(s).toHaveLength(10);
    expect(s[0].ad).toBe('İlO');
    expect(s.map((x) => x.mmi)).toEqual([...s.map((x) => x.mmi)].sort((a, b) => b - a));
  });
  it('Worker siddetIller yoksa kendi IPE ile 81 il hesaplanır (Sındırgı Mw 6,1: Manisa/Balıkesir önde)', () => {
    const il = ilSiddetleriHesapla({ enlem: 39.22, boylam: 28.17, derinlik: 11, mw: 6.1 });
    expect(il).toHaveLength(81);
    const ilk = ilSirala(il).slice(0, 2).map((x) => x.ad);
    expect(ilk).toEqual(expect.arrayContaining(['Balıkesir', 'Manisa']));
  });
  it('büyük sayı MMI ≥ 2,5 il sayısı; çakışma yok', () => {
    const il = [{ ad: 'Manisa', mmi: 5.2 }, { ad: 'İzmir', mmi: 4.3 }, { ad: 'Uşak', mmi: 3.0 }, { ad: 'Ankara', mmi: 2.4 }];
    const r = hissedildiSvg({ olay: olay({ mw: 6.1, enlem: 39.22, boylam: 28.17 }), siddetIller: il });
    expect(r.sayi).toBe(3);
    expect(r.uyari).toEqual([]);
  });
  it('boş il listesinde (Mw 3,2) hata vermez; Worker listesi Elazığ yazımını eşler', async () => {
    const png = await hissedildi({ olay: olay({ mw: 3.2 }), siddetIller: [] });
    expect((await sharp(png).metadata()).width).toBe(1200);
    const r = hissedildiSvg({ olay: olay(), siddetIller: [{ ad: 'Elazığ', mmi: 4.2 }] });
    expect(r.svg).toContain('#c9c5ef'); // 4,2 → IV (3,5–4,5)
  });
});
