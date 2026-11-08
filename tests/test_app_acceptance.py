"""Execute the real Streamlit page: an HTTP shell alone cannot catch script errors."""

from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_watchlist_page_renders_and_runs_again(monkeypatch):
    monkeypatch.setenv("SMOKE_TEST", "1")
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "stock_dashboard.py", default_timeout=15).run()
    assert not app.exception
    assert not app.error
    assert "Value Investing Dashboard" in app.title[0].value
    assert app.session_state["watchlist"]
    assert app.dataframe
    assert any("Watchlist Action Snapshot" in element.value for element in app.markdown)

    app.run()
    assert not app.exception
    assert not app.error
    assert app.dataframe
