from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Required from environment (.env / deployment secrets)
    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days
    app_env: str = "development"  # development, staging, production

    # Bedrock LLM for ranking + resume tailoring
    bedrock_llm_model_id: str = "mistral.ministral-3-8b-instruct"
    bedrock_llm_enabled: bool = True

    # Amazon Titan Text Embeddings V2 for resume-job scoring
    aws_region: str = "us-west-2"
    titan_embed_model_id: str = "amazon.titan-embed-text-v2:0"

    # CORS origins as comma-separated values
    # Example: "https://app.example.com,https://admin.example.com"
    cors_allow_origins: str = "http://localhost:4200"

    # For production, keep this false so temp passwords are never returned in API responses.
    expose_temp_password_in_response: bool = False

    log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR

    # Job collection controls
    job_location: str = "United States"
    job_results_wanted: int = 100
    job_hours_old: int = 2
    job_site_names: str = "indeed,linkedin,zip_recruiter,google"
    job_country_indeed: str = "USA"

    # Scheduler interval (seconds)
    pipeline_interval_seconds: int = 2 * 3600

    # Upload and request guards
    max_resume_upload_mb: int = 10
    rate_limit_auth_per_min: int = 20
    rate_limit_parse_per_min: int = 10
    rate_limit_tailor_per_min: int = 20
    rate_limit_pdf_render_per_min: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
