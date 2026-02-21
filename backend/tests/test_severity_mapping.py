from services.severity import severity_from_score

def test_severity_mapping_thresholds():
    assert severity_from_score(0) == "LOW"
    assert severity_from_score(39) == "LOW"
    assert severity_from_score(40) == "MEDIUM"
    assert severity_from_score(69) == "MEDIUM"
    assert severity_from_score(70) == "HIGH"
    assert severity_from_score(89) == "HIGH"
    assert severity_from_score(90) == "CRITICAL"
    assert severity_from_score(100) == "CRITICAL"
