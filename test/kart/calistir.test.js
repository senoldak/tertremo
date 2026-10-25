import { describe, expect, it, vi } from 'vitest';
import { donemsel, olayKuyrugu } from '../../scripts/kart/calistir.mjs';

const PNG = Buffer.from([1, 2, 3]);
const ortam = { TERTREMO_KART_ANAHTARI: 'a' };

describe('olayKuyrugu', () => {
  const satir = (ek = {}) => ({ id: 'a:1:deprem', olay_id: 'a:1', turler: '["deprem"]', veri: '{}', metin: '<b>x</b>', ses: 1, ...ek });
  it('talep 0 ise gönderim yok', async () => {
    const t = { fotograf: vi.fn(), album: vi.fn() };
    const k = { gonderiyor: async () => true, bekleyenler: async () => [satir()], talep: async () => false, bitir: vi.fn(), birak: vi.fn() };
    const s = await olayKuyrugu({ env: ortam, k, t, cizicilar: { deprem: async () => PNG } });
    expect(t.fotograf).not.toHaveBeenCalled();
    expect(s).toEqual({ gonderilen: 0, atlanan: 1, hatali: 0 });
  });
  it('çizicisi olmayan türler atlanır, olanlar gönderilir; hiçbiri yoksa talep yok', async () => {
    const t = { fotograf: vi.fn(async () => ({ mesajId: 7 })), album: vi.fn() };
    const talep = vi.fn(async () => true);
    const k = { gonderiyor: async () => true, bekleyenler: async () => [satir({ turler: '["deprem","enerji"]' }), satir({ id: 'b', turler: '["enerji"]' })], talep, bitir: vi.fn(async () => {}), birak: vi.fn() };
    const s = await olayKuyrugu({ env: ortam, k, t, cizicilar: { deprem: async () => PNG }, gecikme: 0 });
    expect(t.fotograf).toHaveBeenCalledTimes(1);
    expect(t.album).not.toHaveBeenCalled();
    expect(talep).toHaveBeenCalledTimes(1);
    expect(s).toEqual({ gonderilen: 1, atlanan: 1, hatali: 0 });
  });
  it('tek tür fotoğraf, çok tür albüm; bitir olay_id ile', async () => {
    const t = { fotograf: vi.fn(async () => ({ mesajId: 5 })), album: vi.fn(async () => ({ mesajId: 6 })) };
    const k = { gonderiyor: async () => true, bekleyenler: async () => [satir(), satir({ id: 'b', turler: '["deprem","hissedildi"]' })], talep: async () => true, bitir: vi.fn(), birak: vi.fn() };
    const c = { deprem: async () => PNG, hissedildi: async () => PNG };
    const s = await olayKuyrugu({ env: ortam, k, t, cizicilar: c });
    expect(s.gonderilen).toBe(2);
    expect(t.fotograf.mock.calls[0][0]).toMatchObject({ sohbet: 'kanal', ses: true });
    expect(t.album.mock.calls[0][0].pngler).toHaveLength(2);
    expect(k.bitir).toHaveBeenCalledWith('a:1:deprem', 5, 'a:1');
  });
  it('çizici yoksa talep edilmez; çizim hatasında birak', async () => {
    const k = { gonderiyor: async () => true, bekleyenler: async () => [satir({ turler: '["yok"]' }), satir({ id: 'z' })], talep: vi.fn(async () => true), bitir: vi.fn(), birak: vi.fn(async () => 1) };
    const s = await olayKuyrugu({ env: ortam, k, t: {}, cizicilar: { deprem: async () => { throw new Error('çizim'); } } });
    expect(k.talep).toHaveBeenCalledTimes(1);
    expect(k.birak).toHaveBeenCalledWith('z');
    expect(s).toMatchObject({ atlanan: 1, hatali: 1 });
  });
});

describe('olayKuyrugu — kısmi çizim', () => {
  const satir = (ek = {}) => ({ id: 'a:1:deprem', olay_id: 'a:1', turler: '["deprem"]', veri: '{}', metin: '<b>x</b>', ses: 1, ...ek });
  it('bir çizici hata verirse o tür atlanır, kalanlar gider', async () => {
    const k = { gonderiyor: async () => true, bekleyenler: async () => [satir({ turler: '["deprem","kesit"]' })], talep: async () => true, bitir: vi.fn(async () => {}), birak: vi.fn() };
    const t = { fotograf: vi.fn(async () => ({ mesajId: 9 })), album: vi.fn() };
    const s = await olayKuyrugu({ env: ortam, k, t, cizicilar: { deprem: async () => PNG, kesit: async () => { throw new Error('az olay'); } }, gecikme: 0 });
    expect(s).toEqual({ gonderilen: 1, atlanan: 0, hatali: 0 });
    expect(t.fotograf).toHaveBeenCalledTimes(1);
    expect(t.album).not.toHaveBeenCalled();
    expect(k.birak).not.toHaveBeenCalled();
  });
  it('hepsi hata verirse birak', async () => {
    const k = { gonderiyor: async () => true, bekleyenler: async () => [satir({ turler: '["kesit"]' })], talep: async () => true, bitir: vi.fn(), birak: vi.fn(async () => 1) };
    const s = await olayKuyrugu({ env: ortam, k, t: {}, cizicilar: { kesit: async () => { throw new Error('x'); } } });
    expect(s.hatali).toBe(1);
    expect(k.birak).toHaveBeenCalled();
  });
});

describe('olayKuyrugu — gönderim sonrası', () => {
  const satir = { id: 'a:1:deprem', olay_id: 'a:1', turler: '["deprem"]', veri: '{}', metin: 'x', ses: 0 };
  it('gönderim tamam, bitir hep düşerse: yeniden gönderim yok, birak çağrılmaz, 3 deneme', async () => {
    const t = { fotograf: vi.fn(async () => ({ mesajId: 9 })), album: vi.fn() };
    const k = { gonderiyor: async () => true, bekleyenler: async () => [satir], talep: async () => true, bitir: vi.fn(async () => { throw new Error('d1'); }), birak: vi.fn() };
    const log = vi.spyOn(console, 'error').mockImplementation(() => {});
    const s = await olayKuyrugu({ env: ortam, k, t, cizicilar: { deprem: async () => PNG }, gecikme: 0 });
    expect(t.fotograf).toHaveBeenCalledTimes(1);
    expect(k.birak).not.toHaveBeenCalled();
    expect(k.bitir).toHaveBeenCalledTimes(3);
    expect(log.mock.calls.flat().join(' ')).toContain('9');
    expect(s.hatali).toBe(1);
    log.mockRestore();
  });
  it('talep hatası kartı atlar, döngü sürer', async () => {
    const k = { gonderiyor: async () => true, bekleyenler: async () => [satir, { ...satir, id: 'b' }], talep: vi.fn(async (id) => { if (id === 'b') return true; throw new Error('ağ'); }), bitir: vi.fn(), birak: vi.fn() };
    const t = { fotograf: vi.fn(async () => ({ mesajId: 1 })) };
    const log = vi.spyOn(console, 'error').mockImplementation(() => {});
    const s = await olayKuyrugu({ env: ortam, k, t, cizicilar: { deprem: async () => PNG } });
    expect(s).toMatchObject({ gonderilen: 1, hatali: 1 });
    log.mockRestore();
  });
});

describe('donemsel', () => {
  const uretici = (hedef) => async () => ({ png: PNG, aciklama: 'a', hedef });
  it('yayin kapalı (hedef ozel) → yalnız sahibin sohbeti, D1 dokunulmaz', async () => {
    const t = { fotograf: vi.fn(async () => ({ mesajId: 1 })) };
    const db = { sorgu: vi.fn() };
    const r = await donemsel('etas', { env: ortam, okuVeri: () => ({}), uretici: uretici('ozel'), t, db, k: {} });
    expect(t.fotograf.mock.calls[0][0].sohbet).toBe('ozel');
    expect(db.sorgu).not.toHaveBeenCalled();
    expect(r.hedef).toBe('ozel');
  });
  it('kanal hedefi → bugün bir kez (INSERT OR IGNORE changes 0 → atla)', async () => {
    const t = { fotograf: vi.fn(async () => ({ mesajId: 2 })) };
    const k = { gonderiyor: async () => true, bitir: vi.fn(), birak: vi.fn() };
    const ilk = await donemsel('etas', { env: ortam, okuVeri: () => ({}), uretici: uretici('kanal'), t, k, db: { sorgu: async () => ({ degisen: 1 }) } });
    expect(t.fotograf.mock.calls[0][0].sohbet).toBe('kanal');
    expect(k.bitir).toHaveBeenCalledWith(expect.stringMatching(/^donemsel:etas:\d{4}-\d\d-\d\d$/), 2, null);
    const ikinci = await donemsel('etas', { env: ortam, okuVeri: () => ({}), uretici: uretici('kanal'), t, k, db: { sorgu: async () => ({ degisen: 0 }) } });
    expect(ikinci.atlandi).toBe(true);
    expect(t.fotograf).toHaveBeenCalledTimes(1);
  });
  it('özel hedefte Worker kararını verir: env aktarıma geçer, TELEGRAM_SAHIP aranmaz', async () => {
    const t = { fotograf: vi.fn(async () => ({ mesajId: 1 })) };
    await donemsel('etas', { env: ortam, okuVeri: () => ({}), uretici: uretici('ozel'), t, db: {}, k: {} });
    expect(t.fotograf.mock.calls[0][0]).toMatchObject({ sohbet: 'ozel', env: ortam });
  });
  it('olay: aktarım belirsiz düşerse birak yoluna girer, yeniden gönderim denenmez', async () => {
    const t = { fotograf: vi.fn(async () => { throw new Error('kart aktarımı: bağlantı hatası'); }) };
    const k = { gonderiyor: async () => true, bekleyenler: async () => [{ id: 'q', olay_id: 'o', turler: '["deprem"]', veri: '{}', metin: '', ses: 0 }], talep: async () => true, bitir: vi.fn(), birak: vi.fn(async () => 1) };
    const log = vi.spyOn(console, 'error').mockImplementation(() => {});
    const s = await olayKuyrugu({ env: ortam, k, t, cizicilar: { deprem: async () => PNG } });
    expect(t.fotograf).toHaveBeenCalledTimes(1);
    expect(k.birak).toHaveBeenCalledWith('q');
    expect(s.hatali).toBe(1);
    log.mockRestore();
  });
  it('kanal gönderimi düşerse satır hata olur (bekliyor değil)', async () => {
    const t = { fotograf: vi.fn(async () => { throw new Error('tg'); }) };
    const k = { gonderiyor: async () => true, bitir: vi.fn(), birak: vi.fn(), hataYap: vi.fn(async () => {}) };
    await expect(donemsel('etas', { env: ortam, okuVeri: () => ({}), uretici: uretici('kanal'), t, k, db: { sorgu: async () => ({ degisen: 1 }) } })).rejects.toThrow('tg');
    expect(k.hataYap).toHaveBeenCalledWith(expect.stringMatching(/^donemsel:etas:/));
    expect(k.birak).not.toHaveBeenCalled();
  });
  it('aynı gün yeniden çalışma: hata satırı yeniden talep edilir ve gönderilir', async () => {
    const t = { fotograf: vi.fn(async () => ({ mesajId: 3 })) };
    const k = { gonderiyor: async () => true, bitir: vi.fn(), hataYap: vi.fn() };
    const sorgu = vi.fn()
      .mockResolvedValueOnce({ degisen: 0 })   // INSERT OR IGNORE: var
      .mockResolvedValueOnce({ degisen: 1 });  // UPDATE ... hata → cizimde
    const r = await donemsel('etas', { env: ortam, okuVeri: () => ({}), uretici: uretici('kanal'), t, k, db: { sorgu } });
    expect(sorgu.mock.calls[1][0]).toMatch(/durum='hata'/);
    expect(r.mesajId).toBe(3);
  });
  it('gönderim tamam, bitir düşerse 3 deneme, hataYap yok, çağıran hata alır (çıkış ≠ 0)', async () => {
    const t = { fotograf: vi.fn(async () => ({ mesajId: 4 })) };
    const k = { gonderiyor: async () => true, bitir: vi.fn(async () => { throw new Error('d1'); }), hataYap: vi.fn() };
    const log = vi.spyOn(console, 'error').mockImplementation(() => {});
    await expect(donemsel('etas', { env: ortam, okuVeri: () => ({}), uretici: uretici('kanal'), t, k, db: { sorgu: async () => ({ degisen: 1 }) }, gecikme: 0 })).rejects.toThrow(/kayıt düşmedi/);
    expect(k.bitir).toHaveBeenCalledTimes(3);
    expect(k.hataYap).not.toHaveBeenCalled();
    expect(t.fotograf).toHaveBeenCalledTimes(1);
    log.mockRestore();
  });
  it('gonderiyor 0 (Worker aldı) → gönderim yok', async () => {
    const t = { fotograf: vi.fn() };
    const k = { gonderiyor: async () => false, bitir: vi.fn(), hataYap: vi.fn() };
    const r = await donemsel('etas', { env: ortam, okuVeri: () => ({}), uretici: uretici('kanal'), t, k, db: { sorgu: async () => ({ degisen: 1 }) } });
    expect(r.atlandi).toBe(true);
    expect(t.fotograf).not.toHaveBeenCalled();
  });
});

describe('olayKuyrugu — gonderiliyor geçişi', () => {
  const satir = { id: 'a:1:deprem', olay_id: 'a:1', turler: '["deprem"]', veri: '{}', metin: 'x', ses: 0 };
  it('gonderiyor 0 → gönderim yok, birak yok', async () => {
    const t = { fotograf: vi.fn() };
    const k = { bekleyenler: async () => [satir], talep: async () => true, gonderiyor: async () => false, bitir: vi.fn(), birak: vi.fn() };
    const s = await olayKuyrugu({ env: ortam, k, t, cizicilar: { deprem: async () => PNG } });
    expect(t.fotograf).not.toHaveBeenCalled();
    expect(k.birak).not.toHaveBeenCalled();
    expect(s.atlanan).toBe(1);
  });
  it('gönderim hatası → birak; sıra: talep, gonderiyor, gönder', async () => {
    const sira = [];
    const t = { fotograf: vi.fn(async () => { sira.push('gonder'); throw new Error('tg'); }) };
    const k = { bekleyenler: async () => [satir], talep: async () => { sira.push('talep'); return true; }, gonderiyor: async () => { sira.push('gonderiyor'); return true; }, bitir: vi.fn(), birak: vi.fn(async () => 1) };
    const log = vi.spyOn(console, 'error').mockImplementation(() => {});
    await olayKuyrugu({ env: ortam, k, t, cizicilar: { deprem: async () => PNG } });
    expect(sira).toEqual(['talep', 'gonderiyor', 'gonder']);
    expect(k.birak).toHaveBeenCalledWith('a:1:deprem');
    log.mockRestore();
  });
});
