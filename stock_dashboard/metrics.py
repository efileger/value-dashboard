from typing import Any, Mapping

# Define thresholds
thresholds = {
    "Net Profit Margin (%)": 10,
    "ROE (%)": 10,
    "P/E Ratio": 25,
    "P/B Ratio": 3,
    "P/S Ratio": 3,
    "Dividend Yield (%)": 2,
    "Current Ratio": 1.5,
    "Quick Ratio": 1,
    "Cash Flow/Share": 0,
    "Sales/Share": 0,
    "4 Yr Sales Growth (%)": 5,
    "4 Yr EPS Growth (%)": 5,
    "Operating Margin (%)": 10,
    "Debt/Equity": 100,
    "Free Cash Flow": 0,
    "EBITDA Margin (%)": 10,
    "Return on Assets (%)": 5,
    "EV / EBITDA": 20,
    "PEG Ratio": 1.5,
    "Insider Ownership (%)": 5,
    "Buybacks": True,
}

# Define metric info tooltips
tooltips = {
    "Net Profit Margin (%)": "Should have top 20% profit margin in its industry",
    "Dividend Yield (%)": "Graham recommends ONLY to invest in well known companies with solid div yields.",
    "Insider Ownership (%)": "Higher is better",
    "P/E Ratio": "Lower is better. P/E less than 5 year avg = good sign",
    "Buybacks": "Indicates if the company is actively buying back shares",
}


def format_billions(val: Any) -> Any:
    if isinstance(val, (int, float)):
        return f"{val / 1e9:.2f}B"
    return val


def validate_metrics(metrics: Mapping[str, Any], ticker: str):
    """Ensure the dashboard has real values to display.

    Raises a ``ValueError`` when every metric is missing so the caller can
    fail fast instead of rendering placeholder UI elements.
    """

    if not metrics or all(value is None for value in metrics.values()):
        raise ValueError(f"No metrics available for {ticker}")

    return metrics


def ensure_data_available(ticker: str, sections: Mapping[str, Mapping[str, Any]], metrics: Mapping[str, Any]):
    """Validate that required sections and metrics are populated for the ticker."""

    missing_sections = [name for name, data in sections.items() if not data]
    if missing_sections:
        joined = ", ".join(missing_sections)
        raise ValueError(f"No data found for {ticker}: missing sections {joined}.")

    has_metric_value = any(value is not None for value in metrics.values())
    if not has_metric_value:
        raise ValueError(f"No metrics available for {ticker} from Yahoo Finance.")

    critical_fields = {
        "market cap": sections.get("key_stats", {}).get("marketCap"),
        "total revenue": sections.get("financial_data", {}).get("totalRevenue"),
        "total debt": sections.get("financial_data", {}).get("totalDebt"),
    }
    missing_fields = [name for name, value in critical_fields.items() if value is None]
    if missing_fields:
        joined = ", ".join(missing_fields)
        raise ValueError(f"Missing required fields for {ticker}: {joined}.")


def compute_metrics(ticker: str, sections: Mapping[str, Mapping[str, Any]]):
    """Build the computed metrics used for display."""

    summary = sections.get("summary_detail", {})
    financial = sections.get("financial_data", {})
    key_stats = sections.get("key_stats", {})

    total_revenue_val = financial.get("totalRevenue", None)
    shares_outstanding_val = key_stats.get("sharesOutstanding", None)

    operating_cashflow = financial.get("operatingCashflow", None)
    cashflow_per_share = None
    if isinstance(operating_cashflow, (int, float)) and isinstance(shares_outstanding_val, (int, float)) and shares_outstanding_val != 0:
        cashflow_per_share = operating_cashflow / shares_outstanding_val

    sales_per_share = key_stats.get("revenuePerShare", None)
    if sales_per_share is None and isinstance(total_revenue_val, (int, float)) and isinstance(shares_outstanding_val, (int, float)) and shares_outstanding_val != 0:
        sales_per_share = total_revenue_val / shares_outstanding_val

    free_cash_flow = financial.get("freeCashflow", None)
    if isinstance(free_cash_flow, (int, float)):
        free_cash_flow = free_cash_flow / 1e9

    peg_ratio = key_stats.get("pegRatio", summary.get("pegRatio", None))

    metrics = validate_metrics(
        {
            "Net Profit Margin (%)": financial.get("profitMargins", None),
            "ROE (%)": financial.get("returnOnEquity", None),
            "P/E Ratio": summary.get("trailingPE", None),
            "P/B Ratio": summary.get("priceToBook", None),
            "P/S Ratio": summary.get("priceToSalesTrailing12Months", None),
            "Dividend Yield (%)": summary.get("dividendYield", None),
            "Current Ratio": financial.get("currentRatio", None),
            "Quick Ratio": financial.get("quickRatio", None),
            "Cash Flow/Share": cashflow_per_share,
            "Sales/Share": sales_per_share,
            "4 Yr Sales Growth (%)": financial.get("revenueGrowth", None),
            "4 Yr EPS Growth (%)": financial.get("earningsGrowth", None),
            "Operating Margin (%)": financial.get("operatingMargins", None),
            "Debt/Equity": financial.get("debtToEquity", None),
            "Free Cash Flow": free_cash_flow,
            "EBITDA Margin (%)": financial.get("ebitdaMargins", None),
            "Return on Assets (%)": financial.get("returnOnAssets", None),
            "EV / EBITDA": key_stats.get("enterpriseToEbitda", None),
            "PEG Ratio": peg_ratio,
            "Insider Ownership (%)": key_stats.get("heldPercentInsiders", None),
            "Buybacks": sections.get("buybacks"),
        },
        ticker,
    )

    return metrics
