"""Tests for health / root endpoints."""

import pytest


class TestHealth:
    def test_root(self, client):
        r = client.get("/")
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "ok"

    def test_api_root(self, client):
        r = client.get("/api/")
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "ok"

    def test_api_health(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "ok"
        assert data.get("database") == "ok"

    def test_root_service_name(self, client):
        r = client.get("/")
        assert "service" in r.json()

    def test_api_health_service_name(self, client):
        r = client.get("/api/health")
        assert "service" in r.json()
