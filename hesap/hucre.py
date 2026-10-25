# Hücre istatistikleri (spec §7.3): Mc (MAXC + 0,2; katalog tamlığının altına inmez), b (Aki–Utsu, kutu düzeltmeli), σ_b (Shi & Bolt 1982),
# arka plan hızı λ (bağımsız M≥Mc olay / yıl), son 7 gün Poisson kuyruğu + Benjamini–Hochberg (q 0,05).
import math

import numpy as np
from scipy.stats import poisson

YIL_MS = 365.25 * 24 * 3600 * 1000
GUN_MS = 86_400_000
N_B_EN_AZ = 50
PENCERE_GUN = 7
EPS = 1e-9


def hucre_anahtari(enlem, boylam, katalog):
    """src/istatistik.js hucreAnahtari ile aynı: tr 1°, dünya 5°; -0 → 0."""
    boy = 1 if katalog == 'tr' else 5
    e = math.floor(enlem / boy) * boy
    b = math.floor(boylam / boy) * boy
    return f'{int(e)}_{int(b)}'


def kutula(m, dm=0.1):
    return np.round(np.round(np.asarray(m, float) / dm) * dm, 6)


def mc_maxc(m, dm=0.1):
    """MAXC (Woessner & Wiemer 2005): en kalabalık kutu + 0,2. Eşitlikte küçük kutu."""
    k = kutula(m, dm)
    if k.size == 0:
        return math.nan
    tam = np.round(k / dm).astype(np.int64)
    degerler, sayilar = np.unique(tam, return_counts=True)
    mod = degerler[np.argmax(sayilar)] * dm
    return round(float(mod) + 0.2, 6)


def b_aki_utsu(m, mc, dm=0.1):
    """(b, σ_b): b = log10(e) / (M̄ − (Mc − ΔM/2)); σ_b = 2,30·b²·√(Σ(M−M̄)² / (n(n−1))) (Shi & Bolt 1982)."""
    k = kutula(m, dm)
    k = k[k >= mc - EPS]
    n = k.size
    if n < 2:
        return math.nan, math.nan
    ort = float(k.mean())
    b = math.log10(math.e) / (ort - (mc - dm / 2))
    sigma = 2.30 * b * b * math.sqrt(float(((k - ort) ** 2).sum()) / (n * (n - 1)))
    return b, sigma


def bh_duzelt(p):
    """Benjamini–Hochberg düzeltilmiş p (scipy false_discovery_control 'bh' ile aynı)."""
    p = np.asarray(p, float)
    n = p.size
    if n == 0:
        return p
    sira = np.argsort(p)
    ps = p[sira] * n / np.arange(1, n + 1)
    ps = np.minimum.accumulate(ps[::-1])[::-1]
    sonuc = np.empty(n)
    sonuc[sira] = np.minimum(ps, 1.0)
    return sonuc


def hucre_istatistik(zaman, enlem, boylam, mw, bagimsiz, katalog, baslangic_ms, simdi_ms, dm=0.1, mc_katalog=None):
    """Her hücre için {katalog, anahtar, mc, b, sigma_b, n, lambda, k7, mu7, p, bh_p}.

    Mc ve b hücredeki bütün olaylarla (baslangic_ms sonrası); λ yalnız bağımsız (ebeveynsiz) olaylarla.
    k7: son 7 günde bağımsız M≥Mc; p = P(X ≥ k7 | Poisson(λ·7/365)); bh_p yalnız λ > 0 hücreler arasında.
    mc_katalog (katalog genelinin MBS tamlığı) verilirse hücre Mc'si max(MAXC + 0,2, mc_katalog): MAXC heterojen
    katalogda (EMSC: ML ~2'den, mb/Mw üstte) gerçek tamlığın altında kalır ve b'yi aşağı çeker.
    """
    zaman = np.asarray(zaman, float)
    secim = zaman >= baslangic_ms
    zaman, enlem, boylam = zaman[secim], np.asarray(enlem, float)[secim], np.asarray(boylam, float)[secim]
    mw, bagimsiz = np.asarray(mw, float)[secim], np.asarray(bagimsiz, bool)[secim]
    yil = (simdi_ms - baslangic_ms) / YIL_MS
    anahtar = np.array([hucre_anahtari(e, b, katalog) for e, b in zip(enlem, boylam)], dtype=object)
    sonuc = []
    if zaman.size == 0:
        return sonuc
    sira = np.argsort(anahtar, kind='stable')
    a_sirali = anahtar[sira]
    sinirlar = np.flatnonzero(np.r_[True, a_sirali[1:] != a_sirali[:-1], True])
    son7 = simdi_ms - PENCERE_GUN * GUN_MS
    for i in range(sinirlar.size - 1):
        idx = sira[sinirlar[i]:sinirlar[i + 1]]
        m = mw[idx]
        mc = mc_maxc(m, dm)
        if mc_katalog is not None and math.isfinite(mc_katalog):
            mc = round(max(mc, float(mc_katalog)), 6)
        ustu = kutula(m, dm) >= mc - EPS
        n = int(ustu.sum())
        b = sigma = None
        if n >= N_B_EN_AZ:
            b, sigma = b_aki_utsu(m, mc, dm)
        # λ ve k7 Worker olagandisi ile aynı: ham mw ≥ mc (kutulu değer yalnız Mc, b, n için)
        bag = (m >= mc - EPS) & bagimsiz[idx]
        lam = float(bag.sum()) / yil
        k7 = int((bag & (zaman[idx] > son7)).sum())
        mu7 = lam * PENCERE_GUN / 365
        p = float(poisson.sf(k7 - 1, mu7)) if lam > 0 else None
        sonuc.append({
            'katalog': katalog, 'anahtar': str(a_sirali[sinirlar[i]]), 'mc': mc, 'b': b, 'sigma_b': sigma,
            'n': n, 'lambda': lam, 'k7': k7, 'mu7': mu7, 'p': p, 'bh_p': None,
        })
    test = [s for s in sonuc if s['p'] is not None]
    for s, q in zip(test, bh_duzelt([s['p'] for s in test])):
        s['bh_p'] = float(q)
    return sonuc
