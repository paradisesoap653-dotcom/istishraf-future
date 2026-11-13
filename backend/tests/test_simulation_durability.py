"""ديمومة ملفات المحاكاة عبر cold start (Vercel).

المشكلة: Vercel يمسح القرص المؤقت بين الطلبات، فكان ``/simulation/start``
يرفض العمل برسالة «模拟配置不存在» رغم أن ``/prepare`` نجح.
الحل: قراءة الملفات عبر ``ensure_local_file`` التي تُعيدها من Neon.
"""

import json
import os
import shutil
import tempfile

import pytest

POSTGRES_URL = os.environ.get("TEST_POSTGRES_URL")


def _durable_env(tmp_path, monkeypatch):
    from app.config import Config
    from app.models import storage

    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(tmp_path), raising=False)
    monkeypatch.setattr(Config, "DATABASE_URL", POSTGRES_URL or "", raising=False)
    storage.reset_pool()
    return storage


def test_simulation_config_restored_after_cold_start(tmp_path, monkeypatch):
    if not POSTGRES_URL:
        pytest.skip("TEST_POSTGRES_URL غير مضبوط")
    storage = _durable_env(tmp_path, monkeypatch)
    if not storage.is_durable():
        pytest.skip("التخزين الدائم غير متاح")

    from app.services.simulation_runner import ensure_local_file

    sim_dir = os.path.join(tmp_path, "simulations", "sim_cold_1")
    config_path = os.path.join(sim_dir, "simulation_config.json")
    payload = {"simulation_id": "sim_cold_1", "agent_configs": [{"agent_id": 0}]}
    storage.write_json(config_path, payload)
    assert storage.is_durable()

    # محاكاة cold start: القرص المحلي فُرِّغ بالكامل
    shutil.rmtree(sim_dir, ignore_errors=True)
    assert not os.path.exists(config_path)

    restored = ensure_local_file(config_path)
    assert os.path.exists(restored), "لم يُستعد الملف من التخزين الدائم"
    with open(restored, encoding="utf-8") as handle:
        assert json.load(handle) == payload


def test_run_state_is_persisted_to_durable_storage(tmp_path, monkeypatch):
    if not POSTGRES_URL:
        pytest.skip("TEST_POSTGRES_URL غير مضبوط")
    storage = _durable_env(tmp_path, monkeypatch)
    if not storage.is_durable():
        pytest.skip("التخزين الدائم غير متاح")

    from app.services.simulation_runner import SimulationRunner

    monkeypatch.setattr(SimulationRunner, "RUN_STATE_DIR", str(os.path.join(tmp_path, "simulations")), raising=False)

    sim_dir = os.path.join(tmp_path, "simulations", "sim_state_1")
    os.makedirs(sim_dir, exist_ok=True)
    state_file = os.path.join(sim_dir, "run_state.json")

    class _State:
        simulation_id = "sim_state_1"

        def to_detail_dict(self):
            return {"simulation_id": self.simulation_id, "runner_status": "idle"}

    SimulationRunner._save_run_state(_State())
    shutil.rmtree(sim_dir, ignore_errors=True)
    assert not os.path.exists(state_file)
    assert storage.read_json(state_file)["simulation_id"] == "sim_state_1"
