from __future__ import annotations

from app.common.elastic_logs import ElasticSourceConfig

ACS_SOURCE = ElasticSourceConfig(
    app_name_env="ELASTIC_APP_NAME",
    app_name_default="solar-acs",
    hosts_env="ELASTIC_HOSTS",
    hosts_default=("acss201", "acss202"),
)
