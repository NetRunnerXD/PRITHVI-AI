from app.providers.gpm_imerg import _opendap_ascii_urls
from app.providers.mosdac import DATASETS, L1B, PRIORITY, QUOTA_CAP


def test_mosdac_products_drop_retired_3dimg():
    assert "3DIMG_L1B_STD" not in DATASETS
    assert "3DIMG_L2B_HEM" not in DATASETS
    assert "3SIMG_L2B_HEM" in PRIORITY
    assert "3SIMG_L1B_STD" in L1B
    assert QUOTA_CAP == 400
    assert QUOTA_CAP < 5000


def test_imerg_opendap_uses_gesdisc_hyrax_and_lon_lat_order():
    href = "https://data.gesdisc.earthdata.nasa.gov/data/GPM_L3/GPM_3IMERGHHE.07/2026/256/file.HDF5"
    urls = _opendap_ascii_urls({"href": href}, 2680, 1120)
    assert urls
    assert urls[0].startswith("https://gpm1.gesdisc.eosdis.nasa.gov/opendap/")
    assert "precipitation[0:1:0][2680:1:2680][1120:1:1120]" in urls[0]
    assert ".HDF5" in urls[0] or "file.HDF5" in urls[0]
