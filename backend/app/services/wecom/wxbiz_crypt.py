"""企业微信回调 URL 验证与消息加解密（WXBizMsgCrypt 协议）"""

from __future__ import annotations

import base64
import hashlib
import socket
import struct
from xml.etree import ElementTree as ET

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

OK = 0
ValidateSignature_Error = -40001
ParseXml_Error = -40002
IllegalAesKey = -40004
ValidateCorpid_Error = -40005
DecryptAES_Error = -40007
IllegalBuffer = -40008


class _PKCS7Encoder:
    block_size = 32

    @classmethod
    def decode(cls, decrypted: bytes) -> bytes:
        pad = decrypted[-1]
        if pad < 1 or pad > cls.block_size:
            return decrypted
        return decrypted[:-pad]


def _decode_aes_key(encoding_aes_key: str) -> bytes:
    s = encoding_aes_key.strip()
    pad = (4 - len(s) % 4) % 4
    return base64.b64decode(s + "=" * pad)


class WXBizMsgCrypt:
    def __init__(self, token: str, encoding_aes_key: str, receive_id: str):
        try:
            self.key = _decode_aes_key(encoding_aes_key)
            if len(self.key) != 32:
                raise ValueError("invalid aes key length")
        except Exception as exc:
            raise ValueError("EncodingAESKey invalid") from exc
        self.token = token
        self.receive_id = receive_id

    def _sha1_signature(self, timestamp: str, nonce: str, encrypt: str) -> str:
        items = sorted([self.token, timestamp, nonce, encrypt])
        return hashlib.sha1("".join(items).encode("utf-8")).hexdigest()

    def _decrypt(self, text: str) -> tuple[int, str | None]:
        try:
            cipher = Cipher(algorithms.AES(self.key), modes.CBC(self.key[:16]))
            decryptor = cipher.decryptor()
            plain = decryptor.update(base64.b64decode(text)) + decryptor.finalize()
        except Exception:
            return DecryptAES_Error, None
        try:
            plain = _PKCS7Encoder.decode(plain)
            content = plain[16:]
            xml_len = socket.ntohl(struct.unpack("I", content[:4])[0])
            msg = content[4 : xml_len + 4].decode("utf-8")
            from_receive_id = content[xml_len + 4 :].decode("utf-8")
        except Exception:
            return IllegalBuffer, None
        if from_receive_id != self.receive_id:
            return ValidateCorpid_Error, None
        return OK, msg

    def verify_url(
        self,
        msg_signature: str,
        timestamp: str,
        nonce: str,
        echostr: str,
    ) -> tuple[int, str | None]:
        signature = self._sha1_signature(timestamp, nonce, echostr)
        if signature != msg_signature:
            return ValidateSignature_Error, None
        return self._decrypt(echostr)

    def decrypt_msg(
        self,
        post_data: str,
        msg_signature: str,
        timestamp: str,
        nonce: str,
    ) -> tuple[int, str | None]:
        try:
            root = ET.fromstring(post_data)
            encrypt = root.findtext("Encrypt") or ""
        except Exception:
            return ParseXml_Error, None
        if not encrypt:
            return ParseXml_Error, None
        signature = self._sha1_signature(timestamp, nonce, encrypt)
        if signature != msg_signature:
            return ValidateSignature_Error, None
        return self._decrypt(encrypt)
