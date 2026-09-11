"""Test degli agenti (task 3.3): costruzione dei messaggi Gesprächspartner/Korrektor."""
from types import SimpleNamespace

from app import agents


def _scenario() -> SimpleNamespace:
    return SimpleNamespace(
        role_label="Verkäuferin am Supermarkt",
        title_de="Im Supermarkt",
        title_it="Al supermercato",
        description="Fare la spesa al supermercato.",
        imprevisti=["Der Zopf ist ausverkauft."],
        goals=["Nach einem Produkt fragen und es finden."],
        key_phrases=[{"de": "Ich hätte gern…", "it": "Vorrei…"}],
    )


def test_roleplay_messages_opening_adds_trigger():
    msgs = agents.build_roleplay_messages(_scenario(), [])
    assert msgs[0]["role"] == "system"
    assert "Verkäuferin" in msgs[0]["content"]
    assert "Zürich" in msgs[0]["content"]
    assert "Franken" in msgs[0]["content"]
    assert msgs[-1] == {"role": "user", "content": "Beginne das Gespräch."}


def test_roleplay_messages_with_history_no_trigger():
    history = [
        {"role": "agent", "content": "Grüezi!"},
        {"role": "user", "content": "Ich suche Eier."},
    ]
    msgs = agents.build_roleplay_messages(_scenario(), history)
    assert msgs[-1] == {"role": "user", "content": "Ich suche Eier."}
    # i turni dell'agente vanno inviati come "assistant" (ruolo OpenAI standard,
    # DeepSeek rifiuta ruoli sconosciuti)
    assert msgs[-2] == {"role": "assistant", "content": "Grüezi!"}
    assert not any(m["role"] == "agent" for m in msgs)


def test_roleplay_react_incomprehensible_injects_hint():
    msgs = agents.build_roleplay_messages(
        _scenario(), [{"role": "user", "content": "x"}], react_incomprehensible=True
    )
    system_text = " ".join(m["content"] for m in msgs if m["role"] == "system")
    assert "Wie bitte" in system_text


def test_roleplay_limits_history_to_last_six():
    history = [{"role": "agent" if i % 2 == 0 else "user", "content": f"m{i}"} for i in range(20)]
    msgs = agents.build_roleplay_messages(_scenario(), history)
    contents = [m["content"] for m in msgs if m["role"] in ("user", "assistant")]
    assert contents == [f"m{i}" for i in range(14, 20)]  # ultimi 6


def test_scene_state_injected_in_prompt():
    scene = {"items": ["Eier", "Baguette"], "total_chf": 8.5, "payment": "bar", "incident_done": True, "goals_done": ["Nach einem Produkt fragen"]}
    msgs = agents.build_roleplay_messages(
        _scenario(), [{"role": "user", "content": "ok"}], scene_state=scene
    )
    system = msgs[0]["content"]
    assert "Eier, Baguette" in system
    assert "8.5 Franken" in system
    assert "bar" in system


def test_format_scene_state_empty():
    assert agents.format_scene_state(None) == "- (noch nichts passiert)"
    assert agents.format_scene_state({}) == "- (noch nichts passiert)"


def test_corrector_messages_structure():
    msgs = agents.build_corrector_messages(_scenario(), "Ich suche [uova]", "Die Eier sind dort.")
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    assert "Ich suche [uova]" in msgs[1]["content"]
    assert "Die Eier sind dort." in msgs[1]["content"]


def test_warmup_messages_structure():
    msgs = agents.build_warmup_messages("abwiegen", "pesare (separabile)", "Ich abwiege die Banane.")
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    assert "abwiegen" in msgs[1]["content"]
    assert "Ich abwiege die Banane." in msgs[1]["content"]


def test_planner_messages_structure():
    data = {"requested": ["die Eier"], "error_words": ["das Bier"], "agent_words": ["die Baguette"], "corrections": ["articolo"]}
    msgs = agents.build_planner_messages(_scenario(), data)
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    assert "die Eier" in msgs[0]["content"]


def test_content_gen_messages_structure():
    msgs = agents.build_content_gen_meta_messages(_scenario())
    assert msgs[0]["role"] == "system"
    assert "Im Supermarkt" in msgs[0]["content"]
    assert msgs[1]["role"] == "user"

    vocab_msgs = agents.build_content_gen_vocab_messages(_scenario(), ["der Apfel"], 20)
    assert vocab_msgs[0]["role"] == "system"
    assert "der Apfel" in vocab_msgs[0]["content"]
    assert "20" in vocab_msgs[0]["content"]


def test_warmup_feedback_schema():
    from app.agents import WarmupFeedback

    f = WarmupFeedback.model_validate(
        {"is_correct": False, "corrected_sentence": "Ich wiege die Banane ab.", "feedback_it": "Separabile.", "error_type": "separable_verb"}
    )
    assert f.error_type == "separable_verb"


def test_scene_state_has_greeted():
    from app.agents import SceneState

    s = SceneState.model_validate({"items": [], "greeted": True})
    assert s.greeted is True
    assert "Begrüssung" in agents.format_scene_state({"greeted": True})


def test_prompts_allow_colloquial_forms():
    from app import prompts

    corrector = prompts.load("corrector.md")
    warmup = prompts.load("warmup_feedback.md")
    for text in (corrector, warmup):
        assert "mit Karte zahlen" in text
        assert "bar zahlen" in text
        assert "im Angebot" in text
        assert "Konjunktiv II" in text


def test_content_gen_intro_messages_mention_scenario_and_role():
    sc = _scenario()
    msgs = agents.build_content_gen_intro_messages(sc)
    assert msgs[0]["role"] == "system"
    assert sc.title_de in msgs[0]["content"]
    assert "Verkäuferin am Supermarkt" in msgs[0]["content"]
    assert "hochdeutsch" in msgs[0]["content"].lower()
    assert msgs[-1]["role"] == "user"
