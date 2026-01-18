"""
Planning Application Classifier using LLM.

Classifies planning applications to identify qualifying developments:
- NEW BUILD residential (1-30 units)
- CONVERSION of non-residential to residential (1-30 units)
"""

import json
import re
from typing import Dict, Any, Optional
from dataclasses import dataclass
import logging

from .base import BaseLLMProvider, LLMError
from .cache import LLMCache


@dataclass
class ClassificationResult:
    """Result of classifying a planning application."""

    qualifies: bool
    development_type: str  # "new_build", "conversion", "extension", "other"
    unit_count: Optional[int]
    confidence: str  # "high", "medium", "low"
    reason: str
    raw_response: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "qualifies": self.qualifies,
            "development_type": self.development_type,
            "unit_count": self.unit_count,
            "confidence": self.confidence,
            "reason": self.reason,
        }


CLASSIFICATION_SYSTEM_PROMPT = """You are a UK planning application classifier. Your task is to determine if a planning application qualifies based on specific criteria.

QUALIFYING criteria (ALL must be met):
1. Development must be either:
   - NEW BUILD residential: Construction of new dwelling(s) from scratch
   - CONVERSION: Change of non-residential building (office, shop, warehouse, etc.) to residential use

2. Must propose between 1 and 30 residential units

NOT QUALIFYING (exclude these):
- Extensions or alterations to existing residential properties
- Loft conversions in existing homes
- Change of use between residential types (e.g., HMO to flats)
- Care homes, nursing homes, student accommodation
- Demolition without new residential construction
- Commercial, retail, industrial developments
- Mixed-use where residential is secondary
- Outline applications (no confirmed unit count)
- Reserved matters without unit details

Respond ONLY with valid JSON in this exact format:
{
  "qualifies": true/false,
  "development_type": "new_build" | "conversion" | "extension" | "other",
  "unit_count": number or null,
  "confidence": "high" | "medium" | "low",
  "reason": "brief explanation (max 50 words)"
}"""


CLASSIFICATION_USER_PROMPT = """Classify this planning application:

Application Type: {application_type}

Proposal: {proposal}

Address: {address}

Respond with JSON only."""


class PlanningApplicationClassifier:
    """
    Classifier that uses an LLM to determine if a planning application qualifies.

    Qualifying applications are:
    - New build residential (1-30 units)
    - Conversion to residential (1-30 units)
    """

    def __init__(
        self,
        provider: BaseLLMProvider,
        cache: Optional[LLMCache] = None,
        min_units: int = 1,
        max_units: int = 30,
    ):
        """
        Initialize the classifier.

        Args:
            provider: LLM provider to use for classification
            cache: Optional cache for storing results
            min_units: Minimum unit count to qualify (default: 1)
            max_units: Maximum unit count to qualify (default: 30)
        """
        self.provider = provider
        self.cache = cache or LLMCache()
        self.min_units = min_units
        self.max_units = max_units
        self.logger = logging.getLogger(__name__)

    async def classify(
        self,
        proposal: str,
        application_type: Optional[str] = None,
        address: Optional[str] = None,
    ) -> ClassificationResult:
        """
        Classify a planning application.

        Args:
            proposal: The proposal/description text
            application_type: The application type (optional)
            address: The site address (optional)

        Returns:
            ClassificationResult with qualification decision
        """
        # Create cache key from all inputs
        cache_key = f"{application_type or ''}|{proposal}"

        # Check cache first
        cached = self.cache.get(cache_key)
        if cached:
            self.logger.debug("Using cached classification result")
            return ClassificationResult(**cached)

        # Build the prompt
        user_prompt = CLASSIFICATION_USER_PROMPT.format(
            application_type=application_type or "Not specified",
            proposal=proposal or "Not specified",
            address=address or "Not specified",
        )

        messages = [
            {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        try:
            # Call LLM with retry
            response = await self.provider.complete_with_retry(
                messages=messages,
                temperature=0.0,
                max_tokens=200,
                max_retries=3,
            )

            # Parse the response
            result = self._parse_response(response)

            # Validate unit count range
            if result.qualifies and result.unit_count is not None:
                if result.unit_count < self.min_units or result.unit_count > self.max_units:
                    result = ClassificationResult(
                        qualifies=False,
                        development_type=result.development_type,
                        unit_count=result.unit_count,
                        confidence=result.confidence,
                        reason=f"Unit count {result.unit_count} outside range {self.min_units}-{self.max_units}",
                        raw_response=response,
                    )

            # Cache the result
            self.cache.set(cache_key, result.to_dict())

            return result

        except LLMError as e:
            self.logger.error(f"LLM classification failed: {e}")
            raise

    def _parse_response(self, response: str) -> ClassificationResult:
        """
        Parse the LLM response into a ClassificationResult.

        Args:
            response: Raw LLM response text

        Returns:
            Parsed ClassificationResult
        """
        # Try to extract JSON from the response
        json_match = re.search(r"\{[\s\S]*\}", response)
        if not json_match:
            self.logger.warning(f"No JSON found in LLM response: {response[:200]}")
            return self._default_result(
                reason="Failed to parse LLM response", raw_response=response
            )

        try:
            data = json.loads(json_match.group())

            # Extract and validate fields
            qualifies = bool(data.get("qualifies", False))
            development_type = data.get("development_type", "other")
            unit_count = data.get("unit_count")
            confidence = data.get("confidence", "low")
            reason = data.get("reason", "")

            # Normalize development_type
            if development_type not in ("new_build", "conversion", "extension", "other"):
                development_type = "other"

            # Normalize confidence
            if confidence not in ("high", "medium", "low"):
                confidence = "low"

            # Parse unit_count
            if unit_count is not None:
                try:
                    unit_count = int(unit_count)
                except (ValueError, TypeError):
                    unit_count = None

            return ClassificationResult(
                qualifies=qualifies,
                development_type=development_type,
                unit_count=unit_count,
                confidence=confidence,
                reason=str(reason)[:200],  # Truncate long reasons
                raw_response=response,
            )

        except json.JSONDecodeError as e:
            self.logger.warning(f"JSON parse error: {e}. Response: {response[:200]}")
            return self._default_result(
                reason=f"JSON parse error: {e}", raw_response=response
            )

    def _default_result(
        self, reason: str, raw_response: Optional[str] = None
    ) -> ClassificationResult:
        """Return a default non-qualifying result."""
        return ClassificationResult(
            qualifies=False,
            development_type="other",
            unit_count=None,
            confidence="low",
            reason=reason,
            raw_response=raw_response,
        )

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self.cache.get_stats()
