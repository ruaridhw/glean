# SAM BuildMethod: makefile targets
# SAM calls `make build-<LogicalId>` and expects output in $(ARTIFACTS_DIR)

.PHONY: build-GleanFunction build-AgentWorkerFunction build-AgentDeadLetterFunction build-PreSignUpFunction

# The API, the worker and the dead-letter handler are one bundle: all of src/glean plus every runtime
# dependency. They are separate functions (different handlers, timeouts and policies) but not separate
# code, and the worker imports the agent module, which imports LangGraph — so a copy of only its
# entrypoint would not run.
.PHONY: build-backend-bundle
build-GleanFunction build-AgentWorkerFunction build-AgentDeadLetterFunction: build-backend-bundle

build-backend-bundle:
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
