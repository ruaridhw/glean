# SAM BuildMethod: makefile targets
# SAM calls `make build-<LogicalId>` and expects output in $(ARTIFACTS_DIR)

.PHONY: build-GleanFunction build-PreSignUpFunction

build-GleanFunction:
	uv export --frozen --no-dev --no-editable -o requirements.txt
	uv pip install \
		--no-installer-metadata \
		--no-compile-bytecode \
		--python-platform x86_64-manylinux2014 \
		--python 3.13 \
		--target $(ARTIFACTS_DIR) \
		-r requirements.txt
	cp -r src/glean $(ARTIFACTS_DIR)/glean
	rm -f requirements.txt

build-PreSignUpFunction:
	cp -r src/glean/triggers $(ARTIFACTS_DIR)/glean_triggers_tmp
	mkdir -p $(ARTIFACTS_DIR)/glean
	mv $(ARTIFACTS_DIR)/glean_triggers_tmp $(ARTIFACTS_DIR)/glean/triggers
	touch $(ARTIFACTS_DIR)/glean/__init__.py
