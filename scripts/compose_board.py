"""Compose a wedding decor blueprint poster from a validated specification and local images."""

import argparse
import colorsys
import os
import re
import sys
import tempfile
import unicodedata
from functools import lru_cache
from pathlib import Path

try:
    from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageFont, ImageOps, features
except ModuleNotFoundError as error:
    sys.exit(f"{error.name} is unavailable. Install Pillow with python -m pip install 'Pillow>=9.1'.")

from validate_spec import load_spec


SIZE = (2160, 2880)
LEFT, RIGHT = 80, 2080
WHITE = (255, 255, 255)
INK = (31, 35, 30)
MUTED = (75, 81, 75)
RULE = (212, 217, 210)
MATTE = (245, 246, 242)
ASSETS = Path(__file__).resolve().parent.parent / "assets"
RESAMPLE = Image.Resampling.LANCZOS
IMAGE_ERRORS = (OSError, ValueError, Image.DecompressionBombError)
CLOSING_PUNCTUATION = "，。？！；：、）》」』】〕〉…,.!?;:%)]}"
OPENING_PUNCTUATION = "（《「『【〔〈([{"


def board_size(raw):
    match = re.fullmatch(r"([1-9][0-9]*)[xX×]([1-9][0-9]*)", raw)
    if match:
        width, height = map(int, match.groups())
        if width * 4 == height * 3:
            return width, height
    raise argparse.ArgumentTypeError("Use a 3:4 portrait size such as 2160x2880.")


def art_paths(folder):
    names = ["elevation.png", "plan.png"]
    names.extend(f"component-{i:02d}.png" for i in range(1, 7))
    names.extend(f"step-{i:02d}.png" for i in range(1, 6))
    return [folder / name for name in names]


def read_image(path):
    with Image.open(path) as source:
        return ImageOps.exif_transpose(source).convert("RGBA")


def flatten(image, background=WHITE):
    result = Image.new("RGB", image.size, background)
    result.paste(image, mask=image.getchannel("A"))
    return result


def trim_white(image):
    """Trim almost-white studio margins from generated art only."""
    diff = ImageChops.difference(image, Image.new("RGB", image.size, WHITE))
    red, green, blue = diff.split()
    difference = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    bounds = difference.point(lambda value: 255 if value > 20 else 0).getbbox()
    if bounds is None:
        raise ValueError("blank or entirely transparent image")
    return image.crop(bounds)


def stage_images(paths, spec):
    entries = [spec["views"][key] for key in ("elevation", "plan")]
    entries.extend(spec["components"])
    entries.extend(spec["steps"])
    images, missing = {}, []
    for path, entry in zip(paths, entries):
        if entry["prompt_detail"] is None:
            missing.append((path.name, "prompt_detail is null"))
            continue
        try:
            images[path.name] = trim_white(flatten(read_image(path)))
        except FileNotFoundError:
            missing.append((path.name, "file missing"))
        except IMAGE_ERRORS as error:
            missing.append((path.name, str(error)))
    return images, missing


def system_fonts():
    mac = Path("/System/Library/Fonts")
    supplemental = mac / "Supplemental"
    windows = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    linux = Path("/usr/share/fonts")
    yield from (
        mac / "PingFang.ttc",
        supplemental / "PingFang.ttc",
        Path("/Library/Fonts/PingFang.ttc"),
        windows / "msyh.ttc",
        windows / "msyh.ttf",
        linux / "opentype/noto/NotoSansCJK-Regular.ttc",
        linux / "google-noto-cjk/NotoSansCJK-Regular.ttc",
        linux / "noto-cjk/NotoSansCJK-Regular.ttc",
        linux / "opentype/adobe-source-han-sans/SourceHanSansSC-Regular.otf",
        linux / "truetype/wqy/wqy-zenhei.ttc",
        linux / "truetype/wqy/wqy-microhei.ttc",
        supplemental / "Hiragino Sans GB.ttc",
        supplemental / "Songti.ttc",
        supplemental / "Arial Unicode.ttf",
    )


def glyph_signature(font, character):
    mask = font.getmask(character)
    return mask.size, bytes(mask)


def glyphs_needed(spec):
    labels = [spec["theme"], spec.get("brand_name") or "", *spec["subtitle_elements"]]
    labels.extend(spec["labels"].values())
    labels.extend(view["heading"] for view in spec["views"].values())
    for key, value in spec["dimensions"].items():
        labels.extend([key, value["label"], value["value"] or ""])
    for row in spec["materials"]:
        labels.extend([row["name"], row["detail"]])
    labels.extend(component["name"] for component in spec["components"])
    for step in spec["steps"]:
        labels.extend([str(step["number"]), step["name"], step["description"]])
    labels.append("·/（）" if spec["language"].lower().startswith("zh") else "·/()")
    return sorted({
        c for c in "".join(labels)
        if not c.isspace() and unicodedata.category(c) != "Cf"
        and not ("\ufe00" <= c <= "\ufe0f" or "\U000e0100" <= c <= "\U000e01ef")
    })


def find_font(requested, spec):
    glyphs = glyphs_needed(spec)
    if any(unicodedata.bidirectional(c) in {"R", "AL"} for c in glyphs):
        if not features.check_feature("raqm"):
            raise ValueError("Right-to-left text requires a Pillow build with libraqm support.")
    bundled = sorted(path for path in (ASSETS / "fonts").glob("*")
                     if path.suffix.lower() in {".ttf", ".otf", ".ttc", ".otc"})
    candidates = ([requested] if requested else []) + bundled + list(system_fonts())
    examples = []
    for path in dict.fromkeys(candidates):
        if not path.is_file():
            continue
        collection = path.suffix.lower() in {".ttc", ".otc"}
        for index in range(32 if collection else 1):
            try:
                font = ImageFont.truetype(str(path), 40, index=index)
                missing = {glyph_signature(font, c) for c in ("\u0378", "\U0010ffff")}
                unsupported = [c for c in glyphs if glyph_signature(font, c) in missing]
            except (OSError, ValueError):
                break
            if not unsupported:
                if requested and path != requested:
                    print(f"Requested font unavailable or incomplete. Using {path}.", file=sys.stderr)
                return path, index
            examples.extend(unsupported[:5])
    detail = "".join(dict.fromkeys(examples))[:24]
    if detail:
        detail = f" Missing glyph examples: {detail}."
    raise ValueError(
        "No readable font covers the poster text. Install Noto Sans CJK / Source Han Sans or "
        f"pass --font /path/to/font.ttf.{detail}"
    )


def accent_color(hero, requested):
    if requested:
        color = ImageColor.getrgb(requested)
    else:
        sample = hero.copy()
        sample.thumbnail((128, 128))
        indexed = sample.quantize(colors=16).convert("RGB")
        colors = indexed.getcolors(maxcolors=16)

        def weight(entry):
            count, rgb = entry
            _, saturation, value = colorsys.rgb_to_hsv(*(channel / 255 for channel in rgb))
            if saturation < 0.16 or value < 0.18:
                return 0
            return count * saturation / (0.4 + abs(value - 0.50))

        dominant = max(colors, key=weight)
        color = dominant[1] if weight(dominant) else (76, 76, 76)

    def luminance(rgb):
        levels = [channel / 255 for channel in rgb]
        linear = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in levels]
        return sum(channel * factor for channel, factor in zip(linear, (0.2126, 0.7152, 0.0722)))

    while 1.05 / (luminance(color) + 0.05) < 7:
        color = tuple(round(channel * 0.93) for channel in color)
    return color


def wrap_text(content, width, font, max_lines):
    lines = []
    for paragraph in content.split("\n"):
        remaining = paragraph
        while remaining:
            if len(lines) == max_lines:
                return None
            left, _, right, _ = font.getbbox(remaining)
            if right - left <= width:
                lines.append(remaining)
                break
            low, high = 0, len(remaining) - 1
            while low < high:
                middle = (low + high + 1) // 2
                left, _, right, _ = font.getbbox(remaining[:middle])
                if right - left <= width:
                    low = middle
                else:
                    high = middle - 1
            if low == 0:
                return None
            split = low
            if re.match(r"[A-Za-z0-9]", remaining[low]):
                partial_word = re.search(r"[A-Za-z0-9]+$", remaining[:low])
                if partial_word:
                    split = partial_word.start()
            while split and (remaining[split] in CLOSING_PUNCTUATION
                             or remaining[split - 1] in OPENING_PUNCTUATION):
                split -= 1
            if split == 0:
                return None
            lines.append(remaining[:split].rstrip())
            remaining = remaining[split:].lstrip()
    return lines


class Board:
    def __init__(self, spec, hero, logo, art, font_face, size):
        self.spec = spec
        self.labels = spec["labels"]
        self.hero, self.logo, self.art = hero, logo, art
        self.font_path, self.font_index = font_face
        self.scale = max(1, size[0] / SIZE[0])
        self.size = size
        self.image = Image.new("RGB", (self.px(SIZE[0]), self.px(SIZE[1])), WHITE)
        self.draw = ImageDraw.Draw(self.image)
        self.accent = accent_color(flatten(hero), spec.get("palette", {}).get("accent"))

    def px(self, value):
        return round(value * self.scale)

    def coords(self, items):
        return tuple(self.px(item) for item in items)

    @lru_cache(maxsize=64)
    def font(self, size, bold):
        font = ImageFont.truetype(str(self.font_path), size, index=self.font_index)
        try:
            axes = font.get_variation_axes()
            weights = [axis["default"] for axis in axes]
            for index, axis in enumerate(axes):
                if b"weight" in axis["name"].lower():
                    weights[index] = min(axis["maximum"], max(axis["minimum"], 700 if bold else 400))
            font.set_variation_by_axes(weights)
        except (OSError, ValueError):
            pass
        return font

    def text(self, content, box, preferred, lines=1, bold=False, fill=INK, align="left"):
        x0, y0, x1, y1 = self.coords(box)
        low, high = 1, self.px(preferred)
        fit = None
        while low <= high:
            size = (low + high) // 2
            font = self.font(size, bold)
            strings = wrap_text(content, x1 - x0, font, lines)
            if strings:
                bounds = [self.draw.textbbox((0, 0), string, font=font) for string in strings]
                line_height = max(bottom - top for _, top, _, bottom in bounds)
                gap = max(1, size // 5)
                height = len(strings) * (line_height + gap) - gap
                if height <= y1 - y0:
                    fit = font, strings, bounds, line_height, gap, height
                    low = size + 1
                    continue
            high = size - 1
        if fit is None:
            raise ValueError(f"Text cannot fit its assigned area: {content!r}")
        font, strings, bounds, line_height, gap, height = fit
        y = y0 + (y1 - y0 - height) // 2
        ink_right = x0
        for string, (left, top, right, bottom) in zip(strings, bounds):
            text_width = right - left
            x = x0
            if align == "right":
                x = x1 - text_width
            elif align == "center":
                x = x0 + (x1 - x0 - text_width) // 2
            row_offset = (line_height - (bottom - top)) // 2
            self.draw.text((x - left, y - top + row_offset), string, font=font, fill=fill)
            y += line_height + gap
            ink_right = max(ink_right, x + text_width)
        return ink_right / self.scale

    def rule(self, box, color=RULE, width=2):
        self.draw.line(self.coords(box), fill=color, width=self.px(width))

    def rectangle(self, box, color, outline=None, width=1):
        self.draw.rectangle(self.coords(box), fill=color, outline=outline, width=self.px(width))

    def heading(self, content, x, y, right, extend=False):
        self.rectangle((x, y + 12, x + 12, y + 53), self.accent)
        end = self.text(content, (x + 34, y, right, y + 65), 48, bold=True, fill=self.accent)
        if extend and end + 64 < right:
            self.rule((end + 38, y + 35, right, y + 35))

    def paste(self, image, box, cover=False, bottom_align=False):
        x0, y0, x1, y1 = self.coords(box)
        target = (x1 - x0, y1 - y0)
        if cover:
            scaled = ImageOps.fit(image, target, method=RESAMPLE)
        else:
            ratio = min(target[0] / image.width, target[1] / image.height)
            scaled = image.resize((max(1, round(image.width * ratio)),
                                   max(1, round(image.height * ratio))), RESAMPLE)
        left = x0 + (target[0] - scaled.width) // 2
        vertical_space = target[1] - scaled.height
        top = y0 + (vertical_space if bottom_align else vertical_space // 2)
        mask = scaled.getchannel("A") if scaled.mode == "RGBA" else None
        self.image.paste(scaled, (left, top), mask)
        return tuple(value / self.scale for value in (left, top, left + scaled.width, top + scaled.height))

    def diagram(self, filename, box, name, bottom_align=False):
        if filename in self.art:
            return self.paste(self.art[filename], box, bottom_align=bottom_align)
        x0, y0, x1, y1 = box
        self.rectangle(box, MATTE, RULE, width=2)
        self.text(f'{self.labels["missing_asset"]}\n{name}',
                  (x0 + 16, y0 + 12, x1 - 16, y1 - 12), 27,
                  lines=3, fill=MUTED, align="center")
        return box

    def header(self):
        has_logo = self.logo is not None
        if has_logo:
            self.paste(self.logo, (LEFT, 48, 180, 148))
        if self.spec.get("brand_name"):
            self.text(self.spec["brand_name"], (204 if has_logo else LEFT, 48, RIGHT, 148),
                      56, bold=True)
        self.rectangle((LEFT, 222, LEFT + 12, 398), self.accent)
        title = f'{self.spec["theme"]}·{self.labels["title_suffix"]}'
        end = self.text(title, (124, 214, RIGHT, 337), 70, lines=2, bold=True, fill=self.accent)
        if end + 70 < RIGHT:
            self.rule((end + 48, 276, RIGHT, 276), self.accent)
        self.text(" / ".join(self.spec["subtitle_elements"]), (124, 345, RIGHT, 407), 41, lines=2)

    def dimension_label(self, key, vertical=False):
        measure = self.spec["dimensions"][key]
        label = f'{measure["label"]} {key}'
        value = measure["value"] or self.labels["pending_measurement"]
        bracketed = f"（{value}）" if self.spec["language"].lower().startswith("zh") else f"({value})"
        return label + ("\n" if vertical else " ") + bracketed

    def dimension_line(self, start, end, axis, vertical=False):
        def point(along, across):
            return (across, along) if vertical else (along, across)

        self.rule(point(start, axis) + point(end, axis), INK)
        tip = min(12, (end - start) / 3)
        for edge, sign in ((start, 1), (end, -1)):
            self.rule(point(edge, axis - 9) + point(edge, axis + 9), INK)
            vertices = [point(edge, axis), point(edge + sign * tip, axis - 5),
                        point(edge + sign * tip, axis + 5)]
            self.draw.polygon([self.coords(vertex) for vertex in vertices], fill=INK)

    def diagrams(self, cover):
        self.rectangle((LEFT, 474, 1290, 1328), MATTE)
        self.paste(self.hero, (LEFT, 474, 1290, 1328), cover=cover)
        elevation = self.spec["views"]["elevation"]["heading"]
        self.heading(elevation, 1360, 439, RIGHT)
        x0, y0, x1, y1 = self.diagram("elevation.png", (1510, 517, 2065, 765), elevation)
        self.dimension_line(y0, y1, x0 - 21, vertical=True)
        middle = (y0 + y1) / 2
        vertical_lines = 2 if self.spec["language"].lower().startswith("zh") else 5
        self.text(self.dimension_label("H", True), (1360, middle - 65, 1490, middle + 65),
                  29, lines=vertical_lines, align="center")
        self.dimension_line(x0, x1, y1 + 18)
        self.text(self.dimension_label("W"), (1484, y1 + 33, RIGHT, 849),
                  29, lines=2, align="center")

        plan = self.spec["views"]["plan"]["heading"]
        self.heading(plan, 1360, 856, RIGHT)
        x0, y0, x1, y1 = self.diagram("plan.png", (1360, 935, 1942, 1323), plan)
        self.dimension_line(y0, y1, 1964, vertical=True)
        middle = (y0 + y1) / 2
        self.text(self.dimension_label("D", True), (1979, middle - 68, RIGHT, middle + 68),
                  29, lines=vertical_lines, align="center")
        span = self.spec["views"]["plan"].get("aisle_span") or (0.39, 0.61)
        start, end = [x0 + float(ratio) * (x1 - x0) for ratio in span]
        self.dimension_line(start, end, y1 + 17)
        self.text(self.dimension_label("A"), (1360, y1 + 32, 1942, 1408),
                  29, lines=2, align="center")

    def material_table(self):
        self.heading(self.labels["materials"], LEFT, 1440, 826)
        left, split, right = LEFT, 386, 826
        top, header_height = 1535, 80
        rows = self.spec["materials"]
        row_height = min(95, (2164 - top - header_height) // len(rows))
        self.rectangle((left, top, right, top + header_height), MATTE)
        self.text(self.labels["material_name"], (left + 28, top, split - 18, top + header_height),
                  33, lines=2, bold=True)
        self.text(self.labels["material_detail"], (split + 30, top, right - 20, top + header_height),
                  33, lines=2, bold=True)
        top += header_height
        self.rule((split, top - header_height + 12, split, top + row_height * len(rows)))
        for row in rows:
            bottom = top + row_height
            self.rule((left, top, right, top))
            self.text(row["name"], (left + 28, top + 4, split - 18, bottom - 4),
                      32, lines=2, bold=True)
            self.text(row["detail"], (split + 30, top + 4, right - 16, bottom - 4),
                      31, lines=2)
            top = bottom
        self.rule((left, top, right, top))

    def component_grid(self):
        self.heading(self.labels["components"], 884, 1440, RIGHT)
        width = (RIGHT - 884 - 2 * 26) // 3
        for index, component in enumerate(self.spec["components"]):
            row, col = divmod(index, 3)
            left = 884 + col * (width + 26)
            right = left + width
            top = 1535 + row * 311
            self.rule((left, top, right, top))
            self.diagram(f"component-{index + 1:02d}.png",
                         (left + 16, top + 18, right - 16, top + 238), component["name"])
            self.text(component["name"], (left + 8, top + 245, right - 8, top + 299),
                      35, lines=2, bold=True, align="center")
            if row == 1:
                self.rule((left, top + 311, right, top + 311))

    def setup_sequence(self):
        self.heading(self.labels["steps"], LEFT, 2225, RIGHT, extend=True)
        gap = 46
        width = (RIGHT - LEFT - gap * 4) // 5
        for step in self.spec["steps"]:
            number = step["number"]
            left = LEFT + (number - 1) * (width + gap)
            right = left + width
            self.draw.ellipse(self.coords((left, 2340, left + 55, 2395)), fill=self.accent)
            self.text(str(number), (left + 2, 2340, left + 53, 2395),
                      33, bold=True, fill=WHITE, align="center")
            self.text(step["name"], (left + 70, 2331, right, 2404), 38, lines=2, bold=True)
            self.diagram(f"step-{number:02d}.png", (left, 2420, right, 2640),
                         step["name"], bottom_align=True)
            self.text(step["description"], (left, 2652, right, 2742), 30, lines=2, align="center")
            if number < len(self.spec["steps"]):
                center = right + gap / 2
                self.rule((center - 6, 2517, center + 6, 2530), self.accent, width=4)
                self.rule((center + 6, 2530, center - 6, 2543), self.accent, width=4)
        self.rule((LEFT, 2780, RIGHT, 2780))
        self.text(self.labels["disclaimer"], (LEFT, 2794, RIGHT, 2846),
                  27, lines=2, fill=MUTED, align="right")

    def render(self, cover):
        self.header()
        self.diagrams(cover)
        self.material_table()
        self.component_grid()
        self.setup_sequence()
        if self.image.size == self.size:
            return self.image
        return self.image.resize(self.size, RESAMPLE)


def save_png(image, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent, suffix=".png", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        image.save(temporary, format="PNG")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, type=Path, help="Validated decor-spec.json file.")
    parser.add_argument("--original", required=True, type=Path, help="An original RGB or RGBA scene image.")
    parser.add_argument("--assets", required=True, type=Path, help="Directory of named illustration PNGs.")
    parser.add_argument("--output", required=True, type=Path, help="Destination PNG.")
    parser.add_argument("--logo", type=Path, help="Optional logo image, including PNG transparency.")
    parser.add_argument("--font", type=Path, help="Optional TTF, OTF, TTC or OTC font.")
    parser.add_argument("--size", type=board_size, default=SIZE, help="3:4 portrait size. Default: 2160x2880.")
    parser.add_argument("--hero-fit", choices=("contain", "cover"), default="contain",
                        help="Show the entire original or center-crop it to the main frame.")
    args = parser.parse_args()
    paths = art_paths(args.assets)
    inputs = [args.spec, args.original, args.logo, args.font, *paths]
    if args.output.suffix.lower() != ".png":
        parser.error("--output must end with .png.")
    if args.output.resolve() in {path.resolve() for path in inputs if path is not None}:
        parser.error("--output would replace an input file.")
    try:
        spec = load_spec(args.spec)
        font = find_font(args.font, spec)
        hero = read_image(args.original)
        logo = read_image(args.logo) if args.logo else None
        art, missing = stage_images(paths, spec)
        board = Board(spec, hero, logo, art, font, args.size)
        save_png(board.render(args.hero_fit == "cover"), args.output)
    except IMAGE_ERRORS as error:
        print(f"Could not compose the board: {error}", file=sys.stderr)
        return 1
    print(f"Wrote {args.output} ({args.size[0]}x{args.size[1]}) with font {font[0]}.")
    if missing:
        print(f"Placeholders ({len(missing)} of 13):")
        for filename, reason in missing:
            print(f"  {filename} — {reason}")
    else:
        print("All 13 illustrations placed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
