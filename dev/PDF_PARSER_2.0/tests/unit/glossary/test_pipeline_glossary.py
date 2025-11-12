from pathlib import Path

from kps.core import PipelineConfig, UnifiedPipeline


def test_pipeline_loads_custom_glossary(tmp_path):
    yaml_path = tmp_path / "custom.yaml"
    yaml_path.write_text(
        """
        terms:
          sample-term:
            ru: "тест"
            en: "test"
            fr: "test"
        """,
        encoding="utf-8",
    )

    config = PipelineConfig(
        glossary_path=str(yaml_path),
        export_formats=["json"],
    )
    pipeline = UnifiedPipeline(config)
    validator = pipeline._build_term_validator()
    assert validator is not None
    assert any(rule.tgt == "test" for rule in validator.rules)
