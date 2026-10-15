"""Regenerate both launchers from the existing stroked Glean SVG.

Run from app/: uv run --with cairosvg --with pillow python scripts/generate_launcher_icons.py
CairoSVG preserves strokes (unlike the old ImageMagick pipeline, PR #90).
"""
from io import BytesIO
import json
from pathlib import Path

import cairosvg
from PIL import Image

APP = Path(__file__).resolve().parents[1]
master = Image.open(BytesIO(cairosvg.svg2png(
    url=str(APP / 'assets/brand/glean-b1-icon.svg'),
    output_width=1024,
    output_height=1024,
))).convert('RGB')  # iOS store icon must have no alpha channel.

icons = APP / 'ios/Runner/Assets.xcassets/AppIcon.appiconset'
for icon in json.loads((icons / 'Contents.json').read_text())['images']:
    if 'filename' not in icon:
        continue
    size = round(float(icon['size'].split('x')[0]) * float(icon['scale'].rstrip('x')))
    master.resize((size, size), Image.Resampling.LANCZOS).save(icons / icon['filename'])

res = APP / 'android/app/src/main/res'
for density, size in [('mdpi', 48), ('hdpi', 72), ('xhdpi', 96), ('xxhdpi', 144), ('xxxhdpi', 192)]:
    master.resize((size, size), Image.Resampling.LANCZOS).save(res / f'mipmap-{density}/ic_launcher.png')
print('Generated iOS and Android launcher icons from Glean SVG (strokes retained).')
