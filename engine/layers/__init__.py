"""Registro dos tipos de camada aceitos nos YAML de cena."""
from .base import Fill, Layer, SpriteLayer  # noqa: F401
from .highlight import Highlight
from .logo import Logo
from .map import Map
from .picture import Picture
from .text import Text

TYPES = {
    "fill": Fill,
    "text": Text,
    "picture": Picture,
    "highlight": Highlight,
    "map": Map,
    "logo": Logo,
}
