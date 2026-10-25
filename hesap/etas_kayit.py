# ETAS ileriye dönük sınav kaydı (docs/etas-on-kayit.md). Kayıt D1 tablosu etas_kayit'te tutulur
# (Actions depoya yazmaz): hafta TEXT PRIMARY KEY, olusma INTEGER, tahmin TEXT (JSON), gozlenen TEXT, skor TEXT.
# - tahmin satırı yalnız eklenir (INSERT OR IGNORE): yazılmış tahmin yeniden yazılmaz.
# - gozlenen/skor hafta kapanınca BİR kez doldurulur (UPDATE ... WHERE gozlenen IS NULL).
# - Her hafta 7 bölge için P(≥ 1 Mw ≥ 5) hem ETAS hem Poisson tabanı olarak saklanır (Poisson modunda yayımlanan
#   değer tabandır: p = taban, hafta sınava yine sayılır).
import json
import math

import numpy as np

HEDEF_HAFTA = 52
ARA_RAPOR = 13
EPS = 1e-4          # log ve Brier hesabında olasılık [EPS, 1−EPS] aralığına kırpılır
BOOT = 5000


def tahmin_kaydi(surum, mc, baslangic, bitis, mod, adlar, p, taban):
    return {'surum': surum, 'mc': mc, 'baslangic': int(baslangic), 'bitis': int(bitis), 'mod': mod,
            'bolgeler': list(adlar), 'p': [None if x is None else float(x) for x in p],
            'taban': [float(x) for x in taban]}


def hafta_kaydet(d1, hafta, simdi_ms, tahmin):
    """Haftanın tahminini ekler; o hafta zaten varsa dokunmaz."""
    d1.sorgu('INSERT OR IGNORE INTO etas_kayit (hafta, olusma, tahmin) VALUES (?, ?, ?)',
             [hafta, int(simdi_ms), json.dumps(tahmin, ensure_ascii=False, separators=(',', ':'))])


def gozlenen_hesapla(olaylar, ata, adlar, bas_ms, bit_ms, esik=5.0):
    """[bas, bit) içinde Mw ≥ esik olay olan bölgeler. ata(enlem_dizisi, boylam_dizisi) → bölge adları."""
    s = [o for o in olaylar if bas_ms <= o['zaman_ms'] < bit_ms and o['mw'] >= esik - 1e-9]
    sonuc = {ad: False for ad in adlar}
    if s:
        for ad in ata([o['enlem'] for o in s], [o['boylam'] for o in s]):
            if ad in sonuc:
                sonuc[ad] = True
    return sonuc


def _kirp(x):
    return min(max(float(x), EPS), 1 - EPS)


def hafta_skoru(p, taban, o):
    """Bölgeler üzerinde: ortalama Brier (model, taban), toplam log-olabilirlik (Bernoulli), olay sayısı."""
    bm = bt = lm = lt = 0.0
    for pm, pt, y in zip(p, taban, o):
        y = int(bool(y))
        pm, pt = _kirp(pm), _kirp(pt)
        bm += (pm - y) ** 2
        bt += (pt - y) ** 2
        lm += math.log(pm if y else 1 - pm)
        lt += math.log(pt if y else 1 - pt)
    n = len(list(p))
    return {'brier_model': bm / n, 'brier_taban': bt / n, 'll_model': lm, 'll_taban': lt, 'olay': int(sum(int(bool(y)) for y in o))}


def _beceri(bm, bt):
    s = bt.sum()
    return 0.0 if s <= 0 else float(1 - bm.sum() / s)


def rapor(skorlar, tohum=None, n_boot=BOOT):
    """Brier skill (Poisson tabanına göre; haftalar üzerinde bootstrap %95), olay başına log-olabilirlik bilgi kazancı.
    gecti yalnız 52 hafta dolunca ve iki ölçüt de > 0 ise; ara raporlar (13 haftada bir) betimleyicidir."""
    n = len(skorlar)
    if n == 0:
        return {'hafta': 0, 'brier_beceri': None, 'beceri_aralik': None, 'bilgi_kazanci': None, 'olay': 0, 'gecti': False}
    bm = np.array([s['brier_model'] for s in skorlar])
    bt = np.array([s['brier_taban'] for s in skorlar])
    dl = sum(s['ll_model'] - s['ll_taban'] for s in skorlar)
    olay = sum(s['olay'] for s in skorlar)
    rng = np.random.default_rng(tohum)
    idx = rng.integers(0, n, size=(n_boot, n))
    bm_s, bt_s = bm[idx].sum(axis=1), bt[idx].sum(axis=1)
    sk = np.where(bt_s > 0, 1 - bm_s / np.where(bt_s > 0, bt_s, 1), 0.0)
    alt, ust = (float(x) for x in np.percentile(sk, [2.5, 97.5]))
    beceri = _beceri(bm, bt)
    kazanc = dl / olay if olay else None
    gecti = bool(n >= HEDEF_HAFTA and alt > 0 and kazanc is not None and kazanc > 0)
    return {'hafta': n, 'brier_beceri': beceri, 'beceri_aralik': [alt, ust], 'bilgi_kazanci': kazanc, 'olay': olay,
            'gecti': gecti, 'ara_rapor': n % ARA_RAPOR == 0}


def haftalari_kapat(d1, simdi_ms, gozlenen_fn):
    """Süresi dolan açık haftaları gözlemle kapatır; kapatılan sayısı. gozlenen_fn(tahmin) → {bölge: bool}."""
    kapanan = 0
    for r in d1.sorgu('SELECT hafta, tahmin FROM etas_kayit WHERE gozlenen IS NULL'):
        t = json.loads(r['tahmin'])
        if t['bitis'] > simdi_ms:
            continue
        g = gozlenen_fn(t)
        o = [int(bool(g.get(ad))) for ad in t['bolgeler']]
        p = [pm if pm is not None else pt for pm, pt in zip(t['p'], t['taban'])]
        skor = hafta_skoru(p, t['taban'], o)
        d1.sorgu('UPDATE etas_kayit SET gozlenen = ?, skor = ? WHERE hafta = ? AND gozlenen IS NULL',
                 [json.dumps(dict(zip(t['bolgeler'], o)), ensure_ascii=False, separators=(',', ':')),
                  json.dumps(skor, separators=(',', ':')), r['hafta']])
        kapanan += 1
    return kapanan


def kapali(d1, surum):
    """Aynı model sürümüyle kapanmış haftaların (tahmin, skor) listesi, hafta sırasıyla."""
    sonuc = []
    for r in d1.sorgu('SELECT hafta, olusma, tahmin, gozlenen, skor FROM etas_kayit ORDER BY hafta'):
        if r.get('gozlenen') is None:
            continue
        if json.loads(r['tahmin']).get('surum') == surum:
            sonuc.append(json.loads(r['skor']))
    return sonuc


def sayac(d1, surum):
    return len(kapali(d1, surum))


def calistir(d1, surum, mc, simdi_ms, hafta, tahmin_p, taban, adlar, mod, olaylar, ata, gun_ms=86_400_000):
    """Bir koşu: haftanın tahminini ekle (yoksa), dolan haftaları kapat, sayaç + rapor döndür.
    tahmin_p: bölge sırasıyla ETAS olasılıkları (Poisson modunda None listesi)."""
    hafta_kaydet(d1, hafta, simdi_ms, tahmin_kaydi(surum, mc, simdi_ms, simdi_ms + 7 * gun_ms, mod, adlar, tahmin_p, taban))
    haftalari_kapat(d1, simdi_ms, lambda t: gozlenen_hesapla(olaylar, ata, t['bolgeler'], t['baslangic'], t['bitis']))
    skorlar = kapali(d1, surum)
    return {'hafta': len(skorlar), 'hedef': HEDEF_HAFTA, 'rapor': rapor(skorlar, tohum=0) if skorlar else None}
