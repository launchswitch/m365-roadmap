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

    # Split Copilot items by status into separate pages
    copilot_by_status = {}
    for item in copilot_all:
        status = item.get("status", "Unknown")
        copilot_by_status.setdefault(status, []).append(item)

    STATUS_SLUGS = {
        "In development": "in-development",
        "Rolling out": "rolling-out",
        "Launched": "launched",
        "Cancelled": "cancelled",
    }

    # Write Copilot index page with links to status-split pages
    index_path = os.path.join(OUTPUT_DIR, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write("<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n")
        f.write('<meta charset="utf-8">\n')
        f.write("<title>Microsoft Copilot Roadmap (All-Up)</title>\n")
        f.write("</head>\n<body>\n")
        f.write("<h1>Microsoft Copilot Roadmap (All-Up)</h1>\n")
        f.write(
            "<p>Complete unified view of all Microsoft Copilot-related roadmap items "
            "across all M365 products (Copilot, PowerPoint, Word, Teams, Outlook, Excel, "
            "SharePoint, Purview, Edge, Viva, and others).</p>\n"
        )
        f.write(f"<p>Total Copilot items: {len(copilot_all)}</p>\n")
        f.write("<ul>\n")
        for status in ["In development", "Rolling out", "Launched", "Cancelled"]:
            items = copilot_by_status.get(status, [])
            if items:
                slug = STATUS_SLUGS[status]
                f.write(f'<li><a href="copilot/{slug}/">{status}</a> ({len(items)} items)</li>\n')
        f.write("</ul>\n")
        f.write("</body>\n</html>")

    # Write per-status Copilot pages as subdirectories with index.html
    for status, items in copilot_by_status.items():
        slug = STATUS_SLUGS.get(status, status.lower().replace(" ", "-"))
        subdir = os.path.join(OUTPUT_DIR, "copilot", slug)
        os.makedirs(subdir, exist_ok=True)
        write_page(
            os.path.join(subdir, "index.html"),
            f"Microsoft Copilot Roadmap - {status}",
            items,
            description=(
                f"All Microsoft Copilot-related roadmap items with status '{status}' "
                f"across all M365 products. {len(items)} items."
            ),
        )
        print(f"  copilot/{slug}/ - {status} ({len(items)} items)")

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
    products_dir = os.path.join(OUTPUT_DIR, "products")
    os.makedirs(products_dir, exist_ok=True)
    index_path = os.path.join(products_dir, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write("<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n")
        f.write('<meta charset="utf-8">\n')
        f.write("<title>M365 Roadmap - All Products</title>\n")
        f.write("</head>\n<body>\n")
        f.write("<h1>Microsoft 365 Roadmap - All Products</h1>\n")
        f.write(f"<p>Source: {API_URL} | {len(data)} total items</p>\n")
        f.write('<p><a href="index.html">Copilot All-Up (unified Copilot roadmap)</a></p>\n')
        for status in ["In development", "Rolling out", "Launched", "Cancelled"]:
            items = copilot_by_status.get(status, [])
            if items:
                slug = STATUS_SLUGS[status]
                f.write(f'<p><a href="copilot/{slug}/">Copilot - {status}</a> ({len(items)} items)</p>\n')
        f.write("<ul>\n")
        for product in sorted(products.keys()):
            filename = slugify(product)
            count = len(products[product])
            f.write(f'<li><a href="{filename}">{product}</a> ({count} items)</li>\n')
        f.write("</ul>\n")
        f.write("</body>\n</html>")

    # Write sitemap.xml
    sitemap_path = os.path.join(OUTPUT_DIR, "sitemap.xml")
    base_url = "https://launchswitch.github.io/m365-roadmap"
    with open(sitemap_path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        # Copilot index
        f.write(f"  <url><loc>{base_url}/</loc><priority>1.0</priority></url>\n")
        # Copilot status pages
        for status in ["In development", "Rolling out", "Launched", "Cancelled"]:
            items = copilot_by_status.get(status, [])
            if items:
                slug = STATUS_SLUGS[status]
                f.write(f"  <url><loc>{base_url}/copilot/{slug}/</loc><priority>0.9</priority></url>\n")
        # Product index
        f.write(f"  <url><loc>{base_url}/products/</loc><priority>0.5</priority></url>\n")
        # Product pages
        for product in sorted(products.keys()):
            filename = slugify(product)
            f.write(f"  <url><loc>{base_url}/{filename}</loc><priority>0.3</priority></url>\n")
        f.write('</urlset>')

    print(f"Generated pages in {OUTPUT_DIR}")
    print(f"  index.html - Copilot All-Up index ({len(copilot_all)} items)")
    print(f"  products.html - Product index ({len(products)} products)")
    for product in sorted(products.keys()):
        print(f"  {slugify(product)} - {product} ({len(products[product])} items)")


if __name__ == "__main__":
    main()
