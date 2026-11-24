"""Targeted transfer checks; all CMS requests are mocked."""
import inspect
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pydantic import ValidationError
from test_plugin import MODULE, SEARCH, SYNC, TRANSFER, ROOT, fixture


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory(dir=ROOT / 'release-out')))
        self.settings = {'cms_url':'https://cms.example', 'cms_api_token':'fake-api-secret',
                         'cms_login_token':'fake-web-secret', 'cms_transfer_live':True}

    def prepare(self, live=True):
        manager = TRANSFER.TransferManager(TRANSFER.TransferConfig.from_settings(dict(self.settings, cms_transfer_live=live)), lambda:self.directory)
        data = SEARCH.normalize_results(fixture(), SEARCH.SearchRequest(keyword='测试剧'))
        data.items[1].password_conflict = True
        manager.add_tickets(data)
        self.assertIsNone(data.items[1].transfer_ticket)
        return manager, data.items[0]

    def payload(self, item, request_id='transfer-initial-0001', expected=None):
        return TRANSFER.TransferRequest(ticket=item.transfer_ticket, request_id=request_id, expected_attempt=expected)

    def test_default_dry_run_no_network_and_admin_credential_separation(self):
        manager, item = self.prepare(live=False)
        with patch.object(TRANSFER, '_request') as network:
            self.assertEqual('dry_run', manager.submit(self.payload(item))[0].status)
            network.assert_not_called()
        self.assertEqual([], list(self.directory.iterdir()))
        with self.assertRaises(ValidationError):
            TRANSFER.TransferRequest(ticket=item.transfer_ticket, request_id='transfer-initial-0001', url='https://evil.invalid')
        plugin = MODULE.MppgdonTest()
        plugin.get_data_path = lambda:self.directory
        plugin.init_plugin(dict(self.settings, enabled=True))
        status = plugin.get_status()
        self.assertEqual('live', status.data.transfer_mode)
        for secret in ('fake-api-secret', 'fake-web-secret'):
            self.assertNotIn(secret, status.model_dump_json())
        route = next(route for route in plugin.get_api() if route['path'] == '/transfer')
        self.assertEqual('bear', route['auth'])
        self.assertIs(MODULE.get_current_active_superuser, inspect.signature(route['endpoint']).parameters['_admin'].default)

    def test_exact_open_api_request_no_bearer_and_accepted_replay(self):
        manager, item = self.prepare()
        payload = self.payload(item)
        with patch.object(TRANSFER, '_request', return_value=(200, {'code':'200'})) as network:
            self.assertEqual('accepted', manager.submit(payload)[0].status)
            self.assertEqual('accepted', manager.submit(payload)[0].status)
            self.assertEqual('accepted', manager.submit(self.payload(item, 'transfer-next-click-0002'))[0].status)
            network.assert_called_once_with(manager.config, '/api/cloud/add_share_down_by_token', timeout=30,
                                            body={'url':item.url, 'token':'fake-api-secret'}, bearer=False)
        with patch.object(SYNC, 'build_opener') as builder:
            response = builder.return_value.open.return_value.__enter__.return_value
            response.status, response.read.return_value = 200, b'{"code":200}'
            SYNC._request(manager.config, '/api/cloud/add_share_down_by_token', timeout=30,
                          body={'url':item.url, 'token':manager.config.token}, bearer=False)
            request = builder.return_value.open.call_args.args[0]
            self.assertIsNone(request.get_header('Authorization'))
            self.assertEqual('fake-api-secret', json.loads(request.data)['token'])
        stored = (self.directory / 'cms-transfer.sqlite3').read_bytes()
        self.assertNotIn(b'fake-api-secret', stored)
        self.assertNotIn(item.url.encode(), stored)

    def test_unknown_survives_restart_and_rejected_retry_is_explicit(self):
        manager, item = self.prepare()
        with patch.object(TRANSFER, '_request', return_value=(0, {})):
            self.assertEqual('unknown', manager.submit(self.payload(item))[0].status)
        restored, fresh = self.prepare()
        with patch.object(TRANSFER, '_request') as network:
            self.assertEqual('unknown', restored.submit(self.payload(fresh, 'transfer-after-restart-0002'))[0].status)
            network.assert_not_called()
        # A different share exercises explicit rejection, replay and a user-confirmed retry.
        data = SEARCH.normalize_results(fixture(), SEARCH.SearchRequest(keyword='测试剧'))
        restored.add_tickets(data)
        rejected = data.items[-1]
        original = self.payload(rejected, 'transfer-rejected-0003')
        with patch.object(TRANSFER, '_request', side_effect=[(401, {}), (200, {'code':200})]) as network:
            self.assertTrue(restored.submit(original)[0].retryable)
            self.assertEqual('rejected', restored.submit(original)[0].status)
            no_confirmation = self.payload(rejected, 'transfer-no-confirm-0004')
            self.assertEqual('rejected', restored.submit(no_confirmation)[0].status)
            retry = self.payload(rejected, 'transfer-explicit-retry-0005', original.request_id)
            self.assertEqual('accepted', restored.submit(retry)[0].status)
            self.assertEqual(2, network.call_count)


if __name__ == '__main__':
    unittest.main()
