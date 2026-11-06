"""Password hashing and compatibility for existing administrator credentials."""
import hashlib
import hmac
import os

# scrypt work factors (OWASP-recommended memory-hard parameters; ~50ms/verify)
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
_SCRYPT_MAXMEM = 64 * 1024 * 1024  # hashlib default cap (32MB) is too low for n=2^14,r=8

PASSWORD_SCHEME = "scrypt"  # current scheme for new hashes; sha256/plaintext stay verifiable


def hash_password(password: str) -> str:
    """
    使用 scrypt（memory-hard）哈希密码
    返回格式: scrypt$<n>$<r>$<p>$<salt>$<hash>
    """
    salt = os.urandom(16).hex()
    password_hash = hashlib.scrypt(
        password.encode(),
        salt=salt.encode(),
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        maxmem=_SCRYPT_MAXMEM,
    ).hex()
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt}${password_hash}"


def verify_password(password: str, hashed: str) -> bool:
    """
    验证密码是否匹配
    支持格式: scrypt$n$r$p$salt$hash（现行）、sha256$salt$hash（历史）、明文（最老）
    """
    if not hashed:
        return False

    if hashed.startswith("scrypt$"):
        parts = hashed.split("$")
        if len(parts) != 6:
            return False
        try:
            scheme, n, r, p, salt, stored_hash = parts
            password_hash = hashlib.scrypt(
                password.encode(),
                salt=salt.encode(),
                n=int(n),
                r=int(r),
                p=int(p),
                maxmem=_SCRYPT_MAXMEM,
            ).hex()
        # 默认解释器对超范围的 n/r/p 抛 TypeError/ValueError；部分构建会抛
        # OverflowError，一并视为校验失败，避免坏掉的存量哈希影响登录路径。
        except (ValueError, TypeError, OverflowError):
            return False
        return hmac.compare_digest(password_hash, stored_hash)

    # sha256 格式: sha256$salt$hash（历史数据，验证逻辑保持原样）
    if hashed.startswith("sha256$"):
        parts = hashed.split("$")
        if len(parts) != 3:
            return False
        _, salt, stored_hash = parts
        password_hash = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return hmac.compare_digest(password_hash, stored_hash)

    # 旧格式: 明文比较 (兼容迁移前的数据)
    return hmac.compare_digest(str(password), str(hashed))


def is_password_hashed(password: str) -> bool:
    """
    检查密码是否已经是哈希格式（现行或历史哈希均视为已哈希）
    """
    if password.startswith("scrypt$") and len(password.split("$")) == 6:
        return True
    return password.startswith("sha256$") and len(password.split("$")) == 3


def password_needs_rehash(hashed: str) -> bool:
    """True when the stored hash uses a legacy scheme (sha256/plaintext)."""
    return bool(hashed) and not hashed.startswith(f"{PASSWORD_SCHEME}$")
