"""
core.domains — rotasi custom domain untuk email webhook.

Domain dikelompokkan per TLD (biz.id, my.id, ...) dan dipilih interleave
proporsional (Bresenham) agar satu TLD tidak dihajar berturut-turut.
Blacklist memori (rate-limit sementara) + banned_domains di DB (permanen).

Diport dari engine sumber; DDL banned_domains ada di models.py.
"""
import random
import threading
from collections import OrderedDict

from core import config
from core.log import warn

CUSTOM_DOMAINS: list[str] = list(config.CUSTOM_DOMAINS)

_blacklisted: set[str] = set()
_lock = threading.Lock()
_counter_lock = threading.Lock()
_tld_group_counter = 0
_tld_intra: dict[str, int] = {}
_domain_counter = random.randint(0, len(CUSTOM_DOMAINS) - 1) if CUSTOM_DOMAINS else 0


def domain_count() -> int:
    return len(CUSTOM_DOMAINS)


def _tld_group(domain: str) -> str:
    """'outfitlab.biz.id' → 'biz.id'; 'example.com' → 'example.com'."""
    parts = domain.lower().rsplit(".", 2)
    if len(parts) >= 2:
        return f"{parts[-2]}.{parts[-1]}"
    return domain.lower()


def _engine():
    import db
    return db.get_engine()


def get_db_banned_domains() -> list[str]:
    """Baca banned_domains dari DB (repo); gagal → []."""
    try:
        import repo
        return repo.list_banned_domains(_engine())
    except Exception:
        return []


def ban_domain_in_db(domain: str) -> None:
    """Simpan domain ke banned_domains (permanen sampai dihapus manual)."""
    if not domain:
        return
    try:
        import repo
        repo.ban_domain(_engine(), domain)
    except Exception as e:
        warn(f"Gagal simpan banned domain {domain}: {e}")


def next_domain() -> str:
    """Pilih domain berikutnya (interleave per TLD). '' jika tidak ada yang tersedia."""
    global _domain_counter, _tld_group_counter
    if not CUSTOM_DOMAINS:
        return ""
    db_banned = set(get_db_banned_domains())
    with _lock:
        active = [d for d in CUSTOM_DOMAINS if d not in _blacklisted and d.lower() not in db_banned]
        if not active:
            _blacklisted.clear()
            active = [d for d in CUSTOM_DOMAINS if d.lower() not in db_banned]
            if not active:
                return ""

        groups: OrderedDict[str, list[str]] = OrderedDict()
        for d in active:
            groups.setdefault(_tld_group(d), []).append(d)
        keys = list(groups.keys())

        if len(keys) == 1:
            with _counter_lock:
                _domain_counter += 1
                return active[_domain_counter % len(active)]

        with _counter_lock:
            _tld_group_counter += 1
            total = len(active)
            pos = _tld_group_counter % total
            selected = None
            for tld in sorted(keys, key=lambda t: len(groups[t])):  # minoritas diprioritaskan saat collision
                size = len(groups[tld])
                if ((pos + 1) * size) // total > (pos * size) // total:
                    selected = tld
                    break
            if selected is None:
                selected = keys[0]
            members = groups[selected]
            if selected not in _tld_intra:
                _tld_intra[selected] = random.randint(0, max(0, len(members) - 1))
            _tld_intra[selected] += 1
            return members[_tld_intra[selected] % len(members)]


def blacklist_domain(domain: str) -> None:
    """Blacklist sementara (memori) — rate-limit."""
    if domain:
        with _lock:
            _blacklisted.add(domain)
        warn(f"Domain {domain} diblacklist sementara (rate-limit).")
