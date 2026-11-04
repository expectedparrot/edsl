from examples.handbook_games_catalog import GAMES, render


def test_handbook_catalog_is_structured_unique_and_sourced():
    assert len(GAMES) >= 50
    assert len({game.slug for game in GAMES}) == len(GAMES)
    assert all(game.chapter in range(1, 9) for game in GAMES)
    assert all(game.pages and len(game.description) > 70 for game in GAMES)
    assert all(game.status in {"implemented", "ready", "queued"} for game in GAMES)


def test_implemented_handbook_games_link_to_gallery_cases():
    from examples.workflow_stress_gallery import cases

    gallery_slugs = {case.slug for case in cases()}
    assert {
        game.existing_case for game in GAMES if game.status == "implemented"
    } <= gallery_slugs


def test_handbook_catalog_renders_html_and_embedded_json(tmp_path):
    output = render(tmp_path / "catalog.html")
    text = output.read_text()
    assert "Experimental game catalog" in text
    assert "Machine-readable catalog JSON" in text
    assert "Battle of the Sexes" in text
