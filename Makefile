PY ?= python

.PHONY: test calibrate demo demo-once claim-audit release-audit public-archive docker-build docker-demo docker-calibrate docker-test

test:
	$(PY) -m pytest -q

calibrate:
	$(PY) -m gauntlet calibrate

# `make demo` is EXPECTED to end in a KILL verdict (exit code 1) — that is the demo.
demo:
	-$(PY) -m gauntlet run demo/patchbot/task_demo_patchbot_01.json

demo-once:
	$(PY) -m gauntlet run demo/patchbot/task_demo_patchbot_01.json --once --seed 1

claim-audit:
	$(PY) scripts/audit_public_claims.py

release-audit: claim-audit
	$(PY) scripts/audit_public_release.py

public-archive: release-audit
	git archive --worktree-attributes --format=zip --output probity-public.zip HEAD

docker-build:
	docker build -t probity .

docker-demo: docker-build
	docker run --rm probity demo

docker-calibrate: docker-build
	docker run --rm probity calibrate

docker-test: docker-build
	docker run --rm probity test
