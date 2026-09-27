import copy
import hashlib
import json
import os
from pathlib import Path
import pytest
from mve.observer.checks.regression import verified_inputs, compare, reproduce, EVIDENCE


def test_golden_compare_and_provenance(tmp_path):
    golden = json.loads((EVIDENCE / "lane_check_v2.json").read_text())
    assert compare(golden)["passed"]
    for group, key in [
        ("planck", "a"),
        ("planck", "ks_p_bootstrap_refit"),
        ("cdf_exponent", "b_hat"),
    ]:
        bad = copy.deepcopy(golden)
        bad["blocks"][0][group][key] += 1
        assert not compare(bad)["passed"]
    bad = copy.deepcopy(golden)
    bad["blocks"][0]["zeros"] += 1
    assert not compare(bad)["passed"]
    (tmp_path / "zeros1.gz").write_bytes(b"bad")
    with pytest.raises(ValueError, match="hash mismatch"):
        verified_inputs(tmp_path)
    status = json.loads((EVIDENCE / "lane_check_v2_status.json").read_text())
    for filename, key in [
        ("lane_check_v2.py", "script_sha256"),
        ("lane_check_v2.json", "receipt_sha256"),
    ]:
        assert (
            hashlib.sha256((EVIDENCE / filename).read_bytes()).hexdigest()
            == status[key]
        )
    for name in ("H0", "H1"):
        d = json.loads(Path(f"tests/mve/observer/fixtures/{name}.json").read_text())
        for ref in d["context"]["evidence"]:
            assert (
                hashlib.sha256(Path(ref["path"]).read_bytes()).hexdigest()
                == ref["sha256"]
            )


@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("MVE_RUN_SLOW") != "1",
    reason="set MVE_RUN_SLOW=1 for full v2 regression",
)
def test_v2_reproduction(tmp_path):
    result = reproduce(Path.home() / "Developer/Opensens/cache/odlyzko_zeros")
    assert compare(result)["passed"]
    assert result["inferential"] is False and result["label"] == "nominal"

    (tmp_path / "receipt.json").write_text(json.dumps(result, indent=2) + "\n")
