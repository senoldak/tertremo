import { describe, expect, it } from 'vitest';
import sharp from 'sharp';
import { dunya, dunyaSvg, turkiyeUzaklikKm } from '../../scripts/kart/kartlar/dunya.mjs';
import { enYakinSinir, levha, levhaSvg, yaziSiniri } from '../../scripts/kart/kartlar/levha.mjs';
import { LEVHA_ATIF } from '../../scripts/kart/harita.mjs';
import { OLAY_CIZICILER } from '../../scripts/kart/calistir.mjs';

const olay = (enlem, boylam, ek = {}) => ({
  id: 'x', zaman: Date.UTC(2026, 9, 24, 11, 32, 5), enlem, boylam, derinlik: 35, mw: 7.1, tur: 'Mw',
  yer: 'KERMADEC ISLANDS', bolge: 'dunya', tsunami: 1, pager: 'yellow', baslik: 'Kermadec Adaları, Yeni Zelanda',
  kaynaklar: { usgs: { buyukluk: 7.1 }, emsc: { buyukluk: 7.0 } }, ...ek,
});
const KONUMLAR = { kermadec: [-29.9, -177.8], alaska: [61, -150], japonya: [38, 142], sifir: [0, 0], kutup: [-78, 20], tarihCizgisi: [-17, 179.9] };
const R = 15;

describe('dünya kartı', () => {
  it('Türkiye uzaklığı haversine (Türkiye merkezi 39,0 K 35,0 D)', () => {
    expect(turkiyeUzaklikKm(39, 35)).toBeCloseTo(0, 3);
    expect(turkiyeUzaklikKm(-29.9, -177.8)).toBeGreaterThan(16000);
    expect(turkiyeUzaklikKm(-29.9, -177.8)).toBeLessThan(17500);
  });
  it.each(Object.entries(KONUMLAR))('%s: merkez üssü ortada, halka kesilmez, düzen uyarısı yok', (_, [la, lo]) => {
    const r = dunyaSvg({ olay: olay(la, lo) });
    expect(r.merkez.cx).toBeCloseTo(600, 1);
    expect(r.merkez.cy).toBeGreaterThanOrEqual(R + 2);
    expect(r.merkez.cy).toBeLessThanOrEqual(560 - R - 2);
    expect(r.uyari).toEqual([]);
  });
  it('tsunami ve PAGER satırda; atıf, "tehlike"/"uyarı" yok', () => {
    const r = dunyaSvg({ olay: olay(-29.9, -177.8) });
    expect(r.satir1).toContain('Derinlik 35 km');
    expect(r.satir1).toContain('tsunami');
    expect(r.satir1).toContain('PAGER sarı');
    expect(r.satir2).not.toMatch(/:dd:dd/);
    expect(r.not).toContain(LEVHA_ATIF);
    expect(r.not).toContain("Türkiye'ye");
    expect(`${r.satir1}${r.satir2}${r.not}`.toLowerCase()).not.toMatch(/tehlike|uyarı/);
  });
  it('isteğe bağlı alanlar yoksa çökmez', async () => {
    const o = olay(10, 100, { tsunami: 0, pager: null, derinlik: null });
    const png = await dunya({ olay: o });
    expect((await sharp(png).metadata()).width).toBe(1200);
  });
  it('1200×800 PNG', async () => {
    const m = await sharp(await dunya({ olay: olay(-29.9, -177.8) })).metadata();
    expect([m.width, m.height]).toEqual([1200, 800]);
  });
});

describe('levha sınırı kartı', () => {
  it('Japonya (38; 142): dalma-batma, makul uzaklık', () => {
    const e = enYakinSinir(38, 142);
    const y = yaziSiniri(e);
    expect(y.dalmaBatma).toBe(true);
    expect(y.km).toBeGreaterThan(20);
    expect(y.km).toBeLessThan(400);
    expect(levhaSvg({ olay: olay(38, 142) }).satir1).toMatch(/dalma-batma sınırı · .* km/);
  });
  it('Kermadec (−29,9; −177,8): dalma-batma, tolerans içinde (en yakın hat arka-yay olsa da)', () => {
    const y = yaziSiniri(enYakinSinir(-29.9, -177.8));
    expect(y.dalmaBatma).toBe(true);
    expect(y.km).toBeLessThan(250);
  });
  it('Kuzey Anadolu (40,7; 30,0): tür iddiası yok', () => {
    const r = levhaSvg({ olay: olay(40.7, 30.0, { bolge: 'yakin' }) });
    expect(r.satir1).toMatch(/levha sınırı · (.* km|sınırın üzerinde)/);
    expect(r.satir1).not.toMatch(/dalma|yakınsak|uzaklaşan|yanal|transform/);
  });
  it('Atlantik sırtı (0; −20): tür iddiası yok, dişli çizgi sınıfı yok', () => {
    const r = levhaSvg({ olay: olay(0, -20) });
    expect(r.satir1).not.toMatch(/dalma|yakınsak|uzaklaşan/);
  });
  it.each(Object.entries(KONUMLAR))('%s: halka kesilmez, düzen uyarısı yok', (_, [la, lo]) => {
    const r = levhaSvg({ olay: olay(la, lo) });
    expect(r.merkez.cx).toBeGreaterThanOrEqual(R + 2);
    expect(r.merkez.cx).toBeLessThanOrEqual(1200 - R - 2);
    expect(r.merkez.cy).toBeGreaterThanOrEqual(R + 2);
    expect(r.merkez.cy).toBeLessThanOrEqual(560 - R - 2);
    expect(r.uyari).toEqual([]);
  });
  it('Kermadec merkezde; Alaska ve Japonya kesilmeden', () => {
    expect(levhaSvg({ olay: olay(-29.9, -177.8) }).merkez.cx).toBeCloseTo(600, 1);
    for (const [la, lo] of [KONUMLAR.alaska, KONUMLAR.japonya]) {
      const m = levhaSvg({ olay: olay(la, lo) }).merkez;
      expect(m.cx).toBeGreaterThan(100);
      expect(m.cx).toBeLessThan(1100);
    }
  });
  it('atıf notta; satırlarda en yakın sınır türü ve km', () => {
    const r = levhaSvg({ olay: olay(38, 142) });
    expect(r.not).toContain(LEVHA_ATIF);
    expect(r.satir1).toMatch(/dalma-batma/);
    expect(r.satir1).toMatch(/km/);
  });
  it('1200×800 PNG', async () => {
    const m = await sharp(await levha({ olay: olay(38, 142) })).metadata();
    expect([m.width, m.height]).toEqual([1200, 800]);
  });
  it('çizicilar kayıtlı', () => {
    expect(typeof OLAY_CIZICILER.dunya).toBe('function');
    expect(typeof OLAY_CIZICILER.levha).toBe('function');
  });
});
