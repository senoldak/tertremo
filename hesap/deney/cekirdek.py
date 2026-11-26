# Gölge deney `cekirdek`: büyük depremden sonra artçıların uzamsal dağılımı için yuvarlak (izotropik) çekirdek mi,
# USGS moment tensörüne hizalı uzun (fay boyu) çekirdek mi daha iyi?
# Gerekçe: docs/literatur-taramasi-4-2026-11-26.md §3 (Mancini ve ark. 2020; Han ve ark. 2026 ön baskı).
# Canlı modele DOKUNMAZ: yalnız yerel katalog + USGS önbelleği okunur, sonuç hesap/.onbellek/deney/cekirdek.json'a yazılır.
#
# Yöntem özeti (rapor: docs/olcum-deney-cekirdek-2026-11.md):
#  - Uzamsal yoğunluk f(x) ∝ (r² + d²)^(−q), 300 km'lik disk içinde 1 km'lik ızgarada sayısal normalize
#    (r'nin ızgara histogramı üzerinden; ızgara yoğunluğa göre değil uzaklığa göre özetlendiği için hızlı).
#  - I: r = merkez üssüne uzaklık. E: r = strike boyunca L uzunluğunda, merkez üssünde ortalanmış doğru parçasına uzaklık.
#    E2: aynı, parça ilk 6 saatin artçı merkezinde ortalanmış.
#  - Düzlem seçimi nedensel: yalnız ilk 6 saatin artçıları (ana bileşen azimutu) kullanılır; sınanan artçılar [6 sa, 30 g].
#  - q ve d bir-dışarıda çapraz doğrulamayla (dizi bazında) öbür dizilerden uydurulur.
import argparse
import json
import math
import os
import time
from datetime import datetime, timezone

import numpy as np
from scipy.optimize import minimize

from hesap import katalog
from hesap.katalog import _getir

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TR_YOL = os.path.join(KOK, '.onbellek', 'tr.csv.gz')
DENEY_DIZIN = os.path.join(KOK, '.onbellek', 'deney')
MT_DIZIN = os.path.join(DENEY_DIZIN, 'usgs-mt')
CIKTI = os.path.join(DENEY_DIZIN, 'cekirdek.json')

SAAT_MS = 3600e3
GUN_MS = 24 * SAAT_MS
R_ALAN = 300.0          # km: ana şoktan en uzak artçı (görev tanımı)
ILK_SAAT = 6.0          # düzlem seçimi ve merkez için kullanılan ilk pencere
PENCERE_GUN = 30.0
KM_DERECE = 111.195     # 1° enlem ≈ km (src/geo.js'deki küre yarıçapı 6371 ile uyumlu)
HUCRE_KM = 1.0
BIN_KM = 0.25
MC_TABAN = 3.0          # max(Mc, 3,0): Mc eğitim dönemi MBS'si bulunamayıp MC_YEDEK=4,0'a düşüyor; birincil 3,0 (rapora bak)
EN_AZ_OLAY = 30         # pencerede en az bu kadar olay yoksa dizi dışı
EN_AZ_ILK = 8           # ilk 6 saatte en az bu kadar olay yoksa PCA/merkez güvenilmez, dizi dışı
RASTGELE_TEKRAR = 12    # rastgele-azimut kontrolü: dizi başına bağımsız çekim, 12 tekrar
USGS_URL = 'https://earthquake.usgs.gov/fdsnws/event/1/query'
# Wells & Coppersmith 1994, BSSA 84(4):974-1002, Tablo 2A: log10(RLD) = a + b·M (alt yüzey kırılma boyu, km).
# SS: −2,57 + 0,62·M (s=0,15); R: −2,42 + 0,58·M (s=0,16); N: −1,88 + 0,50·M (s=0,17); hepsi: −2,44 + 0,59·M (s=0,16).
# Yönlendirme: M üzerinden log L (L'yi M'den tahmin için doğru yön; "M = a + b log L" ters regresyon değil).
WC_RLD = {'SS': (-2.57, 0.62), 'R': (-2.42, 0.58), 'N': (-1.88, 0.50), 'ALL': (-2.44, 0.59)}

# Ana şok adayları: Mw≥5,8, Türkiye kutusu (enlem 35,5–42,5; boylam 26–44,4: İran sınırı ve Girit dışarıda).
ADAY_KUTU = {'minlat': 35.5, 'maxlat': 42.5, 'minlon': 26.0, 'maxlon': 44.4}
ADAY_MW = 5.8


# ---------- Geometri ----------

def yerel_xy(enlem, boylam, e0, b0):
    """Merkez üssünde ortalanmış yerel düzlem (km): x doğu, y kuzey. 300 km'de eşdikdörtgen yaklaşımı yeterli."""
    x = (np.asarray(boylam, float) - b0) * math.cos(math.radians(e0)) * KM_DERECE
    y = (np.asarray(enlem, float) - e0) * KM_DERECE
    return x, y


def parca_uzaklik(x, y, cx, cy, azimut, uzunluk):
    """(x, y) noktalarının, (cx, cy)'de ortalanmış, azimut (kuzeyden saat yönü, derece) doğrultusunda `uzunluk` km
    uzunluğundaki doğru parçasına en kısa uzaklığı (km). uzunluk=0 → noktaya uzaklık (izotropik)."""
    a = math.radians(azimut)
    ux, uy = math.sin(a), math.cos(a)
    dx, dy = np.asarray(x) - cx, np.asarray(y) - cy
    t = np.clip(dx * ux + dy * uy, -uzunluk / 2, uzunluk / 2)
    return np.hypot(dx - t * ux, dy - t * uy)


def acisal_fark(a, b):
    """İki azimutun (180° belirsiz) en küçük farkı, 0–90°."""
    f = abs(a - b) % 180.0
    return min(f, 180.0 - f)


def pca_azimut(x, y):
    """Noktaların ana bileşen ekseninin azimutu (kuzeyden saat yönü, 0–180°)."""
    c = np.cov(np.vstack([x, y]))
    w, v = np.linalg.eigh(c)
    vx, vy = v[0, 1], v[1, 1]       # en büyük özdeğerin vektörü
    return math.degrees(math.atan2(vx, vy)) % 180.0


def duzlem_sec(strikelar, pca_az):
    """İlk 6 saatin PCA azimutuna en yakın strike'lı düzlem: (seçilen, öbür, açısal fark)."""
    f = [acisal_fark(s, pca_az) for s in strikelar]
    i = int(np.argmin(f))
    return strikelar[i], strikelar[1 - i], f[i]


def kirilma_turu(rake):
    """Rake'ten faylanma türü (WC94 sınıfları): ±30° içinde doğrultu atımlı, +30…+150 ters, −30…−150 normal; arası hepsi."""
    r = (rake + 180.0) % 360.0 - 180.0
    if abs(r) <= 30 or abs(r) >= 150:
        return 'SS'
    if 30 < r < 150:
        return 'R'
    if -150 < r < -30:
        return 'N'
    return 'ALL'


def wc_uzunluk(mw, rake):
    """Alt yüzey kırılma boyu (km), Wells & Coppersmith 1994 Tablo 2A, faylanma türüne göre."""
    a, b = WC_RLD[kirilma_turu(rake)]
    return 10 ** (a + b * mw)


# ---------- USGS moment tensörü ----------

def _usgs_json(adres, yol):
    if os.path.exists(yol):
        with open(yol, encoding='utf-8') as f:
            return json.load(f)
    govde = _getir(adres)     # ≤ 2 istek/s sınırı katalog._getir içinde (ARALIK_S = 0,5)
    veri = json.loads(govde) if govde else {}
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, 'w', encoding='utf-8') as f:
        json.dump(veri, f)
    return veri


def _mt_sec(urunler):
    """Birden çok moment tensörü ürününden birini seç: us kaynağı, Mww > Mwc > Mwb > Mwr, yoksa ilki."""
    sira = ['mww', 'mwc', 'mwb', 'mwr']

    def puan(u):
        kod = (u.get('code') or '').lower()
        s = u.get('source', '')
        tur = next((i for i, t in enumerate(sira) if kod.endswith('_' + t)), len(sira))
        return (0 if s == 'us' else 1, tur)
    gecerli = [u for u in urunler if 'nodal-plane-1-strike' in u.get('properties', {})]
    return min(gecerli, key=puan) if gecerli else None


def usgs_mt(olay):
    """Katalog olayına karşılık gelen USGS olayının moment tensörü düğüm düzlemleri. Önbellek: usgs-mt/<id>.json.
    Dönüş: {'usgs_id','kaynak','kod','tur','duzlem':[(strike,dip,rake),(strike,dip,rake)]} ya da None."""
    kimlik = olay['id'].replace(':', '_')
    yol = os.path.join(MT_DIZIN, kimlik + '.json')
    t = datetime.fromtimestamp(olay['zaman_ms'] / 1000, tz=timezone.utc)
    pen = (t.timestamp() - 600, t.timestamp() + 600)
    f = lambda s: datetime.fromtimestamp(s, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
    adres = (f'{USGS_URL}?format=geojson&starttime={f(pen[0])}&endtime={f(pen[1])}&minmagnitude={olay["mw"] - 1.0:.1f}'
             f'&latitude={olay["enlem"]}&longitude={olay["boylam"]}&maxradiuskm=150&orderby=magnitude&limit=3')
    ara = _usgs_json(adres, yol)
    ozellik = (ara.get('features') or [])
    if not ozellik:
        return None
    detay_yol = os.path.join(MT_DIZIN, kimlik + '-detay.json')
    detay = _usgs_json(ozellik[0]['properties']['detail'], detay_yol)
    urun = _mt_sec((detay.get('properties', {}).get('products') or {}).get('moment-tensor') or [])
    if not urun:
        return None
    p = urun['properties']
    duzlem = [(float(p[f'nodal-plane-{i}-strike']), float(p[f'nodal-plane-{i}-dip']), float(p[f'nodal-plane-{i}-rake']))
              for i in (1, 2)]
    return {'usgs_id': ozellik[0]['id'], 'kaynak': urun.get('source'), 'kod': urun.get('code'),
            'tur': p.get('derived-magnitude-type'), 'mw_usgs': float(p.get('derived-magnitude', 'nan')),
            'duzlem': duzlem}


# ---------- Dizi seçimi ----------

def katalog_diziler(olaylar):
    z = np.array([o['zaman_ms'] for o in olaylar], float)
    e = np.array([o['enlem'] for o in olaylar], float)
    b = np.array([o['boylam'] for o in olaylar], float)
    m = np.array([o['mw'] for o in olaylar], float)
    return z, e, b, m


def ana_sok_adaylari(olaylar, kutu=ADAY_KUTU, mw_alt=ADAY_MW):
    """Mw ≥ 5,8 ve kutuda olan, önceki 30 günde 300 km içinde daha büyük olayı olmayan olaylar (bağımlı sarsıntıları atar:
    Hatay 2023-02-20 gibi). Dönüş: katalog indeksleri, zaman sırasıyla."""
    z, e, b, m = katalog_diziler(olaylar)
    sonuc = []
    for i in np.where(m >= mw_alt)[0]:
        if not (kutu['minlat'] <= e[i] <= kutu['maxlat'] and kutu['minlon'] <= b[i] <= kutu['maxlon']):
            continue
        x, y = yerel_xy(e, b, e[i], b[i])
        yakin = np.hypot(x, y) <= R_ALAN
        once = (z < z[i]) & (z >= z[i] - PENCERE_GUN * GUN_MS) & yakin & (m > m[i])
        # aynı dakika içindeki eşit/daha büyük tek bir "ön şok" varsa onu ana şok say; yalnız bağımlıları ele
        if once.any():
            continue
        sonuc.append(int(i))
    return sonuc


def olay_kumesi(olaylar, i, mc, bas_ms, bit_ms, hariç=()):
    """Ana şok i'nin yerel düzleminde, zaman penceresi (bas_ms, bit_ms] içinde, Mw ≥ mc, ≤ 300 km olaylar."""
    z, e, b, m = katalog_diziler(olaylar)
    x, y = yerel_xy(e, b, e[i], b[i])
    dz = z - z[i]
    s = (dz > bas_ms) & (dz < bit_ms) & (m >= mc) & (np.hypot(x, y) <= R_ALAN)
    for h in hariç:
        s[h] = False
    return x[s], y[s], np.where(s)[0]


# ---------- Çekirdek yoğunluğu ----------

def izgara_xy(yaricap=R_ALAN, hucre=HUCRE_KM):
    """Merkez üssünde ortalanmış disk içindeki ızgara hücre merkezleri (km)."""
    n = int(math.ceil(yaricap / hucre))
    c = (np.arange(-n, n) + 0.5) * hucre
    gx, gy = np.meshgrid(c, c)
    s = np.hypot(gx, gy) <= yaricap
    return gx[s], gy[s]


class Bilesen:
    """Tek kaynak için bir çekirdek: ızgaradaki r değerlerinin histogramı (normalizasyon) + olayların r'leri."""

    def __init__(self, r_izgara, r_olay, agirlik=1.0, uzunluk=0.0):
        n = int(math.ceil(max(r_izgara.max(), r_olay.max() if r_olay.size else 0) / BIN_KM)) + 1
        idx = np.minimum((r_izgara / BIN_KM).astype(int), n - 1)
        sayi = np.bincount(idx, minlength=n).astype(float)
        topla = np.bincount(idx, weights=r_izgara, minlength=n)
        dolu = sayi > 0
        self.r_bin = topla[dolu] / sayi[dolu]
        self.sayi = sayi[dolu]
        self.r_olay = r_olay
        self.w = agirlik
        self.L = uzunluk


def log_yogunluk(bilesenler, q, d, d_olcekli=False):
    """Olay başına log f(x_i): bileşenlerin ağırlıklı karışımı, her bileşen kendi ızgara toplamıyla normalize
    (km⁻² cinsinden; ızgara hücre alanı karşılaştırmada sadeleşir)."""
    toplam_w = sum(b.w for b in bilesenler)
    parcalar = []
    for b in bilesenler:
        dd = d * b.L if d_olcekli else d
        z = float(np.sum(b.sayi * (b.r_bin ** 2 + dd ** 2) ** (-q)))
        parcalar.append(math.log(b.w / toplam_w) - math.log(z) - q * np.log(b.r_olay ** 2 + dd ** 2))
    if len(parcalar) == 1:
        return parcalar[0]
    return np.logaddexp.reduce(np.vstack(parcalar), axis=0)


def uydur(diziler, degisken, d_olcekli):
    """Dizilerin (dizi başına ortalama log-olabilirliğin ortalaması; her dizi eşit ağırlık) en büyük yapan (q, d).
    Başlangıçlar birkaç; sınırlar: q ∈ [0,3; 4], d ∈ [1; 100] km (ölçekli kipte d/L ∈ [0,003; 3])."""
    d_alt, d_ust = (0.003, 3.0) if d_olcekli else (1.0, 100.0)

    def amac(p):
        q, ld = p
        return -float(np.mean([np.mean(log_yogunluk(s['degisken'][degisken], q, math.exp(ld), d_olcekli)) for s in diziler]))
    en = None
    for q0, d0 in ((1.5, 5.0), (1.0, 20.0), (2.5, 2.0)):
        d0 = d0 / 100.0 if d_olcekli else d0
        d0 = min(max(d0, d_alt * 1.01), d_ust * 0.99)
        s = minimize(amac, [q0, math.log(d0)], method='L-BFGS-B',
                     bounds=[(0.3, 4.0), (math.log(d_alt), math.log(d_ust))])
        if en is None or s.fun < en.fun:
            en = s
    return float(en.x[0]), float(math.exp(en.x[1])), -float(en.fun)


# ---------- Dizi kurma ----------

def dizi_kur(olaylar, i_ana, mc, adi, bit_gun=PENCERE_GUN, bit_ms=None, ikinci=None, rastgele_tohum=0, ek=False):
    """Bir dizinin bütün çekirdek değişkenleri (I, E, Ediger, E2, EPCA, Erast0…).
    bit_ms: pencere bitişi (dizi başlangıcına göre ms; Kahramanmaraş-A için ikinci şoktan önce). ikinci: Kahramanmaraş-B için
    ikinci ana şokun katalog indeksi (iki bileşenli karışım). ek: eşikleri gevşet (≥10 olay, PCA yok) ve yalnız I ile iki
    düzlemi ayrı ayrı (Ed0, Ed1) kur; ana kümeye giremeyen diziler (Düzce vb.) için. Dönüş: (dict, None) ya da (None, neden)."""
    ana = olaylar[i_ana]
    bit = bit_ms if bit_ms is not None else bit_gun * GUN_MS
    hariç = [ikinci] if ikinci is not None else []
    x6, y6, _ = olay_kumesi(olaylar, i_ana, mc, 0.0, ILK_SAAT * SAAT_MS)
    x, y, _ = olay_kumesi(olaylar, i_ana, mc, ILK_SAAT * SAAT_MS, bit, hariç=hariç)
    en_az, en_az6 = (10, 0) if ek else (EN_AZ_OLAY, EN_AZ_ILK)
    if len(x) < en_az:
        return None, f'pencerede {len(x)} olay (< {en_az})'
    if len(x6) < en_az6:
        return None, f'ilk 6 saatte {len(x6)} olay (< {en_az6})'
    mt = usgs_mt(ana)
    if mt is None:
        return None, 'USGS moment tensörü yok'
    kaynaklar = [(ana, i_ana, x6, y6, mt, 0.0, 0.0, 1.0)]
    if ikinci is not None:
        o2 = olaylar[ikinci]
        z, e, b, m = katalog_diziler(olaylar)
        # ikinci şokun ilk 6 saati: ikinci şoka 100 km içinde ve ona birinci şoktan daha yakın olaylar
        x2, y2 = yerel_xy(e, b, o2['enlem'], o2['boylam'])
        x1, y1 = yerel_xy(e, b, ana['enlem'], ana['boylam'])
        dz = z - o2['zaman_ms']
        s = (dz > 0) & (dz < ILK_SAAT * SAAT_MS) & (m >= mc) & (np.hypot(x2, y2) <= 100) & (np.hypot(x2, y2) < np.hypot(x1, y1))
        mt2 = usgs_mt(o2)
        if mt2 is None or s.sum() < EN_AZ_ILK:
            return None, 'ikinci şok için MT ya da ilk 6 saat yetersiz'
        # ikinci şokun yerel koordinatları ana şoka göre
        ox, oy = yerel_xy(o2['enlem'], o2['boylam'], ana['enlem'], ana['boylam'])
        kaynaklar.append((o2, ikinci, x1[s], y1[s], mt2, float(ox), float(oy), None))
    gx, gy = izgara_xy()
    # ağırlık: 10^Mw (log10 üretkenlik α ≈ 1)
    agirliklar = [10 ** k[0]['mw'] for k in kaynaklar]
    rng = np.random.default_rng([rastgele_tohum, int(ana['zaman_ms']) % 1_000_003])
    bilgi = []
    # bileşen başına: (epi_xy, L, azimut_sec, azimut_diger, pca, merkez6)
    for (o, _, xs, ys, mt, ox, oy, _w) in kaynaklar:
        strike = [d[0] for d in mt['duzlem']]
        L_dz = [wc_uzunluk(o['mw'], d[2]) for d in mt['duzlem']]
        if len(xs) >= 3:
            pca = pca_azimut(xs, ys)      # öteleme değişmez: xs, ys hangi çerçevede olursa olsun
            sec, diger, fark = duzlem_sec(strike, pca)
            merkez = (float(np.mean(xs)), float(np.mean(ys)))
        else:
            pca, sec, diger, fark, merkez = math.nan, strike[0], strike[1], math.nan, (ox, oy)
        i_sec = strike.index(sec)
        bilgi.append({'ox': ox, 'oy': oy, 'L': L_dz[i_sec], 'L_diger': L_dz[1 - i_sec], 'L_dz': L_dz, 'sec': sec,
                      'diger': diger, 'pca': pca, 'fark': fark, 'merkez': merkez,
                      'tur': kirilma_turu(mt['duzlem'][i_sec][2]), 'mw': o['mw'], 'strike': strike, 'id': o['id'],
                      'mt': mt, 'n_ilk6': int(len(xs))})

    def bilesenler(az_fn, merkez_fn, uz_fn=lambda b: b['L']):
        """d ölçekli kipte her varyant aynı referans L'yi (seçilen düzlemin WC uzunluğu) kullanır."""
        out = []
        for b, w in zip(bilgi, agirliklar):
            cx, cy = merkez_fn(b)
            uz = uz_fn(b)
            r_iz = parca_uzaklik(gx, gy, cx, cy, az_fn(b), uz) if uz > 0 else np.hypot(gx - cx, gy - cy)
            r_ol = parca_uzaklik(x, y, cx, cy, az_fn(b), uz) if uz > 0 else np.hypot(x - cx, y - cy)
            out.append(Bilesen(r_iz, r_ol, w, b['L']))
        return out
    epi = lambda b: (b['ox'], b['oy'])
    degisken = {
        'I': bilesenler(lambda b: 0.0, epi, uz_fn=lambda b: 0.0),
    }
    if not ek:
        degisken['E'] = bilesenler(lambda b: b['sec'], epi)
    if ek:
        # düzlem seçimi yok: iki düzlem ayrı ayrı, her biri kendi WC uzunluğuyla
        for k in (0, 1):
            degisken[f'Ed{k}'] = bilesenler(lambda b, k=k: b['strike'][k], epi, uz_fn=lambda b, k=k: b['L_dz'][k])
    else:
        degisken['Ediger'] = bilesenler(lambda b: b['diger'], epi, uz_fn=lambda b: b['L_diger'])
        degisken['E2'] = bilesenler(lambda b: b['sec'], lambda b: b['merkez'])
        degisken['I2'] = bilesenler(lambda b: 0.0, lambda b: b['merkez'], uz_fn=lambda b: 0.0)   # E2'nin izotropik karşılığı
        degisken['E2diger'] = bilesenler(lambda b: b['diger'], lambda b: b['merkez'], uz_fn=lambda b: b['L_diger'])
        degisken['EPCA'] = bilesenler(lambda b: b['pca'], epi)     # MT'siz kontrol: yalnız ilk 6 saatin PCA azimutu
        degisken['E2PCA'] = bilesenler(lambda b: b['pca'], lambda b: b['merkez'])
        for j in range(RASTGELE_TEKRAR):
            rast = {id(b): rng.uniform(0, 180) for b in bilgi}
            degisken[f'Erast{j}'] = bilesenler(lambda b, r=rast: r[id(b)], epi)
            degisken[f'E2rast{j}'] = bilesenler(lambda b, r=rast: r[id(b)], lambda b: b['merkez'])
    return {'adi': adi, 'degisken': degisken, 'n': int(len(x)), 'olay_xy': (x, y), 'bilgi': bilgi,
            'ana': {'id': ana['id'], 'zaman_ms': ana['zaman_ms'], 'enlem': ana['enlem'], 'boylam': ana['boylam'],
                    'mw': ana['mw']}}, None


# ---------- Çapraz doğrulama ve ölçüt ----------

def bir_disarida(diziler, degisken, d_olcekli):
    """Her dizi için öbürlerinden uydurulan (q, d) ile olay başına log-olabilirlik. Dönüş: {dizi_adi: (q, d, logf dizisi)}."""
    sonuc = {}
    for s in diziler:
        egitim = [t for t in diziler if t is not s]
        q, d, _ = uydur(egitim, degisken, d_olcekli)
        sonuc[s['adi']] = (q, d, log_yogunluk(s['degisken'][degisken], q, d, d_olcekli))
    return sonuc


def bootstrap_ci(deger_listesi, rng, b=2000):
    """Olay bazında bootstrap: her dizinin olay farkları kendi içinde yeniden örneklenir; birleşik = dizi ortalamalarının
    ortalaması (her dizi eşit) ve olay ağırlıklı ortalama. Dönüş: {dizi: (alt, üst), 'dizi_ort': (...), 'olay_agirlikli': (...)}."""
    dizi_ort = np.zeros((b, len(deger_listesi)))
    toplam = np.zeros(b)
    n_top = sum(len(v) for v in deger_listesi)
    for j, v in enumerate(deger_listesi):
        idx = rng.integers(0, len(v), size=(b, len(v)))
        ort = v[idx].mean(axis=1)
        dizi_ort[:, j] = ort
        toplam += ort * len(v)
    pct = lambda a: [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]
    return [pct(dizi_ort[:, j]) for j in range(len(deger_listesi))], pct(dizi_ort.mean(axis=1)), pct(toplam / n_top)


def dizi_bootstrap_ci(dizi_ortalamalari, rng, b=10000):
    """Dizi düzeyinde bootstrap (diziler yeniden örneklenir): olaylar kümelendiği için olay bootstrap'inden dürüst."""
    a = np.asarray(dizi_ortalamalari, float)
    idx = rng.integers(0, len(a), size=(b, len(a)))
    o = a[idx].mean(axis=1)
    return [float(np.percentile(o, 2.5)), float(np.percentile(o, 97.5))]


def isaret_testi(a):
    """Dizi farklarının işaret testi (iki yönlü, binom p=0,5)."""
    a = np.asarray(a)
    n, k = int((a != 0).sum()), int((a > 0).sum())
    if n == 0:
        return 1.0
    from scipy.stats import binomtest
    return float(binomtest(k, n, 0.5).pvalue)


# (değişken, taban): E−I nedensel düzlemin merkez üssü çevresindeki katkısı; I2−I yalnız merkez kayması; E2−I2 merkezi
# sabitleyip uzamayı yalıtır; E2−I bütün paket.
KIYASLAR = [('E', 'I'), ('Ediger', 'I'), ('EPCA', 'I'), ('Erast', 'I'), ('I2', 'I'),
            ('E2', 'I2'), ('E2diger', 'I2'), ('E2rast', 'I2'), ('E2', 'I'), ('E2PCA', 'I2'), ('E2', 'E2PCA')]


def degerlendir(diziler, d_olcekli, rng):
    """Bütün değişkenleri bir-dışarıda ile (q, d) uydurup KIYASLAR'daki tabanlarla kıyasla. Dönüş: sözlük
    (tam uyum, dizi tablosu, birleşik)."""
    adlar = ('I', 'E', 'Ediger', 'EPCA', 'I2', 'E2', 'E2diger', 'E2PCA')
    cv = {v: bir_disarida(diziler, v, d_olcekli) for v in adlar}
    for j in range(RASTGELE_TEKRAR):
        for on in ('Erast', 'E2rast'):
            cv[f'{on}{j}'] = bir_disarida(diziler, f'{on}{j}', d_olcekli)
    cikti = {'tam_uyum': {}, 'karsilastirma': {}, 'cv_parametreler': {}}
    for v in adlar:
        q, d, ll = uydur(diziler, v, d_olcekli)
        cikti['tam_uyum'][v] = {'q': q, 'd': d, 'ort_loglik': ll}
    ad = [s['adi'] for s in diziler]

    def olay_logf(v, s):
        """Değişken (rastgele ise 12 tekrarın olay başına ortalaması) için dizi s'nin olay başına log f'i."""
        if v in ('Erast', 'E2rast'):
            return np.mean([cv[f'{v}{j}'][s['adi']][2] for j in range(RASTGELE_TEKRAR)], axis=0)
        return cv[v][s['adi']][2]
    for v, taban in KIYASLAR:
        farklar = [olay_logf(v, s) - olay_logf(taban, s) for s in diziler]
        dizi_ci, birlesik_ci, agirlikli_ci = bootstrap_ci(farklar, rng)
        ort = [float(f.mean()) for f in farklar]
        cikti['karsilastirma'][f'{v}-{taban}'] = {
            'diziler': {a: {'n': int(len(f)), 'kazanc': o, 'ci': c} for a, f, o, c in zip(ad, farklar, ort, dizi_ci)},
            'dizi_ort': float(np.mean(ort)), 'dizi_ort_ci_olay': birlesik_ci,
            'birini_cikar': {a: float(np.mean(ort[:j] + ort[j + 1:])) for j, a in enumerate(ad)},   # tek diziye bağımlılık
            'dizi_ort_ci_dizi': dizi_bootstrap_ci(ort, rng),
            'olay_agirlikli': float(sum(f.sum() for f in farklar) / sum(len(f) for f in farklar)),
            'olay_agirlikli_ci': agirlikli_ci,
            'kazanan_dizi': int(sum(o > 0 for o in ort)), 'n_dizi': len(ort), 'isaret_p': isaret_testi(ort)}
    # rastgele azimut: 12 tekrarın her biri için birleşik dizi ortalaması (aynı olaylar, ayrı çekimler)
    for on, taban in (('Erast', 'I'), ('E2rast', 'I2')):
        tek = [float(np.mean([np.mean(cv[f'{on}{j}'][s['adi']][2] - cv[taban][s['adi']][2]) for s in diziler]))
               for j in range(RASTGELE_TEKRAR)]
        cikti['karsilastirma'][f'{on}-{taban}']['tekrarlar'] = {'ort': float(np.mean(tek)), 'min': min(tek), 'max': max(tek)}
    for v in adlar:
        cikti['cv_parametreler'][v] = {a: {'q': x[0], 'd': x[1]} for a, x in cv[v].items()}
    return cikti


def ek_degerlendir(dizi, tam_uyum, d_olcekli):
    """Ana kümeye girmeyen diziler (ör. Düzce): düzlemler seçimsiz, ayrı ayrı; (q, d) ana kümenin tam uyumundan
    (I için I'nın, çekirdekler için E'nin). Dönüş: olay başına ortalama kazanç, düzlem 0 ve 1."""
    li = log_yogunluk(dizi['degisken']['I'], tam_uyum['I']['q'], tam_uyum['I']['d'], d_olcekli)
    return {v: float(np.mean(log_yogunluk(dizi['degisken'][v], tam_uyum['E']['q'], tam_uyum['E']['d'], d_olcekli) - li))
            for v in ('Ed0', 'Ed1')}


# ---------- Ana akış ----------

def diziler_olustur(olaylar, mc, km_kip):
    """Aday ana şoklardan dizi kümesi. km_kip: 'A' (Kahramanmaraş 6–9,1 sa: ikinci şoktan önce kesik), 'B' (iki kaynaklı, 30 gün).
    Dönüş: (kullanılan diziler, dışlananlar [(ad, neden)])."""
    adaylar = ana_sok_adaylari(olaylar)
    diziler, disarida = [], []
    # Kahramanmaraş: ilk (7,8) ve ikinci (7,5) şok; 6,7 (11 dk sonra) ve 6,0'lar artçı sayılır
    km1 = next((i for i in adaylar if olaylar[i]['id'] == 'emsc:20230206_0000008'), None)
    km2 = next((i for i, o in enumerate(olaylar) if o['id'] == 'emsc:20230206_0000222'), None)
    for i in adaylar:
        o = olaylar[i]
        gun = datetime.fromtimestamp(o['zaman_ms'] / 1000, tz=timezone.utc).strftime('%Y-%m-%d')
        ad = f'{gun} Mw{o["mw"]:.1f} {o["yer"].title()[:22]}'
        if i == km1:
            if km_kip == 'A':
                d, neden = dizi_kur(olaylar, i, mc, ad, bit_ms=olaylar[km2]['zaman_ms'] - o['zaman_ms'])
            else:
                d, neden = dizi_kur(olaylar, i, mc, ad, ikinci=km2)
        else:
            d, neden = dizi_kur(olaylar, i, mc, ad)
        if d is None:
            disarida.append((ad, neden, i))
        else:
            diziler.append(d)
    return diziler, disarida


def kosu(mc, d_olcekli, km_kip, olaylar, rng, ek=True):
    """Bir koşu: dizileri kur, bir-dışarıda ile değerlendir, dışarıda kalanları ek olarak ölç."""
    t0 = time.time()
    diziler, disarida = diziler_olustur(olaylar, mc, km_kip)
    if len(diziler) < 3:
        return {'hata': f'yeterli dizi yok ({len(diziler)})', 'disarida': [(a, n) for a, n, _ in disarida]}
    sonuc = degerlendir(diziler, d_olcekli, rng)
    sonuc['mc'] = mc
    sonuc['d_kip'] = 'olcekli' if d_olcekli else 'sabit'
    sonuc['km_kip'] = km_kip
    sonuc['dizi_bilgi'] = [{
        'adi': s['adi'], 'n': s['n'], 'ana': s['ana'],
        'bilesenler': [{'id': b['id'], 'mw': b['mw'], 'L_km': b['L'], 'tur': b['tur'], 'strike': b['strike'],
                        'pca_azimut': b['pca'], 'sec': b['sec'], 'fark_derece': b['fark'], 'n_ilk6': b['n_ilk6'],
                        'merkez_km': b['merkez'], 'usgs': {k: b['mt'][k] for k in ('usgs_id', 'kaynak', 'kod', 'tur', 'mw_usgs', 'duzlem')}}
                       for b in s['bilgi']]} for s in diziler]
    sonuc['disarida'] = [(a, n) for a, n, _ in disarida]
    if ek:
        ek_s = {}
        for a, n, i in disarida:
            if 'USGS' in n:
                continue
            d, _ = dizi_kur(olaylar, i, mc, a, ek=True)
            if d is not None:
                ek_s[a] = {'n': d['n'], 'neden_disarida': n, 'kazanc': ek_degerlendir(d, sonuc['tam_uyum'], d_olcekli),
                           'strike': d['bilgi'][0]['strike'], 'L_km': d['bilgi'][0]['L_dz']}
        sonuc['ek'] = ek_s
    sonuc['sure_s'] = time.time() - t0
    return sonuc


def ana(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--hizli', action='store_true', help='yalnız birincil koşu, az bootstrap')
    a = ap.parse_args(argv)
    olaylar = katalog.yukle(TR_YOL)
    rng = np.random.default_rng(20261126)
    cikti = {'uretim': datetime.now(timezone.utc).isoformat(), 'kosular': {}}
    plan = [('birincil_A', 3.0, False, 'A'), ('km_B', 3.0, False, 'B')]
    if not a.hizli:
        plan += [('olcekli_d_A', 3.0, True, 'A'), ('mc35_A', 3.5, False, 'A'), ('mc40_A', 4.0, False, 'A')]  # mc40: dizi kalmaz, hata olarak raporlanır
    for ad, mc, olcekli, km in plan:
        print(ad, flush=True)
        cikti['kosular'][ad] = kosu(mc, olcekli, km, olaylar, rng)
        print(f"  {cikti['kosular'][ad].get('sure_s', 0):.0f} s", flush=True)
    os.makedirs(DENEY_DIZIN, exist_ok=True)
    with open(CIKTI, 'w', encoding='utf-8') as f:
        json.dump(cikti, f, ensure_ascii=False, indent=1, default=float)
    print('yazıldı', CIKTI)


if __name__ == '__main__':
    ana()
