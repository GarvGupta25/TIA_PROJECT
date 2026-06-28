pip install opencv-python pillow numpy faker
import os
import random
import requests
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from faker import Faker

# Initialize Faker
fake = Faker()

# Configuration
OUTPUT_DIR = "realistic_invoices"
FONT_CURSIVE_PATH = "cursive.ttf"
# Updated to a highly stable, vintage cursive font URL
FONT_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/greatvibes/GreatVibes-Regular.ttf"
NUM_IMAGES = 50
BLUR_PROBABILITY = 0.2

os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- DEBUGGED: Auto-Download Font using 'requests' ---
if not os.path.exists(FONT_CURSIVE_PATH):
    print("Downloading natural cursive font...")
    response = requests.get(FONT_URL)
    if response.status_code == 200:
        with open(FONT_CURSIVE_PATH, 'wb') as f:
            f.write(response.content)
        print("Font downloaded successfully!\n")
    else:
        print(f"CRITICAL ERROR: Failed to download font. HTTP Status: {response.status_code}")

# Parameter lists derived from the dataset requirements
PARAM_OPTIONS = ["Food Allowance", "Housing Subsidy", "Overtime (OT)", "Transport", "Medical Coverage", "Internet Stipend"]

def apply_heavy_blur(image_path):
    img = cv2.imread(image_path)
    blurred_img = cv2.GaussianBlur(img, (21, 21), 0)
    cv2.imwrite(image_path, blurred_img)

def add_red_stamp(img):
    """Creates a semi-transparent red circular 'PAID' stamp to mimic the reference image."""
    stamp_overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    stamp_draw = ImageDraw.Draw(stamp_overlay)

    # Random placement for the stamp
    stamp_x = random.randint(300, 550)
    stamp_y = random.randint(500, 750)

    # Draw stamp circle and text
    stamp_color = (220, 20, 60, 150) # Red with transparency
    stamp_draw.ellipse([stamp_x, stamp_y, stamp_x + 180, stamp_y + 180], outline=stamp_color, width=4)
    stamp_draw.ellipse([stamp_x + 10, stamp_y + 10, stamp_x + 170, stamp_y + 170], outline=stamp_color, width=1)

    try:
        stamp_font = ImageFont.truetype(FONT_CURSIVE_PATH, 45)
    except:
        stamp_font = ImageFont.load_default()

    stamp_draw.text((stamp_x + 45, stamp_y + 65), "PAID", font=stamp_font, fill=stamp_color)

    # Blend the stamp over the main image
    return Image.alpha_composite(img.convert("RGBA"), stamp_overlay).convert("RGB")

def generate_realistic_invoice(index):
    width, height = 800, 1000

    # 1. Vintage Paper Background (Slightly yellowed/off-white)
    base_color = (245, 245, 235)
    img = Image.new("RGB", (width, height), base_color)
    draw = ImageDraw.Draw(img)

    try:
        # Increased font size slightly because 'Great Vibes' renders a bit smaller
        font_cursive = ImageFont.truetype(FONT_CURSIVE_PATH, random.randint(38, 44))
        font_printed = ImageFont.load_default()
    except IOError:
        print("CRITICAL ERROR: Font file not found. Halting generation.")
        return

    # Colors
    ink_color = (15, 25, 65) # Dark blue ballpoint pen
    print_color = (40, 40, 100) # Printed text color
    line_color = (130, 150, 180) # Light blue ledger lines

    # 2. Add Printed Letterhead
    draw.text((50, 40), "THE GENERAL SUPPLIES CO.", font=font_printed, fill=print_color)
    draw.text((50, 55), "123 INDUSTRIAL BLVD.", font=font_printed, fill=print_color)
    draw.text((50, 70), "CHICAGO, ILL.", font=font_printed, fill=print_color)

    # Printed Date line
    draw.text((550, 100), "Date:", font=font_printed, fill=print_color)
    draw.line([(590, 110), (750, 110)], fill=line_color, width=1)

    # Handwritten elements overlapping the printed lines
    draw.text((600, 75), fake.date_this_year().strftime('%b %d, %Y'), font=font_cursive, fill=ink_color)

    draw.text((50, 150), "To:", font=font_printed, fill=print_color)
    draw.line([(80, 160), (450, 160)], fill=line_color, width=1)
    draw.line([(80, 190), (450, 190)], fill=line_color, width=1)

    # Handwritten Name & Address overlapping lines
    draw.text((90, 120), f"Mr. {fake.name()}", font=font_cursive, fill=ink_color)
    draw.text((120, 150), fake.city(), font=font_cursive, fill=ink_color)

    # 3. Draw Ledger Lines (Mimicking the bottom half table structure)
    table_start_y = 250
    line_spacing = 40

    # Horizontal rules
    for y in range(table_start_y, height - 50, line_spacing):
        draw.line([(0, y), (width, y)], fill=line_color, width=2)

    # Vertical rules (Columns for Date, Desc, Amount)
    draw.line([(80, table_start_y), (80, height - 50)], fill=line_color, width=2)
    draw.line([(600, table_start_y), (600, height - 50)], fill=line_color, width=2)
    draw.line([(700, table_start_y), (700, height - 50)], fill=line_color, width=2)

    # 4. Populate Line Items along the ledger lines
    selected_params = random.sample(PARAM_OPTIONS, k=random.randint(2, 5))
    current_y = table_start_y + 5
    total_claim = 0

    for param in selected_params:
        amount = random.randint(15, 450)
        total_claim += amount

        # Jitter ensures handwriting doesn't sit perfectly on the printed lines
        y_jitter = random.randint(-10, -2)

        # Date column
        draw.text((10, current_y + y_jitter), f"{random.randint(1,12)}/{random.randint(1,28)}", font=font_cursive, fill=ink_color)
        # Description column
        draw.text((90, current_y + y_jitter), param, font=font_cursive, fill=ink_color)
        # Amount columns (Dollars / Cents split by vertical line)
        draw.text((630, current_y + y_jitter), str(amount), font=font_cursive, fill=ink_color)
        draw.text((715, current_y + y_jitter), "00", font=font_cursive, fill=ink_color)

        current_y += line_spacing

    # 5. Add Total
    draw.text((450, current_y - 10), "Total:", font=font_cursive, fill=ink_color)
    draw.text((630, current_y - 10), str(total_claim), font=font_cursive, fill=ink_color)

    # 6. Add Red "PAID" Stamp Overlay
    if random.random() > 0.3: # 70% chance to have a stamp
        img = add_red_stamp(img)

    # Add a tiny bit of global noise to make it look like a scan
    img_arr = np.array(img)
    noise = np.random.randint(0, 255, img_arr.shape, dtype='uint8')
    img_arr = cv2.addWeighted(img_arr, 0.97, noise, 0.03, 0)
    img = Image.fromarray(img_arr)

    # Save logic
    is_blurry = random.random() < BLUR_PROBABILITY
    status_tag = "REJECT_BLUR" if is_blurry else "CLEAN"
    filename = f"realistic_invoice_{index}_{status_tag}.png"
    filepath = os.path.join(OUTPUT_DIR, filename)

    img.save(filepath)

    if is_blurry:
        apply_heavy_blur(filepath)

    print(f"Generated: {filename}")

# Execute loop
for i in range(1, NUM_IMAGES + 1):
    generate_realistic_invoice(i)

print(f"\nDone! Check the '{OUTPUT_DIR}' folder.")
import json

# Replace these with your actual filenames!
data = [
    {"image": "realistic_invoice_1_CLEAN.png", "instruction": "Extract all financial data and return strictly as JSON.", "output": "{\"Employee Name\": \"Carlos Smith\", \"Total Claimed\": 450, \"Items\": [\"Food Allowance\"]}"},
    # ... add all 50 entries here ...
]

with open("dataset.jsonl", "w") as f:
    for entry in data:
        json.dump(entry, f)
        f.write("\n")

print("dataset.jsonl created successfully!")