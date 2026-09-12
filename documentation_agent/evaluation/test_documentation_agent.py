"""
test_documentation_agent.py

Detailed test / evaluation harness for:

    module2_financial/documentation_agent.py

Aligned with TECHNICAL_SETUP.md, Section 6.5.

Covers:

1. Dataset-driven evaluation
   - form_data correctness
   - document completion status
   - missing required fields
   - simulated one-field-at-a-time voice collection

2. Contract / structural tests
   - exact run(state) interface
   - Documentation Agent only writes application_status.form_data
   - financial_plan is read-only
   - entrepreneur_profile is read-only
   - business_shortlist is read-only
   - feasibility_record is read-only
   - missing values are never invented
   - blank answers are rejected
   - invalid formatted answers are rejected
   - valid answers are persisted
   - values are reused across documents
   - repeated runs are deterministic
   - upstream-owned fields are not collectable
   - one question is returned at a time
   - required missing fields cannot produce COMPLETE status
   - old bulk arguments are not part of run()

3. Human-readable report

Run:

    python -m unittest test_documentation_agent.py -v

or:

    python test_documentation_agent.py
"""

from __future__ import annotations

import copy
import inspect
import json
import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List

from documentation_agent.agent.documentation_agent import (
    DOCUMENT_TEMPLATES,
    DocumentAutoFiller,
    DocumentStatus,
    DocumentationAgent,
    FieldStatus,
    run,
)

from orchestrator.state import (
    ApplicationStatus,
    BusinessCandidate,
    CaseState,
    EntrepreneurProfile,
    FeasibilityRecord,
    FinancialPlan,
    Location,
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DATASET_PATH = BASE_DIR / "dummy_documentation_cases.json"

REPORT_PATH = (
    BASE_DIR / "documentation_evaluation_report.json"
)


# ============================================================
# DATASET LOADING
# ============================================================

def load_dataset() -> List[Dict[str, Any]]:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATASET_PATH}"
        )

    with open(
        DATASET_PATH,
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(
            "dummy_documentation_cases.json "
            "must contain a JSON list."
        )

    return data


# ============================================================
# CASE STATE BUILDER
# ============================================================

def build_state(case: Dict[str, Any]) -> CaseState:
    """
    Convert one JSON benchmark case into the shared CaseState schema.

    This test harness deliberately constructs the same shared CaseState
    consumed by documentation_agent.py.
    """

    profile_data = (
        case.get("entrepreneur_profile")
        or {}
    )

    location_data = (
        profile_data.get("location")
    )

    entrepreneur_profile = EntrepreneurProfile(
        name=profile_data.get("name"),
        aadhaar_number=profile_data.get(
            "aadhaar_number"
        ),
        pan_number=profile_data.get(
            "pan_number"
        ),
        phone_number=profile_data.get(
            "phone_number"
        ),
        bank_account=profile_data.get(
            "bank_account"
        ),
        guarantor_name=profile_data.get(
            "guarantor_name"
        ),
        available_capital=profile_data.get(
            "available_capital"
        ),
        location=(
            Location(
                address=location_data.get(
                    "address"
                )
            )
            if location_data
            else None
        ),
    )

    business_shortlist = [
        BusinessCandidate(
            business_category=candidate[
                "business_category"
            ],
            selected=candidate.get(
                "selected",
                False,
            ),
        )
        for candidate in case.get(
            "business_shortlist",
            [],
        )
    ]

    financial_plan_data = case.get(
        "financial_plan"
    )

    financial_plan = (
        FinancialPlan(
            **financial_plan_data
        )
        if financial_plan_data
        else None
    )

    feasibility_data = case.get(
        "feasibility_record"
    )

    feasibility_record = (
        FeasibilityRecord(
            **feasibility_data
        )
        if feasibility_data
        else None
    )

    return CaseState(
        entrepreneur_profile=entrepreneur_profile,
        business_shortlist=business_shortlist,
        financial_plan=financial_plan,
        feasibility_record=feasibility_record,
        application_status=ApplicationStatus(
            form_data={}
        ),
    )


# ============================================================
# TEMPLATE HELPERS
# ============================================================

def get_template(
    document_name: str,
):
    for template in DOCUMENT_TEMPLATES:
        if template.name == document_name:
            return template

    raise KeyError(
        f"Unknown document template: {document_name}"
    )


def required_keys(
    document_name: str,
) -> List[str]:
    template = get_template(document_name)

    return [
        field.key
        for field in template.fields
        if field.required
    ]


def collectable_keys(
    document_name: str,
) -> List[str]:
    template = get_template(document_name)

    return [
        field.key
        for field in template.fields
        if field.collectable
    ]


def is_present(value: Any) -> bool:
    if value is None:
        return False

    if isinstance(value, str):
        return bool(value.strip())

    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)

    return True


# ============================================================
# INDEPENDENT STATUS DERIVATION
# ============================================================

def derive_status(
    document_name: str,
    form_data_for_doc: Dict[str, Any],
) -> str:
    """
    Independently derive status from the document template.

    This intentionally does not use the agent's internal checklist status.
    """

    required = required_keys(
        document_name
    )

    present = [
        key
        for key in required
        if is_present(
            form_data_for_doc.get(key)
        )
    ]

    if len(present) == len(required):
        return DocumentStatus.COMPLETE.value

    if len(present) == 0:
        return DocumentStatus.MISSING.value

    return DocumentStatus.PENDING.value


def missing_required(
    document_name: str,
    form_data_for_doc: Dict[str, Any],
) -> List[str]:
    required = required_keys(
        document_name
    )

    return [
        key
        for key in required
        if not is_present(
            form_data_for_doc.get(key)
        )
    ]


# ============================================================
# DATASET VOICE SIMULATION
# ============================================================

def simulate_voice_collection(
    state: CaseState,
    dummy_user_responses: Dict[str, Dict[str, Any]],
    language: str = "Hindi",
    max_turns: int = 100,
) -> CaseState:
    """
    Simulate the actual one-field-at-a-time conversational workflow.

    Each turn:

        1. run(state)
        2. agent.get_next_question()
        3. retrieve benchmark answer
        4. agent.accept_answer()
        5. repeat

    No hidden bulk collection method is used.
    """

    agent = DocumentationAgent(
        state=state,
        language=language,
    )

    for _ in range(max_turns):

        # Synchronize CaseState-derived values.
        run(state)

        next_question = agent.get_next_question()

        if next_question is None:
            break

        document_name = next_question[
            "document"
        ]

        field_key = next_question[
            "field"
        ]

        document_answers = (
            dummy_user_responses.get(
                document_name,
                {},
            )
        )

        if not isinstance(
            document_answers,
            dict,
        ):
            document_answers = {}

        if field_key not in document_answers:
            # No benchmark answer means the simulated user
            # did not answer this field.
            break

        raw_answer = document_answers[
            field_key
        ]

        result = agent.accept_answer(
            document_name=document_name,
            field_key=field_key,
            answer=raw_answer,
        )

        if not result["accepted"]:
            # A supplied invalid answer must not create
            # an infinite loop.
            break

    else:
        raise RuntimeError(
            "Voice collection exceeded max_turns. "
            "Possible infinite question/answer loop."
        )

    # Final synchronization.
    run(state)

    return state


# ============================================================
# SINGLE-CASE DATASET EVALUATION
# ============================================================

def evaluate_case(
    case: Dict[str, Any],
) -> Dict[str, Any]:

    state = build_state(case)

    dummy_user_responses = (
        case.get(
            "dummy_user_responses",
            {},
        )
    )

    language = case.get(
        "language",
        "Hindi",
    )

    expected = case.get(
        "expected",
        {},
    )

    errors: List[str] = []

    try:
        final_state = simulate_voice_collection(
            state=state,
            dummy_user_responses=dummy_user_responses,
            language=language,
        )

        application_status = (
            final_state.application_status
        )

        if application_status is None:
            raise AssertionError(
                "application_status was not created."
            )

        observed_form_data = (
            application_status.form_data
            or {}
        )

        # ----------------------------------------------------
        # Field-by-field comparison
        # ----------------------------------------------------

        expected_form_data = expected.get(
            "form_data",
            {},
        )

        for (
            document_name,
            expected_fields,
        ) in expected_form_data.items():

            observed_fields = (
                observed_form_data.get(
                    document_name,
                    {},
                )
            )

            if not isinstance(
                observed_fields,
                dict,
            ):
                errors.append(
                    f"[{document_name}] "
                    "observed form_data is not a dictionary"
                )
                continue

            for (
                key,
                expected_value,
            ) in expected_fields.items():

                observed_value = (
                    observed_fields.get(key)
                )

                if observed_value != expected_value:
                    errors.append(
                        f"[{document_name}.{key}] "
                        f"expected={expected_value!r} "
                        f"observed={observed_value!r}"
                    )

            unexpected_extra = (
                set(observed_fields)
                - set(expected_fields)
            )

            if unexpected_extra:
                errors.append(
                    f"[{document_name}] "
                    f"unexpected extra fields: "
                    f"{sorted(unexpected_extra)}"
                )

        # ----------------------------------------------------
        # Independently derived document status
        # ----------------------------------------------------

        for (
            document_name,
            expected_status,
        ) in expected.get(
            "document_status",
            {},
        ).items():

            observed_fields = (
                observed_form_data.get(
                    document_name,
                    {},
                )
            )

            observed_status = derive_status(
                document_name,
                observed_fields,
            )

            if observed_status != expected_status:
                errors.append(
                    f"[{document_name}] "
                    f"status expected="
                    f"{expected_status!r} "
                    f"observed="
                    f"{observed_status!r}"
                )

        # ----------------------------------------------------
        # Missing required fields
        # ----------------------------------------------------

        for (
            document_name,
            expected_missing,
        ) in expected.get(
            "missing_required_after_collection",
            {},
        ).items():

            observed_fields = (
                observed_form_data.get(
                    document_name,
                    {},
                )
            )

            observed_missing = missing_required(
                document_name,
                observed_fields,
            )

            if sorted(observed_missing) != sorted(
                expected_missing
            ):
                errors.append(
                    f"[{document_name}] "
                    f"missing_required expected="
                    f"{sorted(expected_missing)} "
                    f"observed="
                    f"{sorted(observed_missing)}"
                )

        return {
            "case_id": case.get(
                "case_id",
                "unknown",
            ),
            "name": case.get(
                "name",
                "",
            ),
            "passed": len(errors) == 0,
            "errors": errors,
            "observed_form_data": (
                observed_form_data
            ),
        }

    except Exception as exc:
        return {
            "case_id": case.get(
                "case_id",
                "unknown",
            ),
            "name": case.get(
                "name",
                "",
            ),
            "passed": False,
            "errors": [
                f"{type(exc).__name__}: {exc}"
            ],
            "observed_form_data": {},
        }


# ============================================================
# UNITTEST: DATASET
# ============================================================

class TestDocumentationAgentDataset(
    unittest.TestCase
):

    @classmethod
    def setUpClass(cls) -> None:
        cls.dataset = load_dataset()

    def test_all_cases(self) -> None:
        for case in self.dataset:

            with self.subTest(
                case_id=case.get("case_id")
            ):
                result = evaluate_case(
                    case
                )

                self.assertTrue(
                    result["passed"],
                    msg=(
                        f"{result['case_id']} "
                        f"({result['name']}) failed:\n"
                        + "\n".join(
                            result["errors"]
                        )
                    ),
                )


# ============================================================
# UNITTEST: CONTRACT / STRUCTURAL BEHAVIOUR
# ============================================================

class TestDocumentationAgentContract(
    unittest.TestCase
):

    # --------------------------------------------------------
    # Shared complete state
    # --------------------------------------------------------

    def _complete_state(self) -> CaseState:

        return CaseState(
            entrepreneur_profile=(
                EntrepreneurProfile(
                    name="Test User",
                    aadhaar_number="123456789012",
                    pan_number="ABCDE1234F",
                    phone_number="9000000000",
                    bank_account="000111222",
                    guarantor_name="Test Guarantor",
                    available_capital=50000,
                    location=Location(
                        address=(
                            "Test Village, "
                            "Test District"
                        )
                    ),
                )
            ),

            business_shortlist=[
                BusinessCandidate(
                    business_category="test business",
                    selected=True,
                )
            ],

            financial_plan=FinancialPlan(
                project_cost=500000,
                loan_eligibility=450000,
                scheme_tier="term_loan",
            ),

            feasibility_record=(
                FeasibilityRecord(
                    verdict="viable"
                )
            ),

            application_status=ApplicationStatus(
                form_data={}
            ),
        )

    # --------------------------------------------------------
    # run() signature
    # --------------------------------------------------------

    def test_run_signature(self) -> None:

        signature = inspect.signature(
            run
        )

        parameters = list(
            signature.parameters.values()
        )

        self.assertEqual(
            len(parameters),
            1,
            "run() must expose exactly one "
            "argument: state",
        )

        self.assertEqual(
            parameters[0].name,
            "state",
        )

        self.assertEqual(
            str(
                parameters[0].annotation
            ),
            "CaseState",
        )

    # --------------------------------------------------------
    # State mutation contract
    # --------------------------------------------------------

    def test_writes_only_application_status_form_data(
        self,
    ) -> None:

        state = self._complete_state()

        before = state.model_dump(
            mode="json"
        )

        before_application_status = (
            copy.deepcopy(
                before.get(
                    "application_status"
                )
            )
        )

        run(state)

        after = state.model_dump(
            mode="json"
        )

        after_application_status = (
            copy.deepcopy(
                after.get(
                    "application_status"
                )
            )
        )

        # Remove application_status completely.
        # Everything else in CaseState must remain unchanged.
        before_without_application = copy.deepcopy(
            before
        )

        after_without_application = copy.deepcopy(
            after
        )

        before_without_application.pop(
            "application_status",
            None,
        )

        after_without_application.pop(
            "application_status",
            None,
        )

        self.assertEqual(
            before_without_application,
            after_without_application,
            "run() mutated a CaseState field outside "
            "application_status.form_data.",
        )

        self.assertIsInstance(
            state.application_status,
            ApplicationStatus,
        )

        self.assertTrue(
            hasattr(
                state.application_status,
                "form_data",
            )
        )

        # Documentation Agent must not own checklist.
        if hasattr(
            state.application_status,
            "checklist",
        ):
            self.assertIsNone(
                state.application_status.checklist
            )

        # Documentation Agent must not own disbursement.
        if hasattr(
            state.application_status,
            "disbursement_status",
        ):
            self.assertIsNone(
                state.application_status.disbursement_status
            )

        # application_status itself should change because form_data
        # is populated, not because another field is changed.
        self.assertNotEqual(
            before_application_status,
            after_application_status,
        )

    # --------------------------------------------------------
    # No invention
    # --------------------------------------------------------

    def test_never_invents_missing_required_value(
        self,
    ) -> None:

        state = CaseState(
            entrepreneur_profile=(
                EntrepreneurProfile(
                    name="No Aadhaar"
                )
            ),

            business_shortlist=[
                BusinessCandidate(
                    business_category="x",
                    selected=True,
                )
            ],

            financial_plan=FinancialPlan(
                project_cost=100000
            ),

            application_status=ApplicationStatus(
                form_data={}
            ),
        )

        run(state)

        self.assertIsNotNone(
            state.application_status
        )

        udyam = (
            state.application_status.form_data.get(
                "Udyam Registration",
                {},
            )
        )

        self.assertNotIn(
            "aadhaar_number",
            udyam,
            "Agent must not fabricate a value for "
            "an unanswered field.",
        )

    # --------------------------------------------------------
    # Blank response
    # --------------------------------------------------------

    def test_blank_voice_answer_is_rejected(
        self,
    ) -> None:

        state = self._complete_state()

        state.entrepreneur_profile.aadhaar_number = None

        run(state)

        agent = DocumentationAgent(
            state,
            language="English",
        )

        result = agent.accept_answer(
            document_name="Udyam Registration",
            field_key="aadhaar_number",
            answer="   ",
        )

        self.assertFalse(
            result["accepted"]
        )

        udyam = (
            state.application_status.form_data.get(
                "Udyam Registration",
                {},
            )
        )

        self.assertNotIn(
            "aadhaar_number",
            udyam,
            "Whitespace-only ASR transcript "
            "must not be accepted.",
        )

    # --------------------------------------------------------
    # Invalid Aadhaar
    # --------------------------------------------------------

    def test_invalid_aadhaar_is_rejected(
        self,
    ) -> None:

        state = self._complete_state()

        state.entrepreneur_profile.aadhaar_number = None

        run(state)

        agent = DocumentationAgent(
            state,
            language="English",
        )

        result = agent.accept_answer(
            document_name="Udyam Registration",
            field_key="aadhaar_number",
            answer="12345",
        )

        self.assertFalse(
            result["accepted"]
        )

        udyam = (
            state.application_status.form_data.get(
                "Udyam Registration",
                {},
            )
        )

        self.assertNotIn(
            "aadhaar_number",
            udyam,
        )

    # --------------------------------------------------------
    # Valid answer
    # --------------------------------------------------------

    def test_valid_answer_is_persisted(
        self,
    ) -> None:

        state = self._complete_state()

        state.entrepreneur_profile.aadhaar_number = None

        run(state)

        agent = DocumentationAgent(
            state,
            language="English",
        )

        result = agent.accept_answer(
            document_name="Udyam Registration",
            field_key="aadhaar_number",
            answer="123456789012",
        )

        self.assertTrue(
            result["accepted"]
        )

        self.assertEqual(
            result["value"],
            "123456789012",
        )

        self.assertEqual(
            state.application_status.form_data[
                "Udyam Registration"
            ]["aadhaar_number"],
            "123456789012",
        )

    # --------------------------------------------------------
    # Cross-document reuse
    # --------------------------------------------------------

    def test_cross_document_reuse_without_reasking(
        self,
    ) -> None:

        state = self._complete_state()

        # Remove Aadhaar from upstream CaseState.
        # User must provide it once.
        state.entrepreneur_profile.aadhaar_number = None

        agent = DocumentationAgent(
            state,
            language="English",
        )

        run(state)

        first_question = (
            agent.get_next_question()
        )

        self.assertIsNotNone(
            first_question
        )

        self.assertEqual(
            first_question["document"],
            "Udyam Registration",
        )

        self.assertEqual(
            first_question["field"],
            "aadhaar_number",
        )

        result = agent.accept_answer(
            document_name="Udyam Registration",
            field_key="aadhaar_number",
            answer="123456789012",
        )

        self.assertTrue(
            result["accepted"]
        )

        # Synchronize after collection.
        run(state)

        kyc_data = (
            state.application_status.form_data.get(
                "KYC",
                {},
            )
        )

        self.assertEqual(
            kyc_data.get(
                "aadhaar_number"
            ),
            "123456789012",
            "A value collected once must be reused "
            "by another document sharing the same field.",
        )

        # The next question must not be KYC Aadhaar.
        next_question = (
            agent.get_next_question()
        )

        if next_question is not None:
            self.assertNotEqual(
                (
                    next_question["document"],
                    next_question["field"],
                ),
                (
                    "KYC",
                    "aadhaar_number",
                ),
            )

    # --------------------------------------------------------
    # Financial plan read-only
    # --------------------------------------------------------

    def test_financial_plan_is_read_only(
        self,
    ) -> None:

        state = self._complete_state()

        before = copy.deepcopy(
            state.financial_plan.model_dump(
                mode="json"
            )
        )

        run(state)

        after = (
            state.financial_plan.model_dump(
                mode="json"
            )
        )

        self.assertEqual(
            before,
            after,
            "Documentation Agent must never modify "
            "financial_plan.",
        )

    # --------------------------------------------------------
    # Entrepreneur profile read-only
    # --------------------------------------------------------

    def test_entrepreneur_profile_is_read_only(
        self,
    ) -> None:

        state = self._complete_state()

        before = copy.deepcopy(
            state.entrepreneur_profile.model_dump(
                mode="json"
            )
        )

        run(state)

        after = (
            state.entrepreneur_profile.model_dump(
                mode="json"
            )
        )

        self.assertEqual(
            before,
            after,
            "Documentation Agent must never modify "
            "entrepreneur_profile.",
        )

    # --------------------------------------------------------
    # Business shortlist read-only
    # --------------------------------------------------------

    def test_business_shortlist_is_read_only(
        self,
    ) -> None:

        state = self._complete_state()

        before = [
            candidate.model_dump(
                mode="json"
            )
            for candidate
            in state.business_shortlist
        ]

        run(state)

        after = [
            candidate.model_dump(
                mode="json"
            )
            for candidate
            in state.business_shortlist
        ]

        self.assertEqual(
            before,
            after,
            "Documentation Agent must never modify "
            "business_shortlist.",
        )

    # --------------------------------------------------------
    # Feasibility read-only
    # --------------------------------------------------------

    def test_feasibility_record_is_read_only(
        self,
    ) -> None:

        state = self._complete_state()

        before = copy.deepcopy(
            state.feasibility_record.model_dump(
                mode="json"
            )
        )

        run(state)

        after = (
            state.feasibility_record.model_dump(
                mode="json"
            )
        )

        self.assertEqual(
            before,
            after,
            "Documentation Agent must never modify "
            "feasibility_record.",
        )

    # --------------------------------------------------------
    # Upstream fields cannot be collected
    # --------------------------------------------------------

    def test_upstream_owned_fields_are_not_collectable(
        self,
    ) -> None:

        loan_template = get_template(
            "Loan Application"
        )

        upstream_fields = {
            "project_cost",
            "loan_eligibility",
            "scheme_tier",
            "margin_capital",
            "feasibility_verdict",
        }

        for field in loan_template.fields:

            if field.key in upstream_fields:
                self.assertFalse(
                    field.collectable,
                    f"{field.key} must be "
                    "collectable=False.",
                )

    # --------------------------------------------------------
    # Upstream fields cannot be manually answered
    # --------------------------------------------------------

    def test_upstream_field_cannot_be_manually_collected(
        self,
    ) -> None:

        state = self._complete_state()

        agent = DocumentationAgent(
            state,
            language="English",
        )

        result = agent.accept_answer(
            document_name="Loan Application",
            field_key="project_cost",
            answer="999999999",
        )

        self.assertFalse(
            result["accepted"],
            "Documentation Agent must not accept "
            "financial-engine-owned fields.",
        )

        loan_data = (
            state.application_status.form_data.get(
                "Loan Application",
                {},
            )
        )

        self.assertNotEqual(
            loan_data.get("project_cost"),
            "999999999",
        )

    # --------------------------------------------------------
    # Determinism
    # --------------------------------------------------------

    def test_determinism(
        self,
    ) -> None:

        case = {
            "entrepreneur_profile": {
                "name": "Determinism Case",
                "available_capital": 40000,
                "location": {
                    "address": "Village X"
                },
            },

            "business_shortlist": [
                {
                    "business_category": "snack stall",
                    "selected": True,
                }
            ],

            "financial_plan": {
                "project_cost": 400000,
                "loan_eligibility": 360000,
                "scheme_tier": "term_loan",
            },

            "feasibility_record": {
                "verdict": "viable"
            },
        }

        dummy_user_responses = {
            "Udyam Registration": {
                "aadhaar_number": "123456789012",
            },

            "KYC": {
                "phone_number": "9111122223",
            },

            "Loan Application": {},
        }

        outputs = []

        for _ in range(3):

            state = build_state(
                case
            )

            final_state = (
                simulate_voice_collection(
                    state=state,
                    dummy_user_responses=(
                        dummy_user_responses
                    ),
                    language="Hindi",
                )
            )

            serialized = json.dumps(
                final_state.application_status.form_data,
                sort_keys=True,
                ensure_ascii=False,
            )

            outputs.append(
                serialized
            )

        self.assertEqual(
            len(set(outputs)),
            1,
            "Identical input must produce "
            "identical form_data.",
        )

    # --------------------------------------------------------
    # Auto-filler status invariant
    # --------------------------------------------------------

    def test_auto_filler_never_marks_complete_with_missing_required_field(
        self,
    ) -> None:

        state = CaseState(
            entrepreneur_profile=(
                EntrepreneurProfile(
                    name="Partial"
                )
            ),

            business_shortlist=[
                BusinessCandidate(
                    business_category="x",
                    selected=True,
                )
            ],

            financial_plan=FinancialPlan(
                project_cost=100000
            ),

            application_status=ApplicationStatus(
                form_data={}
            ),
        )

        filler = DocumentAutoFiller(
            state
        )

        for template in DOCUMENT_TEMPLATES:

            checklist = filler.fill(
                template=template,
                persisted_form_data={},
            )

            required_missing = [
                field
                for field in checklist.fields
                if (
                    field.required
                    and field.status
                    == FieldStatus.MISSING
                )
            ]

            if required_missing:

                self.assertNotEqual(
                    checklist.status,
                    DocumentStatus.COMPLETE,
                    (
                        f"{checklist.name} marked "
                        f"COMPLETE with missing "
                        f"required fields: "
                        f"{[f.key for f in required_missing]}"
                    ),
                )

    # --------------------------------------------------------
    # One-question-at-a-time invariant
    # --------------------------------------------------------

    def test_next_question_returns_only_one_field(
        self,
    ) -> None:

        state = CaseState(
            entrepreneur_profile=(
                EntrepreneurProfile(
                    name=None
                )
            ),

            application_status=ApplicationStatus(
                form_data={}
            ),
        )

        agent = DocumentationAgent(
            state,
            language="English",
        )

        run(state)

        question = (
            agent.get_next_question()
        )

        self.assertIsNotNone(
            question
        )

        expected_keys = {
            "document",
            "field",
            "label",
            "question",
            "required",
        }

        self.assertEqual(
            set(question.keys()),
            expected_keys,
        )

        self.assertIsInstance(
            question["question"],
            str,
        )

        self.assertTrue(
            question["question"].strip()
        )

    # --------------------------------------------------------
    # run() has no old bulk arguments
    # --------------------------------------------------------

    def test_run_does_not_use_old_bulk_arguments(
        self,
    ) -> None:

        signature = inspect.signature(
            run
        )

        parameter_names = set(
            signature.parameters
        )

        self.assertNotIn(
            "dummy_user_responses",
            parameter_names,
        )

        self.assertNotIn(
            "language",
            parameter_names,
        )

    # --------------------------------------------------------
    # Explicitly selected business only
    # --------------------------------------------------------

    def test_business_category_requires_selected_candidate(
        self,
    ) -> None:

        state = CaseState(
            entrepreneur_profile=(
                EntrepreneurProfile(
                    name="Test"
                )
            ),

            business_shortlist=[
                BusinessCandidate(
                    business_category="Unselected Business",
                    selected=False,
                )
            ],

            application_status=ApplicationStatus(
                form_data={}
            ),
        )

        agent = DocumentationAgent(
            state,
            language="English",
        )

        run(state)

        data = (
            state.application_status.form_data.get(
                "Udyam Registration",
                {},
            )
        )

        self.assertNotIn(
            "business_category",
            data,
            "Agent must not silently use an "
            "unselected business candidate.",
        )

        # Business category should remain collectable.
        question = (
            agent.get_next_question()
        )

        self.assertIsNotNone(
            question
        )

        # Depending on earlier missing fields, the exact
        # first question may differ. The important invariant
        # is that business_category can be collected and is
        # not fabricated from an unselected candidate.
        template = get_template(
            "Udyam Registration"
        )

        business_field = next(
            field
            for field in template.fields
            if field.key == "business_category"
        )

        self.assertTrue(
            business_field.collectable
        )


# ============================================================
# HUMAN-READABLE REPORT
# ============================================================

def print_case_result(
    result: Dict[str, Any],
) -> None:

    status = (
        "PASS"
        if result["passed"]
        else "FAIL"
    )

    print(
        f"{result['case_id']} | "
        f"{result['name']} -> {status}"
    )

    for error in result["errors"]:
        print(
            f"    - {error}"
        )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    dataset = load_dataset()

    print()
    print("=" * 70)
    print(
        "DOCUMENTATION AGENT EVALUATION"
    )
    print("=" * 70)

    print(
        f"Dataset size: {len(dataset)}"
    )

    results = [
        evaluate_case(case)
        for case in dataset
    ]

    print()

    for result in results:
        print_case_result(result)

    passed = [
        result
        for result in results
        if result["passed"]
    ]

    failed = [
        result
        for result in results
        if not result["passed"]
    ]

    print()
    print("=" * 70)
    print("DATASET SUMMARY")
    print("=" * 70)

    print(
        f"Passed: {len(passed)}/{len(results)}"
    )

    print(
        f"Failed: {len(failed)}/{len(results)}"
    )

    report = {
        "dataset_size": len(dataset),
        "passed": len(passed),
        "failed": len(failed),
        "cases": results,
    }

    with open(
        REPORT_PATH,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            report,
            f,
            indent=2,
            ensure_ascii=False,
        )

    print()
    print(
        f"Detailed report: {REPORT_PATH}"
    )

    print()
    print("=" * 70)
    print(
        "RUNNING UNITTEST CONTRACT SUITE"
    )
    print("=" * 70)

    suite = (
        unittest.TestLoader()
        .loadTestsFromModule(
            sys.modules[__name__]
        )
    )

    runner = unittest.TextTestRunner(
        verbosity=2
    )

    unit_result = runner.run(
        suite
    )

    if (
        failed
        or not unit_result.wasSuccessful()
    ):
        sys.exit(1)


if __name__ == "__main__":
    main()