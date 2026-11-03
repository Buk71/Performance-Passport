from ui.hall_of_fame import _equipment_text


def test_plain_shoe_name_is_kept():
    assert _equipment_text("Puma Deviate Nitro Elite 3") == "Puma Deviate Nitro Elite 3"


def test_simple_json_list_of_equipment_names_is_kept():
    assert _equipment_text('["Nike Vaporfly 3", "Stryd"]') == "Nike Vaporfly 3, Stryd"


def test_garmin_device_metadata_is_hidden():
    payload = (
        '[{"device_index":"creator","garmin_product":3943,'
        '"manufacturer":"garmin","serial_number":3474026138,'
        '"software_version":26.09,"source_type":"local"}]'
    )
    assert _equipment_text(payload) is None


def test_json_object_is_hidden():
    assert _equipment_text('{"shoe":"unknown","device_index":4}') is None


def test_long_blob_is_hidden():
    assert _equipment_text("x" * 500) is None


def test_empty_equipment_is_hidden():
    assert _equipment_text("") is None
    assert _equipment_text(None) is None
