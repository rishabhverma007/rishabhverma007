#!/usr/bin/env python3
"""
generate_ascii_profile.py
Build an advanced, customizable GitHub profile neofetch SVG card or typing portrait.
Reads details from README.md, processes any photo with contrast and shadow lifting,
and generates responsive dark/light mode SVGs with blinking terminal prompt and typing animations.

Requirements: Pillow (PIL)
Usage:
  python generate_ascii_profile.py --mode profile
  python generate_ascii_profile.py --mode simple --image my_photo.png
"""

import os
import sys
import re
import glob
import argparse
import urllib.request
from PIL import Image, ImageOps, ImageEnhance

# ----------------------------------------------------------------------------
# Constants & Theme Configurations
# ----------------------------------------------------------------------------
IMAGE_EXTS = ("*.jpg", "*.jpeg", "*.png", "*.gif", "*.bmp", "*.webp", "*.tif", "*.tiff")
RAMP = " .'`^\",:;Il!i~+_-?][}{1)(|/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"

# Monospace character advance settings
ASCII_CW = 7.2    # Character width in px for portrait (small font)
ASCII_LH = 12.0   # Line height in px for portrait
ASCII_FS = 11     # Font size in px for portrait

CW = 9.2          # Character width in px for info panel (large font)
LH = 20.0         # Line height in px for info panel
FS = 14           # Font size in px for info panel

THEMES = {
    "dark": {
        "bg": "#0d1117",      # GitHub dark bg
        "text": "#8b949e",    # ASCII gray text
        "key": "#ff7b72",     # Orange/red keys
        "value": "#79c0ff",   # Blue values
        "cc": "#30363d",      # Gray dots & brackets
        "add": "#3fb950",     # Green cursor / add stats
        "dele": "#f85149"     # Red delete stats
    },
    "light": {
        "bg": "#ffffff",      # GitHub light bg
        "text": "#57606a",    # ASCII gray text
        "key": "#cf222e",     # Red keys
        "value": "#0969da",   # Blue values
        "cc": "#d0d7de",      # Gray dots & brackets
        "add": "#1a7f37",     # Green cursor / add stats
        "dele": "#cf222e"     # Red delete stats
    }
}

# ----------------------------------------------------------------------------
# Helper: XML Escape
# ----------------------------------------------------------------------------
def esc(s):
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;")
             .replace("'", "&apos;"))

# ----------------------------------------------------------------------------
# GitHub Avatar Downloader
# ----------------------------------------------------------------------------
def download_github_avatar(username, dest_path):
    url = f"https://github.com/{username}.png"
    try:
        print(f"-> Downloading GitHub avatar for '{username}'...")
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req) as response:
            with open(dest_path, 'wb') as f:
                f.write(response.read())
        print(f"[ok] Downloaded avatar to: {dest_path}")
        return True
    except Exception as e:
        print(f"[error] Error downloading avatar from GitHub: {e}")
        return False

# ----------------------------------------------------------------------------
# Image Auto-detection
# ----------------------------------------------------------------------------
def find_newest_image(folder):
    candidates = []
    for ext in IMAGE_EXTS:
        candidates.extend(glob.glob(os.path.join(folder, ext)))
        candidates.extend(glob.glob(os.path.join(folder, ext.upper())))
    
    # Exclude generated SVG files
    candidates = [c for c in set(candidates) if not c.lower().endswith(".svg")]
    if not candidates:
        return None
    return max(candidates, key=os.path.getmtime)

# ----------------------------------------------------------------------------
# Image Processing & ASCII Conversion
# ----------------------------------------------------------------------------
def image_to_ascii(path, cols, char_aspect=0.6, contrast=1.25, gamma=0.55):
    """
    Reads an image, adjusts contrast and lifts shadows, crops to center,
    resizes to cols, and maps pixels to ASCII characters.
    """
    try:
        im = Image.open(path)
    except Exception as e:
        print(f"[error] Failed to open image {path}: {e}")
        sys.exit(1)
        
    # Handle transparency by pasting onto white background
    if im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info):
        im = im.convert('RGBA')
        background = Image.new("RGBA", im.size, (255, 255, 255, 255))
        background.paste(im, mask=im.split()[-1])
        im = background.convert('L')
    else:
        im = im.convert('L')

    # Apply gamma correction to lift shadows
    if gamma != 1.0:
        im = im.point(lambda v: int(((v / 255.0) ** gamma) * 255))

    # Apply autocontrast to maximize dynamic range
    im = ImageOps.autocontrast(im, cutoff=2)

    # Boost contrast if requested
    if contrast != 1.0:
        im = ImageEnhance.Contrast(im).enhance(contrast)

    # Square center-crop the image to avoid stretching the face
    w, h = im.size
    min_dim = min(w, h)
    left = (w - min_dim) // 2
    top = (h - min_dim) // 2
    im = im.crop((left, top, left + min_dim, top + min_dim))

    # Resize to targets
    # Since monospace characters are taller than they are wide, we compress the height mapping
    target_width = cols
    target_height = max(1, int(cols * (im.size[1] / im.size[0]) * char_aspect))
    im = im.resize((target_width, target_height), Image.Resampling.LANCZOS)

    px = im.load()
    n = len(RAMP) - 1
    rows = []
    
    for y in range(target_height):
        chars = []
        for x in range(target_width):
            lum = px[x, y]
            # Map bright pixels (high lum) to spaces (beginning of RAMP)
            # and dark pixels (low lum) to dense characters (end of RAMP)
            idx = int((255 - lum) / 255.0 * n)
            chars.append(RAMP[idx])
        rows.append("".join(chars).rstrip())
        
    return rows

# ----------------------------------------------------------------------------
# Information Parser: Parses README.md
# ----------------------------------------------------------------------------
def parse_readme_info(readme_path, github_username):
    """
    Parses details from README.md. Falls back to default profile settings
    tailored for Rishabh Verma if fields are missing or parsing fails.
    """
    info = []
    
    # Default Fallbacks
    name = "Rishabh Verma"
    role = "AI / ML Engineer"
    education = "B.Tech CSE (Artificial Intelligence)"
    languages = "Python, C++, SQL, JavaScript"
    frameworks = "PyTorch, TensorFlow, OpenCV, FastAPI"
    tools = "Docker, Git, GCP, Ollama, HuggingFace"
    email = "rishabh300verma@gmail.com"
    linkedin = "rishabhverma007"
    github = github_username
    
    projects = [
        ("VisionFit AI", "AI Fitness Coach & Pose Detector"),
        ("AI Study Comp", "AI Notes & PDF Chat Companion"),
        ("College ERP", "Django Academic Management ERP")
    ]
    
    if os.path.exists(readme_path):
        try:
            with open(readme_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Parse YAML-like block if present
            yaml_match = re.search(r"```yaml\s*\n(.*?)\n```", content, re.DOTALL)
            if yaml_match:
                yaml_text = yaml_match.group(1)
                
                # Parse Name
                name_m = re.search(r"Name:\s*\n\s*[-•]?\s*([^\n\r]+)", yaml_text)
                if name_m: name = name_m.group(1).strip()
                
                # Parse Role
                role_m = re.search(r"Role:\s*\n\s*[-•]?\s*([^\n\r]+)", yaml_text)
                if role_m: role = role_m.group(1).strip()
                
                # Parse Education
                edu_m = re.search(r"Education:\s*\n\s*[-•]?\s*([^\n\r]+)", yaml_text)
                if edu_m: education = edu_m.group(1).strip()
            
            # Parse Email from badges or text
            email_m = re.search(r"mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", content)
            if email_m: email = email_m.group(1).strip()

            # Parse LinkedIn Username
            li_m = re.search(r"linkedin\.com/in/([a-zA-Z0-9\-_]+)", content)
            if li_m: linkedin = li_m.group(1).strip()
            
            # Parse GitHub Username from repository references
            gh_m = re.search(r"github\.com/([a-zA-Z0-9\-_]+)", content)
            if gh_m: github = gh_m.group(1).strip()
            
        except Exception as e:
            print(f"[warning] Warning parsing README.md: {e}. Using defaults.")

    # Format the INFO list
    info = [
        ("header", f"{github.lower()}@github"),
        ("kv", (["OS"], "macOS · Linux · Windows")),
        ("kv", (["Role"], role)),
        ("kv", (["Education"], education)),
        ("kv", (["Kernel"], "Neural Networks & LLMs")),
        ("kv", (["IDE"], "VSCode, Cursor, PyCharm")),
        ("blank", None),
        ("kv", (["Languages"], languages)),
        ("kv", (["AI & ML"], frameworks)),
        ("kv", (["Tools"], tools)),
        ("blank", None),
        ("kv", (["Hobbies"], "Open Source, AI Agents, Dev Tools")),
        ("blank", None),
        ("section", "Contact"),
        ("kv", (["Email"], email)),
        ("kv", (["LinkedIn"], linkedin)),
        ("kv", (["GitHub"], github)),
        ("blank", None),
        ("section", "Featured Projects"),
    ]
    
    # Add projects dynamically
    for p_name, p_desc in projects:
        info.append(("kv", (["Project", p_name.split()[0]], p_desc)))
        
    info.extend([
        ("blank", None),
        ("section", "GitHub Stats"),
        ("stats1", None),
        ("stats2", None),
        ("stats3", None)
    ])
    
    return info

# ----------------------------------------------------------------------------
# Dotted Leaders Alignment Helper
# ----------------------------------------------------------------------------
def get_dots_and_length(keys, value, value_col=24):
    key_txt = ".".join(keys)
    prefix_len = 2 + len(key_txt) + 1  # count: ". " + key_txt + ":"
    dots = max(1, value_col - prefix_len)
    
    # Clean text characters count representation
    char_len = prefix_len + dots + 1 + len(value)
    return dots, char_len

# ----------------------------------------------------------------------------
# SVG Generation Functions
# ----------------------------------------------------------------------------
def generate_simple_typing_svg(ascii_rows, theme_name, out_path):
    """
    Generates a simple typing portrait where each row revealed sequentially (Script A style).
    """
    t = THEMES[theme_name]
    n_rows = len(ascii_rows)
    max_cols = max((len(r) for r in ascii_rows), default=1)
    
    pad = 16
    row_duration = 0.15 # speed of typing
    look_hold = 1.5     # freeze duration at the end
    
    art_w = max_cols * ASCII_CW
    art_h = n_rows * ASCII_LH
    svg_w = int(art_w + pad * 2)
    svg_h = int(art_h + pad * 2)
    
    total_time = n_rows * row_duration + look_hold
    
    parts = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h}" '
        f'viewBox="0 0 {svg_w} {svg_h}" font-family="monospace">'
    )
    parts.append(f'<rect width="100%" height="100%" fill="{t["bg"]}" rx="10"/>')
    parts.append(
        f'<style>'
        f'text{{font-family:Menlo,Consolas,"JetBrains Mono","Fira Code",monospace;'
        f'font-size:{ASCII_FS}px;white-space:pre;dominant-baseline:hanging;}}'
        f'</style>'
    )
    
    for i, row in enumerate(ascii_rows):
        y = pad + i * ASCII_LH
        start = i * row_duration
        row_len = max(len(row), 1)
        row_px = row_len * ASCII_CW
        
        # Reveal rect clipPath
        clip_id = f"c{i}"
        parts.append(
            f'<clipPath id="{clip_id}">'
            f'<rect x="{pad}" y="{y}" width="0" height="{ASCII_LH}">'
            f'<animate attributeName="width" from="0" to="{row_px:.1f}" '
            f'begin="{start:.3f}s" dur="{row_duration:.3f}s" '
            f'fill="freeze" calcMode="linear"/>'
            f'</rect>'
            f'</clipPath>'
        )
        
        # Row text
        parts.append(
            f'<text x="{pad}" y="{y}" fill="{t["text"]}" clip-path="url(#{clip_id})" '
            f'xml:space="preserve">{esc(row)}</text>'
        )
        
        # Sweeping cursor for row
        parts.append(
            f'<rect y="{y}" width="{ASCII_CW:.1f}" height="{ASCII_FS}" fill="{t["add"]}" opacity="0">'
            f'<animate attributeName="x" from="{pad}" to="{pad + row_px:.1f}" begin="{start:.3f}s" '
            f'dur="{row_duration:.3f}s" fill="freeze"/>'
            f'<set attributeName="opacity" to="0.85" begin="{start:.3f}s"/>'
            f'<set attributeName="opacity" to="0" begin="{start + row_duration:.3f}s"/>'
            f'</rect>'
        )
        
    parts.append('</svg>')
    
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
        
    return total_time


def generate_neofetch_profile_svg(ascii_rows, info_list, theme_name, out_path, animate_typing=True):
    """
    Generates a full side-by-side neofetch style card (Script B style).
    - Left side: Static ASCII art portrait (fully visible).
    - Right side: Info details. Can optionally type out row-by-row.
    - Bottom: Blinking green terminal cursor.
    """
    t = THEMES[theme_name]
    
    # Sizing metrics
    # ASCII Portrait dimensions
    portrait_rows = len(ascii_rows)
    portrait_cols = max((len(r) for r in ascii_rows), default=1)
    
    portrait_w = portrait_cols * ASCII_CW
    portrait_h = portrait_rows * ASCII_LH
    
    # Overall card sizing
    pad_x = 24
    pad_y = 28
    info_x = int(portrait_w + pad_x + 36) # Position of right panel
    
    # Calculate right panel dimensions
    info_rows_count = len(info_list)
    right_panel_h = info_rows_count * LH
    
    svg_w = int(info_x + 480) # total width
    svg_h = int(max(portrait_h, right_panel_h) + pad_y * 2 + 30) # leave space for blinking cursor prompt
    
    # Layout calculation helper for right panel
    value_col = 22 # dot padding align column
    line_duration = 0.16 # seconds to type one line
    
    parts = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}px" height="{svg_h}px" '
        f'viewBox="0 0 {svg_w} {svg_h}">'
    )
    
    # Modern card border and background
    parts.append(
        f'<rect width="100%" height="100%" fill="{t["bg"]}" rx="12" '
        f'stroke="{t["cc"]}" stroke-width="1.5"/>'
    )
    
    # CSS Stylesheet
    parts.append(
        f'<style>'
        f'.key{{fill:{t["key"]}; font-weight:bold;}} '
        f'.value{{fill:{t["value"]};}} '
        f'.cc{{fill:{t["cc"]};}} '
        f'.add{{fill:{t["add"]};}} '
        f'.del{{fill:{t["dele"]};}} '
        f'text, tspan{{white-space:pre; font-family:"Fira Code","JetBrains Mono",Consolas,monospace;}} '
        f'</style>'
    )
    
    # ------------------------------------------------------------------------
    # Left Panel: Static ASCII portrait
    # ------------------------------------------------------------------------
    parts.append(
        f'<text x="{pad_x}" y="{pad_y}" fill="{t["text"]}" font-size="{ASCII_FS}px" '
        f'line-height="{ASCII_LH}px" xml:space="preserve">'
    )
    y_pos = pad_y
    for row in ascii_rows:
        parts.append(f'<tspan x="{pad_x}" y="{y_pos}">{esc(row)}</tspan>')
        y_pos += ASCII_LH
    parts.append('</text>')
    
    # ------------------------------------------------------------------------
    # Right Panel: Terminal info rows
    # ------------------------------------------------------------------------
    info_y_start = pad_y + 10
    current_y = info_y_start
    
    # Timing records
    timings = []
    
    for i, (kind, payload) in enumerate(info_list):
        start_time = i * line_duration if animate_typing else 0.0
        
        # Initialize placeholders
        tspan_body = ""
        char_len = 0
        
        if kind == "header":
            # OS header style (e.g. user@host)
            # length of line = len(payload) + dash length + 2
            dash_count = 35 - len(payload)
            dash = "—" * max(4, dash_count)
            tspan_body = (
                f'<tspan fill="{t["add"]}" font-weight="bold">{esc(payload)}</tspan>'
                f'<tspan class="cc"> -{dash}-</tspan>'
            )
            char_len = len(payload) + len(dash) + 2
            
        elif kind == "section":
            # Section separators (e.g. - Contact -)
            dash_count = 35 - len(payload) - 2
            dash = "—" * max(4, dash_count)
            tspan_body = (
                f'<tspan class="cc">- </tspan>'
                f'<tspan fill="{t["text"]}" font-weight="bold">{esc(payload)}</tspan>'
                f'<tspan class="cc"> -{dash}-</tspan>'
            )
            char_len = len(payload) + len(dash) + 4
            
        elif kind == "blank":
            tspan_body = '<tspan class="cc">. </tspan>'
            char_len = 2
            
        elif kind == "kv":
            keys, value = payload
            key_txt = ".".join(keys)
            dots, char_len = get_dots_and_length(keys, value, value_col)
            
            key_spans = (
                '<tspan class="key">' + 
                '</tspan>.<tspan class="key">'.join(esc(k) for k in keys) + 
                '</tspan>'
            )
            
            tspan_body = (
                f'<tspan class="cc">. </tspan>{key_spans}'
                f'<tspan class="cc">:</tspan>'
                f'<tspan class="cc">{"." * dots} </tspan>'
                f'<tspan class="value">{esc(value)}</tspan>'
            )
            
        elif kind == "stats1":
            # GitHub custom mockup stats line 1
            tspan_body = (
                f'<tspan class="cc">. </tspan>'
                f'<tspan class="key">Repos</tspan>'
                f'<tspan class="cc"> ..... </tspan>'
                f'<tspan class="value">34</tspan>'
                f'<tspan class="cc"> | </tspan>'
                f'<tspan class="key">Stars</tspan>'
                f'<tspan class="cc"> ...... </tspan>'
                f'<tspan class="value">12</tspan>'
            )
            char_len = 38
            
        elif kind == "stats2":
            # GitHub custom mockup stats line 2
            tspan_body = (
                f'<tspan class="cc">. </tspan>'
                f'<tspan class="key">Commits</tspan>'
                f'<tspan class="cc"> ... </tspan>'
                f'<tspan class="value">1,408</tspan>'
                f'<tspan class="cc"> | </tspan>'
                f'<tspan class="key">Followers</tspan>'
                f'<tspan class="cc"> .. </tspan>'
                f'<tspan class="value">45</tspan>'
            )
            char_len = 42
            
        elif kind == "stats3":
            # GitHub custom mockup stats line 3
            tspan_body = (
                f'<tspan class="cc">. </tspan>'
                f'<tspan class="key">Member</tspan>'
                f'<tspan class="cc"> .... </tspan>'
                f'<tspan class="value">2023</tspan>'
                f'<tspan class="cc"> | </tspan>'
                f'<tspan class="key">Location</tspan>'
                f'<tspan class="cc"> ... </tspan>'
                f'<tspan class="value">India</tspan>'
            )
            char_len = 41
            
        line_px = char_len * CW
        timings.append((start_time, line_px, current_y))
        
        # Render the text line
        if animate_typing:
            clip_id = f"cliplist-{i}"
            parts.append(
                f'<clipPath id="{clip_id}">'
                f'<rect x="{info_x}" y="{current_y - FS}" width="0" height="{LH + 4}">'
                f'<animate attributeName="width" from="0" to="{line_px:.1f}" '
                f'begin="{start_time:.3f}s" dur="{line_duration:.3f}s" fill="freeze" calcMode="linear"/>'
                f'</rect>'
                f'</clipPath>'
            )
            parts.append(
                f'<text x="{info_x}" y="{current_y}" fill="{t["text"]}" font-size="{FS}px" '
                f'clip-path="url(#{clip_id})">{tspan_body}</text>'
            )
            
            # Sweeping typing cursor for this line
            parts.append(
                f'<rect y="{current_y - FS + 2}" width="{CW:.1f}" height="{FS + 2}" fill="{t["add"]}" opacity="0">'
                f'<animate attributeName="x" from="{info_x}" to="{info_x + line_px:.1f}" begin="{start_time:.3f}s" '
                f'dur="{line_duration:.3f}s" fill="freeze"/>'
                f'<set attributeName="opacity" to="0.85" begin="{start_time:.3f}s"/>'
                f'<set attributeName="opacity" to="0" begin="{start_time + line_duration:.3f}s"/>'
                f'</rect>'
            )
        else:
            parts.append(
                f'<text x="{info_x}" y="{current_y}" fill="{t["text"]}" font-size="{FS}px">{tspan_body}</text>'
            )
            
        current_y += LH

    # ------------------------------------------------------------------------
    # Bottom: Terminal prompt typing & Blinking Cursor
    # ------------------------------------------------------------------------
    prompt_y = current_y + 12
    prompt_text = f"{info_list[0][1].split('@')[0]}@home:~$ "
    prompt_len = len(prompt_text)
    prompt_px = prompt_len * CW
    
    prompt_start = info_rows_count * line_duration if animate_typing else 0.0
    prompt_duration = 0.3
    cursor_start = prompt_start + (prompt_duration if animate_typing else 0.0)
    
    # Draw terminal prompt
    if animate_typing:
        clip_prompt_id = "clipprompt"
        parts.append(
            f'<clipPath id="{clip_prompt_id}">'
            f'<rect x="{info_x}" y="{prompt_y - FS}" width="0" height="{LH + 4}">'
            f'<animate attributeName="width" from="0" to="{prompt_px:.1f}" '
            f'begin="{prompt_start:.3f}s" dur="{prompt_duration:.3f}s" fill="freeze" calcMode="linear"/>'
            f'</rect>'
            f'</clipPath>'
        )
        parts.append(
            f'<text x="{info_x}" y="{prompt_y}" fill="{t["add"]}" font-weight="bold" font-size="{FS}px" '
            f'clip-path="url(#{clip_prompt_id})">{esc(prompt_text)}</text>'
        )
        
        # Cursor sweeping prompt
        parts.append(
            f'<rect y="{prompt_y - FS + 2}" width="{CW:.1f}" height="{FS + 2}" fill="{t["add"]}" opacity="0">'
            f'<animate attributeName="x" from="{info_x}" to="{info_x + prompt_px:.1f}" begin="{prompt_start:.3f}s" '
            f'dur="{prompt_duration:.3f}s" fill="freeze"/>'
            f'<set attributeName="opacity" to="0.85" begin="{prompt_start:.3f}s"/>'
            f'<set attributeName="opacity" to="0" begin="{prompt_start + prompt_duration:.3f}s"/>'
            f'</rect>'
        )
    else:
        parts.append(
            f'<text x="{info_x}" y="{prompt_y}" fill="{t["add"]}" font-weight="bold" font-size="{FS}px">{esc(prompt_text)}</text>'
        )
        
    # Final blinking block cursor
    parts.append(
        f'<rect x="{info_x + prompt_px}" y="{prompt_y - FS + 2}" width="{CW:.1f}" height="{FS + 2}" fill="{t["add"]}" opacity="0">'
        f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.5;1" dur="1.1s" '
        f'begin="{cursor_start:.3f}s" repeatCount="indefinite"/>'
        f'</rect>'
    )
    
    parts.append('</svg>')
    
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
        
    return cursor_start

# ----------------------------------------------------------------------------
# Main function
# ----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Advanced Git neofetch-style SVG Generator")
    parser.add_argument("--mode", choices=["simple", "profile"], default="profile",
                        help="Choose 'simple' for typing portrait only, or 'profile' for neofetch side-by-side style.")
    parser.add_argument("--image", default=None,
                        help="Path to portrait image. If omitted, the script auto-detects or downloads your GitHub avatar.")
    parser.add_argument("--username", default="rishabhverma007",
                        help="GitHub username to download avatar if no image is found (default: rishabhverma007).")
    parser.add_argument("--width", type=int, default=None,
                        help="Width of the ASCII art in characters (default: 56 for profile, 100 for simple).")
    parser.add_argument("--contrast", type=float, default=1.2,
                        help="Contrast adjustment multiplier (default: 1.2).")
    parser.add_argument("--gamma", type=float, default=0.55,
                        help="Gamma correction factor to lift shadows (default: 0.55).")
    parser.add_argument("--no-animation", action="store_true",
                        help="Disable typing reveal animation (profile values will render static immediately).")
    parser.add_argument("--readme", default="README.md",
                        help="Path to README.md to parse info details from.")
    parser.add_argument("--output-dir", default=".",
                        help="Directory to save generated SVGs.")
    
    args = parser.parse_args()
    
    # Establish width defaults
    if args.width is None:
        width = 56 if args.mode == "profile" else 100
    else:
        width = args.width

    # Create output dir if needed
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Find or download image
    image_path = args.image
    temp_image = False
    
    if not image_path:
        # 1. Search locally
        detected = find_newest_image(".")
        if detected:
            image_path = detected
            print(f"[ok] Auto-detected newest image: {image_path}")
        else:
            # 2. Download from GitHub
            temp_image_path = f"github_avatar_{args.username}.png"
            downloaded = download_github_avatar(args.username, temp_image_path)
            if downloaded:
                image_path = temp_image_path
                temp_image = True
            else:
                print("[error] No image found locally, and failed to download from GitHub.")
                print("  Please drop a JPG/PNG/WebP image in this folder or provide the --image argument.")
                sys.exit(1)
                
    # Run conversion
    print(f"-> Processing image '{image_path}' to ASCII (cols={width}, contrast={args.contrast}, gamma={args.gamma})...")
    char_aspect = 0.52
    ascii_rows = image_to_ascii(image_path, cols=width, char_aspect=char_aspect, contrast=args.contrast, gamma=args.gamma)
    
    if args.mode == "simple":
        out_file = os.path.join(args.output_dir, "ascii_typing_portrait.svg")
        print(f"-> Generating simple typing portrait SVG (dark theme)...")
        duration = generate_simple_typing_svg(ascii_rows, "dark", out_file)
        print(f"[ok] Successfully wrote {out_file} (duration ~{duration:.1f}s)")
        
    elif args.mode == "profile":
        print(f"-> Parsing details from '{args.readme}'...")
        info_list = parse_readme_info(args.readme, args.username)
        
        # Render Dark and Light mode SVGs
        for theme_name in ("dark", "light"):
            out_file = os.path.join(args.output_dir, f"{theme_name}_mode.svg")
            print(f"-> Generating side-by-side neofetch SVG ({theme_name} theme)...")
            duration = generate_neofetch_profile_svg(
                ascii_rows, 
                info_list, 
                theme_name, 
                out_file, 
                animate_typing=not args.no_animation
            )
            print(f"[ok] Successfully wrote {out_file} (animation starts blinking at ~{duration:.1f}s)")
            
    # Clean up temp GitHub download
    if temp_image and os.path.exists(image_path):
        try:
            os.remove(image_path)
            print("[ok] Cleaned up temporary downloaded avatar.")
        except Exception as e:
            print(f"[warning] Failed to delete temp avatar {image_path}: {e}")

if __name__ == "__main__":
    main()
