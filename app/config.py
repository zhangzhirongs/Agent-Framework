from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENT_", env_file=ROOT / ".env", extra="ignore")
    model: str = ""
    api_key: SecretStr = SecretStr("")
    base_url: str = ""
    api_mode: Literal["chat", "responses"] = "chat"
    vision_enabled: bool = False
    model_timeout: int = Field(default=120, ge=10, le=1800)
    max_turns: int = Field(default=12, ge=1, le=50)
    max_concurrent_runs: int = Field(default=2, ge=1, le=32)
    search_provider: Literal["none", "tavily", "brave", "searxng"] = "none"
    search_api_key: SecretStr = SecretStr("")
    search_base_url: str = ""
    deployment_mode: Literal["development", "production"] = "development"
    demo_account: bool = True
    secure_cookie: bool = False
    data_dir: Path = ROOT / "data"
    skills_dir: Path = ROOT / "skills"
    mcp_config: Path = ROOT / "mcp.json"
    max_upload_mb: int = Field(default=20, ge=1, le=100)

    @model_validator(mode="after")
    def validate_deployment(self):
        for name in ("data_dir", "skills_dir", "mcp_config"):
            path = getattr(self, name).expanduser()
            setattr(self, name, (ROOT / path).resolve() if not path.is_absolute() else path)
        if self.deployment_mode == "production" and (self.demo_account or not self.secure_cookie):
            raise ValueError("Production requires demo_account=false and secure_cookie=true")
        return self

    @property
    def model_ready(self):
        return bool(self.model and self.base_url and self.api_key.get_secret_value())
