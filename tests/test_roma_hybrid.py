# tests/test_roma_hybrid.py
import pytest
from migration.hybrid_transition import HybridTransition

class TestRomaHybrid:
    @pytest.fixture
    def sample_health_data(self):
        return {
            "steps": 8000,
            "sleep_hours": 7.5,
            "workouts": 3,
            "water_liters": 2.5
        }

    @pytest.mark.asyncio
    async def test_roma_vs_legacy_consistency(self, sample_health_data):
        transition = HybridTransition()

        transition.use_roma = False
        legacy_result = await transition.execute_task("quick_analysis", sample_health_data)

        transition.use_roma = True
        roma_result = await transition.execute_task("quick_analysis", sample_health_data)

        assert abs(
            legacy_result["metrics"]["overall_score"] -
            roma_result["metrics"]["overall_score"]
        ) < 0.1

