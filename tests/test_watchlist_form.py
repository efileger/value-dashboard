import pandas as pd

from stock_dashboard import data_access, ui


class _DummyContext:
    def __init__(self, label: str | None = None):
        self.label = label

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _SessionState(dict):
    def __init__(self):
        super().__init__()
        self._locked_keys: set[str] = set()

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:  # noqa: B904
            raise AttributeError(item) from exc

    def __setattr__(self, key, value):
        self[key] = value

    def __setitem__(self, key, value):
        if key in getattr(self, "_locked_keys", set()):
            raise RuntimeError(
                f"Cannot assign to session_state['{key}'] after widget initialization"
            )
        super().__setitem__(key, value)

    def lock_key(self, key: str) -> None:
        self._locked_keys.add(key)


class _FakeStreamlit:
    def __init__(self):
        self.session_state: _SessionState = _SessionState()
        self.markdowns: list[str] = []
        self.info_messages: list[str] = []
        self.captions: list[str] = []
        self.forms: list[str] = []
        self.tabs_created: list[list[str]] = []
        self.multiselect_value: list[str] | None = None
        self.text_inputs: dict[str, str] = {}
        self.submit_map: dict[str, bool | list[bool]] = {}
        self.data_editor_value: pd.DataFrame | None = None
        self.data_editor_calls: list[pd.DataFrame] = []
        self.column_config = type("_ColumnConfig", (), {"CheckboxColumn": lambda *_args, **_kwargs: None})()

    def set_page_config(self, *_, **__):
        return None

    def title(self, *_args, **__):
        return None

    def info(self, message, *_, **__):
        self.info_messages.append(message)
        return None

    def markdown(self, message, *_, **__):
        self.markdowns.append(message)
        return None

    def caption(self, message, *_, **__):
        self.captions.append(message)
        return None

    def error(self, *_args, **__):
        return None

    def form(self, name, *_, **__):
        self.forms.append(name)
        return _DummyContext()

    def tabs(self, labels):
        self.tabs_created.append(list(labels))
        return [_DummyContext(label) for label in labels]

    def columns(self, spec, *_, **__):
        return tuple(_DummyContext() for _ in range(len(spec)))

    def multiselect(self, *_args, default=None, **__):
        value = self.multiselect_value if self.multiselect_value is not None else default
        key = __.get("key")
        if key:
            dict.__setitem__(self.session_state, key, value)
            self.session_state.lock_key(key)
        return value

    def text_input(self, *_, key: str, **__):
        return self.text_inputs.get(key, "")

    def form_submit_button(self, label, *_, **__):
        value = self.submit_map.get(label)
        if isinstance(value, list):
            return value.pop(0) if value else False
        return bool(value)

    def data_editor(self, df: pd.DataFrame, *_, **__):
        self.data_editor_calls.append(df)
        return self.data_editor_value if self.data_editor_value is not None else df


def _install_fake_streamlit(monkeypatch, fake_st: _FakeStreamlit):
    monkeypatch.setattr(ui, "st", fake_st)


def _stub_defaults(monkeypatch, defaults: str = "AAPL,MSFT"):
    monkeypatch.setattr(data_access, "get_default_watchlist_string", lambda: defaults)


def test_watchlist_form_adds_valid_ticker(monkeypatch):
    fake_st = _FakeStreamlit()
    fake_st.text_inputs["add_ticker_input"] = "good"
    fake_st.multiselect_value = ["AAPL", "MSFT"]
    fake_st.submit_map = {
        "Add to watchlist": True,
        "Remove selected": False,
        "Apply watchlist": True,
    }
    fake_st.data_editor_value = pd.DataFrame(
        {"Ticker": ["AAPL", "MSFT", "GOOD"], "Delete": [False, False, False]}
    )

    _install_fake_streamlit(monkeypatch, fake_st)
    _stub_defaults(monkeypatch)

    validate_calls: list[list[str]] = []

    def fake_validate(tickers, ticker_cls=None):
        validate_calls.append(list(tickers))
        return [t.upper() for t in tickers if t]

    monkeypatch.setattr(data_access, "validate_tickers", fake_validate)
    monkeypatch.setattr(data_access, "get_batched_ticker_client", lambda *_, **__: None)

    displayed: list[str] = []
    monkeypatch.setattr(ui, "display_stock", lambda ticker, ticker_client=None: displayed.append(ticker))

    ui.main()

    assert any(call == ["GOOD"] for call in validate_calls)
    assert displayed == ["AAPL", "MSFT", "GOOD"]


def test_watchlist_form_skips_invalid_ticker(monkeypatch):
    fake_st = _FakeStreamlit()
    fake_st.text_inputs["add_ticker_input"] = "bad"
    fake_st.multiselect_value = ["AAPL", "MSFT"]
    fake_st.submit_map = {
        "Add to watchlist": True,
        "Remove selected": False,
        "Apply watchlist": True,
    }
    fake_st.data_editor_value = pd.DataFrame(
        {"Ticker": ["AAPL", "MSFT"], "Delete": [False, False]}
    )

    _install_fake_streamlit(monkeypatch, fake_st)
    _stub_defaults(monkeypatch)

    validate_calls: list[list[str]] = []

    def fake_validate(tickers, ticker_cls=None):
        validate_calls.append(list(tickers))
        return [t.upper() for t in tickers if t and t.upper() != "BAD"]

    monkeypatch.setattr(data_access, "validate_tickers", fake_validate)
    monkeypatch.setattr(data_access, "get_batched_ticker_client", lambda *_, **__: None)

    displayed: list[str] = []
    monkeypatch.setattr(ui, "display_stock", lambda ticker, ticker_client=None: displayed.append(ticker))

    ui.main()

    assert any(call == ["BAD"] for call in validate_calls)
    assert displayed == ["AAPL", "MSFT"]


def test_watchlist_form_removes_tickers(monkeypatch):
    fake_st = _FakeStreamlit()
    fake_st.multiselect_value = ["AAPL", "MSFT"]
    fake_st.submit_map = {
        "Add to watchlist": False,
        "Remove selected": True,
        "Apply watchlist": True,
    }
    fake_st.data_editor_value = pd.DataFrame(
        {"Ticker": ["AAPL"], "Delete": [False]}
    )

    _install_fake_streamlit(monkeypatch, fake_st)
    _stub_defaults(monkeypatch)

    validate_calls: list[list[str]] = []

    def fake_validate(tickers, ticker_cls=None):
        validate_calls.append(list(tickers))
        return [t.upper() for t in tickers if t]

    monkeypatch.setattr(data_access, "validate_tickers", fake_validate)
    monkeypatch.setattr(data_access, "get_batched_ticker_client", lambda *_, **__: None)

    displayed: list[str] = []
    monkeypatch.setattr(ui, "display_stock", lambda ticker, ticker_client=None: displayed.append(ticker))

    ui.main()

    assert any(call for call in validate_calls if "MSFT" in call)
    assert displayed == ["AAPL"]


def test_watchlist_respects_session_state_lock(monkeypatch):
    fake_st = _FakeStreamlit()
    fake_st.multiselect_value = ["TSLA", "NVDA"]
    fake_st.submit_map = {
        "Add to watchlist": False,
        "Remove selected": False,
        "Apply watchlist": True,
    }
    fake_st.data_editor_value = pd.DataFrame(
        {"Ticker": ["TSLA", "NVDA"], "Delete": [False, False]}
    )

    _install_fake_streamlit(monkeypatch, fake_st)
    _stub_defaults(monkeypatch)

    monkeypatch.setattr(data_access, "validate_tickers", lambda tickers, ticker_cls=None: tickers)
    monkeypatch.setattr(data_access, "get_batched_ticker_client", lambda *_, **__: None)

    displayed: list[str] = []
    monkeypatch.setattr(ui, "display_stock", lambda ticker, ticker_client=None: displayed.append(ticker))

    ui.main()

    assert displayed == ["TSLA", "NVDA"]


def test_watchlist_form_smoke_mode_renders(monkeypatch):
    monkeypatch.setenv("SMOKE_TEST", "1")

    fake_st = _FakeStreamlit()
    fake_st.multiselect_value = ["STUB"]
    fake_st.submit_map = {
        "Add to watchlist": False,
        "Remove selected": False,
        "Apply watchlist": False,
    }
    fake_st.data_editor_value = pd.DataFrame({"Ticker": ["STUB"], "Delete": [False]})

    _install_fake_streamlit(monkeypatch, fake_st)
    _stub_defaults(monkeypatch, defaults="STUB")

    validate_calls: list[list[str]] = []

    def fake_validate(tickers, ticker_cls=None):
        validate_calls.append(list(tickers))
        return [t.upper() for t in tickers]

    monkeypatch.setattr(data_access, "validate_tickers", fake_validate)
    monkeypatch.setattr(data_access, "get_batched_ticker_client", lambda *_, **__: None)

    displayed: list[str] = []
    monkeypatch.setattr(ui, "display_stock", lambda ticker, ticker_client=None: displayed.append(ticker))

    ui.main()

    assert "watchlist_form" in fake_st.forms
    assert any(call == ["STUB"] for call in validate_calls)
    assert displayed == ["STUB"]

