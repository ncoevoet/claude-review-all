# Makefile for /review-all skill
#
# `make install`     — copy skills/review-all/ into ~/.claude/skills/review-all/
# `make uninstall`   — remove the installed copy
# `make review-self` — install, then remind to run /review-all in this repo

SKILL_SRC := skills/review-all
SKILL_DEST := $(HOME)/.claude/skills/review-all

.PHONY: install uninstall review-self help

help:
	@echo "Targets:"
	@echo "  install     copy $(SKILL_SRC)/ to $(SKILL_DEST)/"
	@echo "  uninstall   delete $(SKILL_DEST)/"
	@echo "  review-self install, then run /review-all on this repo"

install:
	@mkdir -p "$(SKILL_DEST)"
	@rsync -a --delete "$(SKILL_SRC)/" "$(SKILL_DEST)/"
	@echo "Installed: $(SKILL_DEST)"

uninstall:
	@rm -rf "$(SKILL_DEST)"
	@echo "Removed: $(SKILL_DEST)"

review-self: install
	@echo "Now run /review-all inside Claude Code in this repo."
