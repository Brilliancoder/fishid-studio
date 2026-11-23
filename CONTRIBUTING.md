# Contributing to FishID Studio

Thank you for your interest in **FishID Studio**! Contributions from researchers, marine biologists, fisheries scientists, and software engineers are very welcome (in English or Portuguese).

## Ways to Contribute

- **Bug reports & edge cases:** report deck lighting, occlusion, calibration, or API issues using the [Bug Report template](.github/ISSUE_TEMPLATE/bug_report.yml).
- **New species & datasets:** suggest pelagic species or open datasets via [Feature Request](.github/ISSUE_TEMPLATE/feature_request.yml) or [GitHub Discussions](https://github.com/viniciusscience/fishid-studio/discussions).
- **Code & documentation improvements:** submit focused pull requests following the workflow below.

## Development Workflow

1. Fork the repository and create a branch from `main`:
   ```bash
   git checkout -b feat/my-improvement
   ```
2. Copy `.env.example` to `.env` (never commit `.env` or credentials).
3. Verify Python syntax across all modules before committing (same check run by CI):
   ```bash
   python -m py_compile \
     backend/main.py \
     backend/storage.py \
     frontend/app.py \
     monitoramento_em.py \
     rodar_suite_benchmark.py \
     rastrear_peixes_auto.py \
     segmentar_peixes_auto.py
   ```
4. If your change affects the web UI or API, test locally with Docker:
   ```bash
   docker compose up --build
   ```
5. Open a pull request against `main` filling out the PR template.

## Licensing & Attribution

By contributing to FishID Studio, you agree that your contributions will be licensed under the repository's [MIT License](LICENSE).
