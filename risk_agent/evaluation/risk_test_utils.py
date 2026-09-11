"""
risk_test_utils.py

Helper functions for Risk Agent evaluation.

Contains:

- Dataset loading
- CaseState construction
- Agent output normalization
- Classification metrics
- Structural risk metrics
- Exact case scoring
- Determinism testing
"""

import json
from pathlib import Path
from typing import Any

from risk_agent.agent.risk_agent import (
    CaseState,
    MarketIntelligence,
    EntrepreneurProfile,
    BusinessCandidate,
    Coordinates,
    MarketReachRecord,
    PricingRecord,
    CompetitorRecord,
    run,
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DATASET_PATH = (
    BASE_DIR / "dummy_risk_cases.json"
)


# ============================================================
# DATASET
# ============================================================

def load_dataset():

    if not DATASET_PATH.exists():

        raise FileNotFoundError(
            f"Dataset not found: {DATASET_PATH}"
        )

    with open(
        DATASET_PATH,
        "r",
        encoding="utf-8",
    ) as f:

        return json.load(f)


# ============================================================
# SAFE DATA ACCESS
# ============================================================

def _first(
    data: dict,
    *keys,
    default=None,
):
    """
    Return the first existing non-None key.
    """

    for key in keys:

        if key in data and data[key] is not None:
            return data[key]

    return default


def _normalise_context_value(value) -> str:

    if value is None:
        return ""

    if isinstance(value, bool):
        return "yes" if value else "no"

    return str(value).strip().lower()


# ============================================================
# STATE BUILDER
# ============================================================

def build_state(case):
    """
    Convert one JSON benchmark case into the
    CaseState schema used by risk_agent.py.

    Supports the current schema and the older benchmark
    naming convention that appeared in the original
    evaluation utility.
    """

    # --------------------------------------------------------
    # Origin
    # --------------------------------------------------------

    origin = _first(
        case,
        "origin",
        default={},
    )

    origin_lat = _first(
        origin,
        "lat",
        "latitude",
    )

    origin_lon = _first(
        origin,
        "lon",
        "longitude",
    )

    if origin_lat is None or origin_lon is None:

        raise ValueError(
            f"{case.get('case_id', 'unknown')}: "
            "origin must contain lat/lon."
        )

    # --------------------------------------------------------
    # Distribution point
    # --------------------------------------------------------

    distribution = _first(
        case,
        "distribution_point",
        "nearest_distribution_point",
        default=None,
    )

    distribution_points = []

    if distribution:

        if isinstance(
            distribution,
            dict,
        ):

            lat = _first(
                distribution,
                "lat",
                "latitude",
            )

            lon = _first(
                distribution,
                "lon",
                "longitude",
            )

            if lat is not None and lon is not None:

                distribution_points.append(
                    Coordinates(
                        lat=float(lat),
                        lon=float(lon),
                    )
                )

    # Support a plural list if present.
    raw_points = case.get(
        "distribution_points",
        []
    )

    if raw_points:

        for point in raw_points:

            if not isinstance(point, dict):
                continue

            lat = _first(
                point,
                "lat",
                "latitude",
            )

            lon = _first(
                point,
                "lon",
                "longitude",
            )

            if lat is not None and lon is not None:

                distribution_points.append(
                    Coordinates(
                        lat=float(lat),
                        lon=float(lon),
                    )
                )

    # --------------------------------------------------------
    # Price history
    # --------------------------------------------------------

    price_history = _first(
        case,
        "price_history",
        "commodity_price_series",
        default=[],
    )

    if price_history is None:
        price_history = []

    price_history = list(
        price_history
    )

    price_start = _first(
        case,
        "price_series_start",
        "price_history_start",
        default="2023-01",
    )

    # --------------------------------------------------------
    # Structural context
    # --------------------------------------------------------

    structural_context = {}

    # If the dataset already contains a complete context,
    # preserve it.
    raw_context = case.get(
        "structural_context",
        {}
    )

    if isinstance(
        raw_context,
        dict,
    ):

        for key, value in raw_context.items():

            structural_context[
                str(key)
            ] = _normalise_context_value(
                value
            )

    # --------------------------------------------------------
    # Buyer concentration
    # --------------------------------------------------------

    buyer_count = _first(
        case,
        "buyer_count",
        default=None,
    )

    if buyer_count is not None:

        structural_context[
            "buyer_count"
        ] = _normalise_context_value(
            buyer_count
        )

    else:

        buyer_concentration = _first(
            case,
            "buyer_concentration",
            default=None,
        )

        if buyer_concentration is not None:

            value = _normalise_context_value(
                buyer_concentration
            )

            # Convert common benchmark labels.
            if value in {
                "single",
                "one",
                "1",
                "high",
            }:
                structural_context[
                    "buyer_count"
                ] = "1"

            elif value in {
                "low",
                "many",
                "multiple",
            }:
                structural_context[
                    "buyer_count"
                ] = "5"

            elif value.isdigit():

                structural_context[
                    "buyer_count"
                ] = value

    # --------------------------------------------------------
    # Perishability
    # --------------------------------------------------------

    perishable = _first(
        case,
        "perishable",
        default=None,
    )

    if perishable is not None:

        structural_context[
            "perishable"
        ] = _normalise_context_value(
            perishable
        )

    # --------------------------------------------------------
    # Cold storage
    # --------------------------------------------------------

    cold_storage = _first(
        case,
        "cold_storage",
        default=None,
    )

    if cold_storage is not None:

        structural_context[
            "cold_storage"
        ] = _normalise_context_value(
            cold_storage
        )

    # --------------------------------------------------------
    # Licensing
    # --------------------------------------------------------

    license_required = _first(
        case,
        "license_required",
        "licensing_required",
        default=None,
    )

    if license_required is not None:

        structural_context[
            "license_required"
        ] = _normalise_context_value(
            license_required
        )

    # --------------------------------------------------------
    # Capital intensity
    # --------------------------------------------------------

    capital_intensity = _first(
        case,
        "capital_intensity",
        default=None,
    )

    if capital_intensity is not None:

        structural_context[
            "capital_intensity"
        ] = _normalise_context_value(
            capital_intensity
        )

    # --------------------------------------------------------
    # Skill experience
    # --------------------------------------------------------

    skill_experience = _first(
        case,
        "skill_experience",
        "skill_level",
        default=None,
    )

    if skill_experience is not None:

        structural_context[
            "skill_experience"
        ] = _normalise_context_value(
            skill_experience
        )

    # --------------------------------------------------------
    # Infrastructure
    # --------------------------------------------------------

    infrastructure = _first(
        case,
        "infrastructure_reliability",
        "infrastructure",
        default=None,
    )

    if infrastructure is not None:

        structural_context[
            "infrastructure_reliability"
        ] = _normalise_context_value(
            infrastructure
        )

    # --------------------------------------------------------
    # Single supplier
    # --------------------------------------------------------

    single_supplier = _first(
        case,
        "single_supplier",
        default=None,
    )

    if single_supplier is not None:

        structural_context[
            "single_supplier"
        ] = _normalise_context_value(
            single_supplier
        )

    # --------------------------------------------------------
    # Market saturation
    # --------------------------------------------------------

    market_saturation = _first(
        case,
        "market_saturation",
        default=None,
    )

    if market_saturation is None:

        market_saturation = (
            structural_context.get(
                "market_saturation"
            )
        )

    if market_saturation is None:

        market_saturation = "low"

    market_saturation = (
        _normalise_context_value(
            market_saturation
        )
    )

    # --------------------------------------------------------
    # Build CaseState
    # --------------------------------------------------------

    profile = EntrepreneurProfile(

        location=Coordinates(
            lat=float(origin_lat),
            lon=float(origin_lon),
        ),

        structural_context=structural_context,
    )

    business_category = _first(
        case,
        "business_category",
        "category",
        default="unknown business",
    )

    candidate = BusinessCandidate(

        business_category=str(
            business_category
        ),

        selected=True,
    )

    market_reach = MarketReachRecord(

        distribution_points=distribution_points
    )

    pricing = PricingRecord(

        commodity_price_series=price_history,

        price_series_start=str(
            price_start
        ),
    )

    competitors = CompetitorRecord(

        market_saturation=market_saturation
    )

    return CaseState(

        entrepreneur_profile=profile,

        business_shortlist=[
            candidate
        ],

        market_intelligence=(
            MarketIntelligence(

                market_reach=market_reach,

                pricing=pricing,

                competitor=competitors,
            )
        ),
    )


# ============================================================
# GENERIC OBJECT READER
# ============================================================

def get_value(
    obj,
    *names,
    default=None,
):
    """
    Works with Pydantic models, dataclasses
    and normal objects.
    """

    for name in names:

        if hasattr(
            obj,
            name,
        ):

            value = getattr(
                obj,
                name,
            )

            if value is not None:
                return value

    return default


# ============================================================
# SEVERITY NORMALIZATION
# ============================================================

def normalize_severity(
    value,
):

    if value is None:
        return None

    if hasattr(
        value,
        "value",
    ):

        value = value.value

    return str(
        value
    ).upper()


# ============================================================
# OUTPUT EXTRACTION
# ============================================================

def extract_prediction(
    state,
):
    """
    Convert Risk Agent output into a normalized dictionary.
    """

    if (
        state.market_intelligence is None
        or state.market_intelligence.risk is None
    ):

        raise ValueError(
            "Risk Agent did not produce a risk record."
        )

    risk = (
        state
        .market_intelligence
        .risk
    )

    # --------------------------------------------------------
    # Overall
    # --------------------------------------------------------

    overall = normalize_severity(
        get_value(
            risk,
            "overall_severity",
            "overall_risk",
            "overall",
            "severity",
        )
    )

    # --------------------------------------------------------
    # Route
    # --------------------------------------------------------

    route = normalize_severity(
        get_value(
            risk,
            "route_risk",
            "route_severity",
        )
    )

    # --------------------------------------------------------
    # Seasonal
    # --------------------------------------------------------

    seasonal = normalize_severity(
        get_value(
            risk,
            "seasonal_risk",
            "seasonal_severity",
        )
    )

    # --------------------------------------------------------
    # Structural
    # --------------------------------------------------------

    structural = []

    flags = get_value(
        risk,
        "structural_risk_flags",
        "flags",
        "risk_flags",
        "structural_risks",
        default=[],
    )

    for flag in flags or []:

        if isinstance(
            flag,
            str,
        ):

            name = flag

            severity = None

        else:

            name = get_value(
                flag,
                "risk_type",
                "category",
                "name",
                "code",
            )

            severity = normalize_severity(
                get_value(
                    flag,
                    "severity",
                )
            )

        # IMPORTANT:
        # Only HIGH structural risks belong in
        # structural_high_risks.
        if (
            name
            and severity == "HIGH"
        ):

            structural.append(
                str(name).lower()
            )

    return {

        "overall": overall,

        "route": route,

        "seasonal": seasonal,

        "structural_high_risks": sorted(
            set(structural)
        ),
    }


# ============================================================
# CLASSIFICATION METRICS
# ============================================================

def classification_metrics(
    y_true,
    y_pred,
    labels,
):

    if len(y_true) != len(y_pred):

        raise ValueError(
            "y_true and y_pred must have the same length."
        )

    per_class = {}

    for label in labels:

        tp = sum(
            actual == label
            and predicted == label
            for actual, predicted
            in zip(
                y_true,
                y_pred,
            )
        )

        fp = sum(
            actual != label
            and predicted == label
            for actual, predicted
            in zip(
                y_true,
                y_pred,
            )
        )

        fn = sum(
            actual == label
            and predicted != label
            for actual, predicted
            in zip(
                y_true,
                y_pred,
            )
        )

        precision = (
            tp / (tp + fp)
            if tp + fp
            else 0.0
        )

        recall = (
            tp / (tp + fn)
            if tp + fn
            else 0.0
        )

        f1 = (
            2 * precision * recall
            / (precision + recall)
            if precision + recall
            else 0.0
        )

        per_class[label] = {

            "precision": precision,

            "recall": recall,

            "f1": f1,

            "support": tp + fn,
        }

    accuracy = (
        sum(
            a == p
            for a, p
            in zip(
                y_true,
                y_pred,
            )
        )
        / len(y_true)
        if y_true
        else 0.0
    )

    macro_f1 = (
        sum(
            x["f1"]
            for x in per_class.values()
        )
        / len(labels)
        if labels
        else 0.0
    )

    return {

        "accuracy": accuracy,

        "macro_f1": macro_f1,

        "per_class": per_class,
    }


# ============================================================
# STRUCTURAL RISK METRICS
# ============================================================

def structural_metrics(
    cases,
):

    tp = 0
    fp = 0
    fn = 0
    exact_matches = 0

    for case in cases:

        expected = set(
            case["expected"].get(
                "structural_high_risks",
                [],
            )
        )

        predicted = set(
            case["prediction"].get(
                "structural_high_risks",
                [],
            )
        )

        if expected == predicted:
            exact_matches += 1

        tp += len(
            expected & predicted
        )

        fp += len(
            predicted - expected
        )

        fn += len(
            expected - predicted
        )

    precision = (
        tp / (tp + fp)
        if tp + fp
        else 0.0
    )

    recall = (
        tp / (tp + fn)
        if tp + fn
        else 0.0
    )

    f1 = (
        2 * precision * recall
        / (precision + recall)
        if precision + recall
        else 0.0
    )

    exact_accuracy = (
        exact_matches / len(cases)
        if cases
        else 0.0
    )

    return {

        "precision": precision,

        "recall": recall,

        "f1": f1,

        "exact_match_accuracy":
            exact_accuracy,
    }


# ============================================================
# EXACT CASE ACCURACY
# ============================================================

def exact_case_accuracy(
    cases,
):

    correct = 0

    for case in cases:

        expected = case["expected"]

        predicted = case["prediction"]

        if (
            expected.get("overall")
            == predicted.get("overall")

            and expected.get("route")
            == predicted.get("route")

            and expected.get("seasonal")
            == predicted.get("seasonal")

            and set(
                expected.get(
                    "structural_high_risks",
                    [],
                )
            )
            ==
            set(
                predicted.get(
                    "structural_high_risks",
                    [],
                )
            )
        ):

            correct += 1

    return (
        correct / len(cases)
        if cases
        else 0.0
    )


# ============================================================
# DETERMINISM
# ============================================================

def test_determinism(
    case,
    repetitions=3,
):

    outputs = []

    for _ in range(
        repetitions
    ):

        state = build_state(
            case
        )

        run(
            state
        )

        prediction = extract_prediction(
            state
        )

        outputs.append(
            json.dumps(
                prediction,
                sort_keys=True,
            )
        )

    return len(
        set(outputs)
    ) == 1


# ============================================================
# CONFUSION MATRIX
# ============================================================

def confusion_matrix(
    y_true,
    y_pred,
    labels,
):

    matrix = {

        actual: {

            predicted: 0
            for predicted in labels

        }

        for actual in labels
    }

    for actual, predicted in zip(
        y_true,
        y_pred,
    ):

        if (
            actual in matrix
            and predicted in matrix[actual]
        ):

            matrix[
                actual
            ][
                predicted
            ] += 1

    return matrix