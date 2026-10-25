import { describe, expect, it } from 'vitest';
import sharp from 'sharp';
import { NOT_METNI, olagandisi, olagandisiSvg, pYazi, poissonAralik } from '../../scripts/kart/kartlar/olagandisi.mjs';
import { OLAY_CIZICILER } from '../../scripts/kart/calistir.mjs';

const veri = (ek = {}, olay = {}) => ({
  olay: { id: 'afad:1', zaman: Date.UTC(2026, 9, 24, 11, 32, 5), enlem: 38.2, boylam: 38.85, mw: 4.6, bolge: 'turkiye', katalog: 'tr', baslik: 'Malatya / Pütürge', ...olay },
  olagandisi: { k: 14, beklenen: 4.1, p: 0.0001, bh_p: 0.001, hucre: { anahtar: '38_38', enlem: 38, boylam: 38, boyut_derece: 1 }, pencere_gun: 7, ...ek },
});

describe('Poisson %95 aralığı (kuyruk toplamı)', () => {
  it('μ = 4,1 → [1, 8] (elle: P(X≤0)=0,0166 < 0,025 ≤ P(X≤1)=0,0845; P(X≤7)=0,9426 < 0,975 ≤ P(X≤8)=0,9754)', () => {
    expect(poissonAralik(4.1)).toEqual([1, 8]);
  });
  it('μ = 0,07 → [0, 1]; μ = 25 → [16, 35]; μ ≤ 0 → [0, 0]', () => {
    expect(poissonAralik(0.07)).toEqual([0, 1]);
    expect(poissonAralik(25)).toEqual([16, 35]);
    expect(poissonAralik(0)).toEqual([0, 0]);
  });
  it('p yazımı', () => {
    expect(pYazi(0.0001)).toBe('< 0,001');
    expect(pYazi(0.012)).toBe('0,012');
    expect(pYazi(null)).toBe('—');
  });
});

describe('olağan dışı kartı', () => {
  it('Türkiye hücresi: büyük sayı k, birim, not, aralık; düzen uyarısı yok', () => {
    const r = olagandisiSvg(veri());
    expect(r.bant.sayi).toBe('14');
    expect(r.bant.birim).toBe('bağımsız deprem');
    expect(r.aralik).toEqual([1, 8]);
    expect(r.bant.satir1).toContain('Son 7 gün · uzun dönem ort. 4,1');
    expect(r.bant.satir2).toContain('BH düzeltilmiş p 0,001');
    expect(r.uyari).toEqual([]);
  });
  it('yasak sözcük yok, not tahmin değildir diyor', () => {
    const r = olagandisiSvg(veri());
    expect(NOT_METNI).toBe('Beklenenden fazla etkinlik tahmin değildir.');
    expect(`${r.bant.baslik}${r.bant.satir1}${r.bant.satir2}${NOT_METNI}`.toLowerCase()).not.toMatch(/tehlike|uyarı/);
  });
  it('bh_p yoksa "yok"; uzun başlık kısalır ama uyarı vermez', () => {
    const r = olagandisiSvg(veri({ bh_p: null }, { baslik: 'Çok Uzun Bir Yer Adı '.repeat(8) }));
    expect(r.bant.satir2).toContain('BH düzeltilmiş p yok');
    expect(r.bant.baslik).toBe('Olağan dışı etkinlik');
    expect(r.uyari).toEqual([]);
  });
  it('dünya hücresi (5°) ve tarih çizgisi: çizilir, uyarı yok', async () => {
    const v = veri({ hucre: { anahtar: '-20_175', enlem: -20, boylam: 175, boyut_derece: 5 } }, { bolge: 'dunya', katalog: 'dunya', baslik: 'Tonga' });
    expect(olagandisiSvg(v).uyari).toEqual([]);
    const m = await sharp(await olagandisi(v)).metadata();
    expect([m.width, m.height]).toEqual([1200, 800]);
  });
  it('hücre alanı yoksa olay konumundan türetilir; olagandisi yoksa açık hata', () => {
    const v = veri();
    delete v.olagandisi.hucre;
    expect(olagandisiSvg(v).hucre).toMatchObject({ enlem: 38, boylam: 38, boyut_derece: 1 });
    expect(() => olagandisiSvg({ olay: v.olay })).toThrow(/olagandisi/);
  });
  it('calistir kaydı', () => {
    expect(typeof OLAY_CIZICILER.olagandisi).toBe('function');
  });
});
