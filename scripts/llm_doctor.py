#!/usr/bin/env python3
"""LLM Doctor - Diagnostic tool for testing LLM configuration.

This script tests the configured LLM to verify it works correctly with
Homebox Companion's requirements. It runs a series of tests and reports
the results.

Usage:
    uv run python scripts/llm_doctor.py

Environment Variables:
    HBC_LLM_API_KEY: API key for the LLM provider
    HBC_LLM_MODEL: Model identifier (e.g., gpt-5-mini)
    HBC_LLM_API_BASE: Optional custom API base URL
    HBC_LLM_ALLOW_UNSAFE_MODELS: Set to 'true' to test non-allowlisted models
"""

from __future__ import annotations

import asyncio
import base64
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from homebox_companion.ai.llm import (
    CapabilityNotSupportedError,
    JSONRepairError,
    LLMError,
    chat_completion,
    vision_completion,
)
from homebox_companion.ai.model_capabilities import get_model_capabilities
from homebox_companion.core.config import settings


@dataclass
class TestResult:
    """Result of a single test."""

    name: str
    passed: bool
    latency_ms: float = 0.0
    repair_needed: bool = False
    error: str | None = None
    details: str | None = None


@dataclass
class DiagnosticReport:
    """Full diagnostic report."""

    model: str
    api_base: str | None
    allow_unsafe: bool
    capabilities: dict[str, bool] = field(default_factory=dict)
    tests: list[TestResult] = field(default_factory=list)

    def print_report(self) -> None:
        """Print the diagnostic report to console."""
        print("\n" + "=" * 60)
        print("LLM DOCTOR - Diagnostic Report")
        print("=" * 60)

        print(f"\nModel: {self.model}")
        print(f"API Base: {self.api_base or '(default)'}")
        print(f"Allow Unsafe Models: {'Yes' if self.allow_unsafe else 'No'}")

        print("\nCapabilities:")
        for cap, supported in self.capabilities.items():
            status = "✓" if supported else "✗"
            print(f"  {status} {cap}")

        print("\nTest Results:")
        print("-" * 60)

        all_passed = True
        for test in self.tests:
            status = "✓ PASS" if test.passed else "✗ FAIL"
            all_passed = all_passed and test.passed

            print(f"\n  {status}: {test.name}")
            if test.latency_ms > 0:
                print(f"         Latency: {test.latency_ms:.0f}ms")
            if test.repair_needed:
                print("         ⚠ JSON repair was needed")
            if test.error:
                print(f"         Error: {test.error}")
            if test.details:
                print(f"         Details: {test.details}")

        print("\n" + "=" * 60)
        if all_passed:
            print("✓ All tests passed! Your LLM configuration is working.")
        else:
            print("✗ Some tests failed. Check the errors above.")
        print("=" * 60 + "\n")


async def test_text_json(model: str) -> TestResult:
    """Test basic text-to-JSON generation."""
    start = time.perf_counter()
    try:
        result = await chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant. Always respond with valid JSON.",
                },
                {
                    "role": "user",
                    "content": (
                        "Return a JSON object with exactly these fields: "
                        '{"test": "success", "number": 42, "items": ["a", "b", "c"]}'
                    ),
                },
            ],
            model=model,
            response_format={"type": "json_object"},
            expected_keys=["test", "number", "items"],
        )

        latency = (time.perf_counter() - start) * 1000

        # Validate response structure
        if result.get("test") and result.get("items"):
            return TestResult(
                name="Text-only JSON generation",
                passed=True,
                latency_ms=latency,
                details=f"Got valid JSON with {len(result)} keys",
            )
        else:
            return TestResult(
                name="Text-only JSON generation",
                passed=False,
                latency_ms=latency,
                error="Response missing expected fields",
                details=f"Got: {list(result.keys())}",
            )

    except JSONRepairError as e:
        return TestResult(
            name="Text-only JSON generation",
            passed=False,
            latency_ms=(time.perf_counter() - start) * 1000,
            repair_needed=True,
            error=str(e),
        )
    except Exception as e:
        return TestResult(
            name="Text-only JSON generation",
            passed=False,
            latency_ms=(time.perf_counter() - start) * 1000,
            error=str(e),
        )


async def test_vision_json(model: str) -> TestResult:
    """Test vision + JSON extraction."""
    # Create a simple 1x1 red pixel PNG as test image
    # This is the minimal valid PNG that can be processed
    png_data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
    )
    data_uri = f"data:image/png;base64,{base64.b64encode(png_data).decode()}"

    start = time.perf_counter()
    try:
        result = await vision_completion(
            system_prompt=(
                "You are an image analyzer. Describe what you see in JSON format. "
                "Always respond with valid JSON containing 'description' and 'color' fields."
            ),
            user_prompt="Describe this image. Return JSON with 'description' and 'color' fields.",
            image_data_uris=[data_uri],
            model=model,
            expected_keys=["description"],
        )

        latency = (time.perf_counter() - start) * 1000

        if "description" in result:
            return TestResult(
                name="Vision + JSON extraction",
                passed=True,
                latency_ms=latency,
                details=f"Successfully analyzed image: {result.get('description', '')[:50]}...",
            )
        else:
            return TestResult(
                name="Vision + JSON extraction",
                passed=False,
                latency_ms=latency,
                error="Response missing 'description' field",
            )

    except CapabilityNotSupportedError as e:
        return TestResult(
            name="Vision + JSON extraction",
            passed=False,
            latency_ms=0,
            error=f"Vision not supported: {e}",
        )
    except JSONRepairError as e:
        return TestResult(
            name="Vision + JSON extraction",
            passed=False,
            latency_ms=(time.perf_counter() - start) * 1000,
            repair_needed=True,
            error=str(e),
        )
    except Exception as e:
        return TestResult(
            name="Vision + JSON extraction",
            passed=False,
            latency_ms=(time.perf_counter() - start) * 1000,
            error=str(e),
        )


async def test_multi_image(model: str) -> TestResult:
    """Test multi-image processing."""
    # Create two different colored 1x1 pixels
    red_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
    )
    blue_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPj/HwADBwIAMCbHYQAAAABJRU5ErkJggg=="
    )

    data_uri_1 = f"data:image/png;base64,{base64.b64encode(red_png).decode()}"
    data_uri_2 = f"data:image/png;base64,{base64.b64encode(blue_png).decode()}"

    start = time.perf_counter()
    try:
        result = await vision_completion(
            system_prompt=(
                "You are an image analyzer comparing multiple images. "
                "Always respond with valid JSON containing 'image_count' and 'comparison' fields."
            ),
            user_prompt=(
                "You are shown 2 images. Return JSON with 'image_count' (integer) "
                "and 'comparison' (string describing the images)."
            ),
            image_data_uris=[data_uri_1, data_uri_2],
            model=model,
            expected_keys=["image_count"],
        )

        latency = (time.perf_counter() - start) * 1000

        if "image_count" in result:
            return TestResult(
                name="Multi-image processing",
                passed=True,
                latency_ms=latency,
                details=f"Processed {result.get('image_count', 'unknown')} images",
            )
        else:
            return TestResult(
                name="Multi-image processing",
                passed=False,
                latency_ms=latency,
                error="Response missing 'image_count' field",
            )

    except CapabilityNotSupportedError as e:
        return TestResult(
            name="Multi-image processing",
            passed=False,
            latency_ms=0,
            error=f"Multi-image not supported: {e}",
        )
    except JSONRepairError as e:
        return TestResult(
            name="Multi-image processing",
            passed=False,
            latency_ms=(time.perf_counter() - start) * 1000,
            repair_needed=True,
            error=str(e),
        )
    except Exception as e:
        return TestResult(
            name="Multi-image processing",
            passed=False,
            latency_ms=(time.perf_counter() - start) * 1000,
            error=str(e),
        )


async def run_diagnostics() -> DiagnosticReport:
    """Run all diagnostic tests and generate report."""
    model = settings.effective_llm_model
    api_base = settings.llm_api_base
    allow_unsafe = settings.llm_allow_unsafe_models

    # Get model capabilities via LiteLLM
    caps = get_model_capabilities(model)

    report = DiagnosticReport(
        model=model,
        api_base=api_base,
        allow_unsafe=allow_unsafe,
    )

    # Store capabilities
    report.capabilities = {
        "vision": caps.vision,
        "multi_image": caps.multi_image,
        "json_mode": caps.json_mode,
    }

    # Run tests
    print(f"\nRunning diagnostics for model: {model}")
    print("-" * 40)

    # Test 1: Text-only JSON
    print("Testing text-only JSON generation...")
    report.tests.append(await test_text_json(model))

    # Test 2: Vision (if supported)
    if caps.vision:
        print("Testing vision + JSON extraction...")
        report.tests.append(await test_vision_json(model))
    else:
        report.tests.append(
            TestResult(
                name="Vision + JSON extraction",
                passed=True,  # Skipped, not a failure
                details="Skipped (model does not support vision)",
            )
        )

    # Test 3: Multi-image (if supported)
    if caps.multi_image:
        print("Testing multi-image processing...")
        report.tests.append(await test_multi_image(model))
    else:
        report.tests.append(
            TestResult(
                name="Multi-image processing",
                passed=True,  # Skipped, not a failure
                details="Skipped (model does not support multi-image)",
            )
        )

    return report


def main() -> int:
    """Main entry point."""
    print("\n" + "=" * 60)
    print("LLM Doctor - Homebox Companion Diagnostic Tool")
    print("=" * 60)

    # Check API key
    if not settings.effective_llm_api_key:
        print("\n✗ ERROR: No API key configured!")
        print("  Set HBC_LLM_API_KEY or HBC_OPENAI_API_KEY environment variable.")
        return 1

    # Show configuration
    print("\nConfiguration:")
    print(f"  Model: {settings.effective_llm_model}")
    print(f"  API Base: {settings.llm_api_base or '(default)'}")
    print(f"  Allow Unsafe Models: {settings.llm_allow_unsafe_models}")

    if settings.using_legacy_openai_env:
        print("\n⚠ Using legacy HBC_OPENAI_* environment variables.")
        print("  Consider migrating to HBC_LLM_* for future compatibility.")

    # Run diagnostics
    try:
        report = asyncio.run(run_diagnostics())
        report.print_report()

        # Return exit code based on results
        all_passed = all(t.passed for t in report.tests)
        return 0 if all_passed else 1

    except LLMError as e:
        print(f"\n✗ LLM ERROR: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

