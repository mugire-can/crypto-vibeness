"""
Unit tests for all cryptographic modules across Jour 2, 3, and 4.

Run with:
    pytest tests/ -v
"""

import os
import sys
import pytest

# ---------------------------------------------------------------------------
# Jour 2 / Jour 3 symmetric utilities (same module, same tests)
# ---------------------------------------------------------------------------

@pytest.fixture(params=['jour2_crypto', 'jour3_asymmetric'])
def sym_module(request):
    """Import crypto_utils from the requested day directory."""
    pkg = request.param
    path = os.path.join(os.path.dirname(__file__), '..', pkg)
    sys.path.insert(0, path)
    import importlib
    mod = importlib.import_module('crypto_utils')
    yield mod
    sys.path.remove(path)
    sys.modules.pop('crypto_utils', None)


class TestKeyDerivation:
    def test_derive_returns_32_byte_key(self, sym_module):
        key, salt = sym_module.derive_key_from_password('secret')
        assert len(key) == 32
        assert len(salt) == 16

    def test_same_password_and_salt_produces_same_key(self, sym_module):
        key1, salt = sym_module.derive_key_from_password('mypassword')
        key2, _ = sym_module.derive_key_from_password('mypassword', salt)
        assert key1 == key2

    def test_different_salts_produce_different_keys(self, sym_module):
        key1, _ = sym_module.derive_key_from_password('mypassword')
        key2, _ = sym_module.derive_key_from_password('mypassword')
        assert key1 != key2

    def test_different_passwords_produce_different_keys(self, sym_module):
        key1, salt = sym_module.derive_key_from_password('password1')
        key2, _ = sym_module.derive_key_from_password('password2', salt)
        assert key1 != key2


class TestAESCBC:
    def test_encrypt_decrypt_roundtrip(self, sym_module):
        key, _ = sym_module.derive_key_from_password('test')
        plaintext = 'Hello, World!'
        ct, iv = sym_module.encrypt_message(plaintext, key)
        assert sym_module.decrypt_message(ct, iv, key) == plaintext

    def test_encrypt_returns_bytes(self, sym_module):
        key = os.urandom(32)
        ct, iv = sym_module.encrypt_message('hello', key)
        assert isinstance(ct, bytes)
        assert isinstance(iv, bytes)
        assert len(iv) == 16

    def test_ciphertext_differs_from_plaintext(self, sym_module):
        key = os.urandom(32)
        plaintext = 'secret message'
        ct, _ = sym_module.encrypt_message(plaintext, key)
        assert plaintext.encode() not in ct

    def test_wrong_key_raises(self, sym_module):
        key1 = os.urandom(32)
        key2 = os.urandom(32)
        ct, iv = sym_module.encrypt_message('hello', key1)
        with pytest.raises(ValueError):
            sym_module.decrypt_message(ct, iv, key2)

    def test_tampered_ciphertext_raises(self, sym_module):
        key = os.urandom(32)
        ct, iv = sym_module.encrypt_message('hello', key)
        tampered = bytes([ct[0] ^ 0xFF]) + ct[1:]
        with pytest.raises(ValueError):
            sym_module.decrypt_message(tampered, iv, key)

    def test_empty_plaintext(self, sym_module):
        key = os.urandom(32)
        ct, iv = sym_module.encrypt_message('', key)
        assert sym_module.decrypt_message(ct, iv, key) == ''

    def test_unicode_plaintext(self, sym_module):
        key = os.urandom(32)
        text = 'Bonjour \U0001f30d'
        ct, iv = sym_module.encrypt_message(text, key)
        assert sym_module.decrypt_message(ct, iv, key) == text

    def test_invalid_key_length_raises(self, sym_module):
        with pytest.raises(ValueError):
            sym_module.encrypt_message('hello', b'tooshort')

    def test_bytes_plaintext_raises(self, sym_module):
        key = os.urandom(32)
        with pytest.raises((AttributeError, TypeError)):
            sym_module.encrypt_message(b'bytes input', key)


class TestAESGCM:
    def test_encrypt_decrypt_roundtrip(self, sym_module):
        key = os.urandom(32)
        plaintext = 'Hello GCM!'
        ct_tag, nonce = sym_module.encrypt_message_gcm(plaintext, key)
        assert sym_module.decrypt_message_gcm(ct_tag, nonce, key) == plaintext

    def test_nonce_is_12_bytes(self, sym_module):
        key = os.urandom(32)
        _, nonce = sym_module.encrypt_message_gcm('hello', key)
        assert len(nonce) == 12

    def test_tampered_tag_raises(self, sym_module):
        key = os.urandom(32)
        ct_tag, nonce = sym_module.encrypt_message_gcm('hello', key)
        tampered = ct_tag[:-1] + bytes([ct_tag[-1] ^ 0xFF])
        with pytest.raises(ValueError):
            sym_module.decrypt_message_gcm(tampered, nonce, key)

    def test_empty_plaintext(self, sym_module):
        key = os.urandom(32)
        ct_tag, nonce = sym_module.encrypt_message_gcm('', key)
        assert sym_module.decrypt_message_gcm(ct_tag, nonce, key) == ''

    def test_unicode(self, sym_module):
        key = os.urandom(32)
        text = 'test \U0001f510'
        ct_tag, nonce = sym_module.encrypt_message_gcm(text, key)
        assert sym_module.decrypt_message_gcm(ct_tag, nonce, key) == text


class TestTransmissionHelpers:
    def test_encode_decode_cbc(self, sym_module):
        key = os.urandom(32)
        ct, iv = sym_module.encrypt_message('test', key)
        encoded = sym_module.encode_for_transmission(ct, iv)
        assert ':' in encoded
        ct2, iv2 = sym_module.decode_from_transmission(encoded)
        assert ct2 == ct and iv2 == iv

    def test_encode_decode_gcm(self, sym_module):
        key = os.urandom(32)
        ct_tag, nonce = sym_module.encrypt_message_gcm('test', key)
        encoded = sym_module.encode_for_transmission(ct_tag, nonce)
        ct2, n2 = sym_module.decode_from_transmission(encoded)
        assert ct2 == ct_tag and n2 == nonce

    def test_invalid_format_raises(self, sym_module):
        with pytest.raises(ValueError):
            sym_module.decode_from_transmission('not_valid_format')


# ---------------------------------------------------------------------------
# Jour 3 RSA utilities
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def rsa_module():
    path = os.path.join(os.path.dirname(__file__), '..', 'jour3_asymmetric')
    sys.path.insert(0, path)
    import importlib
    mod = importlib.import_module('crypto_rsa')
    yield mod
    sys.path.remove(path)
    sys.modules.pop('crypto_rsa', None)


class TestRSA:
    def test_keypair_generation(self, rsa_module):
        priv, pub = rsa_module.generate_rsa_keypair()
        assert priv is not None
        assert pub is not None

    def test_encrypt_decrypt_roundtrip(self, rsa_module):
        priv, pub = rsa_module.generate_rsa_keypair()
        plaintext = b'supersecret_session_key_32bytes!'
        ciphertext = rsa_module.encrypt_with_public_key(plaintext, pub)
        assert rsa_module.decrypt_with_private_key(ciphertext, priv) == plaintext

    def test_sign_verify(self, rsa_module):
        priv, pub = rsa_module.generate_rsa_keypair()
        message = b'This is a test message.'
        sig = rsa_module.sign_message(message, priv)
        assert rsa_module.verify_signature(message, sig, pub) is True

    def test_tampered_message_fails_verification(self, rsa_module):
        priv, pub = rsa_module.generate_rsa_keypair()
        sig = rsa_module.sign_message(b'original', priv)
        assert rsa_module.verify_signature(b'tampered', sig, pub) is False

    def test_public_key_pem_roundtrip(self, rsa_module):
        _, pub = rsa_module.generate_rsa_keypair()
        pem = rsa_module.public_key_to_pem(pub)
        pub2 = rsa_module.pem_to_public_key(pem)
        assert rsa_module.public_key_to_pem(pub2) == pem

    def test_wrong_private_key_raises(self, rsa_module):
        priv1, pub1 = rsa_module.generate_rsa_keypair()
        priv2, _ = rsa_module.generate_rsa_keypair()
        ct = rsa_module.encrypt_with_public_key(b'secret', pub1)
        with pytest.raises(Exception):
            rsa_module.decrypt_with_private_key(ct, priv2)

    def test_save_load_keys(self, rsa_module, tmp_path):
        priv, pub = rsa_module.generate_rsa_keypair()
        priv_path = str(tmp_path / 'test.priv')
        pub_path = str(tmp_path / 'test.pub')
        rsa_module.save_private_key(priv, priv_path)
        rsa_module.save_public_key(pub, pub_path)
        priv2 = rsa_module.load_private_key(priv_path)
        pub2 = rsa_module.load_public_key(pub_path)
        ct = rsa_module.encrypt_with_public_key(b'hello', pub2)
        assert rsa_module.decrypt_with_private_key(ct, priv2) == b'hello'


# ---------------------------------------------------------------------------
# Jour 4 ECDH utilities
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def ecdh_module():
    path = os.path.join(os.path.dirname(__file__), '..', 'jour4_ecdh')
    sys.path.insert(0, path)
    import importlib
    mod = importlib.import_module('crypto_ecdh')
    yield mod
    sys.path.remove(path)
    sys.modules.pop('crypto_ecdh', None)


class TestECDH:
    def test_shared_secret_matches(self, ecdh_module):
        priv_a, pub_a = ecdh_module.generate_x25519_keypair()
        priv_b, pub_b = ecdh_module.generate_x25519_keypair()
        key_a = ecdh_module.ecdh_derive_session_key(priv_a, pub_b)
        key_b = ecdh_module.ecdh_derive_session_key(priv_b, pub_a)
        assert key_a == key_b

    def test_session_key_is_32_bytes(self, ecdh_module):
        priv_a, pub_a = ecdh_module.generate_x25519_keypair()
        priv_b, pub_b = ecdh_module.generate_x25519_keypair()
        key = ecdh_module.ecdh_derive_session_key(priv_a, pub_b)
        assert len(key) == 32

    def test_different_pairs_produce_different_keys(self, ecdh_module):
        priv_a, pub_a = ecdh_module.generate_x25519_keypair()
        priv_b, pub_b = ecdh_module.generate_x25519_keypair()
        priv_c, pub_c = ecdh_module.generate_x25519_keypair()
        key_ab = ecdh_module.ecdh_derive_session_key(priv_a, pub_b)
        key_ac = ecdh_module.ecdh_derive_session_key(priv_a, pub_c)
        assert key_ab != key_ac

    def test_public_key_bytes_roundtrip(self, ecdh_module):
        _, pub = ecdh_module.generate_x25519_keypair()
        raw = ecdh_module.x25519_public_key_to_bytes(pub)
        assert len(raw) == 32
        pub2 = ecdh_module.x25519_public_key_from_bytes(raw)
        assert ecdh_module.x25519_public_key_to_bytes(pub2) == raw


class TestECDSA:
    def test_sign_verify(self, ecdh_module):
        priv, pub = ecdh_module.generate_ecdsa_keypair()
        msg = b'authenticate me'
        sig = ecdh_module.ecdsa_sign(msg, priv)
        assert ecdh_module.ecdsa_verify(msg, sig, pub) is True

    def test_tampered_message_fails(self, ecdh_module):
        priv, pub = ecdh_module.generate_ecdsa_keypair()
        sig = ecdh_module.ecdsa_sign(b'original', priv)
        assert ecdh_module.ecdsa_verify(b'modified', sig, pub) is False

    def test_pem_roundtrip(self, ecdh_module):
        _, pub = ecdh_module.generate_ecdsa_keypair()
        pem = ecdh_module.ecdsa_public_key_to_pem(pub)
        pub2 = ecdh_module.ecdsa_public_key_from_pem(pem)
        assert ecdh_module.ecdsa_public_key_to_pem(pub2) == pem


class TestAESGCMJour4:
    def test_encrypt_decrypt_roundtrip(self, ecdh_module):
        key = os.urandom(32)
        ct_tag, nonce = ecdh_module.aes_gcm_encrypt('test message', key)
        assert ecdh_module.aes_gcm_decrypt(ct_tag, nonce, key) == 'test message'

    def test_wrong_key_raises(self, ecdh_module):
        key1 = os.urandom(32)
        key2 = os.urandom(32)
        ct_tag, nonce = ecdh_module.aes_gcm_encrypt('hello', key1)
        with pytest.raises(ValueError):
            ecdh_module.aes_gcm_decrypt(ct_tag, nonce, key2)

    def test_nonce_size(self, ecdh_module):
        key = os.urandom(32)
        _, nonce = ecdh_module.aes_gcm_encrypt('x', key)
        assert len(nonce) == 12

    def test_transmission_helpers(self, ecdh_module):
        key = os.urandom(32)
        ct_tag, nonce = ecdh_module.aes_gcm_encrypt('roundtrip', key)
        encoded = ecdh_module.encode_for_transmission(ct_tag, nonce)
        ct2, nonce2 = ecdh_module.decode_from_transmission(encoded)
        assert ct2 == ct_tag and nonce2 == nonce


class TestEndToEnd:
    """Integration: full ECDH key exchange + AES-GCM encrypt + ECDSA sign → verify."""

    def test_full_ecdh_e2ee_flow(self, ecdh_module):
        # Alice and Bob generate long-term ECDH keypairs
        alice_ecdh_priv, alice_ecdh_pub = ecdh_module.generate_x25519_keypair()
        bob_ecdh_priv, bob_ecdh_pub = ecdh_module.generate_x25519_keypair()
        alice_ecdsa_priv, alice_ecdsa_pub = ecdh_module.generate_ecdsa_keypair()

        # Alice generates a fresh ephemeral X25519 keypair for PFS
        alice_eph_priv, alice_eph_pub = ecdh_module.generate_x25519_keypair()

        # Key agreement
        session_key_alice = ecdh_module.ecdh_derive_session_key(alice_eph_priv, bob_ecdh_pub)
        session_key_bob = ecdh_module.ecdh_derive_session_key(bob_ecdh_priv, alice_eph_pub)
        assert session_key_alice == session_key_bob

        message = "Hello Bob, this is secret!"

        # Alice encrypts and signs
        ct_tag, nonce = ecdh_module.aes_gcm_encrypt(message, session_key_alice)
        signature = ecdh_module.ecdsa_sign(message.encode(), alice_ecdsa_priv)

        # Bob decrypts and verifies
        encoded = ecdh_module.encode_for_transmission(ct_tag, nonce)
        ct2, n2 = ecdh_module.decode_from_transmission(encoded)
        decrypted = ecdh_module.aes_gcm_decrypt(ct2, n2, session_key_bob)

        assert decrypted == message
        assert ecdh_module.ecdsa_verify(message.encode(), signature, alice_ecdsa_pub)
