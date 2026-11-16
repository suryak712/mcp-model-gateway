"""Benchmark the enabled models in the registry and write a report to reports/.

  python evals/run_eval.py                      # all enabled models, via Ollama
  python evals/run_eval.py --models qwen-small  # just one
  python evals/run_eval.py --backend fake       # no model needed (smoke test)
"""

import argparse
import asyncio
from pathlib import Path

from gateway.backends import FakeBackend, OpenAICompatibleBackend
from gateway.evals import dataset_hash, evaluate, load_cases, write_report
from gateway.registry import Registry

p = argparse.ArgumentParser()
p.add_argument("--dataset", default="evals/dataset.jsonl")
p.add_argument("--registry", default="models.yaml")
p.add_argument("--models", nargs="*", help="registry aliases; default: every enabled model")
p.add_argument("--backend", default="openai", choices=["openai", "fake"])
p.add_argument("--base-url", default="http://127.0.0.1:11434/v1")
p.add_argument("--max-tokens", type=int, default=256)
a = p.parse_args()

registry = Registry.load(Path(a.registry))
aliases = a.models or [alias for alias, e in registry.list().items() if e.enabled]
models = {alias: registry.resolve(alias).name for alias in aliases}  # refuses disabled models too
backend = FakeBackend() if a.backend == "fake" else OpenAICompatibleBackend(a.base_url)
cases = load_cases(Path(a.dataset))

report = asyncio.run(evaluate(backend, models, cases, a.max_tokens))
meta = {"dataset": a.dataset, "dataset_sha": dataset_hash(Path(a.dataset)), "cases": len(cases),
        "max_tokens": a.max_tokens, "backend": a.backend, "models": models}
path = write_report(report, meta, Path("reports"))
print(path.read_text())
