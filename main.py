"""
CSV\ub97c \uc774\uc6a9\ud574 \uc878\uc5c5\uc0ac\uc815 \ud604\uc7ac \uc0c1\ud0dc\ub97c \uc694\uc57d \ucd9c\ub825\ud558\ub294 \uc2e4\ud589 \uc2a4\ud06c\ub9bd\ud2b8.\n(\uc774\ubbf8\uc9c0 \uc778\uc2dd \uc5c6\uc74c, OPENAI_API_KEY \ubd88\ud544\uc694)\n"""

from pathlib import Path

from graduation_status_analyzer import GraduationStatusAnalyzer


def load_csv_path() -> Path:
    """\uae30\ubcf8 CSV \uacbd\ub85c\ub97c \ubc18\ud658\ud569\ub2c8\ub2e4."""
    return Path(__file__).parent / "graduation_status_sample.csv"


def main() -> None:
    csv_path = load_csv_path()
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV \ud30c\uc77c\uc774 \uc5c6\uc2b5\ub2c8\ub2e4: {csv_path}")

    analyzer = GraduationStatusAnalyzer()
    result = analyzer.analyze_csv(str(csv_path))

    print("[\ucd1d \ud559\uc810]")
    print(f"  \ud544\uc694: {result.total_credits.required}")
    print(f"  \uc774\uc218: {result.total_credits.completed}")
    print(f"  \uc794\uc5ec: {result.total_credits.remaining}")
    print("\n[\ubbf8\ucda9\uc871 \uc694\uac74]")
    if result.unsatisfied:
        for item in result.unsatisfied:
            if item:
                print(f" - {item}")
    else:
        print("\ubaa8\ub4e0 \uc694\uac74 \ucda9\uc871")


if __name__ == "__main__":
    main()
