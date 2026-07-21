from app.conf.meta_config import MetaConfig
from app.repositories.qdrant.column_qdrant_repository import _entity_payload


def test_meta_config_accepts_index_version():
    config = MetaConfig(version="v2")

    assert config.version == "v2"


def test_qdrant_private_index_metadata_is_not_passed_to_entity():
    payload = {
        "id": "fact_order.order_id",
        "name": "order_id",
        "_index_version": "v2",
    }

    assert _entity_payload(payload) == {
        "id": "fact_order.order_id",
        "name": "order_id",
    }
