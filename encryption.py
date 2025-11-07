import json
import base64
import cryptography.hazmat.primitives.asymmetric.padding as asym_padding
import cryptography.hazmat.primitives.hashes as hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

class FlowEndpointException(Exception):
    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code


def decrypt_request(body, private_pem, passphrase):
    encrypted_aes_key = base64.b64decode(body["encrypted_aes_key"])
    encrypted_flow_data = base64.b64decode(body["encrypted_flow_data"])
    initial_vector = base64.b64decode(body["initial_vector"])
    
    private_key = serialization.load_pem_private_key(
        private_pem.encode(), password=passphrase.encode()
    )
    
    try:
        decrypted_aes_key = private_key.decrypt(
            encrypted_aes_key,
            asym_padding.OAEP(
                mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
    except Exception as e:
        print(e)
        raise FlowEndpointException(421, "Failed to decrypt the request. Please verify your private key.")
    
    TAG_LENGTH = 16
    encrypted_flow_data_body = encrypted_flow_data[:-TAG_LENGTH]
    encrypted_flow_data_tag = encrypted_flow_data[-TAG_LENGTH:]
    
    cipher = Cipher(algorithms.AES(decrypted_aes_key), modes.GCM(initial_vector, encrypted_flow_data_tag))
    decryptor = cipher.decryptor()
    
    decrypted_json_string = decryptor.update(encrypted_flow_data_body) + decryptor.finalize()
    
    return {
        "decryptedBody": json.loads(decrypted_json_string.decode("utf-8")),
        "aesKeyBuffer": decrypted_aes_key,
        "initialVectorBuffer": initial_vector,
    }
# def decrypt_request(body, private_pem, passphrase):
#     encrypted_aes_key = base64.b64decode(body["encrypted_aes_key"])
#     encrypted_flow_data = base64.b64decode(body["encrypted_flow_data"])
#     initial_vector = base64.b64decode(body["initial_vector"])
    
#     try:
#         private_key = serialization.load_pem_private_key(
#             private_pem.encode(), password=passphrase.encode()
#         )
#         print("Private key loaded successfully.")
#     except ValueError as e:
#         raise FlowEndpointException(500, "Invalid private key or passphrase.") from e
    
#     try:
#         decrypted_aes_key = private_key.decrypt(
#             encrypted_aes_key,
#             asym_padding.OAEP(
#                 mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
#                 algorithm=hashes.SHA256(),
#                 label=None,
#             ),
#         )
#         print("AES Key decrypted successfully:", decrypted_aes_key)
#     except ValueError as e:
#         print("Decryption failed: Incorrect key or bad data.",encrypted_aes_key.hex())
#         raise FlowEndpointException(444, "Decryption failed. Check your private key and encrypted data.") from e
#     except TypeError as e:
#         print("Private key is not loaded correctly.")
#         raise FlowEndpointException(445, "Invalid private key format.") from e
#     except Exception as e:
#         print(f"Unexpected error: {e}")
#         raise FlowEndpointException(446, "Decryption error occurred.") from e

    
#     TAG_LENGTH = 16
#     encrypted_flow_data_body = encrypted_flow_data[:-TAG_LENGTH]
#     encrypted_flow_data_tag = encrypted_flow_data[-TAG_LENGTH:]
    
#     cipher = Cipher(algorithms.AES(decrypted_aes_key), modes.GCM(initial_vector, encrypted_flow_data_tag))
#     decryptor = cipher.decryptor()
    
#     decrypted_json_string = decryptor.update(encrypted_flow_data_body) + decryptor.finalize()
    
#     return {
#         "decryptedBody": json.loads(decrypted_json_string.decode("utf-8")),
#         "aesKeyBuffer": decrypted_aes_key,
#         "initialVectorBuffer": initial_vector,
#     }


def encrypt_response(response, aes_key_buffer, initial_vector_buffer):
    flipped_iv = bytes(~b & 0xFF for b in initial_vector_buffer)
    
    cipher = Cipher(algorithms.AES(aes_key_buffer), modes.GCM(flipped_iv))
    encryptor = cipher.encryptor()
    
    encrypted_data = encryptor.update(json.dumps(response).encode("utf-8")) + encryptor.finalize()
    auth_tag = encryptor.tag
    
    return base64.b64encode(encrypted_data + auth_tag).decode("utf-8")
