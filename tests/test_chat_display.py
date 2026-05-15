from src.core.chat_display import messages_for_display


def test_messages_for_display_truncates_old():
    msgs = [{"role": "user", "content": str(i)} for i in range(100)]
    visible, hidden = messages_for_display(msgs, limit=80)
    assert len(visible) == 80
    assert hidden == 20
    assert visible[0]["content"] == "20"
