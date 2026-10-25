// Cloudflare D1 REST istemcisi (Node). Sırlar yalnız ortamdan: CF_D1_TOKEN, CF_HESAP, D1_ID.
// Hata iletilerinde token yok: yalnız durum kodu ve Cloudflare'in hata iletisi.
const PARCA = 100;
const DENEME = 3;
const bekle = (ms) => new Promise((r) => setTimeout(r, ms));

export class D1Hatasi extends Error {}

export const hazir = () => ['CF_D1_TOKEN', 'CF_HESAP', 'D1_ID'].every((k) => process.env[k]);

function ileti(j) {
  const e = (j?.errors ?? []).map((x) => String(x?.message ?? '')).filter(Boolean).join('; ');
  return e || 'bilinmeyen hata';
}

/** tekrar=false: eşsiz olmayan (yan etkili) ifade; ağ hatası/5xx'te yeniden denenmez (yanıt kaybolmuş olabilir). 429 reddedilmiştir, yine denenir. */
async function istek(govde, tekrar = true) {
  const adres = `https://api.cloudflare.com/client/v4/accounts/${process.env.CF_HESAP}/d1/database/${process.env.D1_ID}/query`;
  for (let deneme = 0; deneme < DENEME; deneme++) {
    let y;
    try {
      y = await fetch(adres, {
        method: 'POST',
        headers: { Authorization: `Bearer ${process.env.CF_D1_TOKEN}`, 'Content-Type': 'application/json', 'User-Agent': 'tertremo-kart' },
        body: JSON.stringify(govde),
        signal: AbortSignal.timeout(15_000),
      });
    } catch {
      if (tekrar && deneme < DENEME - 1) { await bekle(2 ** (deneme + 1) * 500); continue; }
      throw new D1Hatasi('D1 bağlantı hatası');
    }
    let j = null;
    try { j = await y.json(); } catch { /* yanıt çözülemedi */ }
    if (!y.ok) {
      if (([429].includes(y.status) || (tekrar && [500, 502, 503, 504].includes(y.status))) && deneme < DENEME - 1) { await bekle(2 ** (deneme + 1) * 500); continue; }
      throw new D1Hatasi(`D1 HTTP ${y.status}: ${j ? ileti(j) : 'yanıt çözülemedi'}`);
    }
    if (!j?.success) throw new D1Hatasi(`D1 hata: ${j ? ileti(j) : 'yanıt çözülemedi'}`);
    return j.result ?? [];
  }
  throw new D1Hatasi('D1: deneme bitti');
}

const sonucaCevir = (r) => ({ satirlar: r?.results ?? [], degisen: r?.meta?.changes ?? 0 });

/** Tek ifade (tekrar:false → yan etkili, otomatik yeniden deneme yok) → {satirlar, degisen}. */
export async function sorgu(sql, params = [], { tekrar = true } = {}) {
  const s = await istek({ sql, params }, tekrar);
  return sonucaCevir(s[0]);
}

/** [[sql, params], ...] → her ifade için {satirlar, degisen}; 100'lük batch çağrıları. */
export async function toplu(ifadeler) {
  const sonuc = [];
  for (let i = 0; i < ifadeler.length; i += PARCA) {
    const s = await istek({ batch: ifadeler.slice(i, i + PARCA).map(([sql, params = []]) => ({ sql, params })) });
    sonuc.push(...s.map(sonucaCevir));
  }
  return sonuc;
}
