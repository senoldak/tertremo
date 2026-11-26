# Deney "topluluk": haftalık "kutuda ≥ 1 M ≥ 5" olasılığında model ağırlıklandırması (gölge deney).
#
# Gerekçe: Herrmann & Marzocchi 2023 (GJI 234(1):73–87, doi 10.1093/gji/ggad020): OEF-Italy topluluğunda
# lojistik regresyon ağırlığı en iyi tek modeli geçiyor. Marzocchi, Zechar, Jordan 2012 (BSSA 102(3):1179–1192):
# log-olabilirliğe göre ağırlık (SMA benzeri). Burada üç girdi: ETAS (p5), kümelenmesi ayrılmış Poisson (taban5),
# bütün olaylı Poisson (tum5). Hepsi yalnız geçmiş haftalarla; ilk ISINMA hafta değerlendirmeye girmez.
# Var olan modüllere dokunmaz; dogrulama.calistir değiştirilmeden çağrılır.
import argparse
import json
import math
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np
from scipy.optimize import minimize

from hesap import dogrulama as dg
from hesap import etas
from hesap import katalog as kat

ONBELLEK = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.onbellek')
SERI_YOL = os.path.join(ONBELLEK, 'deney', 'topluluk-haftalar.json')
SONUC_YOL = os.path.join(ONBELLEK, 'deney', 'topluluk.json')
ISINMA = 26
EPS = 1e-4          # olasılıkları [EPS, 1-EPS] aralığına kırp (log hesapları için)
MODELLER = ('etas', 'taban', 'tum')
BLOK = 8            # hareketli blok bootstrap blok uzunluğu (hafta)
UTC = timezone.utc


# ---------- seri üretimi ----------

def seri_uret(n=5000, pencere_sinir=None, tohum=0, yol=SERI_YOL):
    """dogrulama.calistir'i değiştirmeden çağırır; haftalık serileri önbelleğe yazar."""
    olaylar = kat.yukle(os.path.join(ONBELLEK, 'tr.csv.gz'))
    bit = max(o['zaman_ms'] for o in olaylar) + 1
    t = time.monotonic()
    s = dg.calistir(olaylar, bit, n=n, tohum=tohum, pencere_sinir=pencere_sinir,
                    gunluk=lambda x: print(str(x)[:160], flush=True))
    h = s['haftalar']
    bas_ms = int(etas._ms(dg.DENEME_BAS))
    cikti = {'kapsam': s['kapsam'] | {'sure_s': round(time.monotonic() - t, 1), 'n': n},
             'p5': h['p5'], 'taban5': h['taban5'], 'tum5': h['tum5'], 'o5': [int(x) for x in h['o5']],
             'p6': h['p6'], 'o6': [int(x) for x in h['o6']],
             'hafta_bas_ms': [bas_ms + i * 7 * dg.GUN_MS for i in range(len(h['p5']))]}
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, 'w', encoding='utf-8') as f:
        json.dump(cikti, f, ensure_ascii=False)
    return cikti


# ---------- ölçütler ----------

def kirp(p):
    return np.clip(np.asarray(p, float), EPS, 1 - EPS)


def brier(p, o):
    return float(np.mean((np.asarray(p, float) - np.asarray(o, float)) ** 2))


def log_olas(p, o):
    """Haftalık log-olabilirlik dizisi (büyük iyi)."""
    p, o = kirp(p), np.asarray(o, float)
    return o * np.log(p) + (1 - o) * np.log(1 - p)


def logit(p):
    p = kirp(p)
    return np.log(p / (1 - p))


def sigmoid(x):
    return 1 / (1 + np.exp(-x))


# ---------- birleştirme yöntemleri (P[t, model], gözlem o[t] → p_birlesik[t]; t için yalnız < t haftaları) ----------

def esit(P, o):
    """(a) Eşit ağırlık: olasılıkların aritmetik ortalaması."""
    return P.mean(axis=1)


def ll_agirlik(P, o, pencere):
    """(b) Son `pencere` haftanın log-olabilirliğine göre ağırlık (Marzocchi vd. 2012 SMA benzeri):
    w_m ∝ exp(L_m − max L), L_m = penceredeki toplam log-olabilirlik. Hafta t'nin ağırlığı yalnız < t haftalarından;
    4 haftadan az geçmiş varsa eşit ağırlık."""
    T, M = P.shape
    cikti = np.empty(T)
    ll = np.column_stack([log_olas(P[:, i], o) for i in range(M)])
    for t in range(T):
        g = ll[max(0, t - pencere):t]
        if len(g) < 4:
            w = np.full(M, 1 / M)
        else:
            L = g.sum(axis=0)
            w = np.exp(L - L.max())
            w /= w.sum()
        cikti[t] = float(w @ P[t])
    return cikti


def lojistik_uyum(X, y, lam=1.0):
    """L2'li lojistik regresyon (kesişim cezasız). X: logit(p) sütunları. Ceza katsayıyı sıfıra değil 1/M'ye
    (logit-ortalama) çeker: 'topluluk ≈ ortalama' önkabulüyle hafif düzenleme."""
    M = X.shape[1]
    w0 = np.full(M, 1 / M)

    def f(th):
        z = th[0] + X @ th[1:]
        return np.sum(np.logaddexp(0, z) - y * z) + lam * np.sum((th[1:] - w0) ** 2)

    def g(th):
        z = th[0] + X @ th[1:]
        r = sigmoid(z) - y
        return np.concatenate([[r.sum()], X.T @ r + 2 * lam * (th[1:] - w0)])

    return minimize(f, np.concatenate([[0.0], w0]), jac=g, method='L-BFGS-B').x


def lojistik(P, o, lam=1.0):
    """(c) Genişleyen pencere lojistik regresyon: t haftası < t haftalarıyla uyumlanır; ısınmada eşit ağırlık."""
    T = len(o)
    X = logit(P)
    cikti = np.empty(T)
    for t in range(T):
        if t < ISINMA or o[:t].sum() < 2:
            cikti[t] = P[t].mean()
        else:
            th = lojistik_uyum(X[:t], o[:t].astype(float), lam)
            cikti[t] = float(sigmoid(th[0] + X[t] @ th[1:]))
    return cikti


def en_iyi_tek(P, o):
    """(d) Geçmişte (t'den önce) toplam log-olabilirliği en yüksek tek model; ilk 4 haftada eşit ağırlık."""
    T, M = P.shape
    ll = np.column_stack([log_olas(P[:, i], o) for i in range(M)])
    cikti = np.empty(T)
    for t in range(T):
        cikti[t] = P[t].mean() if t < 4 else P[t, int(np.argmax(ll[:t].sum(axis=0)))]
    return cikti


# ---------- değerlendirme ----------

def blok_indeksleri(T, blok=BLOK, b=2000, tohum=2):
    """Hareketli blok bootstrap (Künsch 1989) yeniden örnekleme indeksleri; haftalar zamanda bağımlı."""
    if T < blok:
        return None
    rng = np.random.default_rng(tohum)
    nb = math.ceil(T / blok)
    return [np.concatenate([np.arange(s, s + blok) for s in rng.integers(0, T - blok + 1, nb)])[:T]
            for _ in range(b)]


def guvenirlik(p, o, kutular=(0, .05, .1, .2, .3, .5, .7, 1.0001)):
    sat = []
    p, o = np.asarray(p, float), np.asarray(o, float)
    for a, c in zip(kutular[:-1], kutular[1:]):
        m = (p >= a) & (p < c)
        if m.sum():
            sat.append({'aralik': [a, min(c, 1.0)], 'n': int(m.sum()), 'ort_tahmin': float(p[m].mean()),
                        'gozlenen_oran': float(o[m].mean())})
    return sat


def degerlendir(p_yontemler, o, taban_ad='taban'):
    """Her yöntem için Brier, ortalama log skoru, Brier becerisi (BSS = 1 − ΣB/ΣB_taban) ve taban'a göre ortalama
    log-skor farkı; ikisinin %95 aralığı blok bootstrap ile (BLOK hafta)."""
    o = np.asarray(o, float)
    T = len(o)
    idx = blok_indeksleri(T)
    bt = (np.asarray(p_yontemler[taban_ad]) - o) ** 2
    lt = log_olas(p_yontemler[taban_ad], o)
    sonuc = {}
    for ad, p in p_yontemler.items():
        p = np.asarray(p, float)
        bm = (p - o) ** 2
        lm = log_olas(p, o)
        r = {'brier': float(bm.mean()), 'log_skor': float(lm.mean()),
             'bss': None if bt.sum() == 0 else float(1 - bm.sum() / bt.sum())}
        if idx is not None and bt.sum() > 0:
            bss_b = np.array([1 - bm[i].sum() / bt[i].sum() for i in idx if bt[i].sum() > 0])
            r['bss_95'] = [float(np.percentile(bss_b, 2.5)), float(np.percentile(bss_b, 97.5))]
            fark = lm - lt
            fb = [fark[i].mean() for i in idx]
            r['log_fark_taban'] = float(fark.mean())
            r['log_fark_95'] = [float(np.percentile(fb, 2.5)), float(np.percentile(fb, 97.5))]
        sonuc[ad] = r
    return sonuc


def yontemler(P, o):
    """Tek modeller + birleştirmeler. P: T×3 (etas, taban, tum)."""
    k = {ad: P[:, i] for i, ad in enumerate(MODELLER)}
    k['esit'] = esit(P, o)
    k['ll12'] = ll_agirlik(P, o, 12)
    k['ll26'] = ll_agirlik(P, o, 26)
    k['lojistik'] = lojistik(P, o)
    k['en_iyi_tek'] = en_iyi_tek(P, o)
    return k


def analiz(seri, dislanan=None):
    """Isınma sonrası (ve isteğe bağlı olarak `dislanan` haftalar dışarıda) değerlendirme. Yöntemler tüm seri
    üzerinde (dışlanan haftalar geçmişte kalarak) yürütülür; yalnız puanlama dışlar."""
    P = np.column_stack([seri['p5'], seri['taban5'], seri['tum5']])
    o = np.asarray(seri['o5'], int)
    yon = yontemler(P, o)
    m = np.arange(len(o)) >= ISINMA
    if dislanan is not None:
        m &= ~dislanan
    sec = {ad: np.asarray(p)[m] for ad, p in yon.items()}
    return {'hafta': int(m.sum()), 'olay_hafta': int(o[m].sum()),
            'sonuc': degerlendir(sec, o[m]),
            'guvenirlik': {ad: guvenirlik(sec[ad], o[m]) for ad in ('etas', 'taban', 'esit', 'll26', 'lojistik')}}


def analiz_p6(seri):
    """M ≥ 6: seride yalnız ETAS p6 var; taban olarak geçmişin genişleyen olay oranı (Jeffreys 0,5 düzeltmeli)."""
    p, o = np.asarray(seri['p6'], float), np.asarray(seri['o6'], int)
    ik = np.array([(o[:t].sum() + 0.5) / (t + 1) for t in range(len(o))])
    m = np.arange(len(o)) >= ISINMA
    sec = {'etas': p[m], 'iklim': ik[m], 'esit_etas_iklim': (p[m] + ik[m]) / 2}
    return {'hafta': int(m.sum()), 'olay_hafta': int(o[m].sum()),
            'sonuc': degerlendir(sec, o[m], taban_ad='iklim'), 'guvenirlik': {'etas': guvenirlik(p[m], o[m])}}


def kmaras_maske(seri, gun='2023-02-06', once=0, sonra=4):
    """Kahramanmaraş (6 Şubat 2023) haftası ve sonraki `sonra` hafta: artçı dizisi p5'i ve kümelenmeyi etkiler."""
    t = datetime.fromisoformat(gun).replace(tzinfo=UTC).timestamp() * 1000
    h = np.asarray(seri['hafta_bas_ms'], float)
    i0 = int(np.searchsorted(h, t, side='right')) - 1     # depremi içeren hafta
    m = np.zeros(len(h), bool)
    m[max(0, i0 - once):i0 + sonra + 1] = True
    return m


def ana(argv=None):
    for akis in (sys.stdout, sys.stderr):
        if hasattr(akis, 'reconfigure'):
            akis.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='topluluk deneyi')
    ap.add_argument('--seri-uret', action='store_true')
    ap.add_argument('--n', type=int, default=5000)
    ap.add_argument('--pencere', type=int, default=None)
    a = ap.parse_args(argv)
    if a.seri_uret:
        seri_uret(n=a.n, pencere_sinir=a.pencere)
    with open(SERI_YOL, encoding='utf-8') as f:
        seri = json.load(f)
    km = kmaras_maske(seri)
    sonuc = {'kapsam': seri['kapsam'], 'isinma': ISINMA, 'blok': BLOK, 'kmaras_hafta_sayisi': int(km.sum()),
             'kmaras_haftalari': [datetime.fromtimestamp(x / 1000, tz=UTC).date().isoformat()
                                  for x in np.asarray(seri['hafta_bas_ms'])[km]],
             'tum_haftalar': analiz(seri), 'kmaras_disi': analiz(seri, dislanan=km), 'p6': analiz_p6(seri)}
    with open(SONUC_YOL, 'w', encoding='utf-8') as f:
        json.dump(sonuc, f, ensure_ascii=False, indent=1)
    print('yazıldı', SONUC_YOL)
    return 0


if __name__ == '__main__':
    sys.exit(ana())
