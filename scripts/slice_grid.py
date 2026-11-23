"""Cut a component or setup contact sheet into equally divided PNGs in reading order."""

import argparse
import sys
import tempfile
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ModuleNotFoundError as error:
    sys.exit(f"{error.name} is unavailable. Install Pillow with python -m pip install 'Pillow>=9.1'.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Input contact sheet.")
    parser.add_argument("--output-dir", required=True, type=Path, help="Directory for illustration PNGs.")
    parser.add_argument("--kind", required=True, choices=("components", "steps"),
                        help="Six component cells or five step cells. Ignore a sixth step cell.")
    parser.add_argument("--rows", type=int, default=2, help="Number of grid rows. Default: 2.")
    parser.add_argument("--cols", type=int, default=3, help="Number of grid columns. Default: 3.")
    parser.add_argument("--inset", type=int, default=0, help="Pixels to remove from each edge of each cell.")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing output names.")
    args = parser.parse_args()
    if min(args.rows, args.cols) < 1 or args.inset < 0:
        parser.error("Rows and columns must be positive, and inset must be non-negative.")
    count, stem = (6, "component") if args.kind == "components" else (5, "step")
    allowed = {6} if args.kind == "components" else {5, 6}
    if args.rows * args.cols not in allowed:
        parser.error(f"{args.kind} need {' or '.join(map(str, sorted(allowed)))} equal cells.")
    destinations = [args.output_dir / f"{stem}-{index:02d}.png" for index in range(1, count + 1)]
    if args.input.resolve() in {path.resolve() for path in destinations}:
        parser.error("The output would overwrite the contact sheet.")
    existing = [path.name for path in destinations if path.exists()]
    if existing and not args.overwrite:
        parser.error(f"Outputs already exist ({', '.join(existing)}). Choose another directory or use --overwrite.")
    try:
        with Image.open(args.input) as source:
            sheet = ImageOps.exif_transpose(source).convert("RGBA")
        width, height = sheet.size
        if min(width // args.cols, height // args.rows) <= args.inset * 2:
            raise ValueError("Grid cells are too small for the requested inset.")
        args.output_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".slice-", dir=args.output_dir) as temporary:
            staging = Path(temporary)
            for index, destination in enumerate(destinations):
                row, col = divmod(index, args.cols)
                bounds = (
                    col * width // args.cols + args.inset,
                    row * height // args.rows + args.inset,
                    (col + 1) * width // args.cols - args.inset,
                    (row + 1) * height // args.rows - args.inset,
                )
                sheet.crop(bounds).save(staging / destination.name, format="PNG")
            for destination in destinations:
                (staging / destination.name).replace(destination)
    except (OSError, ValueError, Image.DecompressionBombError) as error:
        print(f"Could not slice the grid: {error}", file=sys.stderr)
        return 1
    print(f"Wrote {count} files to {args.output_dir}: {destinations[0].name} … {destinations[-1].name}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
