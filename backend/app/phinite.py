import asyncio
import os
from collections.abc import AsyncIterator

import httpx
from pydantic import ValidationError

from .schemas import RecommendationRequest, RecommendationResponse


class PhiniteConfigurationError(Exception):
    """Raised when the server-side Phinite credentials are missing."""


class PhiniteResponseError(Exception):
    """Raised when Phinite cannot provide a valid completed recommendation."""


async def get_phinite_http_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(timeout=60.0) as client:
        yield client


async def request_phinite_recommendation(
    request: RecommendationRequest,
    client: httpx.AsyncClient,
) -> RecommendationResponse:
    trigger_url = os.getenv("PHINITE_TRIGGER_URL", "").strip()
    api_key = os.getenv("PHINITE_API_KEY", "").strip()

    if not trigger_url or not api_key:
        raise PhiniteConfigurationError(
            "Phinite integration is not configured"
        )

    payload = {
        "message": "Find the best shelf rescue recommendation",
        "user_variables": {
            "merchant_id": request.merchant_id,
            "sku": request.sku,
        },
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    last_error: Exception | None = None

    # Phinite DEV occasionally returns a "completed" workflow
    # before the recommendation state is fully populated.
    # Retry once rather than accepting an incomplete result.
    for attempt in range(2):
        try:
            response = await client.post(
                trigger_url,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()

        except httpx.HTTPStatusError as exc:
            raise PhiniteResponseError(
                f"Phinite request failed with status "
                f"{exc.response.status_code}"
            ) from exc

        except httpx.RequestError as exc:
            raise PhiniteResponseError(
                "Phinite could not be reached"
            ) from exc

        try:
            envelope = response.json()
        except ValueError as exc:
            raise PhiniteResponseError(
                "Phinite returned invalid JSON"
            ) from exc

        if not isinstance(envelope, dict):
            last_error = PhiniteResponseError(
                "Phinite returned an invalid response"
            )

        elif envelope.get("status") != "completed":
            last_error = PhiniteResponseError(
                "Phinite workflow did not complete"
            )

        elif envelope.get("error"):
            raise PhiniteResponseError(
                "Phinite workflow returned an error"
            )

        else:
            recommendation = envelope.get("response")

            if not isinstance(recommendation, dict):
                last_error = PhiniteResponseError(
                    "Phinite response is missing a recommendation"
                )

            else:
                try:
                    normalized = (
                        RecommendationResponse.model_validate(
                            recommendation
                        )
                    )

                except ValidationError as exc:
                    last_error = exc

                else:
                    if (
                        normalized.merchant_id
                        != request.merchant_id
                        or normalized.sku != request.sku
                    ):
                        raise PhiniteResponseError(
                            "Phinite recommendation does not "
                            "match the request"
                        )

                    return normalized

        # One short retry for the transient incomplete-state case.
        if attempt == 0:
            await asyncio.sleep(0.5)

    raise PhiniteResponseError(
        "Phinite returned an incomplete or invalid recommendation "
        "after retry"
    ) from last_error