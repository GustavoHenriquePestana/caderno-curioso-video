import pytest

from engine import theme


def test_named_and_hex_colors():
    assert theme.rgb("marinho") == (0x11, 0x30, 0x51)
    assert theme.rgb("#F5BE3C") == (245, 190, 60)
    assert theme.rgb([1, 2, 3]) == (1, 2, 3)
    with pytest.raises(ValueError):
        theme.rgb("azul")


def test_logo_palette_contrast():
    from qa.media import contrast
    assert contrast(theme.rgb("creme"), theme.rgb("marinho")) >= 7
    assert contrast(theme.rgb("ouro"), theme.rgb("marinho")) >= 4.5


@pytest.mark.parametrize("role", ["titulo", "texto", "italico", "sans", "sans_forte", "numeros", "credito"])
def test_roles_load(role):
    f = theme.font(role, 40)
    assert f.getlength("Caderno") > 0


def test_fonts_have_ofl():
    files = theme.font_files()
    assert len(files) == 8
    for font, lic in files:
        assert font.exists(), font
        assert "Open Font License" in lic.read_text(encoding="utf-8")
