from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "sqlite:///./familymvp.db"

    # Audio storage
    audio_storage_path: str = "./data/audio"

    # WebSocket
    ws_host: str = "0.0.0.0"
    ws_port: int = 8000

    # Tencent Cloud ASR
    tencent_appid: str = "1314143047"  # 实时语音识别需要的 APPID
    tencent_secret_id: str = ""  # 从环境变量 TENCENT_SECRET_ID 读取，勿提交真实密钥
    tencent_secret_key: str = ""  # 从环境变量 TENCENT_SECRET_KEY 读取
    tencent_asr_region: str = "ap-guangzhou"

    # Tencent Cloud COS (对象存储)
    # 配置后即可自动上传音频文件到 COS，实现真实的 ASR 处理
    # 留空则使用占位数据
    tencent_cos_region: Optional[str] = "ap-guangzhou"
    tencent_cos_bucket: Optional[str] = "info-tech-test-1314143047"
    # 是否使用预签名 URL（True=私有读私有写，False=公有读私有写）
    tencent_cos_use_presigned_url: bool = True
    cos_presign_asr_expire_seconds: int = 86400   # ASR 预签名有效期（秒）
    cos_presign_play_expire_seconds: int = 3600   # 播放预签名有效期（秒）

    # Public base URL for building media links (e.g., http://47.236.106.225:9000)
    public_base_url: Optional[str] = None

    @property
    def PUBLIC_BASE_URL(self) -> Optional[str]:
        """Alias for public_base_url (uppercase) for backward compatibility"""
        return self.public_base_url

    # OpenRouter (LLM for harmful content analysis). Set OPENROUTER_API_KEY in .env (local only).
    openrouter_api_key: str = ""
    openrouter_model: str = "google/gemma-3-27b-it"

    # Embedding (semantic vector search for harmful detection)
    # provider: "openai" | "local" (local = sentence-transformers, optional dep)
    embedding_provider: str = "openai"
    embedding_api_key: Optional[str] = None  # OpenAI API key for embeddings
    embedding_model: str = "text-embedding-3-small"
    embedding_base_url: Optional[str] = None  # e.g. custom OpenAI-compatible endpoint

    # JWT Authentication
    jwt_secret_key: str = "your-secret-key-here-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24  # 24 hours

    # Device Ingest Token (for /api/ingest/* endpoints)
    # Set this in .env to enable device authentication for PCM uploads
    device_ingest_token: Optional[str] = None

settings = Settings()
