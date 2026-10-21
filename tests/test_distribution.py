from scripts.verify_distribution import verify


def test_distribution_ignores_private_runtime_files_and_rejects_unknown_files(tmp_path):
    (tmp_path / "README.md").write_text("Public starter", "utf-8")
    (tmp_path / ".env").write_bytes(b"\xff")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "agent.sqlite").write_bytes(b"\xff")
    manifest, errors = verify(tmp_path)
    assert not errors
    assert [item["path"] for item in manifest] == ["README.md"]
    (tmp_path / "Dockerfile").write_text("FROM example", "utf-8")
    assert verify(tmp_path)[1]


def test_distribution_requires_empty_provider_configuration_and_no_symlinks(tmp_path):
    (tmp_path / ".env.example").write_text("AGENT_MODEL=example-model", "utf-8")
    (tmp_path / "linked").symlink_to(tmp_path / ".env.example")
    manifest, errors = verify(tmp_path)
    assert len(manifest) == 1
    assert any("must be blank" in message for message in errors)
    assert any("symbolic links" in message for message in errors)
