from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.db.models import Alarm, Motor, Reading
from app.services.alarms import apply_reading_alarms, evaluate_rules
from app.services.analysis import bucket_readings, daily_slope
from app.services.baseline import Baseline


def motor_stub() -> SimpleNamespace:
    return SimpleNamespace(
        code="M-01",
        name="测试电机",
        temp_limit_c=85.0,
        current_limit_a=252.0,
        temp_deviation_pct=8.0,
        current_deviation_pct=10.0,
        rise_rate_limit_c_per_day=1.0,
        notify_enabled=True,
    )


def baseline_stub() -> Baseline:
    return Baseline(
        temp_median=60.0,
        temp_p10=58.0,
        temp_p90=62.0,
        current_median=200.0,
        current_p10=195.0,
        current_p90=205.0,
        sample_count=100,
        temp_profile={},
    )


def test_evaluate_high_temperature():
    candidates = evaluate_rules(motor_stub(), 90.0, 200.0, baseline_stub(), None)
    keys = {candidate.rule_key for candidate in candidates}
    assert "temp_high" in keys
    assert "temp_deviation" not in keys
    high = next(candidate for candidate in candidates if candidate.rule_key == "temp_high")
    assert high.level == "crit"
    assert high.threshold == 85.0


def test_evaluate_deviation_and_current_high():
    candidates = evaluate_rules(motor_stub(), 67.0, 260.0, baseline_stub(), 1.5)
    keys = {candidate.rule_key for candidate in candidates}
    assert "temp_deviation" in keys
    assert "current_high" in keys
    assert "temp_rise" in keys


def test_evaluate_without_baseline():
    candidates = evaluate_rules(motor_stub(), 70.0, 200.0, None, None)
    assert candidates == []


def test_bucket_and_slope():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    readings = [
        Reading(
            motor_id=1,
            ts=start + timedelta(minutes=index * 15),
            temperature_c=60.0 + index * 0.25,
            current_avg_a=100.0,
            quality="ok",
        )
        for index in range(16)
    ]
    points = bucket_readings(readings, 60)
    assert len(points) == 4
    assert points[0]["temperature_c"] == 60.38
    slope, days = daily_slope(readings, min_days=1)
    assert days == 1
    assert slope == 0.0


def test_daily_slope_multiple_days():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    readings = []
    for day in range(5):
        for hour in (0, 8):
            readings.append(
                Reading(
                    motor_id=1,
                    ts=start + timedelta(days=day, hours=hour),
                    temperature_c=60.0 + day,
                    current_avg_a=100.0,
                    quality="ok",
                )
            )
    slope, days = daily_slope(readings, min_days=3)
    assert days == 5
    assert slope == 1.0


def test_alarm_dedup_and_auto_close(db):
    motor = Motor(code="T-01", name="测试电机", rated_current_a=100, temp_limit_c=85)
    db.add(motor)
    db.flush()
    reading = Reading(
        motor_id=motor.id,
        ts=datetime(2026, 1, 1, tzinfo=timezone.utc),
        temperature_c=70,
        current_avg_a=80,
        quality="ok",
    )
    db.add(reading)
    db.flush()

    config = {"owners": ["王工", "李工"], "critical_enabled": True, "warning_enabled": True}
    candidates = evaluate_rules(motor, 70.5, 80, baseline_stub(), None)
    assert len(candidates) == 1
    first = apply_reading_alarms(db, motor, reading, candidates, config, now=reading.ts)
    second = apply_reading_alarms(db, motor, reading, candidates, config, now=reading.ts)
    assert len(first) == 1
    assert second == []
    assert db.query(Alarm).filter(Alarm.motor_code == "T-01").count() == 1

    apply_reading_alarms(db, motor, reading, [], config, now=reading.ts)
    alarm = db.query(Alarm).filter(Alarm.motor_code == "T-01").one()
    assert alarm.status == "open"
    apply_reading_alarms(db, motor, reading, [], config, now=reading.ts)
    assert alarm.status == "closed"
    assert alarm.closed_by == "system"


def test_api_smoke(client, db):
    from app.db.models import Gateway, Sensor

    gateway = Gateway(code="GW-T", name="测试网关", host="127.0.0.1", port=502, enabled=True)
    motor = Motor(
        code="M-T1",
        name="API 测试电机",
        rated_current_a=200,
        rated_kw=110,
        temp_limit_c=85,
        current_limit_a=210,
        group_name="测试组",
    )
    db.add_all([gateway, motor])
    db.flush()
    db.add(
        Sensor(
            code="T-T1",
            motor_id=motor.id,
            gateway_id=gateway.id,
            kind="temperature",
            enabled=True,
            register_count=1,
            scale=0.1,
            unit="℃",
        )
    )
    db.add(
        Reading(
            motor_id=motor.id,
            ts=datetime.now(timezone.utc),
            temperature_c=65.0,
            current_avg_a=150.0,
            current_a=150.0,
            current_b=150.0,
            current_c=150.0,
            quality="ok",
        )
    )
    db.commit()

    response = client.get("/api/v1/dashboard/overview")
    assert response.status_code == 200
    assert response.json()["kpis"]["total_motors"] >= 1

    response = client.get("/api/v1/motors")
    assert response.status_code == 200
    assert any(item["code"] == "M-T1" for item in response.json()["items"])

    response = client.patch(
        "/api/v1/motors/M-T1/thresholds",
        json={"temp_limit_c": 80, "temp_deviation_pct": 6},
    )
    assert response.status_code == 200
    assert response.json()["temp_limit_c"] == 80

    response = client.get("/api/v1/analysis/self", params={"motor_id": "M-T1"})
    assert response.status_code == 200
    assert response.json()["motor"]["code"] == "M-T1"

    response = client.get("/api/v1/system/info")
    assert response.status_code == 200
    assert response.json()["counts"]["sensors"] >= 1


def test_manual_close_suppresses_regeneration(db):
    motor = Motor(code="T-SUP", name="抑制测试电机", rated_current_a=100, temp_limit_c=85)
    db.add(motor)
    db.flush()
    reading = Reading(
        motor_id=motor.id,
        ts=datetime(2026, 1, 2, tzinfo=timezone.utc),
        temperature_c=70,
        current_avg_a=80,
        quality="ok",
    )
    db.add(reading)
    db.flush()
    config = {"owners": ["王工"], "critical_enabled": True, "warning_enabled": True}
    candidates = evaluate_rules(motor, 70.5, 80, baseline_stub(), None)
    alarms = apply_reading_alarms(db, motor, reading, candidates, config, now=reading.ts)
    assert len(alarms) == 1
    alarms[0].status = "closed"
    alarms[0].suppressed_until = reading.ts + timedelta(minutes=30)
    db.flush()
    again = apply_reading_alarms(db, motor, reading, candidates, config, now=reading.ts)
    assert again == []
    assert db.query(Alarm).filter(Alarm.motor_code == "T-SUP").count() == 1


def test_historical_overview_and_motor_series(client, db):
    from app.core.time import local_now
    from app.db.models import Reading
    from app.services.date_view import resolve_date_view

    target_date = (local_now().date() - timedelta(days=1)).isoformat()
    view = resolve_date_view(target_date)
    motor = Motor(
        code="M-DATE",
        name="历史测试电机",
        rated_current_a=100,
        temp_limit_c=85,
        current_limit_a=105,
        group_name="历史组",
    )
    db.add(motor)
    db.flush()
    db.add(
        Reading(
            motor_id=motor.id,
            ts=view.day_start + timedelta(hours=12),
            temperature_c=61.5,
            current_avg_a=80.0,
            quality="ok",
        )
    )
    db.commit()

    response = client.get(f"/api/v1/dashboard/overview?date={target_date}")
    assert response.status_code == 200
    body = response.json()
    assert body["is_today"] is False
    assert body["date"] == target_date
    historical_motor = next(item for item in body["motors"] if item["code"] == "M-DATE")
    assert historical_motor["temperature_c"] == 61.5

    response = client.get(f"/api/v1/motors/M-DATE?date={target_date}")
    assert response.status_code == 200
    assert response.json()["motor"]["temperature_c"] == 61.5

    response = client.get(f"/api/v1/motors/M-DATE/series?range=24h&date={target_date}")
    assert response.status_code == 200
    assert response.json()["is_today"] is False
    assert len(response.json()["points"]) >= 1


def test_device_config_api(client, db):
    response = client.post(
        "/api/v1/devices/gateways",
        json={
            "code": "GW-CFG",
            "name": "配置测试网关",
            "host": "127.0.0.1",
            "port": 15020,
            "framer": "tcp",
            "enabled": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["created"] is True

    response = client.post(
        "/api/v1/motors",
        json={
            "code": "M-CFG",
            "name": "配置测试电机",
            "group_name": "配置组",
            "rated_current_a": 120,
            "temp_limit_c": 80,
            "current_limit_a": 126,
        },
    )
    assert response.status_code == 200
    assert response.json()["created"] is True

    response = client.post(
        "/api/v1/devices/sensors",
        json={
            "motor_code": "M-CFG",
            "gateway_code": "GW-CFG",
            "kind": "temperature",
            "slave_id": 21,
            "register_address": 0,
            "register_count": 1,
            "scale": 0.1,
            "unit": "℃",
        },
    )
    assert response.status_code == 200
    sensor_id = response.json()["sensor"]["id"]
    assert response.json()["sensor"]["code"].startswith("T-")
    assert response.json()["sensor"]["motor_code"] == "M-CFG"

    response = client.get("/api/v1/devices")
    assert response.status_code == 200
    assert any(
        item["motor_code"] == "M-CFG" and item["gateway_code"] == "GW-CFG"
        for item in response.json()["sensors"]
    )

    response = client.delete(f"/api/v1/devices/sensors/{sensor_id}")
    assert response.status_code == 200
    assert response.json()["deleted"] is True

    response = client.delete("/api/v1/devices/gateways/GW-CFG")
    assert response.status_code == 200
    assert response.json()["deleted"] is True


def test_unit_id_kwargs_supports_pymodbus_versions():
    from app.services.modbus import unit_id_kwargs

    def old_api(address: int, *, count: int = 1, slave: int = 1):
        return address, count, slave

    def new_api(address: int, *, count: int = 1, device_id: int = 1):
        return address, count, device_id

    assert unit_id_kwargs(old_api, 3) == {"slave": 3}
    assert unit_id_kwargs(new_api, 3) == {"device_id": 3}


def test_three_phase_current_high_and_imbalance():
    motor = motor_stub()
    motor.current_limit_a = 105.0
    motor.phase_imbalance_pct = 10.0

    normal = evaluate_rules(
        motor, None, 100.0, None, None, current_a=100.0, current_b=101.0, current_c=99.0
    )
    assert {item.rule_key for item in normal} == set()

    abnormal = evaluate_rules(
        motor, None, 98.3, None, None, current_a=110.0, current_b=90.0, current_c=95.0
    )
    keys = {item.rule_key for item in abnormal}
    assert "current_high" in keys
    assert "current_imbalance" in keys
    imbalance = next(item for item in abnormal if item.rule_key == "current_imbalance")
    assert imbalance.value > 10
    assert imbalance.level in ("warn", "crit")

    severe = evaluate_rules(
        motor, None, 100.0, None, None, current_a=130.0, current_b=80.0, current_c=90.0
    )
    severe_imbalance = next(item for item in severe if item.rule_key == "current_imbalance")
    assert severe_imbalance.level == "crit"


def test_vibration_parse_and_rule():
    from app.services.modbus import SensorPlan, _parse

    sensor = SensorPlan(
        id=1,
        code="V-01",
        motor_id=1,
        motor_code="M-01",
        motor_name="测试电机",
        gateway_id=1,
        gateway_code="GW-01",
        kind="vibration",
        slave_id=1,
        register_address=1,
        register_count=3,
        scale=0.1,
        unit="mm/s",
    )
    values = _parse(sensor, [15, 20, 25])
    assert values["vibration_x"] == 1.5
    assert values["vibration_total_mm_s"] == 3.536

    motor = motor_stub()
    motor.vibration_limit_mm_s = 4.5
    candidates = evaluate_rules(
        motor,
        None,
        100.0,
        None,
        None,
        vibration_total_mm_s=5.2,
        vibration_x=3.0,
        vibration_y=3.5,
        vibration_z=2.2,
    )
    hit = next(item for item in candidates if item.rule_key == "vibration_high")
    assert hit.level == "crit"
    assert hit.threshold == 4.5


def test_overview_and_peer_include_vibration(client, db):
    motor = Motor(
        code="V-01",
        name="振动测试电机",
        group_name="振动测试组",
        rated_current_a=100,
        current_limit_a=120,
        temp_limit_c=85,
        enabled=True,
    )
    db.add(motor)
    db.flush()
    now = datetime.now(timezone.utc)
    db.add(
        Reading(
            motor_id=motor.id,
            ts=now,
            temperature_c=62.0,
            current_a=81.0,
            current_b=82.0,
            current_c=83.0,
            current_avg_a=82.0,
            vibration_x=1.2,
            vibration_y=2.0,
            vibration_z=3.3,
            vibration_total_mm_s=4.05,
            quality="ok",
        )
    )
    db.commit()

    overview = client.get("/api/v1/dashboard/overview").json()
    card = next(item for item in overview["motors"] if item["code"] == "V-01")
    assert card["vibration_total_mm_s"] == 4.05
    assert card["current_b"] == 82.0

    peers = client.get("/api/v1/analysis/peers", params={"group": "振动测试组"}).json()
    peer = next(item for item in peers["motors"] if item["code"] == "V-01")
    assert peer["vibration_total_mm_s"] == 4.05
    assert peer["vibration_limit_mm_s"] == 4.5


def test_feishu_card_buttons_and_callback(db):
    from app.services.feishu_app import apply_card_action, build_alarm_card

    alarm = Alarm(
        level="crit",
        rule_key="vibration_high",
        title="振动速度越限",
        motor_code="V-02",
        motor_name="回调测试电机",
        value=5.2,
        threshold=4.5,
        unit="mm/s",
        status="open",
        owner="王工",
        triggered_at=datetime.now(timezone.utc),
    )
    db.add(alarm)
    db.commit()

    card = build_alarm_card(alarm, "img_test")
    actions = next(item for item in card["elements"] if item["tag"] == "action")
    values = {button["value"]["resolution"]: button["value"]["alarm_id"] for button in actions["actions"]}
    assert values == {"resolved": alarm.id, "unresolved": alarm.id}
    assert any(item["tag"] == "img" for item in card["elements"])

    message = apply_card_action(alarm.id, "unresolved", "ou_test")
    db.expire_all()
    current = db.get(Alarm, alarm.id)
    assert current.status == "ack"
    assert "未解决" in message

    message = apply_card_action(alarm.id, "resolved", "ou_test")
    db.expire_all()
    current = db.get(Alarm, alarm.id)
    assert current.status == "closed"
    assert current.closed_by == "飞书:ou_test"
    assert current.suppressed_until is not None
    assert "已解决" in message


def test_feishu_long_connection_signature():
    from app.services.feishu_longconn import FeishuLongConnection

    connection = FeishuLongConnection({"app_id": "cli_test", "app_secret": "secret-a"})
    assert connection.matches({"app_id": "cli_test", "app_secret": "secret-a"})
    assert not connection.matches({"app_id": "cli_test", "app_secret": "secret-b"})


def test_snapshot_render_png():
    from app.services.snapshot import render_alarm_snapshot

    motor = Motor(
        code="M-09",
        name="快照测试电机",
        temp_limit_c=85,
        current_limit_a=252,
        vibration_limit_mm_s=4.5,
    )
    reading = Reading(
        motor_id=1,
        ts=datetime.now(timezone.utc),
        temperature_c=89.2,
        current_a=231.0,
        current_b=228.0,
        current_c=235.0,
        current_avg_a=231.3,
        vibration_x=2.1,
        vibration_y=2.4,
        vibration_z=3.0,
        vibration_total_mm_s=4.35,
        quality="ok",
    )
    png = render_alarm_snapshot(motor, reading, [reading], reading.ts)
    assert png.startswith(b"\x89PNG")
    assert len(png) > 1000


def test_feishu_app_settings_masks_secret(client):
    response = client.put(
        "/api/v1/settings/feishu",
        json={
            "enabled": False,
            "app_id": "cli_smoke",
            "app_secret": "super-secret-value",
            "chat_id": "oc_smoke",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["secret_set"] is True
    assert "super-secret-value" not in response.text
    assert body["enabled"] is False

    fetched = client.get("/api/v1/settings/feishu")
    assert fetched.status_code == 200
    assert fetched.json()["app_id"] == "cli_smoke"
    assert "super-secret-value" not in fetched.text
