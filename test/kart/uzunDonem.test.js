import { describe, expect, it, vi } from 'vitest';
import sharp from 'sharp';
import { DONEMSEL, donemsel } from '../../scripts/kart/calistir.mjs';
import { KATALOG_NOTU, aciklama, aralikYazi, uzunDonem, uzunDonemSvg } from '../../scripts/kart/kartlar/uzunDonem.mjs';

const simdi = Date.UTC(2026, 10, 1, 6, 0, 0);   // 1 Kasım 2026 09:00 TSİ

const c = (v) => v.map((x) => Math.min(1, x));
const tablo = (k) => ({
  1: { 5: c([0.6 * k, 0.5 * k, 0.7 * k]), 6: c([0.07 * k, 0.04 * k, 0.1 * k]), 7: c([0.01 * k, 0.003 * k, 0.02 * k]) },
  10: { 5: [0.98, 0.95, 0.999], 6: c([0.5 * k, 0.35 * k, 0.65 * k]), 7: c([0.1 * k, 0.04 * k, 0.17 * k]) },
  50: { 5: [1, 1, 1], 6: c([0.95 * k, 0.9 * k, 0.99 * k]), 7: c([0.45 * k, 0.2 * k, 0.7 * k]) },
});
const OLAYLAR = [[40.75, 29.86, 7.6, 1999], [40.76, 31.16, 7.2, 1999], [37.23, 37.01, 7.8, 2023], [38.7, 26.5, 6.1, 1955], [39.2, 28.2, 6.0, 2025], [36.9, 30.7, 6.4, 1957]];
const blok = (ek = {}) => ({
  surum: 'uzun-1', hesap: simdi - 3600e3, baslangic: Date.UTC(2018, 0, 1), bitis: simdi, yil: 8.8, mc: 3.0, kumeleme: 'en-yakin-komsu', bootstrap: 1000,
  uzunKatalog: { yontem: 'gardner-knopoff', kaynak: 'USGS FDSN', bas6: 1964, bas7: 1918, n6: 43, n7: 17, olaylar: OLAYLAR },
  turkiye: { n: 657, n6: 43, n7: 17, b: 1.13, olasilik: tablo(1.6) },
  bolgeler: [['Marmara', 0.9], ['Ege', 1.4], ['Akdeniz', 0.6], ['İç Anadolu', 0.3], ['Karadeniz', 0.15], ['Doğu Anadolu', 1.7]]
    .map(([ad, k]) => ({ ad, n: 12, olasilik: tablo(k) })),
  ...ek,
});

describe('aralık', () => {
  it('aralık yazımı tam yüzde', () => {
    expect(aralikYazi(0.812, 0.9304)).toBe('%81–%93');
    expect(aralikYazi(0.004, 0.012)).toBe('%0–%1');
  });
});

describe('uzun dönem kartı', () => {
  it('SVG: merkez üsleri, lejant, tablo; bölge yüzdesi ve etiketi yok; düzen uyarısı yok', () => {
    const r = uzunDonemSvg(blok());
    for (const rol of ['sayi', 'birim', 'baslik', 'satir1', 'satir2', 'not', 'olaylar', 'tablo', 'lejant', 'katalog-notu', 'gecmis-notu']) expect(r.svg).toContain(`data-rol="${rol}"`);
    expect(r.svg).not.toContain('data-rol="bolge');
    expect(r.uyari).toEqual([]);
  });
  it('olaylar: Mw ≥ 6 küçük nokta, Mw ≥ 7 halka; her merkez üssü bir daire', () => {
    const r = uzunDonemSvg(blok());
    const g = r.svg.match(/data-rol="olaylar"><svg.*?<\/svg>/s)[0];
    expect(g.match(/<circle/g)).toHaveLength(OLAYLAR.length);
    expect(g.match(/r="11"/g)).toHaveLength(3);
    expect(g.match(/r="5.5"/g)).toHaveLength(3);
  });
  it('büyük sayı: Türkiye 1 yılda Mw ≥ 6 (orta değer); USGS dönemi kartta', () => {
    const r = uzunDonemSvg(blok());
    expect(r.bant.sayi).toBe('%11');
    expect(r.bant.birim).toBe('1 yılda Mw ≥ 6, Türkiye');
    expect(r.bant.satir1).toContain('%6–%16');
    expect(r.bant.satir1).toContain('USGS 1964–2026, 43 olay');
    expect(r.bant.satir2).toBe('Kümelenmiş olaylar ayıklanmış (Gardner–Knopoff)');
  });
  it('not: tahmin değildir + zamandan bağımsız Poisson; bölge adı/yüzdesi ne kartta ne açıklamada; yasak sözcük ve kırmızı yok', () => {
    const r = uzunDonemSvg(blok());
    expect(r.metin).toBe('Olasılık hesabıdır; depremin yeri ve zamanı önceden bilinemez. Zamandan bağımsız Poisson modeli.');
    const a = aciklama(blok());
    expect(a.length).toBeLessThanOrEqual(1024);
    expect(a).toContain('Olasılık hesabıdır; depremin yeri ve zamanı önceden bilinemez.');
    expect(a).toContain('Mc 3,0');
    expect(KATALOG_NOTU).toBe('Mw ≥ 6–7: USGS 1964/1918– kataloğu; Mw 5: EMSC 2018–');
    expect(a).toContain(KATALOG_NOTU);
    expect(a).toContain('Gardner–Knopoff');
    expect(a).toContain('en yakın komşu');
    expect(a).toContain('Türkiye (kıyıdan 30 km dahil)');
    expect(a).not.toMatch(/Türkiye ve çevresi/);
    expect(a).not.toMatch(/Marmara|Ege|Akdeniz|Karadeniz|İç Anadolu|Doğu Anadolu|bölge/);
    expect(a).toContain('geçmiş kaydı gösterir, gelecekteki yer ve zamanı göstermez');
    expect((a + r.svg).toLocaleLowerCase('tr')).not.toMatch(/tehlike|uyarı/);
    expect(r.svg.toLowerCase()).not.toMatch(/#f00|#ff0000|red/);
  });
  it('tablo hücreleri Türkçe yüzde: 1/10/50 yıl × Mw ≥ 5/6/7', () => {
    const r = uzunDonemSvg(blok());
    expect(r.tablo).toEqual([['%96', '%11', '%2'], ['%98', '%80', '%16'], ['>%99', '>%99', '%72']]);
  });
  it('1200×800 PNG, kanal hedefi', async () => {
    const k = await uzunDonem({ uzunDonem: blok() }, { simdi });
    const m = await sharp(k.png).metadata();
    expect([m.width, m.height]).toEqual([1200, 800]);
    expect(k.hedef).toBe('kanal');
  });
  it('veri yok ya da önbellek eski: null', async () => {
    expect(await uzunDonem({}, { simdi })).toBeNull();
    const uyar = vi.spyOn(console, 'warn').mockImplementation(() => {});
    expect(await uzunDonem({ uzunDonem: blok({ hesap: simdi - 20 * 86400e3 }) }, { simdi })).toBeNull();
    uyar.mockRestore();
  });
  it('kart-veri.json bölge değerleri duruyor ama kartta çizilmez; olay listesi boşsa da çizilir', () => {
    expect(blok().bolgeler).toHaveLength(6);
    const b = blok();
    b.uzunKatalog = { ...b.uzunKatalog, olaylar: undefined };
    expect(uzunDonemSvg(b).svg).toContain('data-rol="olaylar"');
  });
});

describe('dönemsel kayıt', () => {
  it('DONEMSEL.uzunDonem kayıtlı ve donemsel() kanala gönderir', async () => {
    expect(typeof DONEMSEL.uzunDonem).toBe('function');
    const sorgu = vi.fn(async () => ({ degisen: 1 }));
    const k = { gonderiyor: vi.fn(async () => true), bitir: vi.fn(async () => {}), hataYap: vi.fn() };
    const t = { fotograf: vi.fn(async () => ({ mesajId: 9 })) };
    const r = await donemsel('uzunDonem', { okuVeri: () => ({ uzunDonem: blok() }), k, t, db: { sorgu }, simdi, gecikme: 1 });
    expect(r).toEqual({ hedef: 'kanal', mesajId: 9 });
  });
});
