import importlib
import json
import sys


def _reload(monkeypatch, tmp_path, cfg: dict, local: dict | None = None, env: dict | None = None):
    # modul core.config di-import ulang; kembalikan objek asli setelah test supaya modul lain
    # (runner, api) tetap memegang referensi yang sama dengan test lain
    original = sys.modules.get("core.config")
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    if local is not None:
        (tmp_path / "config.local.json").write_text(json.dumps(local))
    monkeypatch.setenv("CONFIG_FILE", str(tmp_path / "config.json"))
    for k in ("EMAIL_PROVIDER", "WORKERS", "ENABLE_SCHEDULER", "MAIL_SENDER_FILTER", "KLING_SIGNUP_URL",
              "KLING_DEFAULT_PASSWORD", "PROXY_LIST"):
        monkeypatch.delenv(k, raising=False)
    for k, v in (env or {}).items():
        monkeypatch.setenv(k, v)
    sys.modules.pop("core.config", None)
    mod = importlib.import_module("core.config")
    if original is not None:
        import core
        sys.modules["core.config"] = original   # kembalikan objek asli (bukan via monkeypatch: ia akan
        core.config = original                  # merestore nilai *saat dipanggil*, yaitu modul baru)
    return mod


def test_config_json_dibaca(monkeypatch, tmp_path):
    c = _reload(monkeypatch, tmp_path, {"email": {"provider": "mailtm", "sender_filter": ["Kling"]},
                                          "defaults": {"workers": 5}, "scheduler": {"enabled": False},
                                          "site": {"signup_url": "https://x.test/signup"}})
    assert c.EMAIL_PROVIDER == "mailtm" and c.WORKERS == 5 and c.ENABLE_SCHEDULER is False
    assert c.MAIL_SENDER_FILTER == ["kling"] and c.KLING_SIGNUP_URL == "https://x.test/signup"
    assert c.CONFIG_SOURCES == ["config.json"]


def test_local_override_lalu_env_menang(monkeypatch, tmp_path):
    c = _reload(monkeypatch, tmp_path, {"defaults": {"workers": 5}, "email": {"provider": "mailtm"}},
                local={"defaults": {"workers": 7}}, env={"EMAIL_PROVIDER": "gptmail"})
    assert c.WORKERS == 7                    # config.local.json > config.json
    assert c.EMAIL_PROVIDER == "gptmail"     # env > json
    assert c.CONFIG_SOURCES == ["config.json", "config.local.json"]


def test_default_kode_saat_json_kosong(monkeypatch, tmp_path):
    c = _reload(monkeypatch, tmp_path, {})
    assert c.EMAIL_PROVIDER == "1secmail" and c.WORKERS == 2 and c.BATCH_SIZE == 10 and c.ENABLE_SCHEDULER is True


def test_kredensial_hanya_dari_env(monkeypatch, tmp_path):
    c = _reload(monkeypatch, tmp_path, {"site": {"default_password": "bocor"}, "proxy": {"list": ["a:b@c:1"]}},
                env={"KLING_DEFAULT_PASSWORD": "rahasia"})
    assert c.KLING_DEFAULT_PASSWORD == "rahasia" and c.PROXY_LIST == []
