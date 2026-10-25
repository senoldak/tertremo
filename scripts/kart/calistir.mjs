// Kart çalıştırıcı.
//   node scripts/kart/calistir.mjs olay            → kuyruğu boşaltır (her 'bekliyor' kart: talep → çiz → gönder → bitir)
//   node scripts/kart/calistir.mjs donemsel <tur>  → dönemsel kart (etas, tarihteBugun, gunluk, haftalik, dunyaHafta, aylık kartlar)
// Ortam: TERTREMO_KART_ANAHTARI (+ isteğe bağlı KART_ADRES), CF_D1_TOKEN, CF_HESAP, D1_ID. Telegram gönderimini Worker yapar.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import * as d1 from './d1.mjs';
import * as kuyruk from './kuyruk.mjs';
import * as aktarim from './aktarim.mjs';

const KOK = fileURLToPath(new URL('../../', import.meta.url));
const KART_VERI = path.join(KOK, 'hesap', '.onbellek', 'kart-veri.json');

/**
 * Olay kartı çizicileri: tur → async (veri, satir) => png (Buffer). K4+ kartları buraya eklenir.
 * Çizicisi henüz olmayan türler atlanır, olanlar çizilir; hiçbiri yoksa satır talep edilmez (süre dolunca Worker metne düşürür).
 */
export const OLAY_CIZICILER = {
  async deprem(veri) { return (await import('./kartlar/deprem.mjs')).deprem(veri); },
  async hissedildi(veri) { return (await import('./kartlar/hissedildi.mjs')).hissedildi(veri); },
  async artci(veri) { return (await import('./kartlar/artci.mjs')).artci(veri); },
  async ozet(veri) { return (await import('./kartlar/ozet.mjs')).ozet(veri); },
  async kaynaklar(veri) { return (await import('./kartlar/kaynaklar.mjs')).kaynaklar(veri); },
  async enerji(veri, satir) { return (await import('./kartlar/enerji.mjs')).enerji(veri, satir); },
  async dunya(veri) { return (await import('./kartlar/dunya.mjs')).dunya(veri); },
  async levha(veri) { return (await import('./kartlar/levha.mjs')).levha(veri); },
  async gelisim(veri) { return (await import('./kartlar/gelisim.mjs')).gelisim(veri); },
  async kesit(veri) { return (await import('./kartlar/kesit.mjs')).kesit(veri); },
  async olagandisi(veri) { return (await import('./kartlar/olagandisi.mjs')).olagandisi(veri); },
  /** Etki (K17): {png, aciklama} döner; ShakeMap ürünü yoksa `urun-yok` hatası (satır bekletilir). */
  async etki(veri, satir) { return (await import('./kartlar/etki.mjs')).etki(veri, satir); },
};

/** Dönemsel kart üreticileri: tur → async (kartVeri) => {png, aciklama, hedef: 'kanal'|'ozel'}. */
export const DONEMSEL = {
  async etas(kartVeri) {
    const { etasHaftalik } = await import('./kartlar/etasHaftalik.mjs');
    return etasHaftalik(kartVeri);
  },
  /** Aylık Gutenberg–Richter (ayın 1'i); önceki ayın bloğu yoksa null. */
  async aylikGr(kartVeri, o) { return (await import('./kartlar/gr.mjs')).aylikGr(kartVeri, o); },
  /** Aylık b haritası (ayın 1'i); hücre yoksa null. */
  async aylikB(kartVeri, o) { return (await import('./kartlar/bharita.mjs')).aylikB(kartVeri, o); },
  /** Çeyreklik λ haritası (Oca/Nis/Tem/Eki 1'i); hücre yoksa null. */
  async ceyreklikLambda(kartVeri, o) { return (await import('./kartlar/lambdaharita.mjs')).ceyreklikLambda(kartVeri, o); },
  /** Aylık uzun dönem olasılık (Kart 19, ayın 1'i); veri yok / önbellek eskiyse null. */
  async uzunDonem(kartVeri, o) { return (await import('./kartlar/uzunDonem.mjs')).uzunDonem(kartVeri, o); },
  /** Tarihte bugün: kart-veri.json gerekmez; o gün kayıt yoksa null (hiçbir şey gönderilmez). */
  async tarihteBugun(kartVeri, o) {
    const { tarihteBugun } = await import('./kartlar/tarihteBugun.mjs');
    return tarihteBugun(kartVeri, o);
  },
  /** Günlük (21:00 TSİ): bugünün Türkiye Mw ≥ 3 depremleri; boş gün de kart olur. D1'den okur, kart-veri.json gerekmez. */
  async gunluk(kartVeri, o) { return (await import('./kartlar/gunluk.mjs')).gunluk(kartVeri, o); },
  /** Haftalık (Pzt 08:00 TSİ): geçen haftanın Türkiye özeti. */
  async haftalik(kartVeri, o) { return (await import('./kartlar/haftalik.mjs')).haftalik(kartVeri, o); },
  /** Dünya haftası (Paz 20:00 TSİ): son 7 günün dünya Mw ≥ 5 depremleri. */
  async dunyaHafta(kartVeri, o) { return (await import('./kartlar/dunyaHafta.mjs')).dunyaHafta(kartVeri, o); },
};

/** kart-veri.json'a bağlı olmayan dönemsel türler (veriyi D1'den ya da dosyadan kendileri okur). */
const VERISIZ = new Set(['tarihteBugun', 'gunluk', 'haftalik', 'dunyaHafta']);

const json = (s, varsayilan) => { try { return JSON.parse(s); } catch { return varsayilan; } };
const tsiTarih = (ms) => new Date(ms + 3 * 3600_000).toISOString().slice(0, 10);

const bekle = (ms) => new Promise((r) => setTimeout(r, ms));

/**
 * Gönderim BAŞARILI olduktan sonra kayıt: 3 deneme (artan bekleme). Başarısızsa mesaj_id günlüğe yazılır,
 * satır 'cizimde' kalır ve ASLA yeniden gönderilmez (Worker tarafı takılı 'cizimde'yi yönetir). → true/false
 */
async function kaydet(k, id, mesajId, olayId, gecikme) {
  for (let i = 0; i < 3; i++) {
    try { await k.bitir(id, mesajId, olayId); return true; } catch (e) {
      if (i < 2) await bekle(gecikme * 2 ** i); else console.error(`kart ${id}: gönderildi (mesaj_id=${mesajId}) ama kayıt düşmedi: ${e.message}`);
    }
  }
  return false;
}

/** Kuyruktaki olay kartlarını gönderir → {gonderilen, atlanan, hatali}. */
export async function olayKuyrugu({ env = process.env, k = kuyruk, t = aktarim, cizicilar = OLAY_CIZICILER, simdi = Date.now(), gecikme = 500 } = {}) {
  const sonuc = { gonderilen: 0, atlanan: 0, hatali: 0 };
  for (const satir of await k.bekleyenler(simdi)) {
    const turler = json(satir.turler, []).filter((tur) => cizicilar[tur]);
    if (!turler.length) { sonuc.atlanan++; continue; }
    try {
      if (!(await k.talep(satir.id))) { sonuc.atlanan++; continue; }   // Worker metin yaptı ya da başkası aldı
    } catch (e) {                                                       // yanıt kaybolmuş olabilir: yeniden deneme yok
      console.error(`kart ${satir.id}: talep düştü: ${e.message}`);
      sonuc.hatali++;
      continue;
    }
    let r;
    try {
      const veri = json(satir.veri, {});
      const pngler = [];
      let aciklama = satir.metin ?? '';
      const hatalar = [];
      for (const tur of turler) {
        try {
          const c = await cizicilar[tur](veri, satir);
          // Çizici Buffer ya da {png, aciklama} döner; açıklamayı yalnız albümün ilk kartı değiştirebilir.
          if (c?.png) { if (c.aciklama && !pngler.length) aciklama = c.aciklama; pngler.push(c.png); } else pngler.push(c);
        } catch (e) { hatalar.push(e); console.error(`kart ${satir.id}: ${tur} çizilemedi, atlandı: ${e.message}`); }
      }
      if (!pngler.length) {
        // Hepsi "ürün henüz yok" ise (etki): deneme sayılmadan beklet, hata değil.
        if (hatalar.length && hatalar.every((e) => e?.kod === 'urun-yok')) throw Object.assign(new Error(hatalar[0].message), { beklet: true });
        throw new Error('hiçbir kart çizilemedi');
      }
      const girdi = { env, sohbet: 'kanal', aciklama, ses: !!satir.ses };
      if (!(await k.gonderiyor(satir.id))) { sonuc.atlanan++; continue; }   // Worker son anda aldı
      r = pngler.length === 1 ? await t.fotograf({ ...girdi, png: pngler[0] }) : await t.album({ ...girdi, pngler });
    } catch (e) {                                                       // yalnız çizim/gönderim hatası bırakılır
      console.error(`kart ${satir.id}: ${e.message}`);
      if (e.beklet) { await k.beklet(satir.id).catch(() => {}); sonuc.atlanan++; continue; }
      await k.birak(satir.id).catch(() => {});
      sonuc.hatali++;
      continue;
    }
    if (await kaydet(k, satir.id, r.mesajId, satir.olay_id, gecikme)) sonuc.gonderilen++; else sonuc.hatali++;
  }
  return sonuc;
}

/** Dönemsel kart: üret → hedef kanalsa kuyruğa kayıtlı (günde bir; düşen gönderim 'hata' olur, aynı gün yeniden talep edilir), özelse sahibe. */
export async function donemsel(tur, { env = process.env, okuVeri = () => JSON.parse(fs.readFileSync(KART_VERI, 'utf8')), uretici = DONEMSEL[tur], k = kuyruk, t = aktarim, db = d1, simdi = Date.now(), gecikme = 500 } = {}) {
  if (!uretici) throw new Error(`bilinmeyen dönemsel tür: ${tur}`);
  let kartVeri;
  try { kartVeri = okuVeri(); } catch (e) { if (!VERISIZ.has(tur)) throw e; kartVeri = {}; }   // bu türler kart-veri.json'a bağlı değil
  const kart = await uretici(kartVeri, { simdi, db });
  if (!kart) return { hedef: 'kanal', atlandi: true, kayitYok: true };   // o gün için içerik yok: sessizce çık, D1 satırı açma
  const girdi = { env, aciklama: kart.aciklama, ses: false, png: kart.png };
  if (kart.hedef !== 'kanal') {
    const r = await t.fotograf({ ...girdi, sohbet: 'ozel' });
    return { hedef: 'ozel', mesajId: r.mesajId };
  }
  const id = `donemsel:${tur}:${tsiTarih(simdi)}`;
  const ekle = await db.sorgu(
    "INSERT OR IGNORE INTO kart (id, olay_id, turler, veri, metin, ses, hedef, durum, olusma, son, deneme) VALUES (?, NULL, ?, '{}', ?, 0, 'kanal', 'cizimde', ?, ?, 0)",
    [id, JSON.stringify([tur]), kart.aciklama, simdi, simdi + 120_000], { tekrar: false },
  );
  if (ekle.degisen !== 1) {
    // Bugünkü satır var: yalnız önceki deneme düştüyse ('hata') yeniden talep et; gönderilmişse atla.
    const yeniden = await db.sorgu("UPDATE kart SET durum='cizimde', deneme=deneme+1 WHERE id=? AND durum='hata'", [id], { tekrar: false });
    if (yeniden.degisen !== 1) return { hedef: 'kanal', atlandi: true };
  }
  let r;
  try {
    if (!(await k.gonderiyor(id))) return { hedef: 'kanal', atlandi: true };
    r = await t.fotograf({ ...girdi, sohbet: 'kanal' });
  } catch (e) {
    await k.hataYap(id).catch(() => {});
    throw e;
  }
  if (!(await kaydet(k, id, r.mesajId, null, gecikme))) throw new Error(`dönemsel kart gönderildi (mesaj_id=${r.mesajId}) ama kayıt düşmedi`);
  return { hedef: 'kanal', mesajId: r.mesajId };
}

async function ana([mod, tur]) {
  const t0 = Date.now();
  let cikis = 0;
  if (mod === 'olay') {
    const s = await olayKuyrugu();
    console.log(JSON.stringify(s));
    if (s.hatali) cikis = 1;
  } else if (mod === 'donemsel' && tur) {
    console.log(JSON.stringify(await donemsel(tur)));
  } else {
    console.error('Kullanım: calistir.mjs olay | calistir.mjs donemsel <tur>');
    return 2;
  }
  console.log(`süre: ${((Date.now() - t0) / 1000).toFixed(1)} sn`);
  return cikis;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  ana(process.argv.slice(2)).then((c) => process.exit(c), (e) => { console.error(e.message); process.exit(1); });
}
