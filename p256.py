"""ECDSA P-256 signature verification with the standard library, for checking
the signed plugin catalog at build time (the build verifies one document, so
speed does not matter). Signatures are 64-byte IEEE P1363 (r || s) over a
32-byte digest, as MaiCord's CNG signer writes them. Verification only: there
is no secret here, so nothing needs constant-time arithmetic."""

P = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF
N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
B = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B
G = (0x6B17D1F2E12C4247F8BCE6E563A440F277037D812DEB33A0F4A13945D898C296,
     0x4FE342E2FE1A7F9B8EE7EB4A7C0F9E162BCE33576B315ECECBB6406837BF51F5)


def _add(p, q):
    """Affine addition on y^2 = x^3 - 3x + B; None is the point at infinity."""
    if p is None:
        return q
    if q is None:
        return p
    (x1, y1), (x2, y2) = p, q
    if x1 == x2:
        if (y1 + y2) % P == 0:
            return None
        slope = (3 * x1 * x1 - 3) * pow(2 * y1, -1, P) % P
    else:
        slope = (y2 - y1) * pow(x2 - x1, -1, P) % P
    x = (slope * slope - x1 - x2) % P
    return x, (slope * (x1 - x) - y1) % P


def _multiply(k, point):
    result = None
    while k:
        if k & 1:
            result = _add(result, point)
        point = _add(point, point)
        k >>= 1
    return result


def verify(public_key, digest, signature):
    """True when `signature` (64 bytes) signs `digest` (32 bytes) under the
    65-byte uncompressed SEC1 `public_key` (04 || X || Y)."""
    if len(public_key) != 65 or public_key[0] != 4 or len(digest) != 32 or len(signature) != 64:
        return False
    q = (int.from_bytes(public_key[1:33], "big"), int.from_bytes(public_key[33:], "big"))
    if q[0] >= P or q[1] >= P or (q[1] * q[1] - (q[0] ** 3 - 3 * q[0] + B)) % P:
        return False
    r, s = int.from_bytes(signature[:32], "big"), int.from_bytes(signature[32:], "big")
    if not (0 < r < N and 0 < s < N):
        return False
    w = pow(s, -1, N)
    point = _add(_multiply(int.from_bytes(digest, "big") * w % N, G), _multiply(r * w % N, q))
    return point is not None and point[0] % N == r
