PY := .venv/bin/python

# `notebooks` and `data` are also directory names, so every target here is
# declared phony — otherwise make sees the directory and calls it up to date.
.PHONY: install test test-fast cov run uci perft calibrate eval-ab sprt ladder-sprt notebooks self-play ladder gauntlet leaderboard tournament lint format init-db clean

install:
	uv venv --python 3.11 || true
	uv pip install -r requirements.txt

test:
	$(PY) -m pytest tests/ -v

test-fast:          ## skip the self-play ladder matches
	$(PY) -m pytest tests/ -v -m "not slow"

cov:
	$(PY) -m pytest tests/ --cov=engine --cov-report=term-missing

run:
	$(PY) -m streamlit run app/streamlit_app.py

ladder:             ## long gauntlet: does each level beat the one below?
	$(PY) -m scripts.ladder --games 16

tournament:
	$(PY) -m scripts.tournament --format round-robin --levels all --games 2 --time 0.3

gauntlet:           ## test one level against the whole ladder
	$(PY) -m scripts.tournament --format gauntlet --test 7 --levels 1-6 --games 4 --time 0.3

leaderboard:
	$(PY) -m scripts.leaderboard

uci:                ## the engine on stdin/stdout, for a GUI or a match runner
	$(PY) -m uci

bench:               ## record a deterministic speed baseline
	$(PY) -m scripts.bench --out data/bench_baseline.json

bench-check:         ## compare against it, keeping speed and behaviour apart
	$(PY) -m scripts.bench --baseline data/bench_baseline.json

perft:              ## prove the move generation against published counts
	$(PY) -c "from engine.perft import run_suite; s = run_suite(4); print(s.table()); raise SystemExit(0 if s.passed else 1)"

calibrate:          ## rate an external UCI engine against the ladder
	$(PY) -m scripts.calibrate --engine $(ENGINE) --games 12 --movetime 0.3

eval-ab:            ## fixed-length A/B between evaluation variants
	$(PY) -m scripts.eval_ab --games 40 --movetime 0.25

sprt:               ## sequential test: stops as soon as the games answer
	$(PY) -m scripts.sprt_match --a $(A) --b $(B) --minutes 13

ladder-sprt:        ## where every adjacent pairing stands
	$(PY) -m scripts.ladder_sprt --report-only

self-play:          ## TDLeaf(lambda) at a scale a notebook cannot afford
	$(PY) -m scripts.self_play_run --games 10000

notebooks:          ## run every research notebook, embedding its outputs
	cd notebooks && for nb in *.ipynb; do \
		echo "== $$nb"; \
		../$(PY) -m nbconvert --to notebook --execute --inplace \
			--ExecutePreprocessor.timeout=1800 $$nb; \
	done

lint:
	$(PY) -m black --check engine/ tournament/ elo/ scripts/ tests/
	$(PY) -m mypy engine/ tournament/ elo/ scripts/

format:
	$(PY) -m black engine/ tournament/ elo/ scripts/ tests/

init-db:
	$(PY) -c "from elo.database import EloDatabase; EloDatabase()"

clean:
	rm -rf .pytest_cache .mypy_cache htmlcov .coverage
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
