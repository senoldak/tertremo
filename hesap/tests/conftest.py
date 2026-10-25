def pytest_configure(config):
    # Mizrahi `etas` paketinin pandas 3 / shapely 2.2 kullanım uyarıları (inplace=, shapely.ops.transform);
    # hesap/etas.py gece işinde de aynı süzgeci kurar. Yalnız paketin kendi modülleri (etas.*) susturulur.
    for tur in ('DeprecationWarning', 'FutureWarning'):
        config.addinivalue_line('filterwarnings', f'ignore::{tur}:etas')
