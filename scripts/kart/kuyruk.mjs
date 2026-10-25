// Kart kuyruğu (D1 `kart` tablosu). Durumlar: bekliyor → cizimde → gonderiliyor → gonderildi; Worker süre dolunca 'metin' yapar.
// Yarış koruması: yalnız `talep` 1 değişiklik döndüren taraf çizer ve gönderir.
import { sorgu, toplu } from './d1.mjs';

export const EN_COK_DENEME = 3;

/** Çizilmeyi bekleyen, süresi dolmamış kartlar (en eski önce, ≤ 10). */
export async function bekleyenler(simdi = Date.now()) {
  const { satirlar } = await sorgu(
    "SELECT id, olay_id, turler, veri, metin, ses, hedef, olusma, son, deneme FROM kart WHERE durum='bekliyor' AND son > ? ORDER BY olusma LIMIT 10",
    [simdi],
  );
  return satirlar;
}

/** true → kart artık bizim (bekliyor → cizimde). Worker 'metin' yaptıysa ya da başkası aldıysa false. */
export async function talep(id) {
  const { degisen } = await sorgu("UPDATE kart SET durum='cizimde' WHERE id=? AND durum='bekliyor'", [id], { tekrar: false });
  return degisen === 1;
}

/** Gönderimden hemen önce: cizimde → gonderiliyor. false → Worker kartı aldı (metin), gönderme. */
export async function gonderiyor(id) {
  const { degisen } = await sorgu("UPDATE kart SET durum='gonderiliyor' WHERE id=? AND durum='cizimde'", [id], { tekrar: false });
  return degisen === 1;
}

/** Gönderildi: kart satırı + (olay kartıysa) gonderim.mesaj_id aynı atomik toplu çağrıda. */
export async function bitir(id, mesajId, olayId = null) {
  const ifadeler = [["UPDATE kart SET durum='gonderildi', mesaj_id=? WHERE id=? AND durum='gonderiliyor'", [mesajId, id]]];
  if (olayId) ifadeler.push(["UPDATE gonderim SET mesaj_id=? WHERE olay_id=? AND hedef='kanal'", [mesajId, olayId]]);
  await toplu(ifadeler);
}

/** Hata: bekliyor'a dön, deneme+1; EN_COK_DENEME'ye varınca 'hata' (Worker metne düşürmez, elle bakılır). */
export async function birak(id) {
  const { satirlar } = await sorgu('SELECT deneme FROM kart WHERE id=?', [id]);
  const deneme = (satirlar[0]?.deneme ?? 0) + 1;
  await sorgu("UPDATE kart SET durum=?, deneme=? WHERE id=? AND durum IN ('cizimde','gonderiliyor')", [deneme >= EN_COK_DENEME ? 'hata' : 'bekliyor', deneme, id], { tekrar: false });
  return deneme;
}

/** Ürün henüz yok (etki): deneme sayılmadan bekliyor'a döner; Worker yeniden tetikler, süre (son) dolunca bırakır. */
export async function beklet(id) {
  await sorgu("UPDATE kart SET durum='bekliyor' WHERE id=? AND durum IN ('cizimde','gonderiliyor')", [id], { tekrar: false });
}

/** Dönemsel kart gönderimi düştü: 'hata' (aynı gün yeniden çalışma 'hata'yı yeniden talep eder). */
export async function hataYap(id) {
  await sorgu("UPDATE kart SET durum='hata' WHERE id=? AND durum IN ('cizimde','gonderiliyor')", [id]);
}
