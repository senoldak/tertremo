# src/buyukluk.js ve src/istatistik.js hucreAnahtari ile aynı değerler (test/buyukluk.test.js, test/istatistik.test.js)
import pytest

from hesap.mw import mw, tur_duzelt
from hesap.hucre import hucre_anahtari


def test_ml_tan_2021():
    m, yaklasik = mw(4.0, 'ML')
    assert m == pytest.approx(4.056, abs=5e-4)
    assert yaklasik is False


def test_md_ve_buyuk_harf_duyarsiz():
    assert mw(4.0, 'MD')[0] == pytest.approx(3.985, abs=5e-4)
    assert mw(4.0, 'ml')[0] == pytest.approx(4.056, abs=5e-4)


def test_mw_turleri_aynen():
    for t in ['Mw', 'mww', 'mwr', 'MWC', 'MW']:
        assert mw(5.1, t) == (5.1, False)


def test_mb_ms_bilinmeyen_yaklasik():
    assert mw(4.5, 'mb') == (4.5, True)
    assert mw(4.5, 'Ms')[1] is True
    assert mw(4.5, 'xyz')[1] is True
    assert mw(4.5, None)[1] is True


def test_js_ile_ayni_ifade():
    # JS: 1.017 * buyukluk - 0.012 (aynı IEEE işlem sırası → bit bit aynı)
    assert mw(3.3, 'ML')[0] == 1.017 * 3.3 - 0.012
    assert mw(2.7, 'Md')[0] == 1.111 * 2.7 - 0.459


def test_tur_duzelt():
    assert tur_duzelt('ml') == 'ML'
    assert tur_duzelt('mww') == 'Mw'
    assert tur_duzelt('mwp') == 'Mw'
    assert tur_duzelt('') == 'M'
    assert tur_duzelt(None) == 'M'
    assert tur_duzelt('Mi') == 'Mi'


def test_hucre_anahtari_js_ile_ayni():
    assert hucre_anahtari(38.9, 27.1, 'tr') == '38_27'
    assert hucre_anahtari(-12.3, 141.9, 'dunya') == '-15_140'
    assert hucre_anahtari(-0.0, 0.5, 'tr') == '0_0'
    assert hucre_anahtari(0.5, -0.0, 'dunya') == '0_0'
    assert hucre_anahtari(-0.2, -179.9, 'tr') == '-1_-180'
