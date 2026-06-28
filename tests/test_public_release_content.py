from pathlib import Path

from office_agent.portfolio_demo import render_demo_report, run_portfolio_demo
from office_agent.service_runtime import render_demo_ui


PUBLIC_TEXT_FILES = [
    Path("README.md"),
    Path("pyproject.toml"),
    Path("docs/ARCHITECTURE.md"),
    Path("docs/DEMO_GUIDE.md"),
    Path("docs/TESTING.md"),
    Path("docs/TRACE_AND_EVIDENCE.md"),
]


FORBIDDEN_PUBLIC_POSITIONING = [
    "求职",
    "简历",
    "作品集",
    "resume-core",
    "resume/demo",
    "resume project",
    "portfolio showcase",
    "portfolio-facing",
    "portfolio demo",
    "portfolio project",
]


def test_public_docs_do_not_expose_internal_positioning_terms():
    for path in PUBLIC_TEXT_FILES:
        text = path.read_text(encoding="utf-8").lower()
        for forbidden in FORBIDDEN_PUBLIC_POSITIONING:
            assert forbidden.lower() not in text, f"{forbidden!r} leaked in {path}"


def test_user_visible_demo_surfaces_use_neutral_demo_language(tmp_path):
    report = render_demo_report(run_portfolio_demo(checkpoint_dir=tmp_path))
    ui = render_demo_ui()
    combined = f"{report}\n{ui}".lower()

    assert "enterprise office agent demo harness" in combined
    assert "企业办公 agent 本地演示控制台".lower() in combined
    for forbidden in FORBIDDEN_PUBLIC_POSITIONING:
        assert forbidden.lower() not in combined
