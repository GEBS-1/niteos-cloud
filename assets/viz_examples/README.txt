Viz examples for AUTO scenario mode
===================================

Source zip: Downloads/примеры виз.zip

Folders:
- examples/  — 20 normalized test photos for auto template selection
- thumbs/    — auto-generated previews for dealer UI
- INDEX.json — mapping to original archive names

Dealer usage:
1. Open /dealer
2. Switch to "Авто по фото"
3. Click a test photo in the strip
4. System loads source + picks scenario + prepares prompt
5. Press generation as usual

API:
- GET  /api/auto-test-photos
- POST /api/projects/{id}/auto-test-load  (filename, run_auto=1)

Batch CLI:
  python tools/run_auto_scenario_tests.py
  python tools/run_auto_scenario_tests.py 3   # first 3 only
