import requests
import os

API_URL = "https://www.microsoft.com/releasecommunications/api/v1/m365"

# Create output folder
output_dir = "../docs"
os.makedirs(output_dir, exist_ok=True)

# Fetch data
data = requests.get(API_URL).json()

# Group by product
products = {}
for item in data:
    for p in item.get("tagsContainer", {}).get("products", []):
        name = p.get("tagName", "Other")
        products.setdefault(name, []).append(item)

# Generate index
with open(f"{output_dir}/index.html", "w", encoding="utf-8") as f:
    f.write("<h1>M365 Roadmap</h1>\n<ul>\n")
    for product in products:
        filename = product.lower().replace(" ", "_") + ".html"
        f.write(f'<li><a href="{filename}">{product}</a></li>\n')
    f.write("</ul>")

# Generate per-product pages
for product, items in products.items():
    filename = product.lower().replace(" ", "_") + ".html"

    with open(f"{output_dir}/{filename}", "w", encoding="utf-8") as f:
        f.write(f"<h1>{product} Roadmap</h1>\n")

        for item in items[:200]:  # safety limit
            f.write("<hr>")
            f.write(f"<h2>{item.get('title')}</h2>\n")
            f.write(f"<p><b>Status:</b> {item.get('status')}</p>\n")
            f.write(f"<p><b>GA Date:</b> {item.get('publicDisclosureAvailabilityDate')}</p>\n")