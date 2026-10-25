# Büyüklük türünü Mw'ye çevirir — src/buyukluk.js ile birebir (Tan 2021, doi 10.5194/nhess-21-2059-2021)
# ve tür yazımını src/kaynaklar/olay.js turDuzelt ile aynı biçime indirir.

MW_TURLERI = {'mw', 'mww', 'mwr', 'mwc'}

TURLER = {
    'ml': 'ML', 'md': 'Md', 'mb': 'mb', 'ms': 'Ms',
    'mw': 'Mw', 'mww': 'Mw', 'mwr': 'Mw', 'mwb': 'Mw', 'mwc': 'Mw', 'mwp': 'Mw',
}


def tur_duzelt(ham):
    t = str(ham if ham is not None else '').strip()
    if not t:
        return 'M'
    return TURLER.get(t.lower(), t)


def mw(buyukluk, tur):
    """(mw, yaklasik) — JS mw() ile aynı işlem sırası."""
    t = str(tur if tur is not None else '').lower()
    if t == 'ml':
        return 1.017 * buyukluk - 0.012, False
    if t == 'md':
        return 1.111 * buyukluk - 0.459, False
    if t in MW_TURLERI:
        return buyukluk, False
    return buyukluk, True
