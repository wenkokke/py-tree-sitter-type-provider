build:
	poetry build

test:
	tox --skip-missing-interpreters true

bump-patch:
	@poetry run bumpver update --patch
	@$(MAKE) release

bump-minor:
	@poetry run bumpver update --minor
	@$(MAKE) release

bump-major:
	@poetry run bumpver update --major
	@$(MAKE) release

.PHONY: build build-doc test bump-patch bump-minor bump-major
