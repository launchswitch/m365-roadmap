import requests
import os
import json

API_URL = "https://www.microsoft.com/releasecommunications/api/v1/m365"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")

COPILOT_KEYWORDS = ["copilot", "agent mode", "work iq"]


def is_copilot_item(item):
    """Check if an item is Copilot-related by title or description."""
    text = (item.get("title", "") + " " + item.get("description", "")).lower()
    return any(kw in text for kw in COPILOT_KEYWORDS)


def normalize_product(name):
    """Normalize product name for deduplication (case-insensitive merge)."""
    # Known case-variant pairs from the API
    name = name.strip()
    lower = name.lower()
    # Use title case as canonical form
    if lower == "microsoft 365 admin center":
        return "Microsoft 365 Admin Center"
    return name


def slugify(name):
    """Convert product name to URL-safe filename."""
    return name.lower().replace(" ", "_") + ".html"


def render_item(item):
    """Render a single roadmap item as semantic HTML for LLM consumption."""
    title = item.get("title", "")
    description = item.get("description", "")
    status = item.get("status", "")
    ga_date = item.get("publicDisclosureAvailabilityDate", "")
    preview_date = item.get("publicPreviewDate", "")
    roadmap_status = item.get("publicRoadmapStatus", "")
    more_info = item.get("moreInfoLink", "")
    created = item.get("created", "")
    modified = item.get("modified", "")

    # Extract tags
    tc = item.get("tagsContainer", {})
    products = [p.get("tagName", "") for p in tc.get("products", [])]
    clouds = [c.get("tagName", "") for c in tc.get("cloudInstances", [])]
    platforms = [p.get("tagName", "") for p in tc.get("platforms", [])]
    phases = [p.get("tagName", "") for p in tc.get("releasePhase", [])]

    parts = []
    parts.append(f'<section class="roadmap-item">')
    parts.append(f'<h2>{title}</h2>')
    if description:
        parts.append(f'<p class="description">{description}</p>')
    parts.append(f'<p class="meta">Status: {status} | GA Date: {ga_date}')
    if preview_date:
        parts.append(f' | Preview Date: {preview_date}')
    if roadmap_status:
        parts.append(f' | Roadmap Status: {roadmap_status}')
    parts.append('</p>')
    if products:
        parts.append(f'<p class="tags">Products: {", ".join(products)}</p>')
    if clouds:
        parts.append(f'<p class="tags">Cloud: {", ".join(clouds)}</p>')
    if platforms:
        parts.append(f'<p class="tags">Platforms: {", ".join(platforms)}</p>')
    if phases:
        parts.append(f'<p class="tags">Phase: {", ".join(phases)}</p>')
    if more_info:
        parts.append(f'<p class="link"><a href="{more_info}">More info</a></p>')
    parts.append('</section>')
    return "\n".join(parts)


def write_page(filepath, title, items, description=""):
    """Write an HTML page with roadmap items for LLM consumption."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n")
        f.write(f"<meta charset=\"utf-8\">\n")
        f.write(f"<title>{title}</title>\n")
        f.write(f"</head>\n<body>\n")
        f.write(f"<h1>{title}</h1>\n")
        if description:
            f.write(f"<p>{description}</p>\n")
        f.write(f"<p>Total items: {len(items)}</p>\n")
        for item in items:
            f.write(render_item(item))
            f.write("\n")
        f.write("</body>\n</html>")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Fetching M365 roadmap data...")
    data = requests.get(API_URL).json()
    print(f"Retrieved {len(data)} items")

    # Group by product (case-normalized), deduplicate by slug to avoid file collisions
    products = {}
    slug_to_name = {}
    for item in data:
        for p in item.get("tagsContainer", {}).get("products", []):
            name = normalize_product(p.get("tagName", "Other"))
            slug = slugify(name)
            # If slug already used by a different name, merge under existing
            if slug in slug_to_name and slug_to_name[slug] != name:
                name = slug_to_name[slug]
            else:
                slug_to_name[slug] = name
            products.setdefault(name, []).append(item)

    # Deduplicate by ID within each product
    for name in products:
        seen = set()
        unique = []
        for item in products[name]:
            if item["id"] not in seen:
                seen.add(item["id"])
                unique.append(item)
        products[name] = unique

    # Collect all Copilot-related items across all products, deduplicated
    copilot_all = {}
    for item in data:
        if is_copilot_item(item):
            copilot_all[item["id"]] = item
    copilot_all = sorted(copilot_all.values(), key=lambda x: x.get("modified", ""), reverse=True)
    print(f"Found {len(copilot_all)} Copilot-related items across all products")

    # Write Copilot All-Up page (the main page for LLM consumption)
    write_page(
        os.path.join(OUTPUT_DIR, "index.html"),
        "Microsoft Copilot Roadmap (All-Up)",
        copilot_all,
        description=(
            "Complete unified view of all Microsoft Copilot-related roadmap items across "
            "all M365 products. This includes items from Copilot, PowerPoint, Word, Teams, "
            "Outlook, Excel, SharePoint, Purview, Edge, Viva, and other products where Copilot "
            "features are being developed or launched."
        ),
    )

    # Write per-product pages
    for product, items in products.items():
        filename = slugify(product)
        items_sorted = sorted(items, key=lambda x: x.get("modified", ""), reverse=True)
        write_page(
            os.path.join(OUTPUT_DIR, filename),
            f"{product} Roadmap",
            items_sorted,
        )

    # Write a site index page listing all products + the copilot all-up
    index_path = os.path.join(OUTPUT_DIR, "products.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write("<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n")
        f.write('<meta charset="utf-8">\n')
        f.write("<title>M365 Roadmap - All Products</title>\n")
        f.write("</head>\n<body>\n")
        f.write("<h1>Microsoft 365 Roadmap - All Products</h1>\n")
        f.write(f"<p>Source: {API_URL} | {len(data)} total items</p>\n")
        f.write('<p><a href="index.html">Copilot All-Up (unified Copilot roadmap)</a></p>\n')
        f.write("<ul>\n")
        for product in sorted(products.keys()):
            filename = slugify(product)
            count = len(products[product])
            f.write(f'<li><a href="{filename}">{product}</a> ({count} items)</li>\n')
        f.write("</ul>\n")
        f.write("</body>\n</html>")

    print(f"Generated pages in {OUTPUT_DIR}")
    print(f"  index.html - Copilot All-Up ({len(copilot_all)} items)")
    print(f"  products.html - Product index ({len(products)} products)")
    for product in sorted(products.keys()):
        print(f"  {slugify(product)} - {product} ({len(products[product])} items)")


if __name__ == "__main__":
    main()
