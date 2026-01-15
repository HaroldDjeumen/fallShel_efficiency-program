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


def get_key():
    """Generate key using PBKDF2, matching Java implementation"""
    key_iv = PBKDF2(
        PASS_PHRASE,
        INIT_VECTOR,
        dkLen=48,  # 384 bits = 48 bytes
        count=1000
    )
    key = key_iv[:32]  # First 32 bytes for AES-256 key
    # Note: Java generates IV from PBKDF2 but then uses original INIT_VECTOR
    return key


def decrypt_data(text: bytes) -> bytes:
    """
    Decrypt data matching Java implementation.
    Uses PBKDF2-derived key but original INIT_VECTOR as IV.
    """
    key = get_key()
    # Use original INIT_VECTOR as IV (matching Java code)
    cipher = AES.new(key, AES.MODE_CBC, INIT_VECTOR)
    decoded = base64.b64decode(text)
    decrypted = unpad(cipher.decrypt(decoded), AES.block_size)
    return decrypted


def encrypt_data(data) -> bytes:
    """
    Encrypt data matching Java implementation.
    Accepts either bytes or str. Returns base64-encoded bytes.
    """
    if isinstance(data, str):
        data_bytes = data.encode("utf-8")
    else:
        data_bytes = data
    
    key = get_key()
    # Use original INIT_VECTOR as IV (matching Java code)
    cipher = AES.new(key, AES.MODE_CBC, INIT_VECTOR)
    encrypted = cipher.encrypt(pad(data_bytes, AES.block_size))
    return base64.b64encode(encrypted)


def process_file(path):
    """Process a file: decrypt if encrypted, encrypt if decrypted"""
    with open(path, "rb") as f:
        data = f.read()
    
    if is_base64(data):
        print("Decrypting file...")
        output = decrypt_data(data)
        
        # Always write decrypted data as binary first
        output_path = path + ".decrypted" if path.endswith(".sav") else path
        with open(output_path, "wb") as f:
            f.write(output)
        print(f"Successfully decrypted to: {output_path}")
        
        # Try to also save as readable JSON if it's valid UTF-8
        try:
            output_str = output.decode("utf-8")
            json_path = path.replace(".sav", ".json") if path.endswith(".sav") else path + ".json"
            with open(json_path, "w", encoding="utf-8") as f:
                f.write(output_str)
            print(f"Also saved as readable text: {json_path}")
        except UnicodeDecodeError:
            print("(Decrypted data is binary, not text)")
    else:
        print("Encrypting file...")
        output = encrypt_data(data)
        with open(path, "wb") as f:
            f.write(output)
        print(f"Successfully encrypted: {path}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python AESencryption.py <file_path>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    process_file(file_path)