from importlib.metadata import version

import coalition_formation


def test_package_import_and_version() -> None:
    assert coalition_formation.__version__ == "0.1.0"
    assert version("coalition-formation") == coalition_formation.__version__
