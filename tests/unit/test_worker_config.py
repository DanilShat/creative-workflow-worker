from creative_workflow.worker.config import WorkerSettings


def test_env_file_with_windows_bom_loads_first_key(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env.worker"
    env_file.write_text(
        "\ufeffSERVER_BASE_URL=http://192.168.1.124:8000\n"
        "WORKER_ID=designer-laptop-01\n"
        "WORKER_TOKEN=test-token\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("SERVER_BASE_URL", raising=False)

    settings = WorkerSettings.load(env_file)

    assert settings.server_base_url == "http://192.168.1.124:8000"
