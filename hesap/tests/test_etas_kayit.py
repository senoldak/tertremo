import json
import math

import pytest

from hesap import etas_kayit as ek

GUN = 86_400_000
BAS = 1_792_000_000_000
ADLAR = ['Marmara', 'Ege']


class SahteD1:
    """INSERT OR IGNORE / UPDATE ... WHERE gozlenen IS NULL davranışını taklit eden bellek içi tablo."""

    def __init__(self):
        self.satirlar = {}
        self.sorgular = []

    def sorgu(self, sql, params=()):
        self.sorgular.append(sql)
        s = ' '.join(sql.split())
        if s.startswith('INSERT OR IGNORE INTO etas_kayit'):
            hafta, olusma, tahmin = params
            self.satirlar.setdefault(hafta, {'hafta': hafta, 'olusma': olusma, 'tahmin': tahmin, 'gozlenen': None, 'skor': None})
            return []
        if s.startswith('UPDATE etas_kayit'):
            gozlenen, skor, hafta = params
            r = self.satirlar.get(hafta)
            if r and r['gozlenen'] is None:
                r['gozlenen'], r['skor'] = gozlenen, skor
            return []
        if 'WHERE gozlenen IS NULL' in s:
            return [dict(r) for r in self.satirlar.values() if r['gozlenen'] is None]
        if s.startswith('SELECT'):
            return [dict(r) for r in sorted(self.satirlar.values(), key=lambda r: r['hafta'])]
        raise AssertionError(sql)


def tahmin(bas=BAS, p=(0.2, 0.1), taban=(0.1, 0.1), surum='etas-2'):
    return ek.tahmin_kaydi(surum, 4.0, bas, bas + 7 * GUN, 'etas', ADLAR, list(p), list(taban))


def test_tahmin_degismez_ayni_hafta_ikinci_kez_yazilmaz():
    d = SahteD1()
    ek.hafta_kaydet(d, '2026-10-26', BAS, tahmin(p=(0.2, 0.1)))
    ilk = d.satirlar['2026-10-26']['tahmin']
    ek.hafta_kaydet(d, '2026-10-26', BAS + 3600_000, tahmin(p=(0.9, 0.9)))
    assert d.satirlar['2026-10-26']['tahmin'] == ilk
    assert d.satirlar['2026-10-26']['olusma'] == BAS
    assert not any('DELETE' in q.upper() or 'REPLACE INTO' in q.upper() for q in d.sorgular)


def test_hafta_dolmadan_kapanmaz_dolunca_bir_kez_doldurulur():
    d = SahteD1()
    ek.hafta_kaydet(d, '2026-10-26', BAS, tahmin())
    ata = lambda olaylar: {'Marmara': True, 'Ege': False}
    assert ek.haftalari_kapat(d, BAS + 6 * GUN, ata) == 0
    assert d.satirlar['2026-10-26']['gozlenen'] is None
    assert ek.haftalari_kapat(d, BAS + 7 * GUN, ata) == 1
    ilk = (d.satirlar['2026-10-26']['gozlenen'], d.satirlar['2026-10-26']['skor'])
    assert json.loads(ilk[0]) == {'Marmara': 1, 'Ege': 0}
    # ikinci kapanış gözlemi değiştirmez
    ata2 = lambda olaylar: {'Marmara': False, 'Ege': True}
    assert ek.haftalari_kapat(d, BAS + 8 * GUN, ata2) == 0
    assert (d.satirlar['2026-10-26']['gozlenen'], d.satirlar['2026-10-26']['skor']) == ilk


def test_skor_sentetik_brier_ve_logolabilirlik():
    s = ek.hafta_skoru([0.2, 0.1], [0.1, 0.1], [1, 0])
    assert s['brier_model'] == pytest.approx(((0.8) ** 2 + 0.1 ** 2) / 2)
    assert s['brier_taban'] == pytest.approx(((0.9) ** 2 + 0.1 ** 2) / 2)
    assert s['ll_model'] == pytest.approx(math.log(0.2) + math.log(0.9))
    assert s['ll_taban'] == pytest.approx(math.log(0.1) + math.log(0.9))
    assert s['olay'] == 1


def test_olasilik_sinirlari_kirpilir_log_sonsuz_olmaz():
    s = ek.hafta_skoru([0.0, 1.0], [0.1, 0.1], [1, 0])
    assert math.isfinite(s['ll_model'])


def test_rapor_beceri_ve_bilgi_kazanci():
    # model her hafta olayı biliyor: Brier skill > 0, bilgi kazancı > 0
    skorlar = []
    for i in range(20):
        o = [1 if i % 5 == 0 else 0, 0]
        p = [0.6 if o[0] else 0.05, 0.05]
        skorlar.append(ek.hafta_skoru(p, [0.2, 0.05], o))
    r = ek.rapor(skorlar, tohum=1, n_boot=500)
    assert r['hafta'] == 20
    assert r['brier_beceri'] > 0
    assert r['beceri_aralik'][0] > 0
    assert r['bilgi_kazanci'] > 0


def test_rapor_taban_esitse_beceri_sifir_aralik_sifiri_icerir():
    skorlar = [ek.hafta_skoru([0.1, 0.1], [0.1, 0.1], [i % 3 == 0, 0]) for i in range(30)]
    r = ek.rapor(skorlar, tohum=2, n_boot=300)
    assert r['brier_beceri'] == pytest.approx(0)
    assert r['bilgi_kazanci'] == pytest.approx(0)
    assert r['gecti'] is False


def test_gecme_kurali_yalniz_52_haftada_ara_rapor_gecmez():
    iyi = [ek.hafta_skoru([0.6 if i % 5 == 0 else 0.05, 0.05], [0.2, 0.05], [i % 5 == 0, 0]) for i in range(52)]
    assert ek.rapor(iyi[:13], tohum=1, n_boot=300)['gecti'] is False   # ara rapor: yalnız betimleyici
    assert ek.rapor(iyi[:51], tohum=1, n_boot=300)['gecti'] is False
    assert ek.rapor(iyi, tohum=1, n_boot=300)['gecti'] is True


def test_sayac_yalniz_ayni_surum_kapanmis_haftalar():
    d = SahteD1()
    for i, surum in enumerate(['etas-1', 'etas-2', 'etas-2']):
        h = f'2026-11-{2 + 7 * i:02d}'
        ek.hafta_kaydet(d, h, BAS + i * 7 * GUN, tahmin(bas=BAS + i * 7 * GUN, surum=surum))
    ata = lambda olaylar: {'Marmara': False, 'Ege': False}
    ek.haftalari_kapat(d, BAS + 30 * GUN, ata)
    assert ek.sayac(d, 'etas-2') == 2


def test_gozlenen_hesap_pencere_ve_esik():
    olaylar = [
        {'zaman_ms': BAS + GUN, 'mw': 5.2, 'enlem': 40.0, 'boylam': 29.0},
        {'zaman_ms': BAS + GUN, 'mw': 4.9, 'enlem': 38.0, 'boylam': 27.0},     # eşik altı
        {'zaman_ms': BAS + 9 * GUN, 'mw': 6.0, 'enlem': 38.0, 'boylam': 27.0},  # pencere dışı
    ]
    ata = lambda en, bo: ['Marmara' if e > 39 else 'Ege' for e in en]
    g = ek.gozlenen_hesapla(olaylar, ata, ADLAR, BAS, BAS + 7 * GUN)
    assert g == {'Marmara': True, 'Ege': False}
