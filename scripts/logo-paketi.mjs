// tertremo logo paketi (brand/logo/): yazı logosu, ikon ve favicon; açık ve koyu zemin; SVG (yazı glif yolu,
// yazı tipi gerekmez) ve PNG. Logo: Manrope Bold "tertremo", son o yerine indigo odak halkası. İkon: o halka.
// Kullanım: npm run logo
import fs from 'node:fs';
import sharp from 'sharp';
import { halka, logoYazisi, RENK, svg, YAZI } from './kimlik.mjs';

const KLASOR = 'brand/logo';
const EM = YAZI.unitsPerEm;

function logo(koyu) {
  const boy = 200;
  const bosluk = boy * 0.3;
  const ust = (YAZI.charToGlyph('t').getBoundingBox().y2 / EM) * boy; // en uzun harf t
  const yukseklik = ust + bosluk * 2;
  const { ic, genislik } = logoYazisi(bosluk, bosluk + ust, boy, koyu ? RENK.kagit : RENK.murekkep, koyu ? RENK.indigoKoyu : RENK.indigo);
  return svg(genislik + bosluk * 2, yukseklik, ic);
}

// İkon: kare zemin, ortada halka. Telegram daireye kırpar: halka kenarın %56'sı, dairenin içinde rahat kalır.
function ikon(zemin, cizgi, kenar = 640) {
  const r = kenar * 0.28;
  return svg(kenar, kenar, halka(kenar / 2, kenar / 2, r, r * 0.3, cizgi), zemin);
}

// Favicon: küçük boyda halka daha kalın okunsun diye kalınlık oranı ikondakinden yüksek.
function favicon(renk, kenar = 64) {
  const r = kenar * 0.44;
  return svg(kenar, kenar, halka(kenar / 2, kenar / 2, r, r * 0.36, renk));
}

fs.mkdirSync(KLASOR, { recursive: true });
const dosyalar = {
  'tertremo-logo': [logo(false), 1600],
  'tertremo-logo-koyu-zemin': [logo(true), 1600],
  'tertremo-ikon': [ikon(RENK.indigo, '#ffffff'), 640],
  'tertremo-ikon-kagit': [ikon(RENK.kagit, RENK.indigo), 640],
  'tertremo-favicon': [favicon(RENK.indigo), 64],
};
for (const [ad, [icerik, g]] of Object.entries(dosyalar)) {
  fs.writeFileSync(`${KLASOR}/${ad}.svg`, icerik);
  await sharp(Buffer.from(icerik), { density: 300 }).resize({ width: g }).png().toFile(`${KLASOR}/${ad}.png`);
}
console.log(Object.keys(dosyalar).join('\n'));
