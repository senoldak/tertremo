// Kart 21: Etki (USGS ShakeMap MMI konturları + DYFI). Örnek ürünler: Kahramanmaraş 2023 (us6000jllz), USGS kamu malı.
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it, vi } from 'vitest';
import sharp from 'sharp';
import { aciklamaYap, etki, etkiSvg, urunCek, UrunYok } from '../../scripts/kart/kartlar/etki.mjs';
import { OLAY_CIZICILER, olayKuyrugu } from '../../scripts/kart/calistir.mjs';

const FX = JSON.parse(fs.readFileSync(fileURLToPath(new URL('./veri/etki-us6000jllz.json', import.meta.url)), 'utf8'));
const OLAY_URL = 'https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=us6000jllz&format=geojson';
const KONTUR_URL = FX.olay.properties.products.shakemap[0].contents['download/cont_mmi.json'].url;
const RUPTURE_URL = FX.olay.properties.products.shakemap[0].contents['download/rupture.json'].url;

const olay = (ek = {}) => ({
  id: 'us6000jllz', zaman: Date.UTC(2023, 1, 6, 1, 17, 34), enlem: 37.2256, boylam: 37.0143, derinlik: 10, mw: 7.8, tur: 'Mww',
  kaynak: 'afad', bolge: 'turkiye', baslik: 'Kahramanmaraş / Pazarcık', kaynaklar: { usgs: { id: 'us6000jllz', buyukluk: 7.8, tur: 'Mww' } }, ...ek,
});

/** Sahte USGS: değiştirme ile ürünler çıkarılabilir. */
function sahte({ olayGovde = FX.olay, kontur = FX.kontur, rupture = FX.rupture, durum = {} } = {}) {
  const istekler = [];
  const fn = async (url, init) => {
    istekler.push({ url: String(url), sinyal: init?.signal });
    const d = durum[String(url)];
    if (d === 'ag') throw new Error('ağ');
    if (typeof d === 'number') return new Response('yok', { status: d });
    if (String(url) === OLAY_URL) return Response.json(olayGovde);
    if (String(url) === KONTUR_URL) return Response.json(kontur);
    if (String(url) === RUPTURE_URL) return Response.json(rupture);
    return new Response('?', { status: 404 });
  };
  fn.istekler = istekler;
  return fn;
}

const ISTENEN = { sayi: '9,5', birim: 'en yüksek şiddet MMI' };

describe('urunCek', () => {
  it('olay → cont_mmi.json (+ rupture, DYFI sayısı, en yüksek MMI), 15 sn zaman aşımı', async () => {
    const f = sahte();
    const u = await urunCek('us6000jllz', { fetchFn: f });
    expect(f.istekler.map((i) => i.url)).toEqual([OLAY_URL, KONTUR_URL, RUPTURE_URL]);
    expect(f.istekler.every((i) => i.sinyal)).toBe(true);
    expect(u.maxMmi).toBeCloseTo(9.537, 3);
    expect(u.dyfi).toBe(3182);
    expect(u.konturlar.map((k) => k.deger)).toEqual([4, 4.5, 5, 5.5, 6, 6.5, 7, 7.5, 8, 8.5, 9]);
    expect(u.konturlar[0].cizgiler.length).toBeGreaterThan(0);
    expect(u.konturlar[0].cizgiler[0][0]).toHaveLength(2);
    expect(u.rupture.length).toBeGreaterThan(0);
  });
  it('DYFI ve rupture isteğe bağlı: yoksa null, kart yine çizilir', async () => {
    const govde = structuredClone(FX.olay);
    delete govde.properties.products.dyfi;
    const u = await urunCek('us6000jllz', { fetchFn: sahte({ olayGovde: govde, durum: { [RUPTURE_URL]: 404 } }) });
    expect(u.dyfi).toBeNull();
    expect(u.rupture).toBeNull();
    expect(u.konturlar.length).toBe(11);
  });
  it('en yüksek MMI properties.maxmmi yoksa konturların en büyüğü', async () => {
    const govde = structuredClone(FX.olay);
    delete govde.properties.products.shakemap[0].properties.maxmmi;
    expect((await urunCek('us6000jllz', { fetchFn: sahte({ olayGovde: govde }) })).maxMmi).toBe(9);
  });
  it.each([
    ['ShakeMap ürünü yok', () => { const g = structuredClone(FX.olay); delete g.properties.products.shakemap; return { olayGovde: g }; }],
    ['olay bulunamadı (404)', () => ({ durum: { [OLAY_URL]: 404 } })],
    ['olay ağ hatası', () => ({ durum: { [OLAY_URL]: 'ag' } })],
    ['kontur indirilemedi', () => ({ durum: { [KONTUR_URL]: 500 } })],
    ['kontur boş', () => ({ kontur: { type: 'FeatureCollection', features: [] } })],
  ])('%s → urun-yok hatası', async (_, kur) => {
    const hata = await urunCek('us6000jllz', { fetchFn: sahte(kur()) }).catch((e) => e);
    expect(hata).toBeInstanceOf(UrunYok);
    expect(hata.kod).toBe('urun-yok');
    expect(hata.message).toMatch(/^urun-yok/);
  });
});

describe('etki kartı', () => {
  const urun = () => urunCek('us6000jllz', { fetchFn: sahte() });

  it('büyük sayı en yüksek MMI (9,5), birim (MMI); satır 1 DYFI sayısı; not USGS atfı; düzen uyarısı yok', async () => {
    const r = etkiSvg({ olay: olay() }, await urun());
    expect(r.bant.sayi).toBe(ISTENEN.sayi);
    expect(r.bant.birim).toBe(ISTENEN.birim);
    expect(r.bant.satir1).toBe('Did You Feel It? 3.182 bildirim');
    expect(r.bant.baslik).toBe('Kahramanmaraş / Pazarcık · Mw 7,8'); // 46 px'te 800'e sığan en uzun aday
    expect(etkiSvg({ olay: olay({ baslik: 'Sındırgı' }) }, await urun()).bant.baslik).toBe('Sındırgı · Mw 7,8 · sarsıntı haritası');
    expect(r.bant.satir2).toBe('6 Şubat 2023 · 04:17 TSİ');
    expect(r.notMetni).toBe('Kaynak: USGS ShakeMap / DYFI (kamu malı); ilk sürümler güncellenir.');
    expect(r.uyari).toEqual([]);
    expect(r.etiketler.length).toBeGreaterThanOrEqual(4);
  });
  it('PAGER, kayıp, ekonomik tahmin, "tehlike", "uyarı" hiçbir yazıda yok', async () => {
    const r = etkiSvg({ olay: olay({ pager: 'red' }) }, await urun());
    const hepsi = `${Object.values(r.bant).join(' ')} ${r.notMetni} ${aciklamaYap({ olay: olay() }, null, 3182)}`.toLowerCase();
    expect(hepsi).not.toMatch(/pager|kayıp|ekonomik|tehlike|uyarı|alarm/);
    expect(r.svg).not.toContain('#ff0000');
  });
  it('1200×800 PNG: Türkiye (il adlı) ve dünya haritası, yaklaşık şiddetle', async () => {
    const tr = await sharp(await etki({ olay: olay() }, null, { fetchFn: sahte() }).then((x) => x.png)).metadata();
    expect([tr.width, tr.height]).toEqual([1200, 800]);
    const dunya = olay({ bolge: 'dunya', enlem: 38.3, boylam: 142.4, baslik: 'Honşu açıkları, Japonya', mw: 7.1, tur: 'Mww' });
    const u = await urun();
    u.konturlar = [5, 6, 7].map((deger, i) => ({ deger, cizgiler: [Array.from({ length: 61 }, (_, k) => [142.4 + Math.cos(k / 9.5) * (1.6 - i * 0.5), 38.3 + Math.sin(k / 9.5) * (1.2 - i * 0.4)])] }));
    u.rupture = null;
    expect(etkiSvg({ olay: dunya }, u).uyari).toEqual([]);
  });
  it('merkez üssü tarih çizgisinde (±180°): çizilir, çökmez', async () => {
    const o = olay({ bolge: 'dunya', enlem: -17, boylam: 179.9, baslik: 'Fiji', mw: 7.2 });
    const u = await urun();
    u.konturlar = [{ deger: 6, cizgiler: [Array.from({ length: 40 }, (_, k) => [179.9 + Math.cos(k / 6) * 1.5 > 180 ? 179.9 + Math.cos(k / 6) * 1.5 - 360 : 179.9 + Math.cos(k / 6) * 1.5, -17 + Math.sin(k / 6)])] }];
    const png = await sharp((await etki({ olay: o }, null, { urun: u })).png).metadata();
    expect(png.width).toBe(1200);
  });
  it('uzun yer adı ve çok uzun başlık: bant taşmaz, uyarı yok (başlık kısaltılır)', async () => {
    const r = etkiSvg({ olay: olay({ baslik: 'Çok Uzun Bir Yer Adı '.repeat(8).trim() }) }, await urun());
    expect(r.uyari).toEqual([]);
    expect(r.bant.baslik.length).toBeLessThan(130);
  });
  it('DYFI yoksa satır 1 ShakeMap açıklaması; yalnız bir kontur bile çizilir', async () => {
    const u = await urun();
    u.dyfi = null;
    u.konturlar = u.konturlar.slice(0, 1);
    u.maxMmi = 4.2;
    const r = etkiSvg({ olay: olay() }, u);
    expect(r.bant.sayi).toBe('4,2');
    expect(r.bant.satir1).not.toMatch(/Did You Feel It/);
    expect(r.uyari).toEqual([]);
  });
  it('açıklama: Worker başlığı + USGS ShakeMap · DYFI sayısı (binlik noktalı); sayı yoksa yalnız ShakeMap', () => {
    const satir = { metin: '🗺 <b>Mw 7,8 · Kahramanmaraş / Pazarcık · sarsıntı haritası</b>\nUSGS ShakeMap' };
    expect(aciklamaYap({ olay: olay() }, satir, 3182)).toBe('🗺 <b>Mw 7,8 · Kahramanmaraş / Pazarcık · sarsıntı haritası</b>\nUSGS ShakeMap · Did You Feel It? 3.182 bildirim');
    expect(aciklamaYap({ olay: olay() }, satir, null)).toBe(satir.metin);
    expect(aciklamaYap({ olay: olay({ baslik: 'A<B' }) }, null, 5)).toBe('🗺 <b>Mw 7,8 · A&lt;B · sarsıntı haritası</b>\nUSGS ShakeMap · Did You Feel It? 5 bildirim');
  });
  it('çizici {png, aciklama} döner; OLAY_CIZICILER.etki kayıtlı', async () => {
    const r = await etki({ olay: olay() }, { metin: 'x\ny' }, { fetchFn: sahte() });
    expect(Buffer.isBuffer(r.png)).toBe(true);
    expect(r.aciklama).toBe('x\nUSGS ShakeMap · Did You Feel It? 3.182 bildirim');
    expect(typeof OLAY_CIZICILER.etki).toBe('function');
  });
  it('USGS kimliği yok: urun-yok değil, açık hata', async () => {
    const hata = await etki({ olay: olay({ kaynaklar: {} }) }, null, { fetchFn: sahte() }).catch((e) => e);
    expect(hata.message).toMatch(/usgs/i);
    expect(hata.kod).toBeUndefined();
  });
});

describe('calistir: etki satırı', () => {
  const satir = { id: 'etki:x', olay_id: 'etki:x', turler: '["etki"]', veri: JSON.stringify({ olay: olay() }), metin: 'b\nUSGS ShakeMap', ses: 0, hedef: 'kanal', olusma: 1, son: 9e15, deneme: 0 };
  const kur = () => {
    const olaylar = [];
    const k = {
      bekleyenler: async () => [satir], talep: async () => true, gonderiyor: async () => true,
      bitir: async (...a) => olaylar.push(['bitir', ...a]), birak: vi.fn(async () => 1), beklet: vi.fn(async () => {}),
    };
    const t = { fotograf: vi.fn(async () => ({ mesajId: 7 })), album: vi.fn() };
    return { k, t, olaylar };
  };

  it('ürün yok: satır DENEME ARTIRMADAN bekletilir (birak yok), hatalı sayılmaz, gönderim yok', async () => {
    const { k, t } = kur();
    const cizicilar = { etki: async () => { throw new UrunYok('shakemap yok'); } };
    const s = await olayKuyrugu({ env: {}, k, t, cizicilar, gecikme: 0 });
    expect(k.beklet).toHaveBeenCalledWith('etki:x');
    expect(k.birak).not.toHaveBeenCalled();
    expect(t.fotograf).not.toHaveBeenCalled();
    expect(s.hatali).toBe(0);
  });
  it('başka çizim hatası: eskisi gibi birak (deneme artar)', async () => {
    const { k, t } = kur();
    const s = await olayKuyrugu({ env: {}, k, t, cizicilar: { etki: async () => { throw new Error('bozuk'); } }, gecikme: 0 });
    expect(k.birak).toHaveBeenCalledWith('etki:x');
    expect(k.beklet).not.toHaveBeenCalled();
    expect(s.hatali).toBe(1);
  });
  it('çizici {png, aciklama} verince açıklama satırınkinin yerine geçer ve gonderim kimliği bitir ile yazılır', async () => {
    const { k, t, olaylar } = kur();
    const cizicilar = { etki: async () => ({ png: Buffer.from('p'), aciklama: 'YENİ' }) };
    const s = await olayKuyrugu({ env: {}, k, t, cizicilar, gecikme: 0 });
    expect(t.fotograf.mock.calls[0][0]).toMatchObject({ aciklama: 'YENİ', sohbet: 'kanal' });
    expect(olaylar[0]).toEqual(['bitir', 'etki:x', 7, 'etki:x']);
    expect(s.gonderilen).toBe(1);
  });
});
