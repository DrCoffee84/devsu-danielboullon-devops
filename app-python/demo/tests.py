from unittest import mock

from django.db import OperationalError
from django.test import TestCase


class HealthCheckTests(TestCase):
    def test_healthz(self):
        response = self.client.get('/healthz')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})

    def test_healthz_accepts_any_host(self):
        # El kubelet manda la IP del pod como Host.
        response = self.client.get('/healthz', HTTP_HOST='10.1.0.15:8000')
        self.assertEqual(response.status_code, 200)

    def test_readyz(self):
        response = self.client.get('/readyz')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})

    def test_readyz_db_down(self):
        with mock.patch('demo.health.connection') as conn:
            conn.cursor.side_effect = OperationalError('db down')
            response = self.client.get('/readyz')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {'status': 'unavailable'})

    def test_unknown_host_rejected(self):
        response = self.client.get('/api/users/', HTTP_HOST='evil.example.com')
        self.assertEqual(response.status_code, 400)
