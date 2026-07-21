import unittest
from pathlib import Path

from omegaconf import OmegaConf


class MetaConfigMetricsTest(unittest.TestCase):
    def test_order_count_is_registered_as_business_metric(self):
        config = OmegaConf.to_container(
            OmegaConf.load(Path("conf/meta_config.yaml")), resolve=True
        )

        metrics = {metric["name"]: metric for metric in config["metrics"]}
        order_count = metrics.get("订单数")

        self.assertIsNotNone(order_count)
        self.assertEqual(order_count["relevant_columns"], ["fact_order.order_id"])
        self.assertIn("订单量", order_count["alias"])
        self.assertIn("下单数", order_count["alias"])


if __name__ == "__main__":
    unittest.main()
