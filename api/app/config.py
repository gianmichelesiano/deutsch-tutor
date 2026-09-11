from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://deutsch:deutsch@localhost:5433/deutsch_tutor"
    api_prefix: str = "/api"
    timezone: str = "Europe/Zurich"
    user_name: str = "Gianmichele"

    # --- LLM: provider "local" = endpoint OpenAI-compatibile (DeepSeek remoto,
    # oppure llama.cpp/ds4 in locale) / cloud (Anthropic) ---
    local_llm_base_url: str = "https://api.deepseek.com"
    local_llm_api_key: str = ""
    local_llm_model: str = "deepseek-flash"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"
    # auto: route per task con fallback locale->cloud; local-only/cloud-only: forza
    # un provider; mock: client deterministico (test/sviluppo senza modelli).
    llm_provider_mode: str = "auto"
    llm_timeout_seconds: float = 30.0
    roleplay_temperature: float = 0.7
    roleplay_max_tokens: int = 200
    cloud_temperature: float = 0.3
    cloud_max_tokens: int = 1024
    max_roleplay_turns: int = 12
    # DeepSeek Flash è un reasoning model (thinking attivo di default):
    # per il roleplay serve risposta immediata e JSON conciso, quindi il thinking
    # viene disattivato (evita che max_tokens=200 sia consumato dal ragionamento).
    local_llm_thinking_disabled: bool = True
    # Penalità di ripetizione, solo llama.cpp/ds4 (>1 penalizza). 0 = non inviata;
    # l'API DeepSeek non la conosce, quindi resta disattivata di default.
    local_llm_repeat_penalty: float = 0.0
    prompts_dir: str = ""


settings = Settings()
