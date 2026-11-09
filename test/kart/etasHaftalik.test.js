import { describe, expect, it } from 'vitest';
import sharp from 'sharp';
import { aciklama, aralikTr, notMetni, etasHaftalik, etasSvg, hedef, yuzde } from '../../scripts/kart/kartlar/etasHaftalik.mjs';

const GUN = 86_400_000;
const bas = Date.UTC(2026, 9, 24, 3, 0, 0); // 24 Ekim 2026 06:00 TSİ
const bolgeler = [
  ['Marmara', 0.012, 0.009], ['Ege', 0.05, 0.04], ['Akdeniz', 0.03, 0.025], ['İç Anadolu', 0.004, 0.006],
  ['Karadeniz', 0.002, 0.003], ['Doğu Anadolu', 0.061, 0.04], ['Güneydoğu Anadolu', 0.02, 0.015],
].map(([ad, p5, norm5]) => ({ ad, p5, p6: p5 / 10, norm5, norm6: norm5 / 10 }));

const veri = (ek = {}) => ({
  etas: {
    surum: 'etas-1', hesap: bas, baslangic: bas, bitis: bas + 7 * GUN, mod: 'etas', neden: '', simulasyon: 10000,
    turkiye: { p5: 0.183, p6: 0.021, norm5: 0.121, norm6: 0.012 }, bolgeler,
    kapi: { gecti: null, ozet: 'doğrulama yapılmadı', gizliHafta: 0, yayin: false }, ...ek,
  },
});

describe('yuzde', () => {
  it('tam yüzde, %1 altı "<%1", Türkçe yazım', () => {
    expect(yuzde(0.183)).toBe('%18');
    expect(yuzde(0.0149)).toBe('%1');
    expect(yuzde(0.0099)).toBe('<%1');
    expect(yuzde(0)).toBe('<%1');
    expect(yuzde(0.9991)).toBe('>%99');
    expect(yuzde(null)).toBe('—');
  });
});

describe('aralikTr', () => {
  it('aynı ay ve ay devri', () => {
    expect(aralikTr(bas, bas + 7 * GUN)).toBe('24–31 Ekim 2026');
    expect(aralikTr(Date.UTC(2026, 9, 28, 3), Date.UTC(2026, 10, 4, 3))).toBe('28 Ekim – 4 Kasım 2026');
  });
});

describe('açıklama', () => {
  it('şablon: olasılık + olağan hafta, tahmin değil notu, bölgeler, M6 doğrulanmamış', () => {
    const a = aciklama(veri());
    expect(a).toContain('Haftalık deprem olasılığı (deneysel)');
    expect(a).toContain('24–31 Ekim 2026');
    expect(a).toContain('Mw 5 ve üzeri');
    expect(a).toContain('<b>%18</b> (olağan hafta: %12)');
    expect(a).toContain('Mw 6 ve üzeri: %2 (olağan: %1; doğrulanmamış model çıktısı)');
    expect(a).toContain('Doğu Anadolu %6 (olağan %4)');
    expect(a).toContain('İç Anadolu &lt;%1 (olağan &lt;%1)');
    expect(a).toContain('Bu bir tahmin değil, istatistiksel olasılıktır');
    expect(a).not.toContain('deneysel — doğrulama sürüyor');
    expect(a.length).toBeLessThanOrEqual(1024);
  });
  it('"tehlike" ve "uyarı" hiçbir çıktıda yok', () => {
    for (const v of [veri(), veri({ mod: 'poisson', neden: 'bu hafta model güncellenemedi' })]) {
      const metin = (aciklama(v) + etasSvg(v.etas)).toLocaleLowerCase('tr');
      expect(metin).not.toMatch(/tehlike|uyarı/);
    }
  });
  it('Poisson yedeği: "bu hafta model güncellenemedi", yalnız olağan değerler', () => {
    const v = veri({ mod: 'poisson', neden: 'bu hafta model güncellenemedi', turkiye: { p5: null, p6: null, norm5: 0.121, norm6: 0.012 },
      bolgeler: bolgeler.map((b) => ({ ...b, p5: null, p6: null })) });
    const a = aciklama(v);
    expect(a).toContain('bu hafta model güncellenemedi');
    expect(a).toContain('%12');
    expect(a).not.toContain('null');
  });
});

describe('hedef', () => {
  it('her zaman kanal', () => {
    expect(hedef(veri())).toBe('kanal');
    expect(hedef(veri({ kapi: { gecti: false, yayin: false } }))).toBe('kanal');
    expect(hedef({})).toBe('kanal');
  });
});

describe('kart', () => {
  it('1200×800 PNG; büyük sayı, birim, başlık ve not SVG\'de', async () => {
    const svg = etasSvg(veri().etas);
    for (const rol of ['sayi', 'birim', 'baslik', 'satir1', 'satir2', 'not', 'lejant']) expect(svg).toContain(`data-rol="${rol}"`);
    expect(svg).not.toContain('data-rol="etiket"');
    const { png } = await etasHaftalik(veri());
    const m = await sharp(png).metadata();
    expect([m.width, m.height]).toEqual([1200, 800]);
  });
  it('kapı geçtiyse "deneysel — doğrulama sürüyor" etiketi çizilmez', () => {
    const svg = etasSvg(veri({ kapi: { gecti: true, ozet: 'x', gizliHafta: 9, yayin: true } }).etas);
    expect(svg).not.toContain('data-rol="etiket"');
  });
  it('ETAS modunda her bölge yüzdesinin altında olağan hafta satırı; Poisson modunda yok', () => {
    expect(etasSvg(veri().etas).match(/data-rol="bolge-olagan"/g)).toHaveLength(7);
    const p = veri({ mod: 'poisson', turkiye: { p5: null, p6: null, norm5: 0.12, norm6: 0.01 } }).etas;
    expect(etasSvg(p)).not.toContain('data-rol="bolge-olagan"');
  });
  it('kırmızı renk yok', () => {
    expect(etasSvg(veri().etas).toLowerCase()).not.toMatch(/#f00|#ff0000|red/);
  });
  it('ileriye dönük sınav satırı: kartta "İleriye dönük sınavda: N/52 hafta", açıklamada kural bağlantısı', () => {
    const v = veri({ ileri: { hafta: 7, hedef: 52 } });
    const svg = etasSvg(v.etas);
    expect(svg).toContain('data-rol="not"');
    expect(notMetni(v.etas)).toContain('İleriye dönük sınavda: 7/52 hafta');
    expect(notMetni(v.etas)).toContain('deprem önceden bilinemez');
    expect(aciklama(v)).toContain('İleriye dönük sınavda: 7/52 hafta');
    expect(aciklama(v)).toContain('github.com/senoldak/tertremo/blob/main/docs/etas-on-kayit.md');
    expect(aciklama(v).length).toBeLessThanOrEqual(1024);
  });
  it('ileri yoksa sınav satırı çıkmaz', () => {
    expect(notMetni(veri().etas)).not.toContain('İleriye dönük');
    expect(aciklama(veri())).not.toContain('İleriye dönük');
  });
});
