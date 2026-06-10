"""
Exchange-rate engine with pluggable sources and in-memory cache (TTL 24 h).

All internal rates are stored as:
    rates[code] = "how many units of native_currency equals 1 unit of code"
e.g. if native = RON: rates["EUR"] = 4.97  → 1 EUR = 4.97 RON

Supported sources (configured in settings.json → "fx_source"):
    "BNR"          Banca Nationala a Romaniei      native RON
    "ECB"          European Central Bank           native EUR
    "BUBA"         Deutsche Bundesbank (Germania)  native EUR
    "NBP"          Narodowy Bank Polski            native PLN
    "CNB"          Ceska narodni banka             native CZK
    "CBR"          Central Bank of Russia          native RUB
    "RIKSBANK"     Sveriges Riksbank               native SEK
    "NORGES"       Norges Bank                     native NOK
    "DN"           Danmarks Nationalbank           native DKK
    "BOC"          Bank of Canada                  native CAD
    "open.er-api"  open.er-api.com (universal)     native = base_currency

Bank of England and the US Federal Reserve do not expose free public rate
APIs (BoE blocks programmatic access; the Fed/Treasury feed is quarterly),
so for GBP/USD bases use "open.er-api" which serves any base currency.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

_TTL_SECONDS = 86_400   # 24 hours
_TIMEOUT     = 6        # seconds per HTTP request


# ---------------------------------------------------------------------------
# Source fetchers — each returns (native_currency, rates_dict) or None
# ---------------------------------------------------------------------------

def _fetch_bnr() -> Optional[Tuple[str, Dict[str, float]]]:
    """BNR XML: 1 FOREIGN = X RON."""
    try:
        url = "https://www.bnr.ro/nbrfxrates.xml"
        with _open(url) as r:
            root = ET.fromstring(r.read())
        ns = {"bnr": "http://www.bnr.ro/xsd"}
        rates: Dict[str, float] = {}
        for el in root.findall(".//bnr:Rate", ns):
            code = el.get("currency", "").upper()
            mult = float(el.get("multiplier", 1))
            if code and el.text:
                rates[code] = float(el.text) / mult
        return ("RON", rates) if rates else None
    except Exception as e:
        logger.warning("BNR fetch failed: %s", e)
        return None


def _fetch_ecb() -> Optional[Tuple[str, Dict[str, float]]]:
    """ECB XML: published as 1 EUR = X FOREIGN, we store as 1 FOREIGN = Y EUR."""
    try:
        url = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
        with _open(url) as r:
            root = ET.fromstring(r.read())
        ns = {"gesmes": "http://www.gesmes.org/xml/2002-08-01",
              "ecb":    "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}
        rates: Dict[str, float] = {}
        for el in root.findall(".//ecb:Cube[@currency]", ns):
            code = el.get("currency", "").upper()
            raw  = el.get("rate")
            if code and raw:
                eur_per_foreign = float(raw)      # 1 EUR = X foreign
                if eur_per_foreign > 0:
                    rates[code] = round(1.0 / eur_per_foreign, 8)
        return ("EUR", rates) if rates else None
    except Exception as e:
        logger.warning("ECB fetch failed: %s", e)
        return None


def _fetch_nbp() -> Optional[Tuple[str, Dict[str, float]]]:
    """NBP JSON: 1 FOREIGN = X PLN."""
    try:
        url = "https://api.nbp.pl/api/exchangerates/tables/A?format=json"
        with _open(url) as r:
            data = json.loads(r.read())
        rates: Dict[str, float] = {}
        for entry in data[0].get("rates", []):
            code = entry.get("code", "").upper()
            mid  = entry.get("mid")
            if code and mid:
                rates[code] = float(mid)
        return ("PLN", rates) if rates else None
    except Exception as e:
        logger.warning("NBP fetch failed: %s", e)
        return None


def _fetch_cbr() -> Optional[Tuple[str, Dict[str, float]]]:
    """CBR XML: 1 FOREIGN (per nominal) = X RUB."""
    try:
        url = "https://www.cbr.ru/scripts/XML_daily.asp"
        with _open(url) as r:
            root = ET.fromstring(r.read())
        rates: Dict[str, float] = {}
        for v in root.findall("Valute"):
            code = (v.findtext("CharCode") or "").upper()
            nom  = v.findtext("Nominal") or "1"
            val  = v.findtext("Value") or ""
            if code and val:
                try:
                    rates[code] = float(val.replace(",", ".")) / float(nom)
                except ValueError:
                    pass
        return ("RUB", rates) if rates else None
    except Exception as e:
        logger.warning("CBR fetch failed: %s", e)
        return None


def _fetch_bundesbank() -> Optional[Tuple[str, Dict[str, float]]]:
    """Bundesbank CSV (ECB reference rates): 1 EUR = X FOREIGN → invert.

    CSV is semicolon-delimited, German decimal commas, "." for missing values.
    Header row holds series names BBEX3.D.<CODE>.EUR.BB.AC.000; last row is
    the latest date.
    """
    try:
        url = ("https://api.statistiken.bundesbank.de/rest/data/"
               "BBEX3/D..EUR.BB.AC.000?lastNObservations=1&format=csv")
        with _open(url) as r:
            text = r.read().decode("utf-8-sig")
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if len(lines) < 2:
            return None
        header = lines[0].split(";")
        data   = lines[-1].split(";")
        rates: Dict[str, float] = {}
        for i, series in enumerate(header):
            parts = series.strip('"').split(".")
            if len(parts) >= 3 and not series.endswith("_FLAGS") and i < len(data):
                code = parts[2].upper()
                raw  = data[i].strip().replace(",", ".")
                if len(code) == 3 and raw and raw != ".":
                    try:
                        eur_per_foreign = float(raw)   # 1 EUR = X foreign
                        if eur_per_foreign > 0:
                            rates[code] = round(1.0 / eur_per_foreign, 8)
                    except ValueError:
                        pass
        return ("EUR", rates) if rates else None
    except Exception as e:
        logger.warning("Bundesbank fetch failed: %s", e)
        return None


def _fetch_cnb() -> Optional[Tuple[str, Dict[str, float]]]:
    """CNB daily.txt: pipe-delimited, 1*Amount FOREIGN = X CZK."""
    try:
        url = ("https://www.cnb.cz/en/financial-markets/foreign-exchange-market/"
               "central-bank-exchange-rate-fixing/central-bank-exchange-rate-fixing/daily.txt")
        with _open(url) as r:
            text = r.read().decode("utf-8")
        rates: Dict[str, float] = {}
        for line in text.splitlines()[2:]:   # skip date line + header line
            parts = line.split("|")
            if len(parts) == 5:
                try:
                    amount = float(parts[2])
                    code   = parts[3].strip().upper()
                    rate   = float(parts[4])
                    if code and amount > 0:
                        rates[code] = rate / amount
                except ValueError:
                    pass
        return ("CZK", rates) if rates else None
    except Exception as e:
        logger.warning("CNB fetch failed: %s", e)
        return None


def _fetch_riksbank() -> Optional[Tuple[str, Dict[str, float]]]:
    """Riksbank SWEA group 130: seriesId SEK<CODE>PMI, 1 FOREIGN = X SEK.

    Discontinued series keep their last (years-old) observation, so entries
    older than 14 days are dropped.
    """
    try:
        url = "https://api.riksbank.se/swea/v1/Observations/Latest/ByGroup/130"
        with _open(url) as r:
            data = json.loads(r.read())
        cutoff = time.time() - 14 * 86_400
        rates: Dict[str, float] = {}
        for obs in data:
            sid  = obs.get("seriesId", "")
            dstr = obs.get("date", "")
            val  = obs.get("value")
            if not (sid.startswith("SEK") and sid.endswith("PMI") and len(sid) == 9):
                continue
            try:
                ts = time.mktime(time.strptime(dstr, "%Y-%m-%d"))
            except ValueError:
                continue
            if ts < cutoff or not val:
                continue
            rates[sid[3:6].upper()] = float(val)
        return ("SEK", rates) if rates else None
    except Exception as e:
        logger.warning("Riksbank fetch failed: %s", e)
        return None


def _fetch_norges() -> Optional[Tuple[str, Dict[str, float]]]:
    """Norges Bank SDMX-JSON: BASE_CUR per NOK, honouring UNIT_MULT (10^n units)."""
    try:
        url = ("https://data.norges-bank.no/api/data/EXR/B..NOK.SP"
               "?lastNObservations=1&format=sdmx-json")
        with _open(url) as r:
            payload = json.loads(r.read())
        data      = payload["data"]
        structure = data["structure"]
        dims      = structure["dimensions"]["series"]
        base_idx  = next(i for i, d in enumerate(dims) if d["id"] == "BASE_CUR")
        codes     = [v["id"].upper() for v in dims[base_idx]["values"]]

        # UNIT_MULT series attribute: rate is per 10^n units of the currency
        attr_defs = structure.get("attributes", {}).get("series", [])
        mult_pos, mult_values = None, []
        for i, a in enumerate(attr_defs):
            if a.get("id") == "UNIT_MULT":
                mult_pos = i
                mult_values = [int(v.get("id", 0)) for v in a.get("values", [])]

        rates: Dict[str, float] = {}
        for key, series in data["dataSets"][0]["series"].items():
            idx = int(key.split(":")[base_idx])
            obs = series.get("observations", {})
            if not obs:
                continue
            raw = next(iter(obs.values()))[0]
            if raw is None:
                continue
            value = float(raw)
            if mult_pos is not None:
                attr_idx = series.get("attributes", [])[mult_pos]
                if attr_idx is not None and attr_idx < len(mult_values):
                    value /= 10 ** mult_values[attr_idx]
            if idx < len(codes) and value > 0:
                rates[codes[idx]] = value
        return ("NOK", rates) if rates else None
    except Exception as e:
        logger.warning("Norges Bank fetch failed: %s", e)
        return None


def _fetch_dn() -> Optional[Tuple[str, Dict[str, float]]]:
    """Danmarks Nationalbank XML: rates quoted per 100 FOREIGN in DKK."""
    try:
        url = "https://www.nationalbanken.dk/api/currencyratesxml?lang=en"
        with _open(url) as r:
            root = ET.fromstring(r.read())
        rates: Dict[str, float] = {}
        for c in root.iter("currency"):
            code = (c.get("code") or "").upper()
            raw  = c.get("rate") or ""
            if code and raw:
                try:
                    rates[code] = float(raw.replace(",", ".")) / 100.0
                except ValueError:
                    pass
        return ("DKK", rates) if rates else None
    except Exception as e:
        logger.warning("Danmarks Nationalbank fetch failed: %s", e)
        return None


def _fetch_boc() -> Optional[Tuple[str, Dict[str, float]]]:
    """Bank of Canada Valet: series FX<CODE>CAD, 1 FOREIGN = X CAD.

    A single observation row only carries the series published that day,
    so the last 10 rows are merged taking the newest value per series.
    """
    try:
        url = ("https://www.bankofcanada.ca/valet/observations/group/"
               "FX_RATES_DAILY/json?recent=10")
        with _open(url) as r:
            data = json.loads(r.read())
        rates: Dict[str, float] = {}
        for row in data.get("observations", []):      # rows are oldest → newest
            for key, cell in row.items():
                if key.startswith("FX") and key.endswith("CAD") and len(key) == 8:
                    try:
                        rates[key[2:5].upper()] = float(cell["v"])
                    except (KeyError, TypeError, ValueError):
                        pass
        return ("CAD", rates) if rates else None
    except Exception as e:
        logger.warning("Bank of Canada fetch failed: %s", e)
        return None


def _fetch_open_er(base: str) -> Optional[Tuple[str, Dict[str, float]]]:
    """open.er-api.com: 1 BASE = X FOREIGN → invert to get 1 FOREIGN = Y BASE."""
    try:
        url = f"https://open.er-api.com/v6/latest/{base.upper()}"
        with _open(url) as r:
            data = json.loads(r.read())
        raw: Dict[str, float] = data.get("rates", {})
        rates: Dict[str, float] = {}
        for code, base_per_foreign in raw.items():
            code = code.upper()
            if code != base.upper() and base_per_foreign > 0:
                rates[code] = round(1.0 / base_per_foreign, 8)
        return (base.upper(), rates) if rates else None
    except Exception as e:
        logger.warning("open.er-api fetch failed: %s", e)
        return None


def _req(url: str) -> urllib.request.Request:
    return urllib.request.Request(
        url, headers={"User-Agent": "Analyzen-Invoice-Reader/1.0"}
    )


# Some banks (e.g. NBP) serve cert chains that the Windows system store can't
# always complete; certifi's CA bundle resolves this when available.
try:
    import certifi
    import ssl
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = None


def _open(url: str):
    return urllib.request.urlopen(_req(url), timeout=_TIMEOUT, context=_SSL_CTX)


# Mapping of source key → callable (base_currency passed where needed)
_FETCHERS = {
    "BNR":         lambda _: _fetch_bnr(),
    "ECB":         lambda _: _fetch_ecb(),
    "BUBA":        lambda _: _fetch_bundesbank(),
    "NBP":         lambda _: _fetch_nbp(),
    "CNB":         lambda _: _fetch_cnb(),
    "CBR":         lambda _: _fetch_cbr(),
    "RIKSBANK":    lambda _: _fetch_riksbank(),
    "NORGES":      lambda _: _fetch_norges(),
    "DN":          lambda _: _fetch_dn(),
    "BOC":         lambda _: _fetch_boc(),
    "open.er-api": lambda base: _fetch_open_er(base),
}

# Display names shown in the UI
SOURCE_LABELS = {
    "BNR":         "BNR — Banca Nationala a Romaniei",
    "ECB":         "ECB — Banca Centrala Europeana",
    "BUBA":        "Bundesbank — Germania",
    "NBP":         "NBP — Narodowy Bank Polski (Polonia)",
    "CNB":         "CNB — Ceska narodni banka (Cehia)",
    "CBR":         "CBR — Banca Centrala a Rusiei",
    "RIKSBANK":    "Riksbank — Suedia",
    "NORGES":      "Norges Bank — Norvegia",
    "DN":          "Danmarks Nationalbank — Danemarca",
    "BOC":         "Bank of Canada — Canada",
    "open.er-api": "open.er-api.com — universal (orice moneda)",
}


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

class _RateCache:
    def __init__(self) -> None:
        self._native_currency: str = "RON"
        self._rates: Dict[str, float] = {}
        self._fetched_at: float = 0.0
        self._source: str = "BNR"
        self._base: str = "RON"       # user-selected base currency
        self._lock = threading.Lock()

    def configure(self, source: str, base_currency: str) -> None:
        changed = (source != self._source) or (base_currency != self._base)
        self._source = source
        self._base   = base_currency.upper()
        if changed:
            self._fetched_at = 0.0   # force re-fetch on source/base change

    def is_fresh(self) -> bool:
        return bool(self._rates) and (time.time() - self._fetched_at) < _TTL_SECONDS

    def refresh(self) -> bool:
        self._fetched_at = 0.0
        self._refresh_if_stale()
        return self.is_fresh()

    def convert(self, amount: float, from_currency: str,
                to_currency: str) -> float:
        self._refresh_if_stale()
        from_currency = from_currency.upper()
        to_currency   = to_currency.upper()
        if from_currency == to_currency:
            return amount
        with self._lock:
            native = self._native_currency
            rates  = self._rates

        # from → native
        if from_currency == native:
            amt_native = amount
        else:
            r = rates.get(from_currency)
            amt_native = amount * r if r else amount

        # native → to
        if to_currency == native:
            return round(amt_native, 6)
        r2 = rates.get(to_currency)
        return round(amt_native / r2, 6) if r2 else amount

    def get_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        """Return rate: 1 from_currency = X to_currency, or None."""
        self._refresh_if_stale()
        from_currency = from_currency.upper()
        to_currency   = to_currency.upper()
        if from_currency == to_currency:
            return 1.0
        with self._lock:
            native = self._native_currency
            rates  = self._rates
        try:
            # Normalise both through native
            if from_currency == native:
                r_from = 1.0
            else:
                r_from = rates.get(from_currency)
                if r_from is None:
                    return None

            if to_currency == native:
                r_to = 1.0
            else:
                r_to = rates.get(to_currency)
                if r_to is None:
                    return None

            return round(r_from / r_to, 8)
        except Exception:
            return None

    def key_rates(self, display_currencies=("EUR", "USD", "GBP")) -> Dict[str, Optional[float]]:
        """Rates of common currencies expressed in the user's base_currency."""
        return {c: self.get_rate(c, self._base) for c in display_currencies
                if c != self._base}

    # ------------------------------------------------------------------
    def _refresh_if_stale(self) -> None:
        if self.is_fresh():
            return
        fetcher = _FETCHERS.get(self._source, _FETCHERS["BNR"])
        result  = fetcher(self._base)
        if result is None and self._source != "open.er-api":
            result = _fetch_open_er(self._base)
        if result:
            native, rates = result
            with self._lock:
                self._native_currency = native
                self._rates = rates
                self._fetched_at = time.time()
            logger.info("Rates refreshed via %s (native=%s, %d pairs)",
                        self._source, native, len(rates))
        else:
            logger.warning("All rate sources failed")


# Module-level singleton
_cache = _RateCache()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def configure(source: str, base_currency: str) -> None:
    """Call once at startup (and on settings change) to set source + base."""
    _cache.configure(source, base_currency)


def convert(amount: float, from_currency: str,
            to_currency: Optional[str] = None) -> float:
    """Convert amount. If to_currency is None, converts to the configured base."""
    if to_currency is None:
        to_currency = _cache._base
    return _cache.convert(amount, from_currency or "RON", to_currency)


def get_rate(from_currency: str,
             to_currency: Optional[str] = None) -> Optional[float]:
    if to_currency is None:
        to_currency = _cache._base
    return _cache.get_rate(from_currency, to_currency)


def key_rates() -> Dict[str, Optional[float]]:
    return _cache.key_rates()


def base_currency() -> str:
    return _cache._base


def source_name() -> str:
    return SOURCE_LABELS.get(_cache._source, _cache._source)


def is_rates_fresh() -> bool:
    return _cache.is_fresh()


def refresh_rates() -> bool:
    return _cache.refresh()
