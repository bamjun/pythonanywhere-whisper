from datetime import datetime

import pytest
from django.test import Client


def test_health_check(client: Client) -> None:
    # Given: 클라이언트가 준비되었을 때

    # When: /api/health 엔드포인트로 GET 요청을 보내면
    response = client.get("/api/health")

    # Then: 상태 코드가 200이어야 함
    assert response.status_code == 200

    # And: 응답 데이터가 예상한 형식을 가져야 함
    data = response.json()
    assert "status" in data
    assert "timestamp" in data
    assert data["status"] == "ok"

    # And: timestamp가 ISO 형식의 유효한 날짜여야 함
    try:
        datetime.fromisoformat(data["timestamp"])
    except ValueError:
        pytest.fail("Timestamp is not in valid ISO format")


def test_health_check_timestamp_timezone(client: Client) -> None:
    # Given: 클라이언트가 준비되었을 때

    # When: /api/health 엔드포인트로 GET 요청을 보내면
    response = client.get("/api/health")

    # Then: 응답의 timestamp가 현재 시간과 크게 차이나지 않아야 함
    data = response.json()
    response_time = datetime.fromisoformat(data["timestamp"]).replace(tzinfo=None)
    current_time = datetime.now()  # timezone naive
    time_difference = abs((current_time - response_time).total_seconds())

    assert time_difference < 5  # 5초 이내의 차이만 허용
