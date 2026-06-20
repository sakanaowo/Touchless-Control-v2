from touchless_control.core.contracts import IntentContext


def attention_allows_input(context: IntentContext) -> bool:
    attention = context.attention_frame
    return attention is None or attention.attention_on_screen
