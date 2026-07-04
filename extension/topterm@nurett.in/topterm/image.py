import gi

gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")

from gi.repository import Gdk, GdkPixbuf

RESET = "\x1b[0m"
UPPER_HALF_BLOCK = "▀"


def render_texture(
    texture: Gdk.Texture,
    cols: int,
    rows: int,
    char_width: int,
    char_height: int,
    bg_rgba: Gdk.RGBA,
) -> bytes:
    """Truecolor mosaic: each cell is an upper-half-block glyph whose fg is the
    top pixel and bg the bottom pixel, so a cell shows a 1x2 pixel column.
    Scaled to fit cols x rows preserving on-screen aspect ratio (cells are
    char_width x char_height, not square); never upscaled past native size."""
    pixbuf = Gdk.pixbuf_get_from_texture(texture)
    img_w = pixbuf.get_width()
    img_h = pixbuf.get_height()
    scale = min(cols * char_width / img_w, rows * char_height / img_h, 1.0)
    grid_w = min(cols, max(1, round(img_w * scale / char_width)))
    grid_h = 2 * min(rows, max(1, round(img_h * scale / char_height)))
    bg = (
        (round(bg_rgba.red * 255) << 16)
        | (round(bg_rgba.green * 255) << 8)
        | round(bg_rgba.blue * 255)
    )
    # Scales and flattens alpha onto the terminal background in one pass.
    pixbuf = pixbuf.composite_color_simple(
        grid_w, grid_h, GdkPixbuf.InterpType.BILINEAR, 255, 32, bg, bg
    )
    pixels = pixbuf.get_pixels()
    stride = pixbuf.get_rowstride()
    channels = pixbuf.get_n_channels()

    def rgb(x: int, y: int) -> tuple[int, int, int]:
        offset = y * stride + x * channels
        return pixels[offset], pixels[offset + 1], pixels[offset + 2]

    lines = []
    for y in range(0, grid_h, 2):
        cells = []
        for x in range(grid_w):
            top = rgb(x, y)
            bottom = rgb(x, y + 1)
            cells.append(
                f"\x1b[38;2;{top[0]};{top[1]};{top[2]}m"
                f"\x1b[48;2;{bottom[0]};{bottom[1]};{bottom[2]}m"
                f"{UPPER_HALF_BLOCK}"
            )
        lines.append("".join(cells) + RESET)
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")
