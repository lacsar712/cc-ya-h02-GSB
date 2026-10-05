"""H02 验收：角色门禁 -> 写口 -> 首页可写区。

- reader/匿名写偏航记录：在进入 INSERT 之前被拒，库里不多行、不留空白占坑。
- writer 正常送压线样（±1.5° 边界）：新增一行 pending。
- 角色以服务端用户表为准，篡改 token 内 role claim 无效。

数据库访问被打桩：拒绝路径若触发任何 INSERT，store["inserts"] 就会变长。
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

import api


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def fetchone(self):
        return self._value

    def fetchall(self):
        return self._value


@pytest.fixture
def fake_db(monkeypatch):
    store = {"inserts": [], "next_id": 1}

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def commit(self):
            return None

        def execute(self, sql, params=None):
            head = sql.lstrip().upper()
            if head.startswith("INSERT"):
                store["inserts"].append(params)
                row = {
                    "id": store["next_id"],
                    "turbine_code": params[0],
                    "yaw_err_deg": params[1],
                    "status": "pending",
                    "verdict": None,
                    "reason": None,
                    "created_by": params[2],
                    "created_at": params[3],
                    "processed_at": None,
                }
                store["next_id"] += 1
                return _FakeResult(row)
            if "COUNT(*)" in head:  # seed_if_empty：视为已有种子，跳过
                return _FakeResult({"n": 1})
            return _FakeResult([])

    monkeypatch.setattr(api, "connect", lambda *a, **k: FakeConn())
    return store


def _run(coro):
    return asyncio.run(coro)


async def _token(client, username, password):
    res = await client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert res.status_code == 200
    return (await res.get_json())["access_token"]


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


PAYLOAD_LINE_SAMPLE = {"turbine_code": "W12", "yaw_err_deg": 1.5}


def test_reader_post_is_denied_and_leaves_no_row(fake_db):
    async def scenario():
        async with api.app.test_client() as client:
            token = await _token(client, "observer", "obs123456")
            res = await client.post(
                "/api/logs", json=PAYLOAD_LINE_SAMPLE, headers=_bearer(token)
            )
            assert res.status_code == 403
            body = await res.get_json()
            assert "仅现场技师" in body["detail"]

    _run(scenario())
    # 被挡：库里不能多行，也不能插空白占坑
    assert fake_db["inserts"] == []


def test_anonymous_post_is_401_and_leaves_no_row(fake_db):
    async def scenario():
        async with api.app.test_client() as client:
            res = await client.post("/api/logs", json=PAYLOAD_LINE_SAMPLE)
            assert res.status_code == 401

    _run(scenario())
    assert fake_db["inserts"] == []


def test_writer_post_inserts_one_pending_row(fake_db):
    async def scenario():
        async with api.app.test_client() as client:
            token = await _token(client, "technician", "tech123456")
            res = await client.post(
                "/api/logs", json=PAYLOAD_LINE_SAMPLE, headers=_bearer(token)
            )
            assert res.status_code == 201
            row = await res.get_json()
            assert row["status"] == "pending"
            assert row["turbine_code"] == "W12"
            assert row["yaw_err_deg"] == 1.5
            assert row["created_by"] == "technician"

    _run(scenario())
    assert len(fake_db["inserts"]) == 1
    params = fake_db["inserts"][0]
    assert params[0] == "W12"
    assert params[1] == 1.5
    assert params[2] == "technician"


def test_reader_can_still_read_logs(fake_db):
    async def scenario():
        async with api.app.test_client() as client:
            token = await _token(client, "observer", "obs123456")
            res = await client.get("/api/logs", headers=_bearer(token))
            assert res.status_code == 200

    _run(scenario())
    assert fake_db["inserts"] == []


def test_forged_writer_role_claim_is_still_denied(fake_db):
    # 自己用正确的 SECRET 签一个 sub=observer 但 role=writer 的 token
    forged = jwt.encode(
        {
            "sub": "observer",
            "role": "writer",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        api.SECRET,
        algorithm="HS256",
    )

    async def scenario():
        async with api.app.test_client() as client:
            res = await client.post(
                "/api/logs", json=PAYLOAD_LINE_SAMPLE, headers=_bearer(forged)
            )
            assert res.status_code == 403

    _run(scenario())
    assert fake_db["inserts"] == []


def test_writer_validation_failure_does_not_insert(fake_db):
    async def scenario():
        async with api.app.test_client() as client:
            token = await _token(client, "technician", "tech123456")
            res = await client.post(
                "/api/logs",
                json={"turbine_code": "  ", "yaw_err_deg": 1.5},
                headers=_bearer(token),
            )
            assert res.status_code == 400

    _run(scenario())
    assert fake_db["inserts"] == []


@pytest.mark.parametrize("err", [1.5, -1.5, 0.0])
def test_line_pressure_sample_passes_threshold(err):
    # 压线样：恰好落在 ±1.5° 阈值上应为「合格」，worker 据此写结论
    from rules import judge

    verdict, _ = judge(err)
    assert verdict == "合格"


@pytest.mark.parametrize("err", [1.6, -1.6])
def test_sample_over_threshold_fails(err):
    from rules import judge

    verdict, _ = judge(err)
    assert verdict == "偏航超差"
