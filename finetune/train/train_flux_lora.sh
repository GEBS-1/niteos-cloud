#!/usr/bin/env bash
# Train Flux LoRA with kohya-ss/sd-scripts (run on GPU box / RunPod).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DATASET_IMG="${DATASET_IMG:-$ROOT/finetune/data/dataset_v1/train/img}"
OUT_DIR="${OUT_DIR:-$ROOT/finetune/artifacts}"
NAME="${OUTPUT_NAME:-niteos_archlight_v1}"
SD_SCRIPTS="${SD_SCRIPTS:-$HOME/sd-scripts}"
MODEL="${FLUX_MODEL:-$HOME/models/flux1-dev.safetensors}"
CLIP_L="${CLIP_L:-$HOME/models/clip_l.safetensors}"
T5XXL="${T5XXL:-$HOME/models/t5xxl_fp16.safetensors}"
AE="${AE:-$HOME/models/ae.safetensors}"

mkdir -p "$OUT_DIR"
# Kohya expects repeats_foldername structure; symlink dataset into it.
TRAIN_ROOT="$OUT_DIR/_kohya_data"
rm -rf "$TRAIN_ROOT"
mkdir -p "$TRAIN_ROOT"
ln -sfn "$DATASET_IMG" "$TRAIN_ROOT/10_niteos_archlight"

CFG="$ROOT/finetune/train/dataset.toml"
# rewrite image_dir absolute for this run
TMP_CFG="$OUT_DIR/dataset_run.toml"
sed "s|IMAGE_DIR_PLACEHOLDER|$TRAIN_ROOT/10_niteos_archlight|g" "$CFG" > "$TMP_CFG"

cd "$SD_SCRIPTS"
accelerate launch --num_cpu_threads_per_process 1 flux_train_network.py \
  --pretrained_model_name_or_path="$MODEL" \
  --clip_l="$CLIP_L" \
  --t5xxl="$T5XXL" \
  --ae="$AE" \
  --dataset_config="$TMP_CFG" \
  --output_dir="$OUT_DIR" \
  --output_name="$NAME" \
  --save_model_as=safetensors \
  --network_module=networks.lora_flux \
  --network_dim=16 \
  --network_alpha=16 \
  --learning_rate=1e-4 \
  --optimizer_type=adamw8bit \
  --lr_scheduler=cosine_with_restarts \
  --max_train_epochs=10 \
  --train_batch_size=1 \
  --gradient_checkpointing \
  --mixed_precision=bf16 \
  --save_precision=bf16 \
  --cache_latents \
  --cache_text_encoder_outputs \
  --timestep_sampling=shift \
  --model_prediction_type=raw \
  --guidance_scale=1.0 \
  --t5xxl_max_token_length=512 \
  --save_every_n_epochs=2

echo "Done. Weights: $OUT_DIR/${NAME}.safetensors"
