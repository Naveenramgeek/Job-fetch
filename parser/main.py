import json
from .resume_parser import build_resume_object


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract + pre-structure resume content from PDF (robust + other blocks)"
    )
    parser.add_argument("pdf_path", help="Path to resume PDF")
    parser.add_argument("--out", default="resume_structured.json", help="Output JSON file")
    parser.add_argument("--no-ocr", action="store_true", help="Disable OCR fallback")
    args = parser.parse_args()

    data = build_resume_object(args.pdf_path, ocr_fallback=(not args.no_ocr))

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"✅ Structured resume saved to: {args.out}")
    print("Contact:", data["contact"])
    print("Sections found:", list(data["raw_sections"].keys()))
    print("Experience items:", len(data["experience"]))
    print("Education items:", len(data["education"]))
    print("Projects items:", len(data["projects"]))
    print("Other blocks:", len(data["other"]))
