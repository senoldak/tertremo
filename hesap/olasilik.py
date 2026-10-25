# Kart 19 — uzun dönem deprem olasılığı (zamandan bağımsız Poisson; deprem tahmini değildir).
# - λ(M ≥ Mc): kümelenmesi ayrılmış (en yakın komşu, hesap/kume.py) olay sayısı / gözlem yılı.
# - G–R uzatma: λ(M) = λ(Mc)·10^(−b(M−Mc)); P(T yılda ≥ 1 olay) = 1 − exp(−λ(M)·T).
# - Mw ≥ 6 ve Mw ≥ 7: UZUN USGS kaydı (data/tarihte-bugun.json, 1900–, Gardner–Knopoff ile ayıklanmış; λ = olay/yıl, Mw ≥ 6 için 1930'dan,
#   Mw ≥ 7 için 1900'den; Türkiye ve bölgeler için doğrudan sayım). EMSC 2018– yalnız Mw ≥ 5 satırı ve b için (G–R uzatma).
# - Aralık: Poisson bootstrap (her olaya Poisson(1) ağırlık = olay sayısı da değişir), 1.000 çekim; b ve λ HER çekimde yeniden
#   hesaplanır (Türkiye ve her bölge için); orta = veri üzerindeki nokta değeri, aralık = %10 / %90. Bölgelerin ve Türkiye'nin
#   çekimi ortaktır: Türkiye kataloğu çekim başına bir kez örneklenir, hepsi ondan türer (kendi b'si olmayan bölge o çekimin Türkiye b'sini alır).
# - Mc: hesap/etas.py mc_egitim (ETAS ile aynı katalog kuralları). Bölge: data/bolgeler.json (7 bölge; "birlestir" eşlemesiyle 6).
# - Bölge b'si: bölgede ≥ 100 bağımsız olay varsa kendi Aki–Utsu b'si (0,6–1,5 dışıysa Türkiye b'si), yoksa Türkiye b'si.
# Bağımlılık: yalnız numpy/scipy (gece hesabının requirements.txt'i); shapely gerekmez.
import argparse
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np

from hesap import kartveri
from hesap import katalog as kat
from hesap.etas import B_ARALIK, YARDIMCI_BAS, bolgesel_b, kumele, kutuda, mc_egitim
from hesap.hucre import EPS, b_aki_utsu, kutula
from hesap.kume import mesafe_km

UTC = timezone.utc
YIL_MS = 365.25 * 24 * 3600 * 1000
T_LISTE = (1, 10, 50)
M_LISTE = (5.0, 6.0, 7.0)
BOOTSTRAP = 1000
DM = 0.1
BOLGE_B_EN_AZ = 100
SURUM = 'uzun-1'
TARIHTE_BUGUN = os.path.join(os.path.dirname(__file__), '..', 'data', 'tarihte-bugun.json')
M6_BAS = 1930      # Mw ≥ 6 tamlığı: 1930'dan (1900'e kadar iyimser)
M7_BAS = 1900      # Mw ≥ 7 tamlığı: 1900'den
BOLGE_DOSYA = os.path.join(os.path.dirname(__file__), '..', 'data', 'bolgeler.json')
IL_DOSYA = os.path.join(os.path.dirname(__file__), '..', 'data', 'harita', 'iller.json')
LOG10E = math.log10(math.e)


def olasilik(lam_mc, mc, b, m, t):
    """P(t yılda en az bir M ≥ m): λ(m) = λ(Mc)·10^(−b(m−Mc)); P = 1 − exp(−λ(m)·t)."""
    lam = np.asarray(lam_mc, float) * 10.0 ** (-np.asarray(b, float) * (m - mc))
    return 1.0 - np.exp(-lam * t)


def _secim(katalog_bagimsiz, mc, alan):
    mw = np.asarray(katalog_bagimsiz['mw'], float)
    bolge = katalog_bagimsiz.get('bolge')
    if alan is not None:
        if bolge is None:
            raise ValueError('alan verildi ama katalogda bolge yok')
        mw = mw[np.asarray(bolge, dtype=object) == alan]
    k = kutula(mw, DM)
    return k[k >= mc - EPS]


def uzun_donem(katalog_bagimsiz, mc, b, alan=None, T=T_LISTE, M=M_LISTE, n_boot=BOOTSTRAP, tohum=0, b_yeniden=True):
    """{T: {M: (orta, alt, ust)}}. katalog_bagimsiz: {'mw': bağımsız olay büyüklükleri, 'yil': gözlem yılı,
    'bolge': (isteğe bağlı) olay başına bölge adı}; alan: bölge adı (None = hepsi). b_yeniden: True (varsayılan) ise b her
    bootstrap çekiminde olaylardan yeniden hesaplanır (0,6–1,5'e kırpılır), False ise sabit."""
    k = _secim(katalog_bagimsiz, mc, alan)
    yil = float(katalog_bagimsiz['yil'])
    n = k.size
    rng = np.random.default_rng(tohum)
    sonuc = {t: {} for t in T}
    if n == 0:
        for t in T:
            for m in M:
                sonuc[t][m] = (0.0, 0.0, 0.0)
        return sonuc
    lam0 = n / yil
    lam_b = np.empty(n_boot)
    b_b = np.full(n_boot, float(b))
    adim = max(1, min(n_boot, 2_000_000 // n))
    for bas in range(0, n_boot, adim):
        c = min(adim, n_boot - bas)
        w = rng.poisson(1.0, (c, n))
        toplam = w.sum(axis=1)
        lam_b[bas:bas + c] = toplam / yil
        if b_yeniden:
            with np.errstate(divide='ignore', invalid='ignore'):
                ort = (w @ k) / toplam
                bb = LOG10E / (ort - (mc - DM / 2))
            b_b[bas:bas + c] = np.where(toplam > 0, np.clip(bb, *B_ARALIK), b)
    for t in T:
        for m in M:
            orta = float(olasilik(lam0, mc, b, m, t))
            p = olasilik(lam_b, mc, b_b, m, t)
            alt, ust = np.percentile(p, [10, 90])
            sonuc[t][m] = (orta, min(float(alt), orta), max(float(ust), orta))
    return sonuc


class BolgeAtayici:
    """data/bolgeler.json + data/harita/iller.json (shapely'siz). ata(enlem, boylam) → bölge adı ya da None:
    il sınırları içindeyse o ilin bölgesi, değilse ≤ tampon_km uzaktaki en yakın bölge. Birleştirme eşlemesi uygulanır
    (7 bölge → 6). Uzaklık cos 39° ölçekli düzlemde."""

    KOS = math.cos(math.radians(39))

    def __init__(self, bolge_dosya=BOLGE_DOSYA, il_dosya=IL_DOSYA):
        with open(bolge_dosya, encoding='utf-8') as f:
            tanim = json.load(f)
        with open(il_dosya, encoding='utf-8') as f:
            iller = {il['ad']: il for il in json.load(f)}
        birlestir = tanim.get('birlestir', {})
        self.tampon = tanim['tampon_km'] / 111.195
        self.adlar = []
        self.halkalar = {}
        for b in tanim['bolgeler']:
            ad = birlestir.get(b['ad'], b['ad'])
            if ad not in self.halkalar:
                self.adlar.append(ad)
                self.halkalar[ad] = []
            for il in b['iller']:
                for r in iller[il]['r']:
                    xy = np.asarray(r, float).reshape(-1, 2)
                    self.halkalar[ad].append(np.column_stack([xy[:, 0] * self.KOS, xy[:, 1]]))
        self.parcalar = {}
        for ad, hs in self.halkalar.items():
            a = np.vstack([h for h in hs])
            b2 = np.vstack([np.roll(h, -1, axis=0) for h in hs])
            self.parcalar[ad] = (a[:, 0], a[:, 1], b2[:, 0], b2[:, 1])

    def _icinde(self, ad, x, y):
        ic = np.zeros(x.size, bool)
        for h in self.halkalar[ad]:
            x1, y1 = h[:, 0], h[:, 1]
            x2, y2 = np.roll(x1, -1), np.roll(y1, -1)
            s = (x >= x1.min()) & (x <= x1.max()) & (y >= y1.min()) & (y <= y1.max())
            idx = np.flatnonzero(s)
            if idx.size == 0:
                continue
            px, py = x[idx][:, None], y[idx][:, None]
            gecis = ((y1 > py) != (y2 > py)) & (px < (x2 - x1) * (py - y1) / np.where(y2 == y1, 1, y2 - y1) + x1)
            ic[idx] ^= (gecis.sum(axis=1) % 2 == 1)
        return ic

    def _uzaklik(self, ad, x, y):
        ax, ay, bx, by = self.parcalar[ad]
        dx, dy = bx - ax, by - ay
        uz2 = np.where(dx * dx + dy * dy == 0, 1, dx * dx + dy * dy)
        en = np.full(x.size, np.inf)
        adim = 400
        for i in range(0, x.size, adim):
            px, py = x[i:i + adim, None], y[i:i + adim, None]
            t = np.clip(((px - ax) * dx + (py - ay) * dy) / uz2, 0, 1)
            d = np.hypot(px - (ax + t * dx), py - (ay + t * dy))
            en[i:i + adim] = d.min(axis=1)
        return en

    def ata(self, enlem, boylam):
        enlem, boylam = np.atleast_1d(np.asarray(enlem, float)), np.atleast_1d(np.asarray(boylam, float))
        sonuc = np.full(enlem.size, None, dtype=object)
        if enlem.size == 0:
            return sonuc
        x, y = boylam * self.KOS, enlem
        for ad in self.adlar:
            ic = self._icinde(ad, x, y)
            sonuc[ic & (sonuc == None)] = ad  # noqa: E711 (nesne dizisi: eleman karşılaştırması)
        kalan = np.flatnonzero(sonuc == None)  # noqa: E711
        if kalan.size:
            uz = np.vstack([self._uzaklik(ad, x[kalan], y[kalan]) for ad in self.adlar])
            enk = uz.argmin(axis=0)
            yakin = uz.min(axis=0) <= self.tampon
            for j, i in enumerate(kalan):
                if yakin[j]:
                    sonuc[i] = self.adlar[enk[j]]
        return sonuc


def _tablo(sonuc):
    """{T: {M: (o, a, u)}} → JSON: {'10': {'6': [o, a, u]}}."""
    return {str(t): {str(int(m)): [round(float(v), 4) for v in d] for m, d in mm.items()} for t, mm in sonuc.items()}


# ---------- uzun katalog (Mw ≥ 6, USGS 1900–): data/tarihte-bugun.json ----------
# Aynı USGS FDSN kaydı (Türkiye çevresi kutusu 35,5–42,5 K, 25,5–45 D, Mw ≥ 6, 1900–bugün; scripts/kart/veri-hazirla.mjs
# --tarihte-bugun) K12 kartıyla ortak olduğundan yeniden indirilmez; dosya depoda. Mw ≥ 6–7 olasılığı bu kayıttan doğrudan sayımla
# (λ = olay / yıl) hesaplanır: 8,8 yıllık EMSC kaydının G–R uzatması büyük depremleri hafife alıyordu.
# Kümelenme: Gardner & Knopoff (1974) pencereleri (en yakın komşu Mw ≥ 6'da, yaklaşık 125 olayda güvenilir değil).

def uzun_katalog_yukle(yol=TARIHTE_BUGUN):
    """data/tarihte-bugun.json → {'z' (UTC ms), 'e', 'bo', 'm'}; kayıtlardaki saat Türkiye yerel saati (UTC+3)."""
    with open(yol, encoding='utf-8') as f:
        k = json.load(f)
    z = np.array([datetime.fromisoformat(f"{o['t']}T{o['s']}:00").replace(tzinfo=UTC).timestamp() * 1000 - 3 * 3600_000 for o in k])
    return {'z': z, 'e': np.array([o['enlem'] for o in k], float), 'bo': np.array([o['boylam'] for o in k], float),
            'm': np.array([o['mw'] for o in k], float)}


def gk_pencere(m):
    """Gardner–Knopoff (1974): (yarıçap km, süre gün) = (10^(0,1238 M + 0,983), 10^(0,032 M + 2,7389) M ≥ 6,5 / 10^(0,5409 M − 0,547))."""
    km = 10 ** (0.1238 * m + 0.983)
    gun = 10 ** (0.032 * m + 2.7389) if m >= 6.5 else 10 ** (0.5409 * m - 0.547)
    return km, gun


def gk_ayikla(z, e, bo, m):
    """Ana şok maskesi: büyükten küçüğe; kalan her olayın penceresindeki (±süre, ≤ yarıçap) daha küçük ya da eşit olaylar
    (ön/art şok) atılır. Atılmış olay yeni pencere açmaz."""
    z, e, bo, m = (np.asarray(x, float) for x in (z, e, bo, m))
    tut = np.ones(z.size, bool)
    for i in np.argsort(-m, kind='stable'):
        if not tut[i]:
            continue
        km, gun = gk_pencere(m[i])
        yakin = (np.abs(z - z[i]) <= gun * 86_400_000) & (mesafe_km(e[i], bo[i], e, bo) <= km) & (m <= m[i])
        yakin[i] = False
        tut[yakin & tut] = False
    return tut


def _sayim_blogu(uk, atayici, simdi_ms, T=T_LISTE, n_boot=BOOTSTRAP, tohum=0):
    """Uzun katalogdan Türkiye (bölgelerin birleşimi) ve bölge olasılıkları: {'turkiye': {T: {M: (o, a, u)}}, 'bolgeler': {ad: …}, 'bilgi'}.
    λ(Mw ≥ 6) = 1930'dan, λ(Mw ≥ 7) = 1900'den bu yana Gardner–Knopoff ile ayıklanmış olay / yıl; aralık: olaylar üstünde
    Poisson bootstrap (Türkiye ve bölgeler ortak çekim), %10 / %90."""
    z, e, bo, m = uk['z'], uk['e'], uk['bo'], uk['m']
    tut = gk_ayikla(z, e, bo, m)
    adlar = atayici.ata(e, bo)
    iceride = np.array([x is not None for x in adlar], bool)
    rng = np.random.default_rng(tohum)
    sonuc_tr, sonuc_bol = {t: {} for t in T}, {ad: {t: {} for t in T} for ad in atayici.adlar}
    bilgi = {'yontem': 'gardner-knopoff', 'kaynak': 'USGS FDSN', 'toplam': int(z.size), 'ayiklanan': int((~tut).sum())}
    n_bolge = {}
    secilen = np.zeros(z.size, bool)
    for esik, bas in ((6.0, M6_BAS), (7.0, M7_BAS)):
        bas_ms = datetime(bas, 1, 1, tzinfo=UTC).timestamp() * 1000
        s = tut & iceride & (m >= esik - EPS) & (z >= bas_ms) & (z < simdi_ms)
        yil = (simdi_ms - bas_ms) / YIL_MS
        secilen |= s
        et = adlar[s]
        n = int(s.sum())
        bilgi[f'n{int(esik)}'] = n
        bilgi[f'bas{int(esik)}'] = bas
        bilgi[f'yil{int(esik)}'] = round(yil, 2)
        w = rng.poisson(1.0, (n_boot, n)) if n else np.zeros((n_boot, 0), int)
        gruplar = [(None, np.ones(n, bool))] + [(ad, et == ad) for ad in atayici.adlar]
        for ad, mk in gruplar:
            lam0 = mk.sum() / yil
            lam_b = w[:, mk].sum(axis=1) / yil
            if ad is not None:
                n_bolge.setdefault(ad, {})[int(esik)] = int(mk.sum())
            for t in T:
                orta = 1 - math.exp(-lam0 * t)
                alt, ust = np.percentile(1 - np.exp(-lam_b * t), [10, 90])
                v = (orta, min(float(alt), orta), max(float(ust), orta))
                (sonuc_tr if ad is None else sonuc_bol[ad])[t][esik] = v
    bilgi['bolgeN'] = n_bolge
    # Kartta çizilen bağımsız Mw ≥ 6 (1930–) ve Mw ≥ 7 (1900–) merkez üsleri: gerçekleşmiş kayıt, olasılık değil
    bilgi['olaylar'] = [[round(float(e[i]), 2), round(float(bo[i]), 2), round(float(m[i]), 1),
                         (datetime(1970, 1, 1, tzinfo=UTC) + timedelta(milliseconds=float(z[i]))).year] for i in np.flatnonzero(secilen)]
    return {'turkiye': sonuc_tr, 'bolgeler': sonuc_bol, 'bilgi': bilgi}


def _aralik(lam0, b0, lam_b, b_b, mc, T, M):
    sonuc = {t: {} for t in T}
    for t in T:
        for m in M:
            orta = float(olasilik(lam0, mc, b0, m, t))
            alt, ust = np.percentile(olasilik(lam_b, mc, b_b, m, t), [10, 90])
            sonuc[t][m] = (orta, min(float(alt), orta), max(float(ust), orta))
    return sonuc


def uzun_donem_ortak(mw, bolge, yil, mc, b_tr, bolgeler, b_bolge, T=T_LISTE, M=M_LISTE, n_boot=BOOTSTRAP, tohum=0):
    """Türkiye ve bütün bölgeler için ORTAK bootstrap: her çekimde Türkiye kataloğu bir kez (Poisson ağırlık) örneklenir;
    Türkiye λ, b ve her bölgenin λ'sı o çekimden türer. b_bolge: {ad: kendi_b ya da None}; None olan bölge çekimin
    Türkiye b'sini kullanır, kendi b'si olan bölgenin b'si çekimdeki bölge olaylarından yeniden hesaplanır.
    → ({T: {M: (orta, alt, ust)}}, {ad: {T: {M: …}}})."""
    k = kutula(np.asarray(mw, float), DM)
    bolge = np.asarray(bolge, dtype=object)
    n = k.size
    rng = np.random.default_rng(tohum)
    maske = {ad: bolge == ad for ad in bolgeler}
    lam_tr, b_trb = np.empty(n_boot), np.full(n_boot, float(b_tr))
    lam_b = {ad: np.empty(n_boot) for ad in bolgeler}
    b_b = {ad: np.full(n_boot, float(b_bolge[ad] if b_bolge[ad] is not None else b_tr)) for ad in bolgeler}
    adim = max(1, min(n_boot, 2_000_000 // max(n, 1)))

    def bhesap(w, m_, varsayilan):
        with np.errstate(divide='ignore', invalid='ignore'):
            toplam = w.sum(axis=1)
            bb = LOG10E / ((w @ m_) / toplam - (mc - DM / 2))
        return np.where(toplam > 0, np.clip(bb, *B_ARALIK), varsayilan)

    for bas in range(0, n_boot, adim):
        c = min(adim, n_boot - bas)
        w = rng.poisson(1.0, (c, n)) if n else np.zeros((c, 0), int)
        sl = slice(bas, bas + c)
        lam_tr[sl] = w.sum(axis=1) / yil
        if n:
            b_trb[sl] = bhesap(w, k, b_tr)
        for ad in bolgeler:
            wr = w[:, maske[ad]]
            lam_b[ad][sl] = wr.sum(axis=1) / yil
            b_b[ad][sl] = bhesap(wr, k[maske[ad]], b_trb[sl]) if b_bolge[ad] is not None and wr.shape[1] else b_trb[sl]
    tr = _aralik(n / yil, b_tr, lam_tr, b_trb, mc, T, M)
    bol = {ad: _aralik(maske[ad].sum() / yil, b_bolge[ad] if b_bolge[ad] is not None else b_tr, lam_b[ad], b_b[ad], mc, T, M)
           for ad in bolgeler}
    return tr, bol


def uzun_donem_blogu(z, e, bo, m, bagimsiz, simdi_ms, atayici=None, n_boot=BOOTSTRAP, mc=None, b=None, tohum=0, uzun=None):
    """kart-veri.json 'uzunDonem' bloğu. z/e/bo/m: EMSC Türkiye kataloğu (yalnız Mw ≥ 5 satırı ve b için), bagimsiz: kümelenmesi
    ayrılmış maske. Mw ≥ 6 ve ≥ 7 satırları uzun USGS kaydından (uzun: uzun_katalog_yukle() biçimi; yoksa data/tarihte-bugun.json)."""
    z, e, bo, m = (np.asarray(x, float) for x in (z, e, bo, m))
    bagimsiz = np.asarray(bagimsiz, bool)
    if mc is None:
        mc, _ = mc_egitim(z, m)
    if b is None:
        b, _ = bolgesel_b(m, bagimsiz, mc)   # Türkiye içi olaylar bulunursa aşağıda onlardan yeniden hesaplanır
    atayici = atayici or BolgeAtayici()
    bas = max(float(z.min()), YARDIMCI_BAS.timestamp() * 1000)
    yil = (simdi_ms - bas) / YIL_MS
    s = bagimsiz & (kutula(m, DM) >= mc - EPS) & (z >= bas) & (z < simdi_ms) & kutuda(e, bo)
    mw = m[s]
    adlar = atayici.ata(e[s], bo[s])
    # Türkiye geneli = altı bölgenin birleşimi (sınır + 30 km kıyı tamponu); EMSC kutusunun geri kalanı (Yunanistan, Kafkaslar…) sayılmaz
    iceride = np.array([x is not None for x in adlar], bool)
    mw, adlar = mw[iceride], adlar[iceride]
    if mw.size:
        ham, _ = b_aki_utsu(mw, mc, DM)
        b = float(ham) if math.isfinite(ham) and B_ARALIK[0] <= ham <= B_ARALIK[1] else b
    kendi = {}
    for ad in atayici.adlar:
        mw_b = mw[adlar == ad]
        kendi[ad] = None
        if mw_b.size >= BOLGE_B_EN_AZ:
            ham, _ = b_aki_utsu(mw_b, mc, DM)
            if math.isfinite(ham) and B_ARALIK[0] <= ham <= B_ARALIK[1]:
                kendi[ad] = float(ham)
    tr, bol = uzun_donem_ortak(mw, adlar, yil, mc, b, atayici.adlar, kendi, M=(5.0,), n_boot=n_boot, tohum=tohum)
    sayim = _sayim_blogu(uzun if uzun is not None else uzun_katalog_yukle(), atayici, simdi_ms, n_boot=n_boot, tohum=tohum)
    bilgi = sayim['bilgi']
    for t in T_LISTE:
        tr[t].update(sayim['turkiye'][t])
    return {
        'surum': SURUM, 'hesap': int(simdi_ms), 'baslangic': int(bas), 'bitis': int(simdi_ms), 'yil': round(yil, 3),
        'mc': float(mc), 'kumeleme': 'en-yakin-komsu', 'bootstrap': n_boot,
        'uzunKatalog': {k: v for k, v in bilgi.items() if k != 'bolgeN'},   # olaylar: kartta çizilen merkez üsleri
        'turkiye': {'ad': 'Türkiye (kıyıdan 30 km dahil)', 'n': int(mw.size), 'nEmsc': int(mw.size), 'n6': bilgi['n6'], 'n7': bilgi['n7'],
                    'b': round(float(b), 3), 'olasilik': _tablo(tr)},
        'bolgeler': [{
            'ad': ad, 'n': bilgi['bolgeN'][ad][6], 'n7': bilgi['bolgeN'][ad][7], 'nEmsc': int((adlar == ad).sum()),
            'olasilik': _tablo(sayim['bolgeler'][ad]),
        } for ad in atayici.adlar],
    }


def ana(argv=None):
    """Elle/ayrı çalıştırma: önbellekteki Türkiye kataloğundan kümelemeyi yeniden yapar, kart-veri.json 'uzunDonem' yazar."""
    for akis in (sys.stdout, sys.stderr):
        if hasattr(akis, 'reconfigure'):
            akis.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='tertremo uzun dönem olasılık (Kart 19)')
    ap.add_argument('--onbellek', default=os.path.join(os.path.dirname(__file__), '.onbellek'))
    ap.add_argument('--kart-veri', default=None)
    ap.add_argument('--n', type=int, default=BOOTSTRAP)
    a = ap.parse_args(argv)
    simdi = datetime.now(UTC).replace(microsecond=0).timestamp() * 1000
    olaylar = sorted((o for o in kat.yukle(os.path.join(a.onbellek, 'tr.csv.gz')) if o['zaman_ms'] < simdi), key=lambda o: o['zaman_ms'])
    if not olaylar:
        print('HATA: önbellekte Türkiye kataloğu yok', file=sys.stderr)
        return 1
    z = np.array([o['zaman_ms'] for o in olaylar], float)
    e = np.array([o['enlem'] for o in olaylar], float)
    bo = np.array([o['boylam'] for o in olaylar], float)
    m = np.array([o['mw'] for o in olaylar], float)
    bagimsiz, _ = kumele(z, e, bo, m)
    blok = uzun_donem_blogu(z, e, bo, m, bagimsiz, simdi, n_boot=a.n)
    kartveri.yaz(a.kart_veri or os.path.join(a.onbellek, 'kart-veri.json'), 'uzunDonem', blok)
    t = blok['turkiye']
    print(f"uzunDonem: Mc {blok['mc']}, n {t['n']}, b {t['b']}, 10 yılda Mw≥6 {t['olasilik']['10']['6']}")
    return 0


if __name__ == '__main__':
    sys.exit(ana())
