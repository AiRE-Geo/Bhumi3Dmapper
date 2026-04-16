PLUGIN_NAME = bhumi3dmapper
VERSION = 1.0.0
ZIP_NAME = $(PLUGIN_NAME)_v$(VERSION).zip

.PHONY: all test clean package

all: test package

test:
	pytest $(PLUGIN_NAME)/test/ -v --tb=short

compile_resources:
	pyrcc5 $(PLUGIN_NAME)/resources.qrc -o $(PLUGIN_NAME)/resources_rc.py

package:
	zip -r $(ZIP_NAME) $(PLUGIN_NAME)/ \
		--exclude '*/test/*' \
		--exclude '*/__pycache__/*' \
		--exclude '*.pyc' \
		--exclude '*.git*' \
		--exclude '*/conftest.py'
	@echo "Built: $(ZIP_NAME)"

clean:
	rm -f $(ZIP_NAME)
	find $(PLUGIN_NAME) -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	find $(PLUGIN_NAME) -name '*.pyc' -delete 2>/dev/null || true
