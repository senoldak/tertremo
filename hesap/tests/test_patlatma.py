from datetime import datetime, timedelta, timezone

import numpy as np

from hesap import gunluk, kartblok, patlatma

TSI = timezone(timedelta(hours=3))
GUN_MS = 86_400_000


def yerel_ms(*a):
    return datetime(*a, tzinfo=TSI).timestamp() * 1000


def test_pencere_yerel_saat_ve_hafta_ici():
    assert patlatma.pencerede([yerel_ms(2026, 10, 26, 8, 0)])[0]        # Pzt 08:00
    assert patlatma.pencerede([yerel_ms(2026, 10, 30, 16, 59)])[0]      # Cum 16:59
    assert not patlatma.pencerede([yerel_ms(2026, 10, 26, 17, 0)])[0]   # 17:00 dışarıda
    assert not patlatma.pencerede([yerel_ms(2026, 10, 26, 7, 59)])[0]
    assert not patlatma.pencerede([yerel_ms(2026, 10, 31, 10, 0)])[0]   # Cmt
    assert not patlatma.pencerede([yerel_ms(2026, 11, 1, 10, 0)])[0]    # Paz
    # UTC günü Cuma 22:00 = yerel Cumartesi 01:00
    assert not patlatma.pencerede([datetime(2026, 10, 30, 22, 0, tzinfo=timezone.utc).timestamp() * 1000])[0]


def _katalog(tohum=5):
    r = np.random.default_rng(tohum)
    z, e, b, m = [], [], [], []
    t0 = yerel_ms(2024, 1, 1)
    for hucre, (n, pay) in {(38, 30): (400, 0.26), (39, 31): (500, 0.26), (40, 32): (60, 0.85),
                            (37, 29): (6000, 0.30), (36, 28): (20, 1.0)}.items():
        for _ in range(n):
            ister = r.random() < pay
            while True:
                t = t0 + r.uniform(0, 700 * GUN_MS)
                if patlatma.pencerede([t])[0] == ister:
                    break
            z.append(t); e.append(hucre[0] + r.random()); b.append(hucre[1] + r.random()); m.append(r.uniform(1.5, 3.4))
    return map(np.array, (z, e, b, m))


def test_bayrak_yogun_gunduz_hucresi_ama_ufak_sapma_ve_az_olay_degil():
    z, e, b, m = _katalog()
    bay, p0, nt = patlatma.bayrakli(z, e, b, m)
    assert set(bay) == {'40_32'}          # 37_29: n büyük, pay 0,30 vs p0 ≈ 0,3 → etki tabanının altında; 36_28: n < 30
    assert nt == 4 and 0.2 < p0 < 0.4


def test_buyuk_olay_ayiklanmaz():
    z, e, b, m = _katalog()
    bay, _, _ = patlatma.bayrakli(z, e, b, m)
    buyuk = (e >= 40) & (e < 41) & (np.arange(len(m)) % 5 == 0)
    ay = patlatma.ayiklama_maskesi(z, e, b, np.where(buyuk, 4.2, m), bay)
    assert not (ay & buyuk).any() and ay.sum() == ((e >= 40) & (e < 41)).sum() - buyuk.sum()


def test_hesapla_bayrakli_hucrede_kucuk_olaylar_dusur_kume_eksiksiz():
    z, e, b, m = _katalog()
    olaylar = [{'id': f'emsc:{i}', 'zaman_ms': float(z[i]), 'enlem': float(e[i]), 'boylam': float(b[i]), 'mw': float(m[i])}
               for i in range(len(z))]
    simdi = float(z.max()) + GUN_MS
    p, kume, hucreler, ozet = gunluk.hesapla('tr', olaylar, {'d_f': 1.5, 'b': 1.0, 'log_eta0': -5.0}, float(z.min()) - 1, simdi)
    assert set(ozet['patlatma']['hucreler']) == {'40_32'}
    assert ozet['patlatma']['ayiklanan'] == 60
    assert set(kume) == {o['id'] for o in olaylar}            # düşenler de kume'de (ebeveynsiz)
    assert all(h.get('patlatma') for h in hucreler if h['anahtar'] == '40_32') or not any(h['anahtar'] == '40_32' for h in hucreler)
    blok = kartblok.hucre_blogu(hucreler, simdi, z.min(), 1.0, ozet['patlatma'])
    assert blok['patlatmaAyiklandi'] is True
    assert kartblok.hucre_blogu(hucreler, simdi, z.min(), 1.0, None)['patlatmaAyiklandi'] is False


def test_dunya_katalogunda_bayrak_yok():
    z, e, b, m = _katalog()
    olaylar = [{'id': f'u:{i}', 'zaman_ms': float(z[i]), 'enlem': float(e[i]), 'boylam': float(b[i]), 'mw': float(m[i]) + 2.5}
               for i in range(len(z))]
    _, _, _, ozet = gunluk.hesapla('dunya', olaylar, {'d_f': 1.5, 'b': 1.0, 'log_eta0': -5.0}, float(z.min()) - 1, float(z.max()) + GUN_MS)
    assert ozet['patlatma']['ayiklanan'] == 0
