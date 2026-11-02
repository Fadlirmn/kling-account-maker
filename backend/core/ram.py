"""core.ram — RAM guard: batasi jumlah worker/browser paralel berdasarkan RAM tersedia."""
from core.config import RAM_PER_WORKER_MB


def get_available_ram_mb() -> int:
    """Baca MemAvailable dari /proc/meminfo (bukan MemFree). Fallback 1024 MB."""
    try:
        mem = {}
        with open("/proc/meminfo", "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    mem[parts[0].rstrip(":")] = int(parts[1])  # kB
        available_kb = mem.get("MemAvailable", mem.get("MemFree", 1024 * 1024))
        return available_kb // 1024
    except Exception:
        return 1024


def get_safe_workers(requested: int, ram_per_worker_mb: int = RAM_PER_WORKER_MB) -> int:
    """floor(available / per_worker), min 1, max requested."""
    requested = max(1, requested)
    available_mb = get_available_ram_mb()
    max_by_ram = max(1, available_mb // max(1, ram_per_worker_mb))
    safe = min(requested, max_by_ram)
    if safe < requested:
        print(f"\033[33m[RAM Guard] RAM tersedia: {available_mb}MB | {ram_per_worker_mb}MB/worker | "
              f"Max worker aman: {max_by_ram} | Requested: {requested} → Dikurangi ke {safe}\033[0m", flush=True)
    else:
        print(f"[RAM Guard] RAM tersedia: {available_mb}MB | {ram_per_worker_mb}MB/worker | Workers: {safe} (OK)", flush=True)
    return safe
