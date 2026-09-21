"""
Downloads the two models at build time instead of during someone's first check.

Both models fetch themselves the first time they are used: about 190 MB between them. On a
laptop that happens once and is forgotten. On a hosted container the filesystem is thrown away
at every deploy, so without this the first person to run a check after each deploy waits for
the download, and the first person to submit an image waits again.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from sentence_transformers import SentenceTransformer
    from pipeline.verdict_generator import MODEL_NAME, get_model

    get_model()
    print(f"cached {MODEL_NAME}")

    import easyocr

    easyocr.Reader(["en"], gpu=False, verbose=False)
    print("cached EasyOCR english detector and recogniser")


if __name__ == "__main__":
    main()
