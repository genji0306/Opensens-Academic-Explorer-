def pytest_configure(config):
    config.addinivalue_line(
        "markers", "slow: opt-in full-size offline regression/calibration"
    )
