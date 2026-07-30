NITEOS templates edit package
=============================

scenarios/{id}/
  reference.png
  prompt_rules.txt   <- edit first
  prompt_full.txt    <- current full prompt sent to generation
  ies/*.ies
  meta.json

legacy/{legacy_N}/
  reference.jpg|png
  prompt_rules.txt
  prompt_full.txt
  ies/*.ies
  meta.json

shared/
  style_ai_block.txt
  all_prompts.md

After edit, copy prompt_rules.txt back to:
  exports/mvp-fixtures/scenarios/prompts/{id}.txt
