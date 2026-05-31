import logging

import gradio as gr

from app.services.assistant import AssistantUnauthorizedError
from app.api.deps import get_assistant_service

logger = logging.getLogger(__name__)

TITLE = "ACME AI Support"
DEFAULT_ERROR_MESSAGE = (
    "Something went wrong while contacting support. Please try again."
)
UNAUTHORIZED_MESSAGE = (
    "You must be logged in to use support chat. Please sign in and try again."
)


def _assistant_message(content: str) -> dict[str, str]:
    return {"role": "assistant", "content": content}


def _session_id_from_request(request: gr.Request) -> str | None:
    if request.request is None:
        return None
    return request.request.cookies.get("session")


async def respond(
    message: str,
    history: list[dict] | None,
    request: gr.Request,
) -> tuple[list[dict], str]:
    if not message or not message.strip():
        return history or [], ""

    cleaned = message.strip()
    updated = list(history or [])
    updated.append({"role": "user", "content": cleaned})

    try:
        service = get_assistant_service()
        if service is None:
            raise RuntimeError("Assistant service is not initialized")

        payload = await service.get_response(
            cleaned,
            _session_id_from_request(request),
            updated
        )
        updated.append(_assistant_message(payload.message))
    except AssistantUnauthorizedError:
        updated.append(_assistant_message(UNAUTHORIZED_MESSAGE))
    except Exception:
        logger.exception("Unexpected error in respond")
        updated.append(_assistant_message(DEFAULT_ERROR_MESSAGE))

    return updated, ""


HEADER_CSS = """
.acme-header {
    align-items: center !important;
    margin-bottom: 0.5rem !important;
}
.acme-header > :first-child {
    flex: 1 1 auto !important;
    min-width: 0 !important;
}
.acme-header > :last-child {
    flex: 0 0 auto !important;
    margin-left: auto !important;
    width: auto !important;
    min-width: 0 !important;
}
.acme-logout-btn {
    width: fit-content !important;
    min-width: 0 !important;
    flex: 0 0 auto !important;
}
.acme-logout-btn button {
    width: fit-content !important;
    min-width: 0 !important;
    padding: 0.2rem 0.65rem !important;
    font-size: 0.85rem !important;
    line-height: 1.2 !important;
}
"""


def create_ui() -> gr.Blocks:
    with gr.Blocks(title=TITLE, css=HEADER_CSS) as ui:
        with gr.Row(elem_classes=["acme-header"]):
            gr.Markdown(f"# {TITLE}")
            logout_button = gr.Button(
                "Logout",
                variant="secondary",
                size="sm",
                elem_classes=["acme-logout-btn"],
            )
            logout_button.click(
                None,
                js="() => { window.location.href = '/logout'; }",
            )

        chatbot = gr.Chatbot(
            label="Chat",
            height=480,
            buttons=["copy"],
        )

        with gr.Row():
            message_input = gr.Textbox(
                placeholder="Type your message...",
                show_label=False,
                scale=9,
                container=False,
            )
            send_button = gr.Button("Send", variant="primary", scale=1)

        chat_inputs = [message_input, chatbot]
        chat_outputs = [chatbot, message_input]

        send_button.click(respond, chat_inputs, chat_outputs)
        message_input.submit(respond, chat_inputs, chat_outputs)

    return ui
