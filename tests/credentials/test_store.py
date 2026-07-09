"""凭据存储测试 — keyring 封装层的 set/get/delete/exists。"""

import pytest

from myagent.credentials.store import CredentialStore


class TestCredentialStore:
    """CredentialStore 的确定性单元测试（mock keyring backend）。"""

    def test_set_and_get(self, mocker):
        mock_set = mocker.patch("keyring.set_password")
        mock_get = mocker.patch("keyring.get_password", return_value="sk-test-key")

        store = CredentialStore()
        store.set("api_key", "sk-test-key")

        mock_set.assert_called_once()
        assert store.get("api_key") == "sk-test-key"
        mock_get.assert_called_once()

    def test_get_nonexistent_key(self, mocker):
        mocker.patch("keyring.get_password", return_value=None)

        store = CredentialStore()
        assert store.get("nonexistent") is None

    def test_delete(self, mocker):
        mock_delete = mocker.patch("keyring.delete_password")
        mocker.patch("keyring.get_password", return_value=None)

        store = CredentialStore()
        store.delete("api_key")

        mock_delete.assert_called_once()
        assert store.get("api_key") is None

    def test_exists(self, mocker):
        mocker.patch("keyring.get_password", return_value="sk-test")

        store = CredentialStore()
        assert store.exists("api_key") is True

    def test_exists_false(self, mocker):
        mocker.patch("keyring.get_password", return_value=None)

        store = CredentialStore()
        assert store.exists("api_key") is False

    def test_service_name_isolation(self, mocker):
        """不同 service_name 的 key 互不干扰。"""
        mock_get = mocker.patch("keyring.get_password")
        mock_set = mocker.patch("keyring.set_password")

        store_a = CredentialStore(service_name="myagent_a")
        store_b = CredentialStore(service_name="myagent_b")

        store_a.set("key1", "value_a")
        store_b.set("key1", "value_b")

        set_calls = mock_set.call_args_list
        assert set_calls[0][0][0] == "myagent_a"
        assert set_calls[1][0][0] == "myagent_b"
