"""Endpoint-bound secrets: memory or macOS Keychain, never plaintext fallback.

Security.framework's default trusted-application access controls bind new items to
this executable/application. macOS may prompt when an unsigned build is replaced.
No secret is passed through process arguments or environment variables.
"""
from __future__ import annotations
import ctypes
import hashlib
import sys
from .providers import normalize_endpoint

SERVICE = b'com.nocoolusername.VolatilityWorkbench.api'


class CredentialError(RuntimeError):
    pass


class MacKeychain:
    def __init__(self):
        if sys.platform != 'darwin':
            raise CredentialError('Keychain storage is available only on macOS; choose session-only storage')
        self.lib = ctypes.CDLL('/System/Library/Frameworks/Security.framework/Security')
        self.cf = ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
        self.cf.CFRelease.argtypes = [ctypes.c_void_p]
        self.lib.SecKeychainFindGenericPassword.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_char_p,
            ctypes.c_uint32, ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p)]
        self.lib.SecKeychainAddGenericPassword.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_char_p,
            ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        self.lib.SecKeychainItemModifyAttributesAndData.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]
        self.lib.SecKeychainItemFreeContent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        self.lib.SecKeychainItemDelete.argtypes = [ctypes.c_void_p]

    def _find(self, account):
        length, data, item = ctypes.c_uint32(), ctypes.c_void_p(), ctypes.c_void_p()
        status = self.lib.SecKeychainFindGenericPassword(None, len(SERVICE), SERVICE, len(account), account,
                                                       ctypes.byref(length), ctypes.byref(data), ctypes.byref(item))
        return status, length, data, item

    def get(self, account):
        status, length, data, item = self._find(account)
        if status == -25300:
            return None
        if status:
            raise CredentialError(f'macOS Keychain access failed ({status}); unlock/authorize the app or use a session-only secret')
        try:
            return ctypes.string_at(data, length.value).decode('utf-8')
        finally:
            self.lib.SecKeychainItemFreeContent(None, data)
            if item: self.cf.CFRelease(item)

    def put(self, account, secret):
        encoded = secret.encode()
        status, length, data, item = self._find(account)
        if status == 0:
            self.lib.SecKeychainItemFreeContent(None, data)
            try:
                status = self.lib.SecKeychainItemModifyAttributesAndData(item, None, len(encoded), ctypes.c_char_p(encoded))
            finally:
                self.cf.CFRelease(item)
        elif status == -25300:
            status = self.lib.SecKeychainAddGenericPassword(None, len(SERVICE), SERVICE, len(account), account,
                                                         len(encoded), ctypes.c_char_p(encoded), None)
        if status:
            raise CredentialError(f'macOS Keychain save failed ({status}); secret was not saved. Choose session-only storage if desired.')

    def delete(self, account):
        status, length, data, item = self._find(account)
        if status == -25300: return
        if status: raise CredentialError(f'macOS Keychain access failed ({status})')
        self.lib.SecKeychainItemFreeContent(None, data)
        try:
            status = self.lib.SecKeychainItemDelete(item)
            if status: raise CredentialError(f'macOS Keychain delete failed ({status})')
        finally:
            self.cf.CFRelease(item)


class CredentialStore:
    def __init__(self, keychain_factory=MacKeychain):
        self.sessions = {}
        self.keychain_factory = keychain_factory

    @staticmethod
    def account(endpoint):
        return hashlib.sha256(normalize_endpoint(endpoint).encode()).hexdigest().encode()

    def set(self, endpoint, secret, storage):
        account = self.account(endpoint)
        if not isinstance(secret, str) or not secret or len(secret) > 8192 or any(ord(c) < 32 for c in secret):
            raise CredentialError('Secret must be nonempty text under 8192 characters without control characters')
        if storage == 'session':
            self.sessions[account] = secret
        elif storage == 'keychain':
            self.keychain_factory().put(account, secret)
            self.sessions.pop(account, None)
        else:
            raise CredentialError('Choose session or keychain secret storage explicitly')

    def get(self, endpoint, storage):
        account = self.account(endpoint)
        if storage == 'session':
            secret = self.sessions.get(account)
            if not secret:
                raise CredentialError('Session-only credential is unavailable after restart; enter it again in Settings')
            return secret
        if storage == 'keychain':
            secret = self.keychain_factory().get(account)
            if not secret: raise CredentialError('Endpoint-bound credential was not found in macOS Keychain')
            return secret
        if storage == 'none': return None
        raise CredentialError('Unknown credential storage setting')

    def clear(self):
        self.sessions.clear()
