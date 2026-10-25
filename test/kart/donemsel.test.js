import { describe, expect, it, vi } from 'vitest';
import sharp from 'sharp';
import { DONEMSEL, donemsel } from '../../scripts/kart/calistir.mjs';
import { GUN_MS, aralikYazi, dunyaYeri, esdegerMw, tsiGunBasi } from '../../scripts/kart/kartlar/donem.mjs';
import { aciklama as gunlukAciklama, gunluk, gunlukSvg, ozetle as gunlukOzet } from '../../scripts/kart/kartlar/gunluk.mjs';
import { aciklama as haftaAciklama, gunluk7, haftalik, haftalikSvg, hafta, ozetle as haftaOzet } from '../../scripts/kart/kartlar/haftalik.mjs';
import { aciklama as dunyaAciklama, dunyaHafta, dunyaHaftaSvg, pencere } from '../../scripts/kart/kartlar/dunyaHafta.mjs';

// 24 Ekim 2026 Cumartesi 21:00 TSİ = 18:00 UTC
const simdi = Date.UTC(2026, 9, 24, 18, 0, 0);
// 26 Ekim 2026 Pazartesi 08:00 TSİ = 05:00 UTC
const pazartesi = Date.UTC(2026, 9, 26, 5, 0, 0);
// 25 Ekim 2026 Pazar 20:00 TSİ = 17:00 UTC
const pazar = Date.UTC(2026, 9, 25, 17, 0, 0);

const olay = (ek = {}) => ({ zaman: simdi - 3600_000, enlem: 38.3, boylam: 38.4, derinlik: 8, mw: 3.4, tur: 'Mw', il: 'Malatya', ilce: 'Pütürge', yer: 'X', bolge: 'turkiye', ...ek });
const sahteDb = (satirlar) => ({ sorgu: vi.fn(async () => ({ satirlar, degisen: 0 })) });

describe('tarih yardımcıları', () => {
  it('TSİ gün başı: 21:00 TSİ → o günün 00:00 TSİ (21:00 UTC önceki gün)', () => {
    expect(tsiGunBasi(simdi)).toBe(Date.UTC(2026, 9, 23, 21, 0, 0));
  });
  it('aralık yazısı: aynı ay ve ay aşan', () => {
    const bas = Date.UTC(2026, 9, 18, 21);                       // 19 Ekim 00:00 TSİ
    expect(aralikYazi(bas, bas + 7 * GUN_MS)).toBe('19–25 Ekim');
    const bas2 = Date.UTC(2026, 9, 27, 21);                      // 28 Ekim 00:00 TSİ
    expect(aralikYazi(bas2, bas2 + 7 * GUN_MS)).toBe('28 Ekim – 3 Kasım');
  });
  it('enerji eşdeğeri: iki Mw 4 → Mw 4,2', () => {
    expect(esdegerMw(2 * 10 ** (1.5 * 4 + 4.8))).toBeCloseTo(4.2, 1);
  });
  it('dünya yeri: kara → ülke, açık deniz → "<Ülke> açıkları"', () => {
    expect(dunyaYeri({ boylam: 138.5, enlem: 36 })).toBe('Japonya');
    expect(dunyaYeri({ boylam: 142.8, enlem: 38.3 })).toMatch(/Japonya açıkları/);
  });
});

describe('günlük kart', () => {
  it('boş gün: "Bugün Mw ≥ 3 deprem kaydedilmedi" kartı üretilir (1200×800)', async () => {
    const k = await gunluk({}, { simdi, db: sahteDb([]) });
    expect(k.aciklama).toContain('Bugün Mw ≥ 3 deprem kaydedilmedi');
    expect(k.aciklama).toContain('24 Ekim');
    expect(k.hedef).toBe('kanal');
    const m = await sharp(k.png).metadata();
    expect([m.width, m.height]).toEqual([1200, 800]);
  });
  it('boş gün düzen uyarısı vermez', () => {
    expect(gunlukSvg([], simdi).uyari).toEqual([]);
  });
  it('açıklama: sayı, en büyüğü, bölgeler; HTML kaçışlı', () => {
    const l = [olay({ mw: 4.1 }), olay({ mw: 3.2, bolge: 'yakin', il: null, ilce: null, yer: 'AEGEAN <SEA>' }), olay({ mw: 3.1 })];
    const a = gunlukAciklama(l, simdi);
    expect(a).toContain('📅 <b>Bugün · 24 Ekim</b>');
    expect(a).toContain('Türkiye ve çevresinde Mw ≥ 3: 3 deprem · en büyüğü Mw 4,1 (Malatya / Pütürge)');
    expect(a).toContain('Türkiye 2 · yakın çevre 1');
    expect(gunlukOzet(l)).toMatchObject({ toplam: 3, turkiye: 2, yakin: 1 });
    expect(gunlukAciklama([olay({ bolge: 'yakin', il: null, yer: 'A & B' })], simdi)).toContain('A &amp; B');
  });
  it('D1: tek sorgu, olay_katalog_zaman indeksi, TSİ günü [00:00, şimdi]', async () => {
    const db = sahteDb([olay()]);
    await gunluk({}, { simdi, db });
    expect(db.sorgu).toHaveBeenCalledTimes(1);
    const [sql, p] = db.sorgu.mock.calls[0];
    expect(sql).toContain('INDEXED BY olay_katalog_zaman');
    expect(sql).toMatch(/LIMIT \d+/);
    expect(p[0]).toBe(tsiGunBasi(simdi));
    expect(p[1]).toBeGreaterThan(simdi);
  });
  it('çok olay + uzun yer adı: açıklama ≤ 1024, kart çizilir', async () => {
    const l = Array.from({ length: 300 }, (_, i) => olay({ mw: 3 + (i % 20) / 10, il: 'Çok uzun bir il adı '.repeat(8), ilce: null, enlem: 36 + (i % 7), boylam: 27 + (i % 15) }));
    const k = await gunluk({}, { simdi, db: sahteDb(l) });
    expect(k.aciklama.length).toBeLessThanOrEqual(1024);
    expect(k.aciklama).not.toMatch(/<[^>]*$/);
    expect((await sharp(k.png).metadata()).height).toBe(800);
  });
  it('mw eksik/sayı olmayan satırlar atlanır', async () => {
    const k = await gunluk({}, { simdi, db: sahteDb([olay({ mw: null }), olay({ mw: 3.5 })]) });
    expect(k.aciklama).toContain('Mw ≥ 3: 1 deprem');
  });
});

describe('haftalık kart', () => {
  it('pencere: pazartesi sabahı → önceki pazartesi 00:00 – bu pazartesi 00:00 TSİ', () => {
    const { bas, bit } = hafta(pazartesi);
    expect(bit).toBe(Date.UTC(2026, 9, 25, 21, 0, 0));
    expect(bit - bas).toBe(7 * GUN_MS);
    expect(aralikYazi(bas, bit)).toBe('19–25 Ekim');
  });
  it('günlük sayılar 7 gün; pencere dışı olay sayılmaz', () => {
    const { bas } = hafta(pazartesi);
    const g = gunluk7([olay({ zaman: bas + 1000 }), olay({ zaman: bas + 1500 }), olay({ zaman: bas + 6 * GUN_MS + 5000, mw: 5 }), olay({ zaman: bas - 5 })], bas);
    expect(g.map((x) => x.sayi)).toEqual([2, 0, 0, 0, 0, 0, 1]);
    expect(g[6].enBuyuk).toBe(5);
  });
  it('enerji eşdeğeri toplam enerjiden hesaplanır', () => {
    const z = haftaOzet([olay({ mw: 4 }), olay({ mw: 4 })]);
    expect(z.toplam).toBe(2);
    expect(z.esdeger).toBeCloseTo(4.2, 1);
  });
  it('boş hafta: "kaydedilmedi" kartı', async () => {
    const { bas, bit } = hafta(pazartesi);
    expect(haftaAciklama([], bas, bit)).toContain('kaydedilmedi');
    expect(haftalikSvg([], bas, bit).uyari).toEqual([]);
    const k = await haftalik({}, { simdi: pazartesi, db: sahteDb([]) });
    expect((await sharp(k.png).metadata()).width).toBe(1200);
  });
  it('açıklama ≤ 1024; en çok deprem günü, enerji', () => {
    const { bas, bit } = hafta(pazartesi);
    const l = [olay({ mw: 5.1, zaman: bas + 2 * GUN_MS }), olay({ zaman: bas + 2 * GUN_MS + 10 }), olay({ zaman: bas + 3 * GUN_MS })];
    const a = haftaAciklama(l, bas, bit);
    expect(a).toContain('Haftalık · 19–25 Ekim');
    expect(a).toContain('en büyüğü Mw 5,1 (Malatya / Pütürge, 21 Ekim)');
    expect(a).toContain('En çok deprem: Çar 21 Ekim, 2');
    expect(a).toContain('Toplam enerji');
    expect(a.length).toBeLessThanOrEqual(1024);
  });
  it('D1: tek sorgu, olay_katalog_zaman, Mw ≥ 3', async () => {
    const db = sahteDb([olay({ zaman: hafta(pazartesi).bas + 5 })]);
    await haftalik({}, { simdi: pazartesi, db });
    expect(db.sorgu).toHaveBeenCalledTimes(1);
    expect(db.sorgu.mock.calls[0][0]).toContain('INDEXED BY olay_katalog_zaman');
    expect(db.sorgu.mock.calls[0][1][2]).toBe(3);
  });
});

describe('dünya haftası kartı', () => {
  const d = (ek = {}) => ({ zaman: pazar - 86_400_000, enlem: 36, boylam: 138.5, derinlik: 20, mw: 5.4, tur: 'Mw', il: null, ilce: null, yer: 'Honshu', bolge: 'dunya', ...ek });
  it('pencere: pazartesi 00:00 TSİ – şimdi', () => {
    const { bas, bit } = pencere(pazar);
    expect(aralikYazi(bas, bit)).toBe('19–25 Ekim');
  });
  it('D1: olay_katalog_mw indeksi, tek sorgu', async () => {
    const db = sahteDb([d()]);
    await dunyaHafta({}, { simdi: pazar, db });
    expect(db.sorgu).toHaveBeenCalledTimes(1);
    expect(db.sorgu.mock.calls[0][0]).toContain('INDEXED BY olay_katalog_mw');
    expect(db.sorgu.mock.calls[0][1][0]).toBe(5);
  });
  it('açıklama: ilk 5, ≤ 1024; harita levha atfını taşır', () => {
    const { bas, bit } = pencere(pazar);
    const l = Array.from({ length: 40 }, (_, i) => d({ mw: 6.8 - i * 0.04, enlem: -20 + i, boylam: 170 + i }));
    const a = dunyaAciklama(l, bas, bit, () => 'Çok uzun yer adı '.repeat(10));
    expect(a.length).toBeLessThanOrEqual(1024);
    expect(a).not.toMatch(/<[^>]*$/);
    const r = dunyaHaftaSvg([d()], bas, bit);
    expect(r.uyari).toEqual([]);
  });
  it('tarih çizgisini geçen olay (±180°) çizilir, uyarı yok', async () => {
    const { bas, bit } = pencere(pazar);
    const k = await dunyaHaftaSvg([d({ boylam: 179.9, mw: 6.2 }), d({ boylam: -179.9, mw: 5.1 })], bas, bit);
    expect(k.uyari).toEqual([]);
  });
  it('boş hafta kart olur', async () => {
    const k = await dunyaHafta({}, { simdi: pazar, db: sahteDb([]) });
    expect(k.aciklama).toContain('kaydedilmedi');
    expect((await sharp(k.png).metadata()).height).toBe(800);
  });
});

describe('donemsel() ile günlük/haftalık/dünya haftası', () => {
  const ortam = { TERTREMO_KART_ANAHTARI: 'a' };
  it('kart-veri.json olmadan çalışır; kanal, sessiz; id donemsel:<tur>:<tarih>', async () => {
    const t = { fotograf: vi.fn(async () => ({ mesajId: 11 })) };
    const k = { gonderiyor: async () => true, bitir: vi.fn(async () => {}), hataYap: vi.fn() };
    const sorgu = vi.fn(async (sql) => (/INSERT OR IGNORE/.test(sql) ? { degisen: 1, satirlar: [] } : { satirlar: [], degisen: 0 }));
    const r = await donemsel('gunluk', { env: ortam, okuVeri: () => { throw new Error('yok'); }, t, k, db: { sorgu }, simdi });
    expect(r.mesajId).toBe(11);
    expect(t.fotograf.mock.calls[0][0]).toMatchObject({ sohbet: 'kanal', ses: false });
    expect(t.fotograf.mock.calls[0][0].aciklama).toContain('Bugün Mw ≥ 3 deprem kaydedilmedi');
    expect(k.bitir).toHaveBeenCalledWith('donemsel:gunluk:2026-10-24', 11, null);
  });
  it('tekrar önleme: aynı tür aynı gün ikinci kez gönderilmez', async () => {
    const t = { fotograf: vi.fn(async () => ({ mesajId: 1 })) };
    const k = { gonderiyor: async () => true, bitir: vi.fn(), hataYap: vi.fn() };
    const sorgu = vi.fn(async (sql) => (/INSERT OR IGNORE/.test(sql) ? { degisen: 0, satirlar: [] } : { degisen: 0, satirlar: [] }));
    const r = await donemsel('haftalik', { env: ortam, okuVeri: () => ({}), t, k, db: { sorgu }, simdi: pazartesi });
    expect(r.atlandi).toBe(true);
    expect(t.fotograf).not.toHaveBeenCalled();
  });
  it('kayıtlı üç tür', () => {
    for (const tur of ['gunluk', 'haftalik', 'dunyaHafta']) expect(typeof DONEMSEL[tur]).toBe('function');
  });
});
