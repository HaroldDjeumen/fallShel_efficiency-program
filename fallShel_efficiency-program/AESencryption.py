import base64
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Util.Padding import pad, unpad

PASS_PHRASE = "UGxheWVy"
INIT_VECTOR = b"tu89geji340t89u2"  # 16 bytes


def is_base64(data: bytes) -> bool:
    try:
        base64.b64decode(data, validate=True)
        return True
    except Exception:
        return False


def get_key_and_iv():
    key_iv = PBKDF2(
        PASS_PHRASE,
        INIT_VECTOR,
        dkLen=48,
        count=1000
    )
    key = key_iv[:32]
    iv = key_iv[32:48]
    return key, iv


def decrypt_data(payload) -> str:
    """
    Accepts either base64/text bytes, or raw encrypted bytes.
    If payload is base64-encoded, it will be decoded first; otherwise it's treated
    as the raw AES-CBC ciphertext. Returns a UTF-8 string.
    """
    key, iv = get_key_and_iv()
    cipher = AES.new(key, AES.MODE_CBC, iv)

    # normalize to bytes
    if isinstance(payload, str):
        data_bytes = payload.encode("utf-8")
    else:
        data_bytes = payload

    # If it's base64-encoded text, decode it first; otherwise treat as raw ciphertext
    if is_base64(data_bytes):
        try:
            decoded = base64.b64decode(data_bytes)
        except Exception as e:
            raise ValueError(f"Invalid base64 payload: {e}")
    else:
        decoded = data_bytes

    try:
        decrypted = unpad(cipher.decrypt(decoded), AES.block_size)
    except Exception as e:
        raise ValueError(f"Decryption failed: {e}")

    try:
        return decrypted.decode("utf-8")
    except Exception:
        # Fallback: return as latin-1 to preserve bytes if UTF-8 is not valid
        return decrypted.decode("latin-1")


def encrypt_data(text: str) -> bytes:
    key, iv = get_key_and_iv()
    cipher = AES.new(key, AES.MODE_CBC, iv)
    encrypted = cipher.encrypt(pad(text.encode("utf-8"), AES.block_size))
    return base64.b64encode(encrypted)


def process_file(path):
    with open(path, "rb") as f:
        data = f.read()

    if is_base64(data):
        print("Decrypting file")
        output = decrypt_data(data)
        with open(path, "w", encoding="utf-8") as f:
            f.write(output)
    else:
        print("Encrypting file")
        # Attempt to decode as UTF-8, fallback to latin-1 to preserve bytes
        try:
            text = data.decode("utf-8")
        except Exception:
            text = data.decode("latin-1")
        output = encrypt_data(text)
        # write base64 string (text mode) to match Java FileWriter behavior
        with open(path, "w", encoding="utf-8") as f:
            f.write(output.decode("ascii"))