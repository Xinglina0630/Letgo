import sys
import unittest
from pathlib import Path

from pydantic import ValidationError


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.schemas.itinerary import (  # noqa: E402
    ItineraryCreateRequest,
    ItineraryEdgeCreate,
    ItineraryNodeCreate,
)


class ItineraryInputValidationTests(unittest.TestCase):
    def test_rejects_blank_name(self):
        with self.assertRaises(ValidationError):
            ItineraryCreateRequest(name="", city="上海")

    def test_rejects_invalid_coordinates(self):
        with self.assertRaises(ValidationError):
            ItineraryNodeCreate(
                temp_id="node-1",
                name="外滩",
                node_type="attraction",
                day_number=1,
                order_in_day=0,
                latitude=91,
                longitude=121.49,
            )

    def test_rejects_negative_route_values(self):
        with self.assertRaises(ValidationError):
            ItineraryEdgeCreate(
                source_node_id="node-1",
                target_node_id="node-2",
                transport_type="taxi",
                estimated_time_minutes=-1,
            )

    def test_accepts_normal_itinerary(self):
        request = ItineraryCreateRequest(
            name="上海周末",
            city="上海",
            nodes=[
                ItineraryNodeCreate(
                    temp_id="node-1",
                    name="外滩",
                    node_type="attraction",
                    day_number=1,
                    order_in_day=0,
                    latitude=31.24,
                    longitude=121.49,
                )
            ],
        )
        self.assertEqual(request.name, "上海周末")


if __name__ == "__main__":
    unittest.main()
