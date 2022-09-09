build:
	poetry build

test:
	tox --skip-missing-interpreters true

bump-patch:
	@poetry run bumpver update --patch

bump-minor:
	@poetry run bumpver update --minor

bump-major:
	@poetry run bumpver update --major

.PHONY: build build-doc test bump-patch bump-minor bump-major
