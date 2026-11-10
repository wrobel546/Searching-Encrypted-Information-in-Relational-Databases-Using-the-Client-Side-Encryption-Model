import hashlib
import json
import platform
from dataclasses import dataclass
from pathlib import Path

from .data import (Distribution, QUERY_DEFINITIONS, generate_dataset, save_dataset,)

SCENARIO_VERSION = 1
DATASET_SIZES = (1_000, 10_000, 100_000)
DISTRIBUTIONS: tuple[Distribution, ...] = ("uniform", "skewed")
DEFAULT_SEED = 42


@dataclass(frozen=True)
class BenchmarkDatasetConfig:
    count: int
    distribution: Distribution
    seed: int = DEFAULT_SEED

    def __post_init__(self) -> None:
        if type(self.count) is not int or self.count not in DATASET_SIZES:
            raise ValueError("Rozmiar benchmarku musi wynosić 1000, 10000 lub 100000.")

        if self.distribution not in DISTRIBUTIONS:
            raise ValueError("Rozkład musi mieć wartość 'uniform' lub 'skewed'.")

        if type(self.seed) is not int:
            raise ValueError("Seed musi być liczbą całkowitą.")

    @property
    def name(self) -> str:
        return f"{self.distribution}_{self.count}_seed{self.seed}"


BENCHMARK_CONFIGS = tuple(BenchmarkDatasetConfig(count=count,distribution=distribution,)
    for count in DATASET_SIZES
    for distribution in DISTRIBUTIONS
)


def export_benchmark_datasets(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    scenarios = []

    for config in BENCHMARK_CONFIGS:
        dataset = generate_dataset(count=config.count, seed=config.seed, distribution=config.distribution,)

        filename = f"{config.name}.json"
        dataset_path = output_dir / filename

        save_dataset(dataset, dataset_path)

        file_hash = hashlib.sha256(dataset_path.read_bytes()).hexdigest()

        scenarios.append(
            {
                "name": config.name,
                "count": config.count,
                "distribution": config.distribution,
                "seed": config.seed,
                "file": filename,
                "sha256": file_hash,
                "expected_counts": {
                    query.category: len(query.expected_ids)
                    for query in dataset.queries
                },
            }
        )

    manifest = {
        "scenario_version": SCENARIO_VERSION,
        "python_version": platform.python_version(),
        "queries": [
            {
                "category": category,
                "surname": surname,
            }
            for category, surname in QUERY_DEFINITIONS
        ],
        "scenarios": scenarios,
    }

    manifest_path = output_dir / "manifest.json"

    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2, ), encoding="utf-8",)

    return manifest_path