from pydantic_settings import BaseSettings
from functools import lru_cache
import platform


class Settings(BaseSettings):
    # App
    app_name: str = "Game Panel"
    app_url: str = "https://game.example.com"
    debug: bool = False

    # JWT
    jwt_secret: str = "CHANGE_ME"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/game_panel.db"

    # SMTP
    smtp_host: str = "mail.example.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_from: str = "noreply@example.com"
    admin_email: str = "admin@example.com"

    # Initial admin
    admin_username: str = "admin"
    admin_password: str = "CHANGE_ME"

    # Docker
    docker_socket: str = "/var/run/docker.sock"
    game_network: str = "game-servers"

    # Health check
    healthcheck_interval_minutes: int = 5
    auto_delete_days: int = 7
    healthcheck_notify: bool = True

    # Ports
    panel_https_port: int = 443
    panel_http_port: int = 80

    # ─── Discord OAuth2 ───
    discord_client_id: str = ""
    discord_client_secret: str = ""
    discord_redirect_uri: str = "https://game.example.com/api/auth/discord/callback"
    discord_guild_id: str = ""        # 비공개 디스코드 서버 ID
    discord_bot_token: str = ""       # 서버 멤버 확인용 봇 토큰
    discord_enabled: bool = True

    # ─── Discord 알림 채널 ───
    discord_notify_channel_id: str = ""   # 서버 상태 알림 채널
    discord_request_channel_id: str = ""  # 게임 신청 알림 채널 (비워두면 notify 채널 사용)
    discord_notify_enabled: bool = True

    # ─── Discord 역할 제한 ───
    discord_allowed_role_ids: str = ""    # 허용 역할 ID (쉼표 구분, 비워두면 멤버만 확인)

    @property
    def allowed_role_ids(self) -> list[str]:
        """쉼표 구분 역할 ID → 리스트"""
        if not self.discord_allowed_role_ids.strip():
            return []
        return [r.strip() for r in self.discord_allowed_role_ids.split(",") if r.strip()]

    # ─── 초대 코드 (디스코드 안 쓰는 지인용) ───
    invite_code_enabled: bool = True

    # ─── 모드 관리 ───
    max_mod_upload_size_mb: int = 100  # 모드 파일 최대 크기 (MB)

    @property
    def docker_base_url(self) -> str:
        if platform.system() == "Windows":
            return "npipe:////./pipe/docker_engine"
        return f"unix://{self.docker_socket}"

    @property
    def is_windows(self) -> bool:
        return platform.system() == "Windows"

    @property
    def discord_auth_url(self) -> str:
        from urllib.parse import quote
        return (
            f"https://discord.com/api/oauth2/authorize"
            f"?client_id={self.discord_client_id}"
            f"&redirect_uri={quote(self.discord_redirect_uri, safe='')}"
            f"&response_type=code"
            f"&scope=identify+guilds+guilds.members.read"
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
