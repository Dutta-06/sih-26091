"""
module2_financial/documentation_agent.py

Documentation Agent — Module 2: Financial Structuring and Funding

Aligned with TECHNICAL_SETUP.md, Section 6.5.

Responsibilities
----------------
Reads:
    - state.entrepreneur_profile
    - state.financial_plan
    - state.business_shortlist
    - state.feasibility_record

Writes:
    - state.application_status.form_data

The Documentation Agent:
    1. Auto-fills document fields from CaseState.
    2. Reuses values already collected in form_data.
    3. Asks the entrepreneur for ONE missing collectable field at a time.
    4. Validates answers deterministically.
    5. Persists accepted answers in application_status.form_data.
    6. Never modifies financial-engine outputs.
    7. Never owns application checklist/disbursement state.
    8. Never invents missing required information.

Production contract:
    def run(state: CaseState) -> CaseState
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ============================================================================
# CaseState imports
# ============================================================================

try:
    from orchestrator.state import (
        CaseState,
        ApplicationStatus,
    )
except ImportError:
    from orchestrator.state import CaseState, ApplicationStatus


# ============================================================================
# Configuration
# ============================================================================

DEFAULT_LANGUAGE = os.getenv("DOCUMENTATION_LANGUAGE", "hi")

INDICTRANS2_MODEL = os.getenv(
    "INDICTRANS2_MODEL",
    "ai4bharat/indictrans2-indic-en-1B",
)


# ============================================================================
# Enums
# ============================================================================

class FieldStatus(str, Enum):
    COMPLETE = "complete"
    MISSING = "missing"
    INVALID = "invalid"


class DocumentStatus(str, Enum):
    COMPLETE = "complete"
    PENDING = "pending"


# ============================================================================
# ASR / TTS adapters
# ============================================================================

class ASRAdapter:
    """
    Optional ASR adapter.

    ASR is infrastructure only. The documentation logic remains
    deterministic and does not depend on a specific ASR implementation.
    """

    def transcribe(
        self,
        audio: Any,
        language: str = DEFAULT_LANGUAGE,
    ) -> str:
        if audio is None:
            return ""

        if isinstance(audio, str):
            return audio.strip()

        try:
            import whisper  # type: ignore

            model_name = os.getenv("WHISPER_MODEL", "tiny")
            model = whisper.load_model(model_name)

            result = model.transcribe(
                audio,
                language=None if language == "auto" else language,
            )

            return str(result.get("text", "")).strip()

        except Exception:
            return ""


class TTSAdapter:
    """
    Optional TTS adapter.
    """

    def synthesize(
        self,
        text: str,
        language: str = DEFAULT_LANGUAGE,
    ) -> Any:
        if not text:
            return None

        return None


# ============================================================================
# Language utilities
# ============================================================================

INDIC_LANGUAGE_CODES = {
    "hindi": "hi",
    "hi": "hi",
    "english": "en",
    "en": "en",
    "bengali": "bn",
    "bn": "bn",
    "gujarati": "gu",
    "gu": "gu",
    "marathi": "mr",
    "mr": "mr",
    "tamil": "ta",
    "ta": "ta",
    "telugu": "te",
    "te": "te",
    "kannada": "kn",
    "kn": "kn",
    "malayalam": "ml",
    "ml": "ml",
    "punjabi": "pa",
    "pa": "pa",
    "odia": "or",
    "or": "or",
    "assamese": "as",
    "as": "as",
}


def normalize_language(language: Optional[str]) -> str:
    if not language:
        return DEFAULT_LANGUAGE

    value = language.strip().lower()
    return INDIC_LANGUAGE_CODES.get(value, value)


# ============================================================================
# Deterministic fallback questions
# ============================================================================

FALLBACK_QUESTIONS: Dict[str, str] = {
    "applicant_name": "Please tell me your full name.",
    "aadhaar_number": "Please tell me your 12-digit Aadhaar number.",
    "business_category": "Please tell me your business category.",
    "business_address": "Please tell me your business address.",
    "investment_amount": "Please tell me the total investment amount.",
    "bank_account": "Please tell me your bank account number.",
    "residential_address": "Please tell me your residential address.",
    "phone_number": "Please tell me your phone number.",
    "pan_number": "Please tell me your PAN number.",
    "guarantor_name": "Please provide the guarantor name.",
}


# ============================================================================
# IndicTrans2 translator
# ============================================================================

class IndicTrans2Translator:
    """
    Lazy optional IndicTrans2 wrapper.

    Translation is non-critical. If IndicTrans2 cannot be loaded,
    the original English question is returned.
    """

    def __init__(
        self,
        model_name: str = INDICTRANS2_MODEL,
    ) -> None:
        self.model_name = model_name
        self._tokenizer = None
        self._model = None
        self._loaded = False
        self._load_error: Optional[Exception] = None

    def _load(self) -> bool:
        if self._loaded:
            return self._model is not None

        self._loaded = True

        try:
            from transformers import (
                AutoModelForSeq2SeqLM,
                AutoTokenizer,
            )

            self._tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                trust_remote_code=True,
            )

            self._model = AutoModelForSeq2SeqLM.from_pretrained(
                self.model_name,
                trust_remote_code=True,
            )

            return True

        except Exception as exc:
            self._load_error = exc
            self._tokenizer = None
            self._model = None
            return False

    def translate(
        self,
        text: str,
        source_language: str = "en",
        target_language: str = DEFAULT_LANGUAGE,
    ) -> str:
        if not text:
            return ""

        target_language = normalize_language(target_language)

        if target_language == "en":
            return text

        if not self._load():
            return text

        # Keep deterministic fallback until the production
        # IndicTrans2 preprocessing pipeline is explicitly configured.
        return text


# ============================================================================
# Question phrasing
# ============================================================================

class QuestionPhraser:

    def __init__(
        self,
        language: str = DEFAULT_LANGUAGE,
        translator: Optional[IndicTrans2Translator] = None,
    ) -> None:
        self.language = normalize_language(language)
        self.translator = translator or IndicTrans2Translator()

    def phrase(self, field_template: "FilledField") -> str:
        english_question = FALLBACK_QUESTIONS.get(
            field_template.key,
            f"Please provide your {field_template.label.lower()}.",
        )

        return self.translator.translate(
            english_question,
            source_language="en",
            target_language=self.language,
        )


# ============================================================================
# Field / document templates
# ============================================================================

@dataclass
class FieldTemplate:
    key: str
    label: str
    required: bool
    source_path: Optional[str] = None

    # True  -> Documentation Agent may ask entrepreneur.
    # False -> field is owned by another module.
    collectable: bool = True


@dataclass
class FilledField(FieldTemplate):
    value: Any = None
    status: FieldStatus = FieldStatus.MISSING


@dataclass
class DocumentTemplate:
    name: str
    fields: List[FieldTemplate] = field(default_factory=list)


@dataclass
class DocumentChecklist:
    name: str
    fields: List[FilledField] = field(default_factory=list)
    status: DocumentStatus = DocumentStatus.PENDING

    @property
    def missing_required(self) -> List[str]:
        return [
            field.key
            for field in self.fields
            if field.required
            and field.status != FieldStatus.COMPLETE
        ]

    @property
    def missing_collectable(self) -> List[str]:
        return [
            field.key
            for field in self.fields
            if field.collectable
            and field.status != FieldStatus.COMPLETE
        ]


# ============================================================================
# Document templates
# ============================================================================

DOCUMENT_TEMPLATES: List[DocumentTemplate] = [

    # ------------------------------------------------------------------------
    # Udyam Registration
    # ------------------------------------------------------------------------
    DocumentTemplate(
        name="Udyam Registration",
        fields=[
            FieldTemplate(
                key="applicant_name",
                label="Applicant name",
                required=True,
                source_path="entrepreneur_profile.name",
            ),
            FieldTemplate(
                key="aadhaar_number",
                label="Aadhaar number",
                required=True,
                source_path="entrepreneur_profile.aadhaar_number",
            ),
            FieldTemplate(
                key="business_category",
                label="Business category",
                required=True,
                source_path="selected_business_category",
            ),
            FieldTemplate(
                key="business_address",
                label="Business address",
                required=True,
                source_path="entrepreneur_profile.location.address",
            ),
            FieldTemplate(
                key="investment_amount",
                label="Investment amount",
                required=True,
                source_path="financial_plan.project_cost",
            ),
            FieldTemplate(
                key="bank_account",
                label="Bank account",
                required=False,
                source_path="entrepreneur_profile.bank_account",
            ),
        ],
    ),

    # ------------------------------------------------------------------------
    # KYC
    # ------------------------------------------------------------------------
    DocumentTemplate(
        name="KYC",
        fields=[
            FieldTemplate(
                key="applicant_name",
                label="Applicant name",
                required=True,
                source_path="entrepreneur_profile.name",
            ),
            FieldTemplate(
                key="aadhaar_number",
                label="Aadhaar number",
                required=True,
                source_path="entrepreneur_profile.aadhaar_number",
            ),
            FieldTemplate(
                key="residential_address",
                label="Residential address",
                required=True,
                source_path="entrepreneur_profile.location.address",
            ),
            FieldTemplate(
                key="phone_number",
                label="Phone number",
                required=True,
                source_path="entrepreneur_profile.phone_number",
            ),
            FieldTemplate(
                key="pan_number",
                label="PAN number",
                required=False,
                source_path="entrepreneur_profile.pan_number",
            ),
        ],
    ),

    # ------------------------------------------------------------------------
    # Loan Application
    # ------------------------------------------------------------------------
    DocumentTemplate(
        name="Loan Application",
        fields=[
            FieldTemplate(
                key="applicant_name",
                label="Applicant name",
                required=True,
                source_path="entrepreneur_profile.name",
            ),
            FieldTemplate(
                key="business_category",
                label="Business category",
                required=True,
                source_path="selected_business_category",
            ),

            # Financial-engine owned fields.
            FieldTemplate(
                key="project_cost",
                label="Project cost",
                required=True,
                source_path="financial_plan.project_cost",
                collectable=False,
            ),
            FieldTemplate(
                key="loan_eligibility",
                label="Loan eligibility",
                required=True,
                source_path="financial_plan.loan_eligibility",
                collectable=False,
            ),
            FieldTemplate(
                key="scheme_tier",
                label="Scheme tier",
                required=True,
                source_path="financial_plan.scheme_tier",
                collectable=False,
            ),
            FieldTemplate(
                key="margin_capital",
                label="Margin capital",
                required=True,
                source_path="entrepreneur_profile.available_capital",
                collectable=False,
            ),
            FieldTemplate(
                key="feasibility_verdict",
                label="Feasibility verdict",
                required=True,
                source_path="feasibility_record.verdict",
                collectable=False,
            ),

            FieldTemplate(
                key="guarantor_name",
                label="Guarantor name",
                required=False,
                source_path="entrepreneur_profile.guarantor_name",
            ),
        ],
    ),
]


# ============================================================================
# Generic state helpers
# ============================================================================

def _read_value(obj: Any, path: str) -> Any:
    """
    Safely resolve a dotted path from Pydantic models,
    normal objects, dictionaries, or nested combinations.
    """
    if obj is None or not path:
        return None

    current = obj

    for part in path.split("."):
        if current is None:
            return None

        if isinstance(current, dict):
            if part not in current:
                return None

            current = current[part]
            continue

        try:
            current = getattr(current, part)
        except AttributeError:
            return None

    return current


def _is_present(value: Any) -> bool:
    """
    Meaningful-value check.

    0 / False -> present
    "" / [] / {} / None -> missing
    """
    if value is None:
        return False

    if isinstance(value, str):
        return bool(value.strip())

    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)

    return True


def _clean_string(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip()


# ============================================================================
# Selected business helpers
# ============================================================================

def _selected_business(state: CaseState) -> Any:
    """
    Return only the explicitly selected business.

    Never silently selects the first candidate.
    """
    shortlist = getattr(state, "business_shortlist", None) or []

    for candidate in shortlist:
        if bool(getattr(candidate, "selected", False)):
            return candidate

    return None


def _selected_business_category(
    state: CaseState,
) -> Optional[str]:

    candidate = _selected_business(state)

    if candidate is None:
        return None

    for attribute in (
        "category",
        "business_category",
        "sector",
        "name",
    ):
        value = getattr(candidate, attribute, None)

        if _is_present(value):
            return str(value).strip()

    return None


# ============================================================================
# Auto filler
# ============================================================================

class DocumentAutoFiller:
    """
    Resolve fields from:

        1. exact persisted document value
        2. CaseState
        3. another document's persisted value

    No cache is used.

    This is important because form_data changes during voice collection.
    """

    def __init__(self, state: CaseState) -> None:
        self.state = state

    def _resolve_source_path(
        self,
        source_path: Optional[str],
    ) -> Any:

        if not source_path:
            return None

        if source_path == "selected_business_category":
            return _selected_business_category(self.state)

        return _read_value(self.state, source_path)

    @staticmethod
    def _stored_document_value(
        persisted_form_data: Dict[str, Any],
        document_name: str,
        field_key: str,
    ) -> Any:

        document_data = persisted_form_data.get(
            document_name,
            {},
        )

        if not isinstance(document_data, dict):
            return None

        value = document_data.get(field_key)

        if _is_present(value):
            return value

        return None

    @staticmethod
    def _stored_any_document_value(
        persisted_form_data: Dict[str, Any],
        field_key: str,
    ) -> Any:

        for document_data in persisted_form_data.values():

            if not isinstance(document_data, dict):
                continue

            value = document_data.get(field_key)

            if _is_present(value):
                return value

        return None

    def fill(
        self,
        template: DocumentTemplate,
        persisted_form_data: Optional[Dict[str, Any]] = None,
    ) -> DocumentChecklist:

        persisted_form_data = (
            persisted_form_data
            if isinstance(persisted_form_data, dict)
            else {}
        )

        filled_fields: List[FilledField] = []

        for template_field in template.fields:

            value = None

            # ---------------------------------------------------------------
            # 1. Exact document persisted value
            # ---------------------------------------------------------------

            stored_value = self._stored_document_value(
                persisted_form_data,
                template.name,
                template_field.key,
            )

            if _is_present(stored_value):
                value = stored_value

            # ---------------------------------------------------------------
            # 2. CaseState value
            # ---------------------------------------------------------------

            source_value = self._resolve_source_path(
                template_field.source_path,
            )

            if _is_present(source_value):
                value = source_value

            # ---------------------------------------------------------------
            # 3. Cross-document persisted value
            #
            # Important:
            # Do NOT replace a current CaseState value with another
            # document's value.
            # ---------------------------------------------------------------

            if not _is_present(value):

                cross_document_value = (
                    self._stored_any_document_value(
                        persisted_form_data,
                        template_field.key,
                    )
                )

                if _is_present(cross_document_value):
                    value = cross_document_value

            status = (
                FieldStatus.COMPLETE
                if _is_present(value)
                else FieldStatus.MISSING
            )

            filled_fields.append(
                FilledField(
                    key=template_field.key,
                    label=template_field.label,
                    required=template_field.required,
                    source_path=template_field.source_path,
                    collectable=template_field.collectable,
                    value=value,
                    status=status,
                )
            )

        checklist_status = (
            DocumentStatus.COMPLETE
            if not any(
                field.required
                and field.status != FieldStatus.COMPLETE
                for field in filled_fields
            )
            else DocumentStatus.PENDING
        )

        return DocumentChecklist(
            name=template.name,
            fields=filled_fields,
            status=checklist_status,
        )


# ============================================================================
# Validators
# ============================================================================

def _validate_text(value: Any) -> Tuple[bool, str]:

    text = _clean_string(value)

    if not text:
        return False, "This field cannot be blank."

    return True, text


def _validate_phone(value: Any) -> Tuple[bool, str]:

    text = re.sub(
        r"\D",
        "",
        _clean_string(value),
    )

    if len(text) != 10:
        return False, "Phone number must contain exactly 10 digits."

    if text[0] not in "6789":
        return False, "Please provide a valid 10-digit Indian phone number."

    return True, text


def _validate_aadhaar(value: Any) -> Tuple[bool, str]:

    text = re.sub(
        r"\D",
        "",
        _clean_string(value),
    )

    if len(text) != 12:
        return False, "Aadhaar number must contain exactly 12 digits."

    return True, text


def _validate_pan(value: Any) -> Tuple[bool, str]:

    text = (
        _clean_string(value)
        .upper()
        .replace(" ", "")
    )

    if not re.fullmatch(
        r"[A-Z]{5}[0-9]{4}[A-Z]",
        text,
    ):
        return False, "Please provide a valid PAN number."

    return True, text


def _validate_bank_account(value: Any) -> Tuple[bool, str]:

    text = re.sub(
        r"\D",
        "",
        _clean_string(value),
    )

    if not 9 <= len(text) <= 18:
        return (
            False,
            "Bank account number must contain 9 to 18 digits.",
        )

    return True, text


def _validate_money(value: Any) -> Tuple[bool, Any]:

    if isinstance(value, (int, float)):

        if value < 0:
            return False, "Amount cannot be negative."

        return True, value

    text = (
        _clean_string(value)
        .replace(",", "")
        .replace("₹", "")
        .strip()
    )

    if not text:
        return False, "Please provide an amount."

    try:
        amount = float(text)

        if amount < 0:
            return False, "Amount cannot be negative."

        if amount.is_integer():
            return True, int(amount)

        return True, amount

    except ValueError:
        return False, "Please provide a valid amount."


def validate_field(
    field: FilledField,
    value: Any,
) -> Tuple[bool, Any, str]:
    """
    Deterministic field validation.
    """

    if value is None:
        return False, None, "Blank answers are not accepted."

    if isinstance(value, str) and not value.strip():
        return False, None, "Blank answers are not accepted."

    key = field.key

    if key in {
        "applicant_name",
        "business_category",
        "business_address",
        "residential_address",
        "guarantor_name",
    }:
        valid, normalized = _validate_text(value)

        if not valid:
            return False, None, normalized

        return True, normalized, ""

    if key == "aadhaar_number":

        valid, normalized = _validate_aadhaar(value)

        if not valid:
            return False, None, normalized

        return True, normalized, ""

    if key == "phone_number":

        valid, normalized = _validate_phone(value)

        if not valid:
            return False, None, normalized

        return True, normalized, ""

    if key == "pan_number":

        valid, normalized = _validate_pan(value)

        if not valid:
            return False, None, normalized

        return True, normalized, ""

    if key == "bank_account":

        valid, normalized = _validate_bank_account(value)

        if not valid:
            return False, None, normalized

        return True, normalized, ""

    if key in {
        "investment_amount",
        "project_cost",
    }:

        valid, normalized = _validate_money(value)

        if not valid:
            return False, None, normalized

        return True, normalized, ""

    valid, normalized = _validate_text(value)

    if not valid:
        return False, None, normalized

    return True, normalized, ""


# ============================================================================
# Conversational collector
# ============================================================================

class ConversationalCollector:
    """
    One-field-at-a-time conversational collector.

    Never asks for upstream-owned fields.
    """

    def __init__(
        self,
        state: CaseState,
        language: str = DEFAULT_LANGUAGE,
        asr: Optional[ASRAdapter] = None,
        tts: Optional[TTSAdapter] = None,
        phraser: Optional[QuestionPhraser] = None,
    ) -> None:

        self.state = state
        self.language = normalize_language(language)

        self.asr = asr or ASRAdapter()
        self.tts = tts or TTSAdapter()

        self.phraser = phraser or QuestionPhraser(
            language=self.language,
        )

    def first_missing_field(
        self,
        checklist: DocumentChecklist,
    ) -> Optional[FilledField]:

        for field in checklist.fields:

            if not field.collectable:
                continue

            if field.status == FieldStatus.COMPLETE:
                continue

            return field

        return None

    def next_question(
        self,
        checklist: DocumentChecklist,
    ) -> Optional[str]:

        field = self.first_missing_field(checklist)

        if field is None:
            return None

        return self.phraser.phrase(field)


# ============================================================================
# Documentation Agent
# ============================================================================

class DocumentationAgent:
    """
    Main Documentation Agent.

    Ownership boundary:
        state.application_status.form_data

    The agent does NOT modify:

        entrepreneur_profile
        financial_plan
        feasibility_record
        business_shortlist
        application checklist
        disbursement status
    """

    def __init__(
        self,
        state: CaseState,
        language: str = DEFAULT_LANGUAGE,
    ) -> None:

        self.state = state
        self.language = normalize_language(language)

        self._ensure_application_status()

    # ------------------------------------------------------------------------
    # State/form helpers
    # ------------------------------------------------------------------------

    def _ensure_application_status(self) -> None:

        application_status = getattr(
            self.state,
            "application_status",
            None,
        )

        if application_status is None:
            self.state.application_status = ApplicationStatus()

        form_data = getattr(
            self.state.application_status,
            "form_data",
            None,
        )

        if form_data is None:
            self.state.application_status.form_data = {}

    @property
    def form_data(self) -> Dict[str, Any]:

        self._ensure_application_status()

        data = self.state.application_status.form_data

        if not isinstance(data, dict):
            data = {}
            self.state.application_status.form_data = data

        return data

    # ------------------------------------------------------------------------
    # Templates/checklists
    # ------------------------------------------------------------------------

    def _build_checklists(
        self,
    ) -> Dict[str, DocumentChecklist]:

        filler = DocumentAutoFiller(self.state)

        current_form_data = self.form_data

        return {
            template.name: filler.fill(
                template,
                persisted_form_data=current_form_data,
            )
            for template in DOCUMENT_TEMPLATES
        }

    # ------------------------------------------------------------------------
    # Synchronization
    # ------------------------------------------------------------------------

    def _synchronize_form_data(
        self,
        checklists: Optional[
            Dict[str, DocumentChecklist]
        ] = None,
    ) -> None:
        """
        Synchronize known values into form_data.

        Only application_status.form_data is mutated.
        """

        if checklists is None:
            checklists = self._build_checklists()

        form_data = self.form_data

        # --------------------------------------------------------------------
        # Preserve all values that were already collected.
        # --------------------------------------------------------------------

        known_values: Dict[str, Any] = {}

        for document_data in form_data.values():

            if not isinstance(document_data, dict):
                continue

            for key, value in document_data.items():

                if _is_present(value):
                    known_values[key] = value

        # --------------------------------------------------------------------
        # Populate each document.
        # --------------------------------------------------------------------

        for document_name, checklist in checklists.items():

            document_data = form_data.setdefault(
                document_name,
                {},
            )

            for field in checklist.fields:

                current_value = document_data.get(
                    field.key
                )

                # Existing user-collected value always wins.
                if _is_present(current_value):
                    known_values[field.key] = current_value
                    continue

                # Upstream CaseState value.
                if _is_present(field.value):
                    document_data[field.key] = field.value
                    known_values[field.key] = field.value
                    continue

                # Previously collected value from another document.
                reused_value = known_values.get(field.key)

                if _is_present(reused_value):
                    document_data[field.key] = reused_value

    # ------------------------------------------------------------------------
    # Public question API
    # ------------------------------------------------------------------------

    def get_next_question(
        self,
        document_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Return exactly ONE missing collectable field.
        """

        self._synchronize_form_data()

        checklists = self._build_checklists()

        if document_name is not None:

            checklist = checklists.get(document_name)

            if checklist is None:
                return None

            selected_checklists = [checklist]

        else:
            selected_checklists = list(
                checklists.values()
            )

        collector = ConversationalCollector(
            self.state,
            language=self.language,
        )

        for checklist in selected_checklists:

            field = collector.first_missing_field(
                checklist
            )

            if field is None:
                continue

            return {
                "document": checklist.name,
                "field": field.key,
                "label": field.label,
                "question": collector.phraser.phrase(field),
                "required": field.required,
            }

        return None

    # ------------------------------------------------------------------------
    # Answer handling
    # ------------------------------------------------------------------------

    def accept_answer(
        self,
        document_name: str,
        field_key: str,
        answer: Any,
    ) -> Dict[str, Any]:
        """
        Validate and persist exactly ONE answer.

        The only state mutation is:
            state.application_status.form_data
        """

        # Always inspect the latest state/form_data.
        # This prevents stale checklist information during a conversation.
        self._synchronize_form_data()

        checklists = self._build_checklists()

        checklist = checklists.get(document_name)

        if checklist is None:
            return {
                "accepted": False,
                "document": document_name,
                "field": field_key,
                "value": None,
                "message": "Unknown document.",
            }

        target_field: Optional[FilledField] = None

        for field in checklist.fields:

            if field.key == field_key:
                target_field = field
                break

        if target_field is None:
            return {
                "accepted": False,
                "document": document_name,
                "field": field_key,
                "value": None,
                "message": "Unknown field.",
            }

        # --------------------------------------------------------------------
        # Upstream-owned fields cannot be manually collected.
        # --------------------------------------------------------------------

        if not target_field.collectable:
            return {
                "accepted": False,
                "document": document_name,
                "field": field_key,
                "value": target_field.value,
                "message": (
                    "This field is populated by an upstream module "
                    "and cannot be collected manually."
                ),
            }

        # --------------------------------------------------------------------
        # Reject blank values.
        # --------------------------------------------------------------------

        if answer is None:
            return {
                "accepted": False,
                "document": document_name,
                "field": field_key,
                "value": None,
                "message": "Blank answers are not accepted.",
            }

        if isinstance(answer, str) and not answer.strip():
            return {
                "accepted": False,
                "document": document_name,
                "field": field_key,
                "value": None,
                "message": "Blank answers are not accepted.",
            }

        # --------------------------------------------------------------------
        # Deterministic validation.
        # --------------------------------------------------------------------

        valid, normalized_value, message = validate_field(
            target_field,
            answer,
        )

        if not valid:
            return {
                "accepted": False,
                "document": document_name,
                "field": field_key,
                "value": None,
                "message": message,
            }

        # --------------------------------------------------------------------
        # ONLY OWNED WRITE
        #
        # application_status.form_data
        # --------------------------------------------------------------------

        form_data = self.form_data

        document_data = form_data.setdefault(
            document_name,
            {},
        )

        document_data[field_key] = normalized_value

        # --------------------------------------------------------------------
        # Cross-document reuse.
        #
        # A collected value is copied only into the same field in another
        # document when that document does not already contain a value.
        # --------------------------------------------------------------------

        for template in DOCUMENT_TEMPLATES:

            if template.name == document_name:
                continue

            other_document_data = form_data.setdefault(
                template.name,
                {},
            )

            for other_field in template.fields:

                if other_field.key != field_key:
                    continue

                existing_value = other_document_data.get(
                    field_key
                )

                if not _is_present(existing_value):
                    other_document_data[field_key] = (
                        normalized_value
                    )

        # --------------------------------------------------------------------
        # IMPORTANT:
        #
        # Do not run synchronization here.
        #
        # The accepted value has already been persisted. A synchronization
        # pass is intentionally deferred until the next question/checklist
        # build, where persisted values have priority.
        # --------------------------------------------------------------------

        return {
            "accepted": True,
            "document": document_name,
            "field": field_key,
            "value": normalized_value,
            "message": "Answer accepted.",
        }

    # ------------------------------------------------------------------------
    # Conversational response collection
    # ------------------------------------------------------------------------

    def collect_application_data(
        self,
        responses: Optional[
            Dict[str, Dict[str, Any]]
        ] = None,
    ) -> Dict[str, Any]:
        """
        Process supplied voice/test responses.

        Expected input:

            {
                "Udyam Registration": {
                    "aadhaar_number": "123456789012"
                },
                "KYC": {
                    "phone_number": "9876543210"
                }
            }

        Every answer is processed through accept_answer().

        The method intentionally processes each supplied response directly
        rather than depending on the order in which documents appear in the
        templates.

        This matters when one response unlocks another document through
        cross-document reuse.
        """

        self._synchronize_form_data()

        if not responses:
            return self.form_data

        # --------------------------------------------------------------------
        # Normalize the supplied response structure.
        #
        # This accepts the documented nested format while also safely
        # ignoring malformed entries.
        # --------------------------------------------------------------------

        normalized_responses: List[
            Tuple[str, str, Any]
        ] = []

        for document_name, document_answers in responses.items():

            if not isinstance(document_answers, dict):
                continue

            for field_key, answer in document_answers.items():

                normalized_responses.append(
                    (
                        str(document_name),
                        str(field_key),
                        answer,
                    )
                )

        # --------------------------------------------------------------------
        # Process responses one by one.
        #
        # Do NOT synchronize between individual answers because
        # accept_answer() already persists the accepted value and propagates
        # it across documents.
        # --------------------------------------------------------------------

        for document_name, field_key, answer in normalized_responses:

            self.accept_answer(
                document_name=document_name,
                field_key=field_key,
                answer=answer,
            )

        # --------------------------------------------------------------------
        # Final synchronization.
        #
        # This rebuilds all known document fields from the now-current
        # form_data without losing accepted answers.
        # --------------------------------------------------------------------

        self._synchronize_form_data()

        return self.form_data


# ============================================================================
# Agent entry point
# ============================================================================

def run(state: CaseState) -> CaseState:
    """
    Technical Setup contract:

        CaseState -> CaseState

    Ownership:

        application_status.form_data only.
    """

    agent = DocumentationAgent(state)

    agent._synchronize_form_data()

    return state


# ============================================================================
# Optional voice helpers
# ============================================================================

def transcribe_answer(
    audio: Any,
    language: str = DEFAULT_LANGUAGE,
    asr: Optional[ASRAdapter] = None,
) -> str:
    """
    Convert voice input into text.

    Does not modify CaseState.
    """

    adapter = asr or ASRAdapter()

    return adapter.transcribe(
        audio,
        language=normalize_language(language),
    )


def speak_question(
    question: str,
    language: str = DEFAULT_LANGUAGE,
    tts: Optional[TTSAdapter] = None,
) -> Any:
    """
    Optional TTS helper.

    Does not modify CaseState.
    """

    adapter = tts or TTSAdapter()

    return adapter.synthesize(
        question,
        language=normalize_language(language),
    )


# ============================================================================
# Mock state
# ============================================================================

def _mock_state() -> CaseState:
    """
    Minimal local mock state.
    """

    from types import SimpleNamespace

    entrepreneur_profile = SimpleNamespace(
        name="Test Entrepreneur",
        aadhaar_number="123456789012",
        phone_number="9876543210",
        pan_number=None,
        bank_account="123456789012",
        available_capital=50000,
        location=SimpleNamespace(
            address="Delhi, India",
        ),
        guarantor_name=None,
    )

    selected_business = SimpleNamespace(
        selected=True,
        category="Food Processing",
        business_category="Food Processing",
        name="Food Processing",
    )

    financial_plan = SimpleNamespace(
        project_cost=500000,
        loan_eligibility=450000,
        scheme_tier="Micro Finance",
    )

    feasibility_record = SimpleNamespace(
        verdict="feasible",
    )

    application_status = ApplicationStatus(
        form_data={},
    )

    return CaseState(
        entrepreneur_profile=entrepreneur_profile,
        business_shortlist=[selected_business],
        market_intelligence=None,
        feasibility_record=feasibility_record,
        financial_plan=financial_plan,
        application_status=application_status,
        monitoring_record=[],
        grievance_log=[],
        session_meta=SimpleNamespace(),
    )


# ============================================================================
# Mock voice responses
# ============================================================================

def _mock_dummy_user_responses() -> Dict[str, Dict[str, Any]]:
    return {
        "Udyam Registration": {
            "aadhaar_number": "123456789012",
        },
        "KYC": {
            "phone_number": "9876543210",
        },
    }


# ============================================================================
# Local smoke test
# ============================================================================

if __name__ == "__main__":

    state = _mock_state()

    print(
        "Running Documentation Agent smoke test...\n"
    )

    # Initial synchronization.
    state = run(state)

    agent = DocumentationAgent(state)

    print("Initial form data:")
    print(agent.form_data)

    print("\nNext question:")
    print(agent.get_next_question())

    # Simulate Aadhaar answer.
    result = agent.accept_answer(
        document_name="Udyam Registration",
        field_key="aadhaar_number",
        answer="123456789012",
    )

    print("\nAccepted Aadhaar:")
    print(result)

    print("\nKYC after Aadhaar cross-document reuse:")
    print(agent.form_data.get("KYC", {}))

    print("\nNext question:")
    print(agent.get_next_question())

    # Simulate phone answer.
    result = agent.accept_answer(
        document_name="KYC",
        field_key="phone_number",
        answer="9876543210",
    )

    print("\nAccepted phone:")
    print(result)

    print("\nFinal form data:")
    print(agent.form_data)

    # Full response helper test.
    state2 = _mock_state()
    agent2 = DocumentationAgent(state2)

    result = agent2.collect_application_data(
        _mock_dummy_user_responses()
    )

    print("\ncollect_application_data() result:")
    print(result)