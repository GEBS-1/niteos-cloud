# NITEOS fine-tune (Flux LoRA)

- Export dataset: `python -m finetune.export_dataset`
- Pull prod history: `bash finetune/pull_prod_cloud_data.sh` (or `.ps1`)
- Train docs: [train/README.md](train/README.md)
- Soft inference (no GPU yet): select **NITEOS LoRA** in dealer � uses few-shot from dataset via Gemini
- Real LoRA: set `FINETUNED_IMAGE_API_URL` after training

Trigger token: `niteos_archlight`
