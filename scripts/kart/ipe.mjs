// Hissedilen şiddet: Allen, Wald & Worden (2012) IPE (ln = doğal logaritma), medyan MMI.
// Katsayılar OpenQuake allen_2012_ipe ile eşleşir; Worker'daki hesapla aynı değerleri verir (testte parite).
const kirp = (x) => Math.min(10, Math.max(1, x));

/** {mw, derinlik (km), mesafeKm (merkez üssüne yatay)} → {mmi, sigma, sonlu}. */
export function mmi({ mw, derinlik, mesafeKm }) {
  const h = derinlik > 0 ? derinlik : 0;
  const repi = Math.max(0, mesafeKm);
  if (mw < 6.5) {
    const r = Math.sqrt(repi ** 2 + h ** 2);
    const rm = -0.209 + 2.042 * Math.exp(mw - 5);
    let v = 2.085 + 1.428 * mw - 1.402 * Math.log(Math.sqrt(r ** 2 + rm ** 2));
    if (r > 50) v += 0.078 * Math.log(r / 50);
    const sigma = 0.82 + 0.37 / (1 + (r / 22.9) ** 2);
    return { mmi: kirp(v), sigma, sonlu: false };
  }
  const L = 10 ** (-2.57 + 0.62 * mw);
  const rx = Math.max(repi - L / 2, 0);
  const rrup = Math.sqrt(rx ** 2 + h ** 2);
  const v = 3.95 + 0.913 * mw - 1.107 * Math.log(Math.sqrt(rrup ** 2 + (1 + 0.813 * Math.exp(mw - 5)) ** 2));
  const sigma = 0.72 + 0.23 / (1 + (rrup / 44.7) ** 2);
  return { mmi: kirp(v), sigma, sonlu: true };
}

/** MMI'nin esikMmi'ye düştüğü merkez üssü uzaklığı (km), ikiye bölme. Eşiğe hiç ulaşılmıyorsa 0. */
export function halkaYaricapi(mw, derinlik, esikMmi) {
  if (mmi({ mw, derinlik, mesafeKm: 0 }).mmi < esikMmi) return 0;
  let a = 0, b = 3000;
  for (let i = 0; i < 60; i++) {
    const m = (a + b) / 2;
    if (mmi({ mw, derinlik, mesafeKm: m }).mmi >= esikMmi) a = m; else b = m;
  }
  return a;
}

/** Enlem-boylam arası büyük daire uzaklığı (km, R = 6371). */
export function mesafeKm(la1, lo1, la2, lo2) {
  const r = (d) => (d * Math.PI) / 180;
  const a = Math.sin(r(la2 - la1) / 2) ** 2 + Math.cos(r(la1)) * Math.cos(r(la2)) * Math.sin(r(lo2 - lo1) / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(a));
}
