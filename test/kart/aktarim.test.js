import { afterEach, describe, expect, it, vi } from 'vitest';
import { album, fotograf, VARSAYILAN_ADRES } from '../../scripts/kart/aktarim.mjs';

afterEach(() => vi.unstubAllGlobals());
const PNG = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10, 1, 2, 3]);
const yanit = (govde, status = 200) => vi.fn(async () => new Response(JSON.stringify(govde), { status }));
const env = { TERTREMO_KART_ANAHTARI: 'GIZLI' };

describe('aktarım (Worker)', () => {
  it('fotograf: multipart + Authorization Bearer, varsayılan adres, {mesajId}', async () => {
    const f = yanit({ mesajId: 12 });
    vi.stubGlobal('fetch', f);
    const s = await fotograf({ env, sohbet: 'kanal', png: PNG, aciklama: '<b>x</b>', ses: true });
    expect(s).toEqual({ mesajId: 12 });
    const [url, init] = f.mock.calls[0];
    expect(url).toBe('https://vesaire.tidsrost.com/tertremo/kart');
    expect(VARSAYILAN_ADRES).toBe(url);
    expect(init.method).toBe('POST');
    expect(init.headers.authorization).toBe('Bearer GIZLI');
    expect(init.body).toBeInstanceOf(FormData);
    expect(init.body.get('hedef')).toBe('kanal');
    expect(init.body.get('aciklama')).toBe('<b>x</b>');
    expect(init.body.get('ses')).toBe('1');
    const dosyalar = init.body.getAll('png');
    expect(dosyalar).toHaveLength(1);
    expect(dosyalar[0].size).toBe(PNG.length);
    expect(init.signal).toBeInstanceOf(AbortSignal);
  });
  it('album: 2 png, hedef ozel, ses 0; KART_ADRES ile adres değişir', async () => {
    const f = yanit({ mesajId: 7 });
    vi.stubGlobal('fetch', f);
    const s = await album({ env: { ...env, KART_ADRES: 'https://x.test/k' }, sohbet: 'ozel', pngler: [PNG, PNG], aciklama: 'a', ses: false });
    expect(s).toEqual({ mesajId: 7 });
    expect(f.mock.calls[0][0]).toBe('https://x.test/k');
    expect(f.mock.calls[0][1].body.get('hedef')).toBe('ozel');
    expect(f.mock.calls[0][1].body.get('ses')).toBe('0');
    expect(f.mock.calls[0][1].body.getAll('png')).toHaveLength(2);
  });
  it('albüm 2–10 dışı reddedilir; geçersiz hedef reddedilir; istek atılmaz', async () => {
    const f = yanit({});
    vi.stubGlobal('fetch', f);
    await expect(album({ env, sohbet: 'kanal', pngler: [PNG] })).rejects.toThrow(/2.*10/);
    await expect(album({ env, sohbet: 'kanal', pngler: Array(11).fill(PNG) })).rejects.toThrow(/2.*10/);
    await expect(fotograf({ env, sohbet: '-100123', png: PNG })).rejects.toThrow(/hedef/);
    expect(f).not.toHaveBeenCalled();
  });
  it('anahtar yoksa istek atılmaz', async () => {
    const f = yanit({});
    vi.stubGlobal('fetch', f);
    await expect(fotograf({ env: {}, sohbet: 'kanal', png: PNG })).rejects.toThrow(/TERTREMO_KART_ANAHTARI/);
    expect(f).not.toHaveBeenCalled();
  });
  it('Worker 502 {hata} → fırlatır, anahtar iletide yok', async () => {
    vi.stubGlobal('fetch', yanit({ hata: 'Telegram sendPhoto 400: chat not found' }, 502));
    const e = await fotograf({ env, sohbet: 'kanal', png: PNG }).catch((x) => x);
    expect(e.message).toContain('chat not found');
    expect(e.message).not.toContain('GIZLI');
  });
  it('404 / ağ hatası / mesajId yok → fırlatır (belirsiz sonuç, yeniden deneme yok)', async () => {
    vi.stubGlobal('fetch', yanit(null, 404));
    await expect(fotograf({ env, sohbet: 'kanal', png: PNG })).rejects.toThrow(/404/);
    const f = vi.fn(async () => { throw new Error('GIZLI ağ'); });
    vi.stubGlobal('fetch', f);
    const e = await fotograf({ env, sohbet: 'kanal', png: PNG }).catch((x) => x);
    expect(e.message).toMatch(/bağlantı/);
    expect(e.message).not.toContain('GIZLI');
    expect(f).toHaveBeenCalledTimes(1);
    vi.stubGlobal('fetch', yanit({}));
    await expect(fotograf({ env, sohbet: 'kanal', png: PNG })).rejects.toThrow(/mesajId/);
  });
});

describe('sır yok', () => {
  it('scripts/kart ve iş akışında TELEGRAM_* kullanılmaz', async () => {
    const fs = await import('node:fs'), path = await import('node:path');
    const kok = path.resolve(import.meta.dirname, '../..');
    const dosyalar = [];
    const gez = (d) => { for (const e of fs.readdirSync(d, { withFileTypes: true })) { const p = path.join(d, e.name); e.isDirectory() ? gez(p) : dosyalar.push(p); } };
    gez(path.join(kok, 'scripts/kart'));
    dosyalar.push(path.join(kok, '.github/workflows/kart.yml'));
    for (const d of dosyalar) expect(fs.readFileSync(d, 'utf8'), d).not.toMatch(/TELEGRAM_(BOT_TOKEN|KANAL|SAHIP)|api\.telegram\.org/);
  });
});
