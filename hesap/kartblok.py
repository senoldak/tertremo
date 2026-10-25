# Dönemsel kartların (14 Gutenberg–Richter, 15 b haritası, 16 λ haritası) kart-veri.json blokları.
# Gece hesabı (hesap/gunluk.py) bunları önbelleğe yazar; scripts/kart/kartlar/{gr,bharita,lambdaharita}.mjs okur.
import math
from datetime import datetime, timezone

import numpy as np

from hesap.hucre import EPS, N_B_EN_AZ, b_aki_utsu, kutula, mc_maxc

UTC = timezone.utc
TSI_MS = 3 * 3600 * 1000
DM = 0.1


def ay_araligi(simdi_ms):
    """Önceki takvim ayı, Türkiye yerel saatiyle (UTC+3, yaz saati yok): (başlangıç_ms, bitiş_ms, 'YYYY-AA')."""
    yerel = datetime.fromtimestamp((simdi_ms + TSI_MS) / 1000, tz=UTC)
    y, a = (yerel.year - 1, 12) if yerel.month == 1 else (yerel.year, yerel.month - 1)
    bas = datetime(y, a, 1, tzinfo=UTC).timestamp() * 1000 - TSI_MS
    bit = datetime(yerel.year, yerel.month, 1, tzinfo=UTC).timestamp() * 1000 - TSI_MS
    return bas, bit, f'{y:04d}-{a:02d}'


def gr_blogu(mw, ay):
    """Bir aylık katalog → Gutenberg–Richter bloğu; Mc'nin üstünde 50'den az olay varsa None.
    histogram: 0,1'lik kutular [[merkez, sayı], …] (sayı > 0); b, σ_b: Aki–Utsu / Shi–Bolt (hesap/hucre.py)."""
    mw = np.asarray(mw, float)
    mw = mw[np.isfinite(mw)]
    if mw.size == 0:
        return None
    km = kutula(mw, DM)
    mc = mc_maxc(mw, DM)
    n = int((km >= mc - EPS).sum())
    if n < N_B_EN_AZ:
        return None
    b, sigma = b_aki_utsu(mw, mc, DM)
    if not (math.isfinite(b) and math.isfinite(sigma)):
        return None
    tam = np.round(km / DM).astype(np.int64)
    kutular, sayilar = np.unique(tam, return_counts=True)
    return {
        'ay': ay, 'n': n, 'toplam': int(mw.size), 'mc': float(mc), 'b': round(float(b), 4), 'sigma': round(float(sigma), 4),
        'dm': DM, 'histogram': [[round(float(k) * DM, 1), int(c)] for k, c in zip(kutular, sayilar)],
    }


def hucre_blogu(hucreler, simdi_ms, baslangic_ms, b_tr=None):
    """gunluk.hesapla hücre satırlarından Türkiye (1°) hücreleri: hucre tablosundaki değerlerin aynısı.
    b yalnız n ≥ 50 hücrede (hucre_istatistik zaten böyle üretir); λ bağımsız M ≥ Mc olay / yıl."""
    liste = []
    for h in hucreler:
        if h.get('katalog') != 'tr':
            continue
        liste.append({
            'anahtar': h['anahtar'], 'mc': h['mc'], 'n': h['n'],
            'b': None if h['b'] is None else round(float(h['b']), 4),
            'sigma_b': None if h['sigma_b'] is None else round(float(h['sigma_b']), 4),
            'lambda': round(float(h['lambda']), 4),
        })
    liste.sort(key=lambda s: s['anahtar'])
    # turkiyeB: λ haritası güvenilir b'si olmayan hücreyi Türkiye b'siyle M ≥ 4'e çevirir
    return {'hesap': int(simdi_ms), 'baslangic': int(baslangic_ms), 'turkiyeB': None if b_tr is None else round(float(b_tr), 3), 'hucreler': liste}
