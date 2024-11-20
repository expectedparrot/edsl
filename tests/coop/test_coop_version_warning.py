from edsl import Coop


def test_latest_stable_version():
    c = Coop()

    assert c._get_latest_stable_version("0.1.37") == "0.1.37"
    assert c._get_latest_stable_version("0.1.37.dev1") == "0.1.36"
    assert c._get_latest_stable_version("0.1.38.dev2") == "0.1.37"

    # Check for single digit versions
    assert c._get_latest_stable_version("0.1.9") == "0.1.9"
    assert c._get_latest_stable_version("0.1.9.dev1") == "0.1.8"
    assert c._get_latest_stable_version("0.1.1.dev1") == "0.1.0"


def test_user_version_is_outdated_patch_changes():
    c = Coop()

    # 0.1.36 < 0.1.37
    assert c._user_version_is_outdated(
        user_version_str="0.1.37.dev1", server_version_str="0.1.37"
    )
    # 0.1.37 < 0.1.38
    assert c._user_version_is_outdated(
        user_version_str="0.1.37", server_version_str="0.1.38"
    )
    # 0.1.37 == 0.1.37
    assert not c._user_version_is_outdated(
        user_version_str="0.1.38.dev2", server_version_str="0.1.37"
    )

    # 0.1.37 == 0.1.37
    assert not c._user_version_is_outdated(
        user_version_str="0.1.38.dev2", server_version_str="0.1.38.dev5"
    )

    # 0.1.37 == 0.1.37
    assert not c._user_version_is_outdated(
        user_version_str="0.1.37", server_version_str="0.1.37"
    )


def test_user_version_is_outdated_minor_changes():
    c = Coop()

    # 0.1.37 < 0.2.37
    assert c._user_version_is_outdated(
        user_version_str="0.1.37", server_version_str="0.2.37"
    )

    # 0.1.8 < 0.2.8
    assert c._user_version_is_outdated(
        user_version_str="0.1.8", server_version_str="0.2.8"
    )


def test_user_version_is_outdated_major_changes():
    c = Coop()

    # 0.1.37 < 1.1.37
    assert c._user_version_is_outdated(
        user_version_str="0.1.37", server_version_str="1.1.37"
    )

    # 1.1.8 < 2.1.8
    assert c._user_version_is_outdated(
        user_version_str="1.1.8", server_version_str="2.1.8"
    )
