"""Shared transport for bounded OpenAI Responses calls."""

import httpx


def respond(settings, model, instructions, input_text, *, timeout=15, **options):
    response = httpx.post(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": "Bearer " + settings.openai_api_key.get_secret_value()
        },
        json={
            "model": model,
            "store": False,
            "instructions": instructions,
            "input": input_text,
            **options,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "completed":
        raise ValueError("The OpenAI response was not completed.")
    return [
        item
        for message in payload.get("output", [])
        if message.get("type") == "message"
        for item in message.get("content", [])
        if item.get("type") == "output_text"
    ]


def structured_response(settings, instructions, question, schema):
    output = respond(
        settings,
        settings.openai_search_model,
        instructions,
        question,
        text={
            "format": {
                "type": "json_schema",
                "name": schema.__name__,
                "strict": True,
                "schema": schema.model_json_schema(),
            }
        },
    )
    if len(output) != 1:
        raise ValueError("No structured response was returned.")
    return schema.model_validate_json(output[0]["text"])
