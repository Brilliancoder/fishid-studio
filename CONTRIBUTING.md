# Contributing to FishID Studio

Thank you for your interest in **FishID Studio**! Contributions from researchers, marine biologists, fisheries scientists, and software engineers are very welcome (in English or Portuguese).

---

## ⭐ Star-First Review Priority Policy

Because **FishID Studio** receives a high volume of community and automated Pull Requests across our open issues, **we prioritize reviewing and merging Pull Requests from contributors who have explored the project and starred ⭐ the [viniciusscience/fishid-studio](https://github.com/viniciusscience/fishid-studio) repository** (or support open marine science via [GitHub Sponsors](https://github.com/sponsors/viniciusscience)).

> **Why?** Starring and following the repository shows that you actually checked out what **FishID Studio** does for open-source marine conservation (UN SDG 14) rather than just running a drive-by PR script without knowing the project. When multiple PRs compete for the same issue, **contributors who have starred the repository receive priority review and merge preference**.

---

## Ways to Contribute

- **Bug reports & edge cases:** report deck lighting, occlusion, calibration, or API issues using the [Bug Report template](.github/ISSUE_TEMPLATE/bug_report.yml).
- **New species & datasets:** suggest pelagic species or open datasets via [Feature Request](.github/ISSUE_TEMPLATE/feature_request.yml) or [GitHub Discussions](https://github.com/viniciusscience/fishid-studio/discussions).
- **Code & documentation improvements:** submit focused pull requests following the workflow below.

## Development Workflow

1. **Star ⭐ the repository** at [github.com/viniciusscience/fishid-studio](https://github.com/viniciusscience/fishid-studio) and read the [README.en.md](README.en.md) / [README.md](README.md) to understand the domain (ConvNeXt-Tiny species classification + YOLO-World / ByteTrack / SAM 2.1 Electronic Monitoring).
2. Fork the repository and create a branch from `main`:
   ```bash
   git checkout -b feat/my-improvement
   ```
3. Copy `.env.example` to `.env` (never commit `.env` or credentials).
4. Verify Python syntax and run the unit test suite before committing (same checks run by CI):
   ```bash
   python -m py_compile \
     backend/main.py \
     backend/storage.py \
     frontend/app.py \
     monitoramento_em.py \
     rodar_suite_benchmark.py \
     rastrear_peixes_auto.py \
     segmentar_peixes_auto.py
   python -m pytest -v
   ```
5. If your change affects the web UI or API, test locally with Docker:
   ```bash
   docker compose up --build
   ```
6. Open a pull request against `main` filling out the PR template.

## Licensing & Attribution

By contributing to FishID Studio, you agree that your contributions will be licensed under the repository's [MIT License](LICENSE).
