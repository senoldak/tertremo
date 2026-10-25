# En yakın komşu kümeleme (Zaliapin & Ben-Zion; Zaliapin 2008 PRL, arXiv:0712.1303) — src/kume.js ile aynı:
# log η = log10 τ + d_f·log10 r − b·m_ebeveyn; τ YIL, r haversine km (R 6371, alt sınır 0,1 km); ebeveyn kesin
# olarak daha önce ve en çok 10 yıl (3652 gün) önce (Worker'daki canlı kume.js 365 gün: D1 okuma maliyeti). Aday kümesi Worker'ın adayGetir'i ile aynı kurallar: olayın 1° hücresi
# ve 8 komşusu (mw ≥ mwAlt, en yeni 1000) + ±kutu içinde büyük olaylar (mw ≥ buyuk), toplam en çok 1000.
import math

import numpy as np
from scipy.optimize import brentq
from sklearn.mixture import GaussianMixture

YIL_MS = 365.25 * 24 * 3600 * 1000
GUN_MS = 24 * 3600 * 1000
MIN_R_KM = 0.1
PENCERE_GUN = 3652  # 10 yıl: büyük ana şokların (ör. 2023 Kahramanmaraş) 1 yıldan sonraki Omori kuyruğu da bağlı sayılsın
LIMIT = 1000
ESIK_EN_AZ = 20  # esik(): daha az sonlu log η ile karışım kurulmaz (nan)
R_DUNYA = 6371.0
KATALOG = {
    'tr': {'kutu': 3, 'mw_alt': 2.0, 'buyuk': 4.5},
    'dunya': {'kutu': 15, 'mw_alt': 4.5, 'buyuk': 6.0},
}


def mesafe_km(e1, b1, e2, b2):
    """src/geo.js mesafeKm ile aynı (haversine)."""
    rad = math.pi / 180
    de = (np.asarray(e2) - e1) * rad
    db = (np.asarray(b2) - b1) * rad
    a = np.sin(de / 2) ** 2 + np.cos(np.asarray(e1) * rad) * np.cos(np.asarray(e2) * rad) * np.sin(db / 2) ** 2
    return 2 * R_DUNYA * np.arcsin(np.minimum(1, np.sqrt(a)))


def log_eta_cift(t_e, e_e, b_e, m_e, t_c, e_c, b_c, d_f, b):
    tau = (t_c - t_e) / YIL_MS
    if not tau > 0:
        return math.inf
    r = max(float(mesafe_km(e_e, b_e, e_c, b_c)), MIN_R_KM)
    return math.log10(tau) + d_f * math.log10(r) - b * m_e


def en_yakin_komsu(zaman, enlem, boylam, mw, d_f, b, katalog='tr'):
    """(ebeveyn_idx, log_eta): ebeveyn yoksa -1 ve inf. Girdi sırası korunur."""
    k = KATALOG[katalog]
    zaman = np.asarray(zaman, float)
    n = zaman.size
    sira = np.argsort(zaman, kind='stable')
    t = zaman[sira]
    la = np.asarray(enlem, float)[sira]
    lo = np.asarray(boylam, float)[sira]
    m = np.asarray(mw, float)[sira]
    he = np.floor(la).astype(np.int64)
    hb = np.floor(lo).astype(np.int64)

    # 1° hücre → zaman sıralı aday dizinleri (mw ≥ mw_alt)
    aday = np.flatnonzero(m >= k['mw_alt'])
    hucre = {}
    if aday.size:
        anahtar = he[aday] * 1000 + hb[aday]
        s = np.argsort(anahtar, kind='stable')
        a_s = anahtar[s]
        sinir = np.flatnonzero(np.r_[True, a_s[1:] != a_s[:-1], True])
        for i in range(sinir.size - 1):
            idx = aday[s[sinir[i]:sinir[i + 1]]]
            hucre[int(a_s[sinir[i]])] = (idx, t[idx])
    buyuk = np.flatnonzero(m >= k['buyuk'])
    t_buyuk = t[buyuk]

    eb_s = np.full(n, -1, dtype=np.int64)
    le_s = np.full(n, np.inf)
    pencere = PENCERE_GUN * GUN_MS
    for j in range(n):
        tj = t[j]
        bas = tj - pencere
        parcalar = []
        for de in (-1, 0, 1):
            for db_ in (-1, 0, 1):
                h = hucre.get(int((he[j] + de) * 1000 + hb[j] + db_))
                if h is None:
                    continue
                idx, th = h
                alt = np.searchsorted(th, bas, 'left')
                ust = np.searchsorted(th, tj, 'left')
                if ust > alt:
                    parcalar.append(idx[max(alt, ust - LIMIT):ust])
        if parcalar:
            yerel = np.concatenate(parcalar)
            yerel = yerel[np.argsort(-t[yerel], kind='stable')][:LIMIT]
        else:
            yerel = np.empty(0, np.int64)
        alt = np.searchsorted(t_buyuk, bas, 'left')
        ust = np.searchsorted(t_buyuk, tj, 'left')
        bolgesel = buyuk[alt:ust]
        if bolgesel.size and yerel.size < LIMIT:
            e_alt, e_ust = max(-90, la[j] - k['kutu']), min(90, la[j] + k['kutu'])
            sec = ((la[bolgesel] >= e_alt) & (la[bolgesel] <= e_ust)
                   & (lo[bolgesel] >= lo[j] - k['kutu']) & (lo[bolgesel] <= lo[j] + k['kutu']))
            bolgesel = bolgesel[sec][::-1][:LIMIT]
            bolgesel = bolgesel[~np.isin(bolgesel, yerel)][:LIMIT - yerel.size]
            adaylar = np.concatenate([yerel, bolgesel])
        else:
            adaylar = yerel
        if adaylar.size == 0:
            continue
        tau = (tj - t[adaylar]) / YIL_MS
        r = np.maximum(mesafe_km(la[adaylar], lo[adaylar], la[j], lo[j]), MIN_R_KM)
        with np.errstate(divide='ignore'):
            v = np.where(tau > 0, np.log10(np.where(tau > 0, tau, 1)) + d_f * np.log10(r) - b * m[adaylar], np.inf)
        i = int(np.argmin(v))
        if np.isfinite(v[i]):
            eb_s[j] = adaylar[i]
            le_s[j] = v[i]

    ebeveyn = np.full(n, -1, dtype=np.int64)
    log_eta = np.full(n, np.inf)
    var = eb_s >= 0
    ebeveyn[sira[var]] = sira[eb_s[var]]
    log_eta[sira] = le_s
    return ebeveyn, log_eta


def korelasyon_boyutu(enlem, boylam, r_alt=5.0, r_ust=100.0, en_cok=5000, tohum=0):
    """Grassberger–Procaccia: log C(r) – log r eğimi, r ∈ [r_alt, r_ust] km (en çok 5000 olaylık sabit örnek)."""
    enlem = np.asarray(enlem, float)
    boylam = np.asarray(boylam, float)
    if enlem.size > en_cok:
        s = np.random.default_rng(tohum).choice(enlem.size, en_cok, replace=False)
        enlem, boylam = enlem[s], boylam[s]
    n = enlem.size
    r = np.logspace(math.log10(r_alt), math.log10(r_ust), 15)
    sayi = np.zeros(r.size + 1, dtype=np.int64)
    for i in range(n - 1):
        d = mesafe_km(enlem[i], boylam[i], enlem[i + 1:], boylam[i + 1:])
        sayi += np.bincount(np.searchsorted(r, d, 'right'), minlength=r.size + 1)
    c = np.cumsum(sayi)[:-1]  # c[k] = #(d < r[k])
    var = c > 0
    if var.sum() < 3:
        return math.nan
    egim, _ = np.polyfit(np.log10(r[var]), np.log10(c[var]), 1)
    return float(egim)


def esik(log_eta, tohum=0):
    """İki Gauss karışımı; ağırlıklı yoğunlukların eşit olduğu, ortalamalar arasındaki nokta."""
    x = np.asarray(log_eta, float)
    x = x[np.isfinite(x)].reshape(-1, 1)
    if x.shape[0] < ESIK_EN_AZ:
        return math.nan
    try:
        g = GaussianMixture(2, random_state=tohum).fit(x)
    except ValueError:
        return math.nan
    ort = g.means_.ravel()
    sd = np.sqrt(g.covariances_.ravel())
    w = g.weights_
    s = np.argsort(ort)
    (m1, m2), (s1, s2), (w1, w2) = ort[s], sd[s], w[s]

    def fark(v):
        return (math.log(w1) - math.log(s1) - 0.5 * ((v - m1) / s1) ** 2) - (
            math.log(w2) - math.log(s2) - 0.5 * ((v - m2) / s2) ** 2)

    if fark(m1) * fark(m2) > 0:
        return float((m1 + m2) / 2)
    return float(brentq(fark, m1, m2))
