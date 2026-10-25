// Türkiye + 30 km tampon (hesap/olasilik.py BolgeAtayici ile aynı tanım: il sınırlarının içi ya da en yakın il sınırına
// ≤ 30 km; uzaklık cos 39° ölçekli düzlemde). λ ve b haritaları yalnız merkezi bu bölgede olan 1° hücreleri çizer.
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

export const TAMPON_KM = 30;
const KOS = Math.cos((39 * Math.PI) / 180);
const TAMPON = TAMPON_KM / 111.195;

let halkalar = null;
function yukle() {
  if (halkalar) return halkalar;
  const iller = JSON.parse(fs.readFileSync(fileURLToPath(new URL('../../data/harita/iller.json', import.meta.url)), 'utf8'));
  halkalar = [];
  for (const il of iller) {
    for (const r of il.r) {
      const x = [], y = [];
      for (let i = 0; i + 1 < r.length; i += 2) { x.push(r[i] * KOS); y.push(r[i + 1]); }
      halkalar.push({ x, y, x0: Math.min(...x), x1: Math.max(...x), y0: Math.min(...y), y1: Math.max(...y) });
    }
  }
  return halkalar;
}

/** Nokta (enlem, boylam) Türkiye il sınırlarının içinde ya da ≤ 30 km dışında mı? */
export function turkiyeIcinde(enlem, boylam) {
  const px = boylam * KOS, py = enlem;
  const hs = yukle();
  let ic = false;
  for (const h of hs) {
    if (px < h.x0 || px > h.x1 || py < h.y0 || py > h.y1) continue;
    const n = h.x.length;
    for (let i = 0, j = n - 1; i < n; j = i++) {
      if ((h.y[i] > py) !== (h.y[j] > py) && px < ((h.x[j] - h.x[i]) * (py - h.y[i])) / (h.y[j] - h.y[i]) + h.x[i]) ic = !ic;
    }
  }
  if (ic) return true;
  for (const h of hs) {
    if (px < h.x0 - TAMPON || px > h.x1 + TAMPON || py < h.y0 - TAMPON || py > h.y1 + TAMPON) continue;
    const n = h.x.length;
    for (let i = 0, j = n - 1; i < n; j = i++) {
      const ax = h.x[j], ay = h.y[j], dx = h.x[i] - ax, dy = h.y[i] - ay;
      const u = dx * dx + dy * dy;
      const t = u === 0 ? 0 : Math.min(1, Math.max(0, ((px - ax) * dx + (py - ay) * dy) / u));
      if (Math.hypot(px - (ax + t * dx), py - (ay + t * dy)) <= TAMPON) return true;
    }
  }
  return false;
}

/** Hücre anahtarı "la_lo" (1° hücrenin güneybatı köşesi) → merkezi Türkiye + 30 km içinde mi? */
export function hucreTurkiyede(h) {
  const [la, lo] = h.anahtar.split('_').map(Number);
  return turkiyeIcinde(la + 0.5, lo + 0.5);
}

/** Yalnız merkezi Türkiye + 30 km içindeki hücreler. */
export const turkiyeHucreleri = (hucreler) => hucreler.filter(hucreTurkiyede);
