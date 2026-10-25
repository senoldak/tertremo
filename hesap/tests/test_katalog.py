

def test_olay_turu_suzgeci():
    import json
    from hesap.katalog import emsc_ayristir, usgs_ayristir
    u = {'features': [
        {'id': 'a', 'properties': {'mag': 6.3, 'magType': 'mb', 'time': 1700000000000, 'type': 'earthquake'}, 'geometry': {'coordinates': [129.0, 41.3, 5]}},
        {'id': 'b', 'properties': {'mag': 6.3, 'magType': 'mb', 'time': 1700000000000, 'type': 'nuclear explosion'}, 'geometry': {'coordinates': [129.0, 41.3, 0]}},
        {'id': 'c', 'properties': {'mag': 2.1, 'magType': 'ml', 'time': 1700000000000, 'type': 'quarry blast'}, 'geometry': {'coordinates': [-118.0, 34.0, 0]}}]}
    assert len(usgs_ayristir(json.dumps(u))) == 1
    e = {'features': [
        {'id': 'e1', 'properties': {'unid': 'e1', 'time': '2026-10-24T12:00:00Z', 'lat': 39, 'lon': 35, 'depth': 10, 'mag': 3.6, 'magtype': 'ml', 'evtype': 'ke'}},
        {'id': 'e2', 'properties': {'unid': 'e2', 'time': '2026-10-24T12:00:00Z', 'lat': 39, 'lon': 35, 'depth': 10, 'mag': 3.6, 'magtype': 'ml', 'evtype': 'kx'}}]}
    assert len(emsc_ayristir(json.dumps(e))) == 1
