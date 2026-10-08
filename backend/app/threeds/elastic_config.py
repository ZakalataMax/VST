from __future__ import annotations

from app.common.elastic_logs import ElasticSourceConfig

THREEDS_SOURCE = ElasticSourceConfig(
    app_name_env="ELASTIC_3DS_APP_NAME",
    app_name_default="solar-3ds-server",
    hosts_env="ELASTIC_3DS_HOSTS",
    hosts_default=("3dss201", "3dss202"),
)
