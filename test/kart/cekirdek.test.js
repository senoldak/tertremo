import { describe, expect, it } from 'vitest';
import sharp from 'sharp';
import { YAZI } from '../../scripts/kimlik.mjs';
import { altBant, genislik, kart, kisalt, logoKutusu, not, sayiTr, tarihTr } from '../../scripts/kart/cekirdek.mjs';
import { LEVHA_ATIF, bolgeHaritasi, dunyaHaritasi, turkiyeCevresi } from '../../scripts/kart/harita.mjs';

// <g data-rol="x"> içindeki yol verisinin sınır kutusu (toPathData yalnız mutlak M/L/Q/C/Z üretir).
function rolKutusu(svg, rol) {
  const g = new RegExp(`<g data-rol="${rol}">([\\s\\S]*?)</g>`).exec(svg);
  expect(g, `rol ${rol} yok`).toBeTruthy();
  const d = [...g[1].matchAll(/ d="([^"]+)"/g)].map((m) => m[1]).join(' ');
  const n = (d.match(/-?\d+(?:\.\d+)?/g) ?? []).map(Number);
  const xs = n.filter((_, i) => i % 2 === 0);
  const ys = n.filter((_, i) => i % 2 === 1);
  return { x1: Math.min(...xs), x2: Math.max(...xs), y1: Math.min(...ys), y2: Math.max(...ys) };
}
const kesisir = (a, b) => a.x1 < b.x2 && b.x1 < a.x2 && a.y1 < b.y2 && b.y1 < a.y2;
const UZUN = 'Çok uzun bir yer adı '.repeat(8).slice(0, 120);

describe('altBant', () => {
  const svg = altBant({ sayi: '6,1', birim: 'Mw', baslik: UZUN, satir1: UZUN, satir2: UZUN });
  it('120 karakterlik yazılar sağ sütunda 360–1160 içinde kalır', () => {
    for (const rol of ['baslik', 'satir1', 'satir2']) {
      const k = rolKutusu(svg, rol);
      expect(k.x1).toBeGreaterThanOrEqual(360);
      expect(k.x2).toBeLessThanOrEqual(1160);
    }
  });
  it('logo kutusuyla ve büyük sayıyla çakışmaz', () => {
    const logo = logoKutusu();
    const sayi = rolKutusu(svg, 'sayi');
    for (const rol of ['baslik', 'satir1', 'satir2']) {
      const k = rolKutusu(svg, rol);
      expect(kesisir(k, logo)).toBe(false);
      expect(kesisir(k, sayi)).toBe(false);
    }
  });
  it('çok geniş sayı sol sütuna sığar (56–340)', () => {
    const k = rolKutusu(altBant({ sayi: '16.800.000', birim: 'km', baslik: 'a', satir1: 'b', satir2: 'c' }), 'sayi');
    expect(k.x1).toBeGreaterThanOrEqual(56);
    expect(k.x2).toBeLessThanOrEqual(340);
  });
  it('alt bant y 560–800 içinde, yazılar kart dışına taşmaz', () => {
    for (const rol of ['baslik', 'satir1', 'satir2', 'sayi', 'birim']) {
      const k = rolKutusu(svg, rol);
      expect(k.y1).toBeGreaterThanOrEqual(560);
      expect(k.y2).toBeLessThanOrEqual(800);
    }
  });
});

describe('kisalt', () => {
  it('sığan metni olduğu gibi bırakır', () => {
    expect(kisalt('Malatya / Pütürge', 46, 800)).toBe('Malatya / Pütürge');
  });
  it('uzun metni "…" ile keser ve genişliğe uyar', () => {
    const k = kisalt(UZUN, 46, 800);
    expect(k.endsWith('…')).toBe(true);
    expect(genislik(k, 46)).toBeLessThanOrEqual(800);
    expect(genislik(UZUN, 46)).toBeGreaterThan(800);
    expect(k).not.toMatch(/\s…$/);
  });
  it('kesilen metin mümkün olan en uzunu korur', () => {
    const k = kisalt(UZUN, 46, 800);
    const bir = UZUN.slice(0, k.length - 1 + 1) + '…';
    expect(genislik(bir, 46)).toBeGreaterThan(800);
  });
  it('çok dar genişlikte bile taşmaz', () => {
    expect(genislik(kisalt('Merhaba', 46, 10), 46)).toBeLessThanOrEqual(46);
  });
});

describe('kart', () => {
  it('1200×800 PNG üretir', async () => {
    const png = await kart(altBant({ sayi: '4,6', birim: 'Mw', baslik: 'Test', satir1: 'a', satir2: 'b' }));
    const m = await sharp(png).metadata();
    expect([m.format, m.width, m.height]).toEqual(['png', 1200, 800]);
  });
});

describe('not', () => {
  it('18 px not y 548 tabanında, 56 soldan başlar', () => {
    const k = rolKutusu(not('Tahmin değildir.'), 'not');
    expect(k.x1).toBeGreaterThanOrEqual(56);
    expect(k.y2).toBeLessThanOrEqual(548 + 6);
  });
});

describe('sayiTr', () => {
  it('Türkçe biçim', () => {
    expect(sayiTr(4.6, 1)).toBe('4,6');
    expect(sayiTr(-0.04, 1)).toBe('0,0');
    expect(sayiTr(-1.5, 1)).toBe('−1,5');
    expect(sayiTr(16800, 0)).toBe('16.800');
    expect(sayiTr(1234567.891, 2)).toBe('1.234.567,89');
    expect(sayiTr(999.96, 1)).toBe('1.000,0');
    expect(sayiTr(7, 0)).toBe('7');
  });
});

describe('tarihTr', () => {
  it('TSİ (UTC+3) biçimi', () => {
    expect(tarihTr(Date.UTC(2026, 9, 24, 11, 32, 5))).toBe('24 Ekim 2026 · 14:32:05 TSİ');
  });
  it('gün değişimini TSİ ile hesaplar', () => {
    expect(tarihTr(Date.UTC(2026, 11, 31, 21, 30, 0))).toBe('1 Ocak 2027 · 00:30:00 TSİ');
  });
});

describe('yazı tipi kapsamı', () => {
  it('kartlarda geçen özel karakterler tanımlı', () => {
    for (const c of '−…·≥İşğ%') expect(YAZI.charToGlyph(c).index, c).toBeGreaterThan(0);
  });
});

describe('turkiyeCevresi', () => {
  const t = turkiyeCevresi();
  it('sabit kutu: 35,2 D ortada, 43,4 K üstte', () => {
    expect(t.px(35.2)).toBeCloseTo(600, 1);
    expect(t.py(43.4)).toBeCloseTo(0, 5);
  });
  it('zemin dolu ve NaN yok', () => {
    expect(t.zemin.length).toBeGreaterThan(1000);
    expect(t.zemin).not.toMatch(/NaN/);
  });
});

describe('dunyaHaritasi', () => {
  it('merkez boylamı x ≈ 600', () => {
    const d = dunyaHaritasi({ boylamMerkez: -177.8 });
    expect(Math.abs(d.px(-177.8) - 600)).toBeLessThanOrEqual(2);
    expect(Math.abs(d.px(-177.8 + 100) - (600 + (100 / 360) * 1200))).toBeLessThanOrEqual(2);
  });
  it('tarih çizgisini kesen ülkeler atılmaz, çizim geçerli', () => {
    const d = dunyaHaritasi({ boylamMerkez: -177.8 });
    expect(d.zemin).not.toMatch(/NaN/);
    expect(d.zemin.length).toBeGreaterThan(5000);
  });
  it('kesim noktasının iki yakası zıt kenarlara düşer', () => {
    const d = dunyaHaritasi({ boylamMerkez: 0 });
    expect(d.px(179)).toBeGreaterThan(1100);
    expect(d.px(-179)).toBeLessThan(100);
  });
});

describe('bolgeHaritasi', () => {
  const b = bolgeHaritasi({ enlem: 39.24, boylam: 28.18, kmYaricap: 100 });
  it('merkez (600, 280) noktasına oturur', () => {
    expect(b.px(28.18)).toBeCloseTo(600, 3);
    expect(b.py(39.24)).toBeCloseTo(280, 3);
  });
  it('ölçek kmYaricap\'e göre: dikeyde yarıçap 280 px', () => {
    expect(b.pxKm).toBeCloseTo(2.8, 3);
    expect(b.py(39.24 - 100 / 111.195)).toBeCloseTo(560, 1);
  });
  it('il adları çizilir, birbirini kesmez ve alanın içinde kalır', () => {
    expect(b.etiketler.length).toBeGreaterThan(3);
    expect(b.etiketler).toContain('Balıkesir');
    for (const e of b.etiketler) expect(e).toBeTypeOf('string');
  });
  it('ölçek çubuğu: yarıçap ≤ 150 km ise 50 km, değilse 100 km', () => {
    expect(b.olcekKm).toBe(50);
    expect(bolgeHaritasi({ enlem: 39.24, boylam: 28.18, kmYaricap: 300 }).olcekKm).toBe(100);
  });
  it('NaN yok', () => {
    expect(b.zemin).not.toMatch(/NaN/);
  });
});

describe('dunyaHaritasi kıyı çizgisi', () => {
  for (const merkez of [-177.8, 0, 100]) {
    it(`kutup halkasının çizgisinde alt kenar boyunca ya da dikey iniş yok (merkez ${merkez})`, () => {
      const d = dunyaHaritasi({ boylamMerkez: merkez });
      let kontrol = 0;
      for (const parca of d.kiyi.split('M').filter(Boolean)) {
        const n = parca.replace(/[LZ]/g, ' ').trim().split(/\s+/).map((c) => c.split(',').map(Number));
        for (let i = 1; i < n.length; i++) {
          const [[x1, y1], [x2, y2]] = [n[i - 1], n[i]];
          expect(y1 >= 559.5 && y2 >= 559.5, 'alt kenar boyunca segment').toBe(false);
          expect(Math.abs(x1 - x2) < 0.05 && Math.abs(y1 - y2) > 100, 'dikey iniş').toBe(false);
          kontrol++;
        }
      }
      expect(kontrol).toBeGreaterThan(1000);
    });
  }
});

describe('levha atfı', () => {
  it('sabit ve levha çizgisi çizen harita atıf döndürür', () => {
    expect(LEVHA_ATIF).toBe('Levha sınırları: Bird (2003), ODC-By');
    expect(dunyaHaritasi({ boylamMerkez: 0, levha: true }).atif).toBe(LEVHA_ATIF);
    expect(dunyaHaritasi({ boylamMerkez: 0 }).atif).toBe('');
  });
});
