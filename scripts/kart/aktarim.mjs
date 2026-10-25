// Kart aktarımı: PNG'ler Telegram'a doğrudan DEĞİL, Worker'a gider (bot token'ı GitHub'da yok).
//   POST KART_ADRES  (multipart: hedef 'kanal'|'ozel', aciklama, ses '0'|'1', 1–10 png)  Authorization: Bearer TERTREMO_KART_ANAHTARI
// Ortam: KART_ADRES (varsayılan aşağıda), TERTREMO_KART_ANAHTARI.
// Belirsiz sonuç (ağ hatası, zaman aşımı, 5xx) fırlatır; yeniden DENEME YOK (çift gönderim olmasın) —
// çağıran mevcut birak / hataYap yoluna girer.
export const VARSAYILAN_ADRES = 'https://vesaire.tidsrost.com/tertremo/kart';
const HEDEFLER = new Set(['kanal', 'ozel']);

async function gonder({ env = process.env, sohbet, pngler, aciklama = '', ses = false }) {
  if (!HEDEFLER.has(sohbet)) throw new Error(`kart hedefi 'kanal' ya da 'ozel' olmalı: ${sohbet}`);
  const anahtar = env.TERTREMO_KART_ANAHTARI;
  if (!anahtar) throw new Error('TERTREMO_KART_ANAHTARI yok');
  const f = new FormData();
  f.set('hedef', sohbet);
  f.set('aciklama', aciklama);
  f.set('ses', ses ? '1' : '0');
  pngler.forEach((png, i) => f.append('png', new Blob([png], { type: 'image/png' }), `kart${i}.png`));
  let y;
  try {
    y = await fetch(env.KART_ADRES || VARSAYILAN_ADRES, {
      method: 'POST',
      headers: { authorization: `Bearer ${anahtar}` },
      body: f,
      signal: AbortSignal.timeout(45_000),
    });
  } catch {
    throw new Error('kart aktarımı: bağlantı hatası');
  }
  let j = null;
  try { j = await y.json(); } catch { /* gövde yok */ }
  if (!y.ok) throw new Error(`kart aktarımı ${y.status}: ${j?.hata ?? 'yanıt çözülemedi'}`);
  if (j?.mesajId == null) throw new Error('kart aktarımı: yanıtta mesajId yok');
  return { mesajId: j.mesajId };
}

/** Tek kart → {mesajId}. */
export const fotograf = ({ png, ...g }) => gonder({ ...g, pngler: [png] });

/** Albüm (2–10 kart); açıklama yalnız ilk öğede → {mesajId (ilk)}. */
export function album({ pngler, ...g }) {
  if (pngler.length < 2 || pngler.length > 10) return Promise.reject(new Error('albüm 2–10 görsel olmalı'));
  return gonder({ ...g, pngler });
}
