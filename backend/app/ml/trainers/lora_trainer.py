import hashlib
import json
import os
import random
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
import yaml
from peft import LoraConfig, TaskType, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainingArguments,
)

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("lora_trainer")


@dataclass
class LoRATrainingConfig:
    base_model: str = "gpt2"
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    target_modules: list[str] = field(default_factory=lambda: ["c_attn", "c_proj"])
    learning_rate: float = 2e-4
    epochs: int = 3
    batch_size: int = 4
    gradient_accumulation_steps: int = 4
    warmup_steps: int = 100
    max_seq_length: int = 512
    weight_decay: float = 0.01
    load_in_4bit: bool = False
    seed: int = 42
    output_dir: str = "/tmp/llmflow_training"


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)


def get_library_versions() -> dict:
    import peft
    import transformers

    versions = {
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "peft": peft.__version__,
        "numpy": np.__version__,
    }
    try:
        import bitsandbytes

        versions["bitsandbytes"] = bitsandbytes.__version__
    except ImportError:
        pass
    return versions


def get_pip_freeze() -> str:
    try:
        result = subprocess.run(
            ["pip", "freeze"], capture_output=True, text=True, timeout=30
        )
        return result.stdout
    except Exception:
        return ""


def compute_config_hash(config: dict) -> str:
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


class LoRATrainer:
    def __init__(self, config: LoRATrainingConfig):
        self.config = config
        self.model = None
        self.tokenizer = None
        self.start_time: float | None = None

    def setup(self) -> None:
        set_seed(self.config.seed)

        logger.info("loading_model", model=self.config.base_model)

        model_kwargs: dict = {}
        if self.config.load_in_4bit:
            try:
                from transformers import BitsAndBytesConfig

                model_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4",
                )
            except ImportError:
                logger.warning("bitsandbytes_unavailable", msg="Falling back to fp32")

        self.tokenizer = AutoTokenizer.from_pretrained(self.config.base_model)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        self.model = AutoModelForCausalLM.from_pretrained(
            self.config.base_model, **model_kwargs
        )

        lora_config = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=self.config.lora_r,
            lora_alpha=self.config.lora_alpha,
            lora_dropout=self.config.lora_dropout,
            target_modules=self.config.target_modules,
        )
        self.model = get_peft_model(self.model, lora_config)

        trainable = sum(p.numel() for p in self.model.parameters() if p.requires_grad)
        total = sum(p.numel() for p in self.model.parameters())
        logger.info(
            "model_ready",
            trainable_params=trainable,
            total_params=total,
            pct=f"{100 * trainable / total:.2f}%",
        )

    def train(self, train_dataset, eval_dataset=None) -> dict:
        self.start_time = time.time()

        training_args = TrainingArguments(
            output_dir=self.config.output_dir,
            num_train_epochs=self.config.epochs,
            per_device_train_batch_size=self.config.batch_size,
            gradient_accumulation_steps=self.config.gradient_accumulation_steps,
            learning_rate=self.config.learning_rate,
            weight_decay=self.config.weight_decay,
            warmup_steps=self.config.warmup_steps,
            logging_steps=10,
            save_strategy="epoch",
            eval_strategy="epoch" if eval_dataset else "no",
            seed=self.config.seed,
            fp16=torch.cuda.is_available(),
            report_to=[],
        )

        data_collator = DataCollatorForLanguageModeling(
            tokenizer=self.tokenizer, mlm=False
        )

        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            data_collator=data_collator,
        )

        result = trainer.train()
        elapsed = time.time() - self.start_time

        metrics = {
            "train_loss": result.training_loss,
            "train_runtime_seconds": result.metrics.get("train_runtime", elapsed),
            "train_samples_per_second": result.metrics.get("train_samples_per_second", 0),
            "epochs": self.config.epochs,
        }

        if eval_dataset:
            eval_result = trainer.evaluate()
            metrics["eval_loss"] = eval_result.get("eval_loss", 0)
            metrics["perplexity"] = float(np.exp(eval_result.get("eval_loss", 0)))

        return metrics

    def save(self, output_path: str) -> None:
        if self.model and self.tokenizer:
            self.model.save_pretrained(output_path)
            self.tokenizer.save_pretrained(output_path)
            logger.info("model_saved", path=output_path)

    def get_gpu_hours(self) -> float:
        if not self.start_time:
            return 0.0
        elapsed_seconds = time.time() - self.start_time
        return elapsed_seconds / 3600

    def get_cost(self) -> float:
        return self.get_gpu_hours() * settings.gpu_cost_per_hour

    def get_reproducibility_info(self) -> dict:
        return {
            "seed": self.config.seed,
            "library_versions": get_library_versions(),
            "config_hash": compute_config_hash(self.config.__dict__),
            "pip_freeze": get_pip_freeze()[:5000],
        }
