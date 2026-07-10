# file: config.py
# description: 应用配置管理模块
# author: YanYuCloudCube Team
# version: v1.0.0
# created: 2026-03-21
# updated: 2026-04-04
# status: active
# tags: [config],[settings],[management]

"""
@file: app/config.py
@description: 应用配置模块，提供环境变量和配置管理
@author: YanYuCloudCube Team <admin@0379.email>
@version: v1.0.0
@created: 2026-03-13
@updated: 2026-03-13
@status: stable
@license: MIT
@copyright: Copyright (c) 2026 YanYuCloudCube Team
@tags: config,python,core,public
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    postgres_password: str = ""
    replicator_password: str = ""

    ollama_host: str = "host.docker.internal"
    ollama_port: int = 11434
    ollama_models: str = "/mnt/models"

    openai_api_key: str = ""
    zhipu_api_key: str = ""
    deepseek_api_key: str = ""

    prometheus_multiproc_dir: str = "/tmp/prometheus_multiproc"

    host_ip: str = "10.200.0.2"
    host_ip_suffix: str = "2"

    db_host: str = "postgres"
    db_port: int = 5432
    db_user: str = "postgres"
    db_password: str = ""
    db_name: str = "yyc3_gpt"

    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4

    auth_enabled: bool = True
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24

    api_keys: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.db_password and self.postgres_password:
            self.db_password = self.postgres_password


settings = Settings()
