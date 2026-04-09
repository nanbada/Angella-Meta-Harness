# Setup Gemma 4 with MLX

Angella supports running Gemma 4 models using the MLX framework for optimal performance on Apple Silicon.

## Configuration

Set the following environment variables in your `.env.mlx`:

```bash
export ANGELLA_LOCAL_WORKER_BACKEND=mlx
export ANGELLA_MLX_BASE_URL=http://127.0.0.1:11435/v1 # AUTO_SYNC:MLX_BASE_URL
export ANGELLA_MLX_MODEL=gemma-4-26B-A4B-it-GGUF # AUTO_SYNC:MLX_MODEL_NAME
```

## Setup

Run the setup script with the MLX worker model:

```bash
bash setup.sh --worker-model mlx_gemma4_26b_it_gguf # AUTO_SYNC:MLX_MODEL_ID
```
