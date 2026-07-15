from edsl.base.git_package import _exclude_from_package_archive


def test_package_archive_excludes_transient_git_pack_files():
    assert _exclude_from_package_archive(".git/objects/pack/tmp_pack_abc123")
    assert _exclude_from_package_archive(".git/objects/pack/tmp_idx_abc123")
    assert not _exclude_from_package_archive(".git/objects/pack/pack-abc123.pack")
    assert not _exclude_from_package_archive(".git/objects/pack/pack-abc123.idx")
