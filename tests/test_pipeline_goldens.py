from pathlib import Path

from app.pipeline.loaders import ArtifactStore
from app.pipeline.publish import canonical_json
from app.pipeline.runner import run_pipeline

GOLDEN = Path(__file__).parent / "golden/CL-0003"


def test_margarethe_artifact_goldens(tmp_path, request):
    run_pipeline(curated_dir=tmp_path)
    store = ArtifactStore(tmp_path)
    artifacts = {
        "curated_client_bundle": store.load_curated_bundle("CL-0003"),
        "fact_bundle": store.load_fact_bundle("CL-0003"),
        "signal_set": store.load_signal_set("CL-0003"),
        "change_report": store.load_change_report("CL-0003"),
        "data_quality_report": store.load_data_quality_report(client_id="CL-0003"),
    }
    for name, artifact in artifacts.items():
        expected = GOLDEN / f"{name}.json"
        actual = canonical_json(artifact)
        if request.config.getoption("--update-goldens"):
            expected.parent.mkdir(parents=True, exist_ok=True)
            expected.write_bytes(actual)
        assert expected.is_file(), f"{expected}: run pytest --update-goldens after reviewing values"
        assert actual == expected.read_bytes(), f"Golden mismatch: {name}"
