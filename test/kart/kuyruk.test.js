import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { bekleyenler, beklet, bitir, birak, gonderiyor, hataYap, talep } from '../../scripts/kart/kuyruk.mjs';
import { sorgu, toplu } from '../../scripts/kart/d1.mjs';

// Sahte D1: tek tablo, ifade metnine bakan küçük yorumlayıcı. Her çağrı {sql, params} ya da {batch}.
function sahteD1(satirlar, gonderim = []) {
  const kayit = [];
  const yurut = ({ sql, params = [] }) => {
    kayit.push({ sql, params });
    const meta = { changes: 0 };
    let results = [];
    if (/^UPDATE kart SET durum='cizimde'/.test(sql)) {
      const r = satirlar.find((x) => x.id === params[0] && x.durum === 'bekliyor');
      if (r) { r.durum = 'cizimde'; meta.changes = 1; }
    } else if (/^UPDATE kart SET durum='gonderiliyor'/.test(sql)) {
      const r = satirlar.find((x) => x.id === params[0] && x.durum === 'cizimde');
      if (r) { r.durum = 'gonderiliyor'; meta.changes = 1; }
    } else if (/^UPDATE kart SET durum='gonderildi'/.test(sql)) {
      const r = satirlar.find((x) => x.id === params[1] && x.durum === 'gonderiliyor');
      if (r) { r.durum = 'gonderildi'; r.mesaj_id = params[0]; meta.changes = 1; }
    } else if (/^UPDATE gonderim/.test(sql)) {
      const g = gonderim.find((x) => x.olay_id === params[1] && x.hedef === 'kanal');
      if (g) { g.mesaj_id = params[0]; meta.changes = 1; }
    } else if (/^SELECT .* FROM kart WHERE durum='bekliyor'/.test(sql)) {
      results = satirlar.filter((x) => x.durum === 'bekliyor' && x.son > params[0]);
    } else if (/^SELECT deneme FROM kart/.test(sql)) {
      results = satirlar.filter((x) => x.id === params[0]).map((x) => ({ deneme: x.deneme }));
    } else if (/^UPDATE kart SET durum='hata'/.test(sql)) {
      const r = satirlar.find((x) => x.id === params[0] && ['cizimde', 'gonderiliyor'].includes(x.durum));
      if (r) { r.durum = 'hata'; meta.changes = 1; }
    } else if (/^UPDATE kart SET durum='bekliyor'/.test(sql)) {
      const r = satirlar.find((x) => x.id === params[0] && ['cizimde', 'gonderiliyor'].includes(x.durum));
      if (r) { r.durum = 'bekliyor'; meta.changes = 1; }
    } else if (/^UPDATE kart SET durum=\?/.test(sql)) {
      const r = satirlar.find((x) => x.id === params[2] && ['cizimde', 'gonderiliyor'].includes(x.durum));
      if (r) { r.durum = params[0]; r.deneme = params[1]; meta.changes = 1; }
    }
    return { success: true, results, meta };
  };
  const fetchSahte = vi.fn(async (url, init) => {
    const g = JSON.parse(init.body);
    const result = g.batch ? g.batch.map(yurut) : [yurut(g)];
    return new Response(JSON.stringify({ success: true, result }), { status: 200 });
  });
  return { fetchSahte, kayit };
}

beforeEach(() => {
  vi.stubEnv('CF_D1_TOKEN', 'gizli-token-123');
  vi.stubEnv('CF_HESAP', 'hesap1');
  vi.stubEnv('D1_ID', 'db1');
});
afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

const simdi = Date.now();
const satir = (ek = {}) => ({ id: 'afad:1:deprem', olay_id: 'afad:1', durum: 'bekliyor', olusma: simdi, son: simdi + 120000, deneme: 0, ...ek });

describe('talep', () => {
  it('iki talep yarışında yalnız biri 1 alır', async () => {
    const s = [satir()];
    vi.stubGlobal('fetch', sahteD1(s).fetchSahte);
    const [a, b] = await Promise.all([talep('afad:1:deprem'), talep('afad:1:deprem')]);
    expect([a, b].filter(Boolean)).toHaveLength(1);
    expect(s[0].durum).toBe('cizimde');
  });
  it('Worker metin yaptıktan sonra talep 0 → gönderim yok', async () => {
    const s = [satir({ durum: 'metin' })];
    vi.stubGlobal('fetch', sahteD1(s).fetchSahte);
    expect(await talep('afad:1:deprem')).toBe(false);
    expect(s[0].durum).toBe('metin');
  });
});

describe('talep — yeniden deneme güvenliği', () => {
  it('ağ hatasında otomatik yeniden denenmez (yanıt kaybolduysa çift talep olmasın)', async () => {
    const f = vi.fn(async () => { throw new Error('ağ'); });
    vi.stubGlobal('fetch', f);
    await expect(talep('x')).rejects.toThrow();
    expect(f).toHaveBeenCalledTimes(1);
  });
  it('5xx de yeniden denenmez; sorgu varsayılanı denenir', async () => {
    const f = vi.fn(async () => new Response('{}', { status: 503 }));
    vi.stubGlobal('fetch', f);
    await expect(talep('x')).rejects.toThrow(/503/);
    expect(f).toHaveBeenCalledTimes(1);
  });
});

describe('hataYap', () => {
  it('cizimde → hata', async () => {
    const s = [satir({ durum: 'cizimde' })];
    const { fetchSahte, kayit } = sahteD1(s);
    vi.stubGlobal('fetch', fetchSahte);
    await hataYap('afad:1:deprem');
    expect(kayit[0].sql).toMatch(/durum='hata'.*durum IN/);
  });
});

describe('bekleyenler', () => {
  it('yalnız bekliyor ve süresi dolmamış; LIMIT 10 ve zaman parametresi', async () => {
    const s = [satir(), satir({ id: 'b', son: simdi - 1 }), satir({ id: 'c', durum: 'metin' })];
    const { fetchSahte, kayit } = sahteD1(s);
    vi.stubGlobal('fetch', fetchSahte);
    const r = await bekleyenler(simdi);
    expect(r.map((x) => x.id)).toEqual(['afad:1:deprem']);
    expect(kayit[0].sql).toMatch(/LIMIT 10/);
    expect(kayit[0].params).toEqual([simdi]);
  });
});

describe('gonderiyor', () => {
  it('cizimde → gonderiliyor; Worker metin yaptıysa false', async () => {
    const s = [satir({ durum: 'cizimde' }), satir({ id: 'm', durum: 'metin' })];
    vi.stubGlobal('fetch', sahteD1(s).fetchSahte);
    expect(await gonderiyor('afad:1:deprem')).toBe(true);
    expect(s[0].durum).toBe('gonderiliyor');
    expect(await gonderiyor('m')).toBe(false);
  });
  it('bitir cizimde satırı değiştirmez (yalnız gonderiliyor → gonderildi)', async () => {
    const s = [satir({ durum: 'cizimde' })];
    vi.stubGlobal('fetch', sahteD1(s).fetchSahte);
    await bitir('afad:1:deprem', 1);
    expect(s[0].durum).toBe('cizimde');
  });
  it('birak gonderiliyor durumundan da bekliyor yapar', async () => {
    const s = [satir({ durum: 'gonderiliyor' })];
    vi.stubGlobal('fetch', sahteD1(s).fetchSahte);
    await birak('afad:1:deprem');
    expect(s[0]).toMatchObject({ durum: 'bekliyor', deneme: 1 });
  });
  it('beklet: cizimde/gonderiliyor → bekliyor, deneme artmaz', async () => {
    const s = [satir({ durum: 'cizimde', deneme: 1 }), satir({ id: 'b', durum: 'gonderildi' })];
    vi.stubGlobal('fetch', sahteD1(s).fetchSahte);
    await beklet('afad:1:deprem');
    await beklet('b');
    expect(s[0]).toMatchObject({ durum: 'bekliyor', deneme: 1 });
    expect(s[1].durum).toBe('gonderildi');
  });
  it('hataYap gonderiliyor durumundan da hata yapar', async () => {
    const s = [satir({ durum: 'gonderiliyor' })];
    vi.stubGlobal('fetch', sahteD1(s).fetchSahte);
    await hataYap('afad:1:deprem');
    expect(s[0].durum).toBe('hata');
  });
});

describe('bitir / birak', () => {
  it('bitir: kart gönderildi + gonderim.mesaj_id', async () => {
    const s = [satir({ durum: 'gonderiliyor' })];
    const g = [{ olay_id: 'afad:1', hedef: 'kanal', mesaj_id: null }];
    vi.stubGlobal('fetch', sahteD1(s, g).fetchSahte);
    await bitir('afad:1:deprem', 42, 'afad:1');
    expect(s[0]).toMatchObject({ durum: 'gonderildi', mesaj_id: 42 });
    expect(g[0].mesaj_id).toBe(42);
  });
  it('birak: bekliyor ve deneme+1; 3. başarısızlıkta hata', async () => {
    const s = [satir({ durum: 'cizimde' })];
    vi.stubGlobal('fetch', sahteD1(s).fetchSahte);
    await birak('afad:1:deprem');
    expect(s[0]).toMatchObject({ durum: 'bekliyor', deneme: 1 });
    s[0].deneme = 2; s[0].durum = 'cizimde';
    await birak('afad:1:deprem');
    expect(s[0]).toMatchObject({ durum: 'hata', deneme: 3 });
  });
});

describe('d1', () => {
  it('hata iletisinde token yok', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ success: false, errors: [{ message: 'kötü' }] }), { status: 400 })));
    const e = await sorgu('SELECT 1').catch((x) => x);
    expect(e.message).toContain('400');
    expect(e.message).not.toContain('gizli-token-123');
  });
  it('ağ hatasında da token yok; toplu batch gövdesi', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('boom gizli-token-123'); }));
    const e = await sorgu('SELECT 1').catch((x) => x);
    expect(e.message).not.toContain('gizli-token-123');
    const { fetchSahte } = sahteD1([]);
    vi.stubGlobal('fetch', fetchSahte);
    await toplu([['SELECT 1', []], ['SELECT 2', []]]);
    expect(JSON.parse(fetchSahte.mock.calls[0][1].body).batch).toHaveLength(2);
    expect(fetchSahte.mock.calls[0][1].headers.Authorization).toBe('Bearer gizli-token-123');
  });
});
