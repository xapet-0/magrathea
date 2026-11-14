# ============================================================================ #
#   1337 / 42 Local Evaluation & Exam Ecosystem — Master Makefile              #
#    Zero-Setup Plug & Play Edition                                             #
# ============================================================================ #

SHELL       := /bin/sh
PYTHON      := python3
MOULINETTE  := ./bin/moulinette
EXAMSHELL   := ./bin/examshell
DEEPTHOUGHT := ./bin/deepthought
NORMINETTE  := ./bin/norminette
SHNORM      := ./bin/shnorm
PFORGE      := ./bin/pforge

.PHONY: all help check install list piscine exam practice norm shnorm test clean

all: help

help:
	@printf "\033[1;36m================================================================================\033[0m\n"
	@printf "\033[1;32m  1337 / 42 Authentic ExamShell & Moulinette Grading Platform (v0.1.1)\033[0m\n"
	@printf "\033[1;36m================================================================================\033[0m\n"
	@printf "  \033[1;33m./bin/moulinette\033[0m                 Launch interactive Piscine & Exam REPL\n"
	@printf "  \033[1;33m./bin/moulinette <exercise>\033[0m      Grade an exercise (e.g. ft_putchar, ft_split)\n"
	@printf "  \033[1;33m./bin/examshell\033[0m                  Launch interactive 42 / 1337 ExamShell v0.1.1\n"
	@printf "  \033[1;33m./bin/examshell --practice\033[0m       Launch ExamShell in Coaching / Practice Mode\n"
	@printf "  \033[1;33mmake check\033[0m                       Verify OS tools, Python >= 3.10, and norminette\n"
	@printf "  \033[1;33mmake install\033[0m                     Install prerequisites and link CLI tools\n"
	@printf "  \033[1;33mmake list\033[0m                        Display all 17 Piscine modules & 18 Exam pools\n"
	@printf "  \033[1;33mmake norm\033[0m                        Run 42 Norminette v3 on workspace/\n"
	@printf "  \033[1;33mmake shnorm\033[0m                      Run POSIX Shell Norm on install.sh, bin/ & bocal/\n"
	@printf "  \033[1;33mmake test\033[0m                        Run the automated Python test suite\n"
	@printf "  \033[1;33mmake clean\033[0m                       Clean temporary workspace and caches\n"
	@printf "\033[1;36m================================================================================\033[0m\n"

check:
	@sh ./install.sh --check

install:
	@sh ./install.sh

list:
	@$(PYTHON) $(MOULINETTE) --list

piscine:
	@$(PYTHON) $(MOULINETTE)

exam:
	@$(PYTHON) $(EXAMSHELL)

practice:
	@$(PYTHON) $(EXAMSHELL) --practice

norm:
	@$(PYTHON) $(NORMINETTE) workspace/

shnorm:
	@$(PYTHON) $(SHNORM) install.sh bin/ifconfig bocal/*.sh bin/*.sh

test:
	@$(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v

clean:
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f \( -name "*.pyc" -o -name "*.pyo" -o -name "*.o" -o -name "*.log" -o -name "*.trace" -o -name "*~" -o -name "*.swp" \) -delete 2>/dev/null || true
	@rm -rf workspace/rendu/* workspace/subject/* workspace/traces/* vogsphere/* 2>/dev/null || true
	@mkdir -p workspace/rendu workspace/subject workspace/traces vogsphere schemas 2>/dev/null || true
	@touch workspace/rendu/.gitkeep workspace/subject/.gitkeep workspace/traces/.gitkeep vogsphere/.gitkeep schemas/.gitkeep 2>/dev/null || true
	@printf "\033[1;32m[OK] Cleaned Python bytecode caches, swap files, and trace artifacts.\033[0m\n"
