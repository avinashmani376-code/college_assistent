from core.router import route_message


def test_route_message_detects_english_video_intent():
    response = route_message("Hello Ideal College AI play college video")
    assert response["intent"] == "video"
    assert response["show_video"] is True
    assert response["language"] == "en"
    assert response["video_url"]


def test_route_message_detects_telugu_images_intent():
    response = route_message("\u0c39\u0c32\u0c4b \u0c10\u0c21\u0c3f\u0c2f\u0c32\u0c4d \u0c15\u0c3e\u0c32\u0c47\u0c1c\u0c4d \u0c0f\u0c10 \u0c15\u0c3e\u0c32\u0c47\u0c1c\u0c40 \u0c2b\u0c4b\u0c1f\u0c4b\u0c32\u0c41 \u0c1a\u0c42\u0c2a\u0c3f\u0c02\u0c1a\u0c41")
    assert response["intent"] == "images"
    assert response["show_images"] is True
    assert response["language"] == "te"
    assert response["images"]


def test_route_message_uses_general_response_language(monkeypatch):
    def fake_query_groq(message, history, system_prompt=None, lang="en"):
      return "Mee kosam clear Telugu reply." if lang == "te" else "Here is a clear English reply."

    monkeypatch.setattr("core.router.query_groq", fake_query_groq)
    response = route_message("naku admissions gurunchi cheppu")
    assert response["language"] == "te"
    assert "Telugu" in response["reply"]
