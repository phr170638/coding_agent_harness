"""凭据安全存储 — keyring 跨平台封装。

API key 存入 OS 钥匙串（Windows Credential Manager / macOS Keychain /
Linux Secret Service），不落盘、不进入 Git、不在日志中回显。
"""

import keyring


class CredentialStore:
    """管理 API key 的安全存储，基于 keyring 库。"""

    def __init__(self, service_name: str = "myagent") -> None:
        self._service = service_name

    def set(self, key: str, value: str) -> None:
        """存储凭据到系统钥匙串。"""
        keyring.set_password(self._service, key, value)

    def get(self, key: str) -> str | None:
        """从系统钥匙串读取凭据，不存在时返回 None。"""
        return keyring.get_password(self._service, key)  # type: ignore[no-any-return]

    def delete(self, key: str) -> None:
        """从系统钥匙串删除凭据。"""
        try:
            keyring.delete_password(self._service, key)
        except keyring.errors.PasswordDeleteError:
            pass

    def exists(self, key: str) -> bool:
        """检查凭据是否已存储。"""
        return self.get(key) is not None
