"""
Pegas operator configuration.

Unlike FunSun/Kompas (SAMO-based, public search, no login), Pegas:
- runs its own non-SAMO JSON REST API
- requires an authenticated session (ASP.NET Core cookie auth)
- returns a single self-contained catalog (countries/resorts/hotels/meals)
  via GetInitialOptions, rather than per-request mapping lookups

See PEGAS_PROJECT_SUMMARY.md sections 2.1 and 6 in the original handoff doc
for the architectural rationale.
"""
from __future__ import annotations

BASE_URL = "https://kz.pegast.asia"

GET_INITIAL_OPTIONS_PATH = "/PackageSearch/GetInitialOptions"
SEARCH_PATH = "/PackageSearch/Search"

# operators.code value for this connector, used to resolve the Operator row
# and to key OperatorSession lookups.
OPERATOR_CODE = "pegas"

DEFAULT_HEADERS = {
    "Content-Type": "application/json; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/",
}