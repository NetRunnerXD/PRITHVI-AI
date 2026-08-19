from app.data.india_mask import in_india


def test_indian_cities_in():
    assert in_india(22.57, 88.36)  # Kolkata
    assert in_india(26.54, 88.72)  # Jalpaiguri
    assert in_india(26.32, 89.45)  # Cooch Behar
    assert in_india(25.22, 88.76)  # Dakshin Dinajpur
    assert in_india(28.61, 77.21)  # Delhi
    assert in_india(19.08, 72.88)  # Mumbai
    assert in_india(13.08, 80.27)  # Chennai
    assert in_india(12.97, 77.59)  # Bengaluru
    assert in_india(26.14, 91.74)  # Guwahati
    assert in_india(27.34, 88.61)  # Gangtok
    assert in_india(23.83, 91.29)  # Agartala
    assert in_india(34.15, 77.58)  # Leh
    assert in_india(8.52, 76.94)  # Thiruvananthapuram
    assert in_india(11.62, 92.72)  # Port Blair
    assert in_india(10.57, 72.64)  # Kavaratti


def test_foreign_out():
    assert not in_india(29.65, 91.13)  # Lhasa
    assert not in_india(31.10, 90.00)  # Tibet
    assert not in_india(25.04, 102.72)  # Kunming
    assert not in_india(23.81, 90.41)  # Dhaka
    assert not in_india(27.72, 85.32)  # Kathmandu
    assert not in_india(22.36, 91.78)  # Chittagong
    assert not in_india(16.87, 96.20)  # Yangon
    assert not in_india(6.93, 79.85)  # Colombo
