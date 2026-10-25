// Kart düzeni denetimi: altBant() yazıları sessizce kısaltır; bu yardımcı kısaltmayı/küçültmeyi uyarı olarak bildirir.
import { altBant, genislik, not } from './cekirdek.mjs';

const SINIRLAR = [['baslik', 46, 800], ['satir1', 28, 800], ['satir2', 28, 800], ['birim', 26, 284]];

/** Alt banttaki kısaltma/küçültme uyarıları (boş dizi = sorun yok). */
export function bantUyari(o) {
  const uyari = [];
  for (const [k, boy, en] of SINIRLAR) if (genislik(o[k], boy) > en) uyari.push(`${k} kısaltıldı: ${o[k]}`);
  if (genislik(o.sayi, 112) > 284) uyari.push(`sayı küçültüldü: ${o.sayi}`);
  return uyari;
}

export function notUyari(metin) {
  return genislik(metin, 18) > 1088 ? [`not kısaltıldı: ${metin}`] : [];
}

export { altBant, not };
