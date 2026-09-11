"""
evaluate_risk_agent.py

Main evaluation runner for Risk Agent.
"""

import json
import time
from pathlib import Path

from risk_agent.evaluation.risk_test_utils import (
    load_dataset,
    build_state,
    extract_prediction,
    test_determinism,
    classification_metrics,
    structural_metrics,
    exact_case_accuracy,
    confusion_matrix,
)

from risk_agent.agent.risk_agent import run


# ============================================================
# PATHS / LABELS
# ============================================================

BASE_DIR = Path(
    __file__
).resolve().parent

LABELS = [
    "LOW",
    "MEDIUM",
    "HIGH",
]


# ============================================================
# RUN ONE CASE
# ============================================================

def evaluate_case(
    case,
):

    state = build_state(
        case
    )

    start = time.perf_counter()

    try:

        # ----------------------------------------------------
        # Run Risk Agent
        # ----------------------------------------------------

        run(
            state
        )

        elapsed = (
            time.perf_counter()
            - start
        ) * 1000

        # ----------------------------------------------------
        # Extract prediction
        # ----------------------------------------------------

        prediction = extract_prediction(
            state
        )

        # ----------------------------------------------------
        # Determinism
        # ----------------------------------------------------

        deterministic = test_determinism(
            case
        )

        return {

            "case_id": case.get(
                "case_id",
                "unknown",
            ),

            "expected": case[
                "expected"
            ],

            "prediction": prediction,

            "latency_ms": elapsed,

            "deterministic":
                deterministic,

            "error": None,
        }

    except Exception as e:

        return {

            "case_id": case.get(
                "case_id",
                "unknown",
            ),

            "expected": case.get(
                "expected",
                {},
            ),

            "prediction": {

                "overall": "ERROR",

                "route": "ERROR",

                "seasonal": "ERROR",

                "structural_high_risks": [],
            },

            "latency_ms": None,

            "deterministic": False,

            "error": (
                f"{type(e).__name__}: {e}"
            ),
        }


# ============================================================
# PRINT CASE RESULT
# ============================================================

def print_case_result(
    case,
    result,
):

    print(
        f"{case.get('case_id', 'unknown')} | "
        f"{case.get('name', 'Unnamed case')}"
    )

    if result["error"]:

        print(
            f"  ERROR: "
            f"{result['error']}"
        )

        return

    expected = result[
        "expected"
    ]

    prediction = result[
        "prediction"
    ]

    print(
        f"  Overall : "
        f"{expected.get('overall')} "
        f"-> "
        f"{prediction.get('overall')}"
    )

    print(
        f"  Route   : "
        f"{expected.get('route')} "
        f"-> "
        f"{prediction.get('route')}"
    )

    print(
        f"  Seasonal: "
        f"{expected.get('seasonal')} "
        f"-> "
        f"{prediction.get('seasonal')}"
    )

    print(
        f"  Structural HIGH risks: "
        f"{prediction.get('structural_high_risks', [])}"
    )

    print(
        f"  Latency : "
        f"{result['latency_ms']:.2f} ms"
    )

    print(
        f"  Stable  : "
        f"{result['deterministic']}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    dataset = load_dataset()

    print()

    print(
        "=" * 70
    )

    print(
        "RISK AGENT EVALUATION"
    )

    print(
        "=" * 70
    )

    print(
        f"Dataset size: "
        f"{len(dataset)}"
    )

    results = []

    # --------------------------------------------------------
    # Run benchmark
    # --------------------------------------------------------

    for case in dataset:

        result = evaluate_case(
            case
        )

        results.append(
            result
        )

        print()

        print_case_result(
            case,
            result,
        )

    # --------------------------------------------------------
    # Remove failed cases from metrics
    # --------------------------------------------------------

    valid = [

        result

        for result in results

        if result["error"] is None
    ]

    failed = [

        result

        for result in results

        if result["error"] is not None
    ]

    if not valid:

        print()

        print(
            "No valid cases were evaluated."
        )

        return

    # --------------------------------------------------------
    # Overall
    # --------------------------------------------------------

    y_true = [

        x["expected"]["overall"]

        for x in valid
    ]

    y_pred = [

        x["prediction"]["overall"]

        for x in valid
    ]

    overall = classification_metrics(
        y_true,
        y_pred,
        LABELS,
    )

    # --------------------------------------------------------
    # Route
    # --------------------------------------------------------

    route_true = [

        x["expected"]["route"]

        for x in valid
    ]

    route_pred = [

        x["prediction"]["route"]

        for x in valid
    ]

    route = classification_metrics(
        route_true,
        route_pred,
        LABELS,
    )

    # --------------------------------------------------------
    # Seasonal
    # --------------------------------------------------------

    seasonal_true = [

        x["expected"]["seasonal"]

        for x in valid
    ]

    seasonal_pred = [

        x["prediction"]["seasonal"]

        for x in valid
    ]

    seasonal = classification_metrics(
        seasonal_true,
        seasonal_pred,
        LABELS,
    )

    # --------------------------------------------------------
    # Structural
    # --------------------------------------------------------

    structural = structural_metrics(
        valid
    )

    # --------------------------------------------------------
    # Exact case
    # --------------------------------------------------------

    case_accuracy = (
        exact_case_accuracy(
            valid
        )
    )

    # --------------------------------------------------------
    # Determinism
    # --------------------------------------------------------

    deterministic = (

        sum(
            x["deterministic"]
            for x in valid
        )

        / len(valid)
    )

    # --------------------------------------------------------
    # Latency
    # --------------------------------------------------------

    latencies = [

        x["latency_ms"]

        for x in valid

        if x["latency_ms"] is not None
    ]

    average_latency = (

        sum(latencies)
        / len(latencies)

        if latencies

        else 0.0
    )

    # --------------------------------------------------------
    # Print final report
    # --------------------------------------------------------

    print()

    print(
        "=" * 70
    )

    print(
        "FINAL METRICS"
    )

    print(
        "=" * 70
    )

    # --------------------------------------------------------
    # Overall
    # --------------------------------------------------------

    print()

    print(
        "OVERALL RISK"
    )

    print(
        f"Accuracy : "
        f"{overall['accuracy']:.2%}"
    )

    print(
        f"Macro F1 : "
        f"{overall['macro_f1']:.3f}"
    )

    for label, metric in (
        overall["per_class"].items()
    ):

        print(
            f"  {label:<6} "
            f"P={metric['precision']:.3f} "
            f"R={metric['recall']:.3f} "
            f"F1={metric['f1']:.3f}"
        )

    # --------------------------------------------------------
    # Route
    # --------------------------------------------------------

    print()

    print(
        "ROUTE RISK"
    )

    print(
        f"Accuracy : "
        f"{route['accuracy']:.2%}"
    )

    print(
        f"Macro F1 : "
        f"{route['macro_f1']:.3f}"
    )

    # --------------------------------------------------------
    # Seasonal
    # --------------------------------------------------------

    print()

    print(
        "SEASONAL RISK"
    )

    print(
        f"Accuracy : "
        f"{seasonal['accuracy']:.2%}"
    )

    print(
        f"Macro F1 : "
        f"{seasonal['macro_f1']:.3f}"
    )

    # --------------------------------------------------------
    # Structural
    # --------------------------------------------------------

    print()

    print(
        "STRUCTURAL RISK"
    )

    print(
        f"Precision: "
        f"{structural['precision']:.3f}"
    )

    print(
        f"Recall   : "
        f"{structural['recall']:.3f}"
    )

    print(
        f"F1       : "
        f"{structural['f1']:.3f}"
    )

    print(
        f"Exact    : "
        f"{structural['exact_match_accuracy']:.2%}"
    )

    # --------------------------------------------------------
    # System
    # --------------------------------------------------------

    print()

    print(
        "SYSTEM"
    )

    print(
        f"Exact Case Accuracy : "
        f"{case_accuracy:.2%}"
    )

    print(
        f"Determinism         : "
        f"{deterministic:.2%}"
    )

    print(
        f"Average Latency     : "
        f"{average_latency:.2f} ms"
    )

    print(
        f"Valid Cases         : "
        f"{len(valid)}/{len(results)}"
    )

    print(
        f"Failed Cases        : "
        f"{len(failed)}"
    )

    # --------------------------------------------------------
    # Confusion matrix
    # --------------------------------------------------------

    matrix = confusion_matrix(
        y_true,
        y_pred,
        LABELS,
    )

    print()

    print(
        "CONFUSION MATRIX"
    )

    print()

    print(
        f"{'Actual':<10}"
        f"{'LOW':>8}"
        f"{'MEDIUM':>10}"
        f"{'HIGH':>8}"
    )

    for actual in LABELS:

        print(
            f"{actual:<10}"
            f"{matrix[actual]['LOW']:>8}"
            f"{matrix[actual]['MEDIUM']:>10}"
            f"{matrix[actual]['HIGH']:>8}"
        )

    # --------------------------------------------------------
    # Failed cases
    # --------------------------------------------------------

    if failed:

        print()

        print(
            "FAILED CASES"
        )

        for result in failed:

            print(
                f"  {result['case_id']}: "
                f"{result['error']}"
            )

    # --------------------------------------------------------
    # Save JSON report
    # --------------------------------------------------------

    report = {

        "dataset_size":
            len(dataset),

        "valid_cases":
            len(valid),

        "failed_cases":
            len(failed),

        "overall":
            overall,

        "route":
            route,

        "seasonal":
            seasonal,

        "structural":
            structural,

        "exact_case_accuracy":
            case_accuracy,

        "determinism":
            deterministic,

        "average_latency_ms":
            average_latency,

        "confusion_matrix":
            matrix,

        "cases":
            results,
    }

    report_path = (
        BASE_DIR
        / "risk_evaluation_report.json"
    )

    with open(
        report_path,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            report,
            f,
            indent=2,
        )

    print()

    print(
        "Detailed report:"
    )

    print(
        report_path
    )

    print()

    print(
        "=" * 70
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()