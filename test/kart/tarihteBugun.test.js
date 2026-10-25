import fs from 'node:fs';
import { describe, expect, it, vi } from 'vitest';
import sharp from 'sharp';
import { donemsel, DONEMSEL } from '../../scripts/kart/calistir.mjs';
import { aciklama, bugunKayitlari, tarihteBugun } from '../../scripts/kart/kartlar/tarihteBugun.mjs';
import { kayitDonustur, yerAdi, yerelZaman } from '../../scripts/kart/veri-hazirla.mjs';

const kayitlar = JSON.parse(fs.readFileSync(new URL('../../data/tarihte-bugun.json', import.meta.url), 'utf8'));
const ags17 = Date.UTC(2026, 7, 17, 6, 0, 0);     // 17 Ağustos 2026 09:00 TSİ

describe('veri', () => {
  it('1999-08-17 Kocaeli depremi kayıtlı (Mw 7,6)', () => {
    const k = kayitlar.find((x) => x.t === '1999-08-17' && x.mw >= 7);
    expect(k).toBeTruthy();
    expect(k.yer).toBe('Kocaeli');
    expect(k.mw).toBeCloseTo(7.6, 1);
  });
  it('alanlar tam ve hepsi Mw ≥ 6', () => {
    for (const k of kayitlar) {
      expect(k.t).toMatch(/^\d{4}-\d\d-\d\d$/);
      expect(k.s).toMatch(/^\d\d:\d\d$/);
      expect(Number.isFinite(k.enlem) && Number.isFinite(k.boylam)).toBe(true);
      expect(k.mw).toBeGreaterThanOrEqual(6);
      expect(typeof k.yer).toBe('string');
    }
  });
});

const harita = {
  iller: JSON.parse(fs.readFileSync(new URL('../../data/harita/iller.json', import.meta.url), 'utf8')),
  ulkeler: JSON.parse(fs.readFileSync(new URL('../../data/harita/ulkeler-bolge.json', import.meta.url), 'utf8')),
};

describe('yerAdi', () => {
  it('Türkiye içinde il; yurt dışı olaylar ülke adıyla, denizde "açıkları"', () => {
    expect(yerAdi(29.86, 40.75, harita)).toBe('Kocaeli');
    expect(yerAdi(44.73, 38.11, harita)).toBe('İran');          // 1930-05-06 Salmas
    expect(yerAdi(25.64, 42.35, harita)).toBe('Bulgaristan');    // 1928-04-14 Çirpan
    expect(yerAdi(26.69, 42.22, harita)).toBe('Bulgaristan');    // 1909-02-15
    expect(yerAdi(43.74, 41.9, harita)).toBe('Gürcistan');       // 1940-05-07
    expect(yerAdi(25.74, 36.53, harita)).toBe('Yunanistan açıkları'); // 1911-04-04 Kiklad denizi
    expect(yerAdi(27.01, 37.43, harita)).toBe('Aydın açıkları');    // 1904-08-11: en yakın kıyı Didim (Sisam daha uzak)
  });
  it('deniz: yakın Türk kıyısı → "<İl> açıkları"; uzakta → ülke açıkları', () => {
    expect(yerAdi(26.0, 40.4, harita)).toMatch(/açıkları$/);
    expect(yerAdi(29.0, 41.3, harita)).toMatch(/açıkları$|^İstanbul$/);
  });
  it('USGS özelliği → kayıt (Türkiye yerel saati)', () => {
    const f = { properties: { mag: 7.6, time: Date.UTC(1999, 7, 17, 0, 1, 39) }, geometry: { coordinates: [30.0, 40.7, 15] } };
    expect(kayitDonustur(f, harita)).toEqual({ t: '1999-08-17', s: '03:01', enlem: 40.7, boylam: 30, mw: 7.6, yer: 'Kocaeli' });
  });
  it('yerel zaman: 22:30 UTC 16 Ağustos → 17 Ağustos 01:30', () => {
    expect(yerelZaman(Date.UTC(2026, 7, 16, 22, 30))).toEqual({ t: '2026-08-17', s: '01:30' });
  });
});

describe('bugunKayitlari', () => {
  it('gün-ay eşleşir, en büyük önce', () => {
    const l = bugunKayitlari(kayitlar, ags17);
    expect(l.length).toBeGreaterThan(0);
    expect(l[0].t).toBe('1999-08-17');
    for (let i = 1; i < l.length; i++) expect(l[i - 1].mw).toBeGreaterThanOrEqual(l[i].mw);
  });
  it('22:30 UTC 16 Ağustos olayı yerel 17 Ağustos kaydıdır ve 17 Ağustos kartında çıkar', () => {
    const k = kayitDonustur({ properties: { mag: 6.5, time: Date.UTC(1970, 7, 16, 22, 30) }, geometry: { coordinates: [30, 40.7] } }, harita);
    expect(k.t).toBe('1970-08-17');
    expect(bugunKayitlari([k], ags17)).toEqual([k]);
    expect(bugunKayitlari([k], Date.UTC(2026, 7, 16, 12))).toEqual([]);
  });
  it('kayıtsız gün boş', () => {
    expect(bugunKayitlari([{ t: '1999-08-17', s: '00:01', enlem: 40, boylam: 30, mw: 7.6, yer: 'Kocaeli' }], Date.UTC(2026, 0, 3, 6))).toEqual([]);
  });
});

describe('tarihteBugun kartı', () => {
  it('17 Ağustos: PNG 1200×800, sade açıklama, hedef kanal', async () => {
    const k = await tarihteBugun({}, { simdi: ags17 });
    const m = await sharp(k.png).metadata();
    expect([m.width, m.height]).toEqual([1200, 800]);
    expect(k.hedef).toBe('kanal');
    expect(k.aciklama.startsWith('🗓 <b>Tarihte bugün</b>\n17 Ağustos 1999 · Kocaeli · Mw 7,6')).toBe(true);
    expect(k.aciklama).toContain('17 Ağustos 1999 · Kocaeli · Mw 7,6');
  });
  it('aynı günde birden çok kayıt: en büyüğü ana, diğerleri listede', () => {
    const l = [
      { t: '1999-08-17', s: '00:01', enlem: 40.7, boylam: 30, mw: 7.6, yer: 'Kocaeli' },
      { t: '1950-08-17', s: '10:00', enlem: 38, boylam: 35, mw: 6.1, yer: 'Kayseri' },
    ];
    const a = aciklama(l, ags17);
    expect(a).toContain('17 Ağustos 1999 · Kocaeli · Mw 7,6');
    expect(a).toContain('Aynı gün: 1950 Kayseri Mw 6,1');
  });
  it('kayıtsız gün: null', async () => {
    expect(await tarihteBugun({}, { simdi: ags17, kayitlar: [] })).toBeNull();
  });
});

describe('donemsel tarihteBugun', () => {
  it('DONEMSEL içinde kayıtlı', () => { expect(typeof DONEMSEL.tarihteBugun).toBe('function'); });
  it('kayıtsız gün: çıkış 0 (hata yok), gönderim yok, D1 satırı yok', async () => {
    const t = { fotograf: vi.fn(), album: vi.fn() };
    const db = { sorgu: vi.fn() };
    const k = { gonderiyor: vi.fn(), bitir: vi.fn(), hataYap: vi.fn() };
    const uretici = (kv, o) => tarihteBugun(kv, { ...o, kayitlar: [] });
    const r = await donemsel('tarihteBugun', { env: {}, okuVeri: () => { throw new Error('kart-veri yok'); }, uretici, t, db, k, simdi: ags17 });
    expect(r).toEqual({ hedef: 'kanal', atlandi: true, kayitYok: true });
    expect(t.fotograf).not.toHaveBeenCalled();
    expect(db.sorgu).not.toHaveBeenCalled();
  });
});
