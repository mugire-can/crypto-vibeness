"""Unit tests for unified crypto_utils (61 total)."""
import os, sys, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import crypto_utils

class TestKeyDerivation:
    def test_derive_returns_32_byte_key(self): 
        key, salt = crypto_utils.derive_key_pbkdf2('s')
        assert len(key) == 32 and len(salt) == 16
    def test_same_password_and_salt_produces_same_key(self):
        key1, salt = crypto_utils.derive_key_pbkdf2('p')
        key2, _ = crypto_utils.derive_key_pbkdf2('p', salt)
        assert key1 == key2 
    def test_different_salts_produce_different_keys(self):
        key1, _ = crypto_utils.derive_key_pbkdf2('p')
        key2, _ = crypto_utils.derive_key_pbkdf2('p')
        assert key1 != key2
    def test_different_passwords_produce_different_keys(self):
        key1, salt = crypto_utils.derive_key_pbkdf2('p1')
        key2, _ = crypto_utils.derive_key_pbkdf2('p2', salt)
        assert key1 != key2

class TestAESCBC:
    def test_encrypt_decrypt_roundtrip(self):
        key, _ = crypto_utils.derive_key_pbkdf2('t')
        pt = 'Hello!'
        ct = crypto_utils.encrypt_aes_cbc(pt, key)
        assert crypto_utils.decrypt_aes_cbc(ct, key) == pt
    def test_encrypt_returns_bytes(self):
        key = os.urandom(32)
        ct = crypto_utils.encrypt_aes_cbc('x', key)
        assert isinstance(ct, bytes) and len(ct) > 16
    def test_ciphertext_differs_from_plaintext(self):
        key = os.urandom(32)
        pt = 'secret'
        ct = crypto_utils.encrypt_aes_cbc(pt, key)
        assert pt.encode() not in ct
    def test_wrong_key_raises(self):
        ct = crypto_utils.encrypt_aes_cbc('x', os.urandom(32))
        with pytest.raises(ValueError):
            crypto_utils.decrypt_aes_cbc(ct, os.urandom(32))
    def test_tampered_ciphertext_raises(self):
        key = os.urandom(32)
        ct = crypto_utils.encrypt_aes_cbc('x', key)
        tampered = bytes([ct[0] ^ 0xFF]) + ct[1:]
        with pytest.raises(ValueError):
            crypto_utils.decrypt_aes_cbc(tampered, key)
    def test_empty_plaintext(self):
        key = os.urandom(32)
        ct = crypto_utils.encrypt_aes_cbc('', key)
        assert crypto_utils.decrypt_aes_cbc(ct, key) == ''
    def test_unicode_plaintext(self):
        key = os.urandom(32)
        text = '🔐'
        ct = crypto_utils.encrypt_aes_cbc(text, key)
        assert crypto_utils.decrypt_aes_cbc(ct, key) == text
    def test_invalid_key_raises(self):
        with pytest.raises(ValueError):
            crypto_utils.encrypt_aes_cbc('x', b'x')

class TestAESGCM:
    def test_encrypt_decrypt_roundtrip(self):
        key = os.urandom(32)
        pt = 'Hello GCM!'
        ct = crypto_utils.encrypt_aes_gcm(pt, key)
        assert crypto_utils.decrypt_aes_gcm(ct, key) == pt
    def test_encrypt_with_aad(self):
        key, pt, aad = os.urandom(32), 'x', b'aad'
        ct = crypto_utils.encrypt_aes_gcm(pt, key, aad)
        assert crypto_utils.decrypt_aes_gcm(ct, key, aad) == pt
    def test_wrong_aad_raises(self):
        key = os.urandom(32)
        ct = crypto_utils.encrypt_aes_gcm('x', key, b'aad1')
        with pytest.raises(ValueError):
            crypto_utils.decrypt_aes_gcm(ct, key, b'aad2')
    def test_tampered_ciphertext_raises(self):
        key = os.urandom(32)
        ct = crypto_utils.encrypt_aes_gcm('x', key)
        tampered = bytes([ct[0] ^ 0xFF]) + ct[1:]
        with pytest.raises(ValueError):
            crypto_utils.decrypt_aes_gcm(tampered, key)
    def test_empty_plaintext(self):
        key = os.urandom(32)
        ct = crypto_utils.encrypt_aes_gcm('', key)
        assert crypto_utils.decrypt_aes_gcm(ct, key) == ''
    def test_unicode(self):
        key = os.urandom(32)
        ct = crypto_utils.encrypt_aes_gcm('🔐', key)
        assert crypto_utils.decrypt_aes_gcm(ct, key) == '🔐'

class TestTransmissionHelpers:
    def test_encode_decode(self):
        ct = os.urandom(32)
        enc = crypto_utils.encode_for_transmission(ct)
        assert isinstance(enc, str)
        assert crypto_utils.decode_from_transmission(enc) == ct
    def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            crypto_utils.decode_from_transmission('bad')

class TestRSA:
    def test_keypair_generation(self):
        priv, pub = crypto_utils.generate_rsa_keypair()
        assert priv and pub
    def test_encrypt_decrypt_roundtrip(self):
        priv, pub = crypto_utils.generate_rsa_keypair()
        pt = 'key_32_bytes_string'
        ct = crypto_utils.rsa_encrypt(pub, pt)
        assert crypto_utils.rsa_decrypt(priv, ct) == pt
    def test_sign_verify(self):
        priv, pub = crypto_utils.generate_rsa_keypair()
        msg = 'msg'
        sig = crypto_utils.rsa_sign(priv, msg)
        assert crypto_utils.rsa_verify(pub, msg, sig) is True
    def test_tampered_message_fails(self):
        priv, pub = crypto_utils.generate_rsa_keypair()
        sig = crypto_utils.rsa_sign(priv, 'orig')
        assert crypto_utils.rsa_verify(pub, 'changed', sig) is False
    def test_pem_roundtrip(self):
        _, pub = crypto_utils.generate_rsa_keypair()
        pem = crypto_utils.public_key_to_pem(pub)
        pub2 = crypto_utils.pem_to_public_key(pem)
        assert crypto_utils.public_key_to_pem(pub2) == pem
    def test_wrong_key(self):
        _, pub1 = crypto_utils.generate_rsa_keypair()
        priv2, _ = crypto_utils.generate_rsa_keypair()
        ct = crypto_utils.rsa_encrypt(pub1, 'x')
        with pytest.raises(Exception):
            crypto_utils.rsa_decrypt(priv2, ct)
    def test_save_load_keys(self, tmp_path):
        priv, pub = crypto_utils.generate_rsa_keypair()
        p = str(tmp_path / 'p.key')
        pb = str(tmp_path / 'pb.key')
        crypto_utils.save_rsa_private_key(priv, p)
        crypto_utils.save_rsa_public_key(pub, pb)
        p2 = crypto_utils.load_rsa_private_key(p)
        pb2 = crypto_utils.load_rsa_public_key(pb)
        ct = crypto_utils.rsa_encrypt(pb2, 'x')
        assert crypto_utils.rsa_decrypt(p2, ct) == 'x'

class TestECDH:
    def test_shared_secret_matches(self):
        pa, puba = crypto_utils.generate_ecdh_keypair()
        pb, pubb = crypto_utils.generate_ecdh_keypair()
        sa = crypto_utils.ecdh_shared_secret(pa, pubb)
        sb = crypto_utils.ecdh_shared_secret(pb, puba)
        assert sa == sb
    def test_session_key_derivation(self):
        pa, puba = crypto_utils.generate_ecdh_keypair()
        pb, pubb = crypto_utils.generate_ecdh_keypair()
        secret = crypto_utils.ecdh_shared_secret(pa, pubb)
        ka = crypto_utils.derive_session_key_from_secret(secret)
        kb = crypto_utils.derive_session_key_from_secret(secret)
        assert ka == kb and len(ka) == 32
    def test_different_pairs_different_secrets(self):
        pa, puba = crypto_utils.generate_ecdh_keypair()
        pb, pubb = crypto_utils.generate_ecdh_keypair()
        pc, pubc = crypto_utils.generate_ecdh_keypair()
        sab = crypto_utils.ecdh_shared_secret(pa, pubb)
        sac = crypto_utils.ecdh_shared_secret(pa, pubc)
        assert sab != sac

class TestECDSA:
    def test_sign_verify(self):
        priv, pub = crypto_utils.generate_ecdsa_keypair()
        msg = 'auth'
        sig = crypto_utils.ecdsa_sign(priv, msg)
        assert crypto_utils.ecdsa_verify(pub, msg, sig) is True
    def test_tampered_message_fails(self):
        priv, pub = crypto_utils.generate_ecdsa_keypair()
        sig = crypto_utils.ecdsa_sign(priv, 'orig')
        assert crypto_utils.ecdsa_verify(pub, 'changed', sig) is False
    def test_wrong_key_fails(self):
        p1, pub1 = crypto_utils.generate_ecdsa_keypair()
        _, pub2 = crypto_utils.generate_ecdsa_keypair()
        sig = crypto_utils.ecdsa_sign(p1, 'msg')
        assert crypto_utils.ecdsa_verify(pub2, 'msg', sig) is False

class TestEndToEnd:
    def test_full_e2ee_flow(self):
        ap, apub = crypto_utils.generate_ecdh_keypair()
        bp, bpub = crypto_utils.generate_ecdh_keypair()
        asp, aspub = crypto_utils.generate_ecdsa_keypair()
        sa = crypto_utils.ecdh_shared_secret(ap, bpub)
        sb = crypto_utils.ecdh_shared_secret(bp, apub)
        assert sa == sb
        ka = crypto_utils.derive_session_key_from_secret(sa)
        kb = crypto_utils.derive_session_key_from_secret(sb)
        assert ka == kb
        msg = "Test!"
        ct = crypto_utils.encrypt_aes_gcm(msg, ka)
        sig = crypto_utils.ecdsa_sign(asp, msg)
        pt = crypto_utils.decrypt_aes_gcm(ct, kb)
        assert pt == msg
        assert crypto_utils.ecdsa_verify(aspub, msg, sig) is True
