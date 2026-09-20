"""Keep profile values literal and prevent implicit provider credential lookup."""

from pydantic import SecretStr

# None and empty strings trigger LiteLLM's ambient credential lookup. A nonempty
# placeholder supports keyless local endpoints without exposing process secrets.
NO_API_KEY = "companion-no-api-key"


def validate_literal_llm_value(value: object) -> object:
    """Reject LiteLLM environment references in profile-controlled values."""
    raw = value.get_secret_value() if isinstance(value, SecretStr) else value
    if isinstance(raw, str) and raw.strip().startswith("os.environ/"):
        raise ValueError("Environment references are not allowed in LLM profiles; enter a literal value")
    return value


def build_llm_params(model: str, api_key: str | None, api_base: str | None) -> dict[str, str]:
    """Validate again at the provider boundary, including persisted profiles."""
    for value in (model, api_key, api_base):
        validate_literal_llm_value(value)
    params = {"model": model, "api_key": api_key or NO_API_KEY}
    if api_base:
        params["api_base"] = api_base
    return params
