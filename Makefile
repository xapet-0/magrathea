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

.PHONY: all help list piscine exam practice norm shnorm clean

all: help

help:
	@printf "\033[1;36m================================================================================\033[0m\n"
	@printf "\033[1;32m  1337 / 42 Authentic ExamShell & Moulinette Grading Platform (v0.1.1)\033[0m\n"
	@printf "\033[1;36m================================================================================\033[0m\n"
	@printf "  \033[1;33m./bin/moulinette\033[0m                 Launch interactive Piscine & Exam REPL\n"
	@printf "  \033[1;33m./bin/moulinette <exercise>\033[0m      Grade an exercise (e.g. ft_putchar, ft_split)\n"
	@printf "  \033[1;33m./bin/examshell\033[0m                  Launch interactive 42 / 1337 ExamShell v0.1.1\n"
	@printf "  \033[1;33m./bin/examshell --practice\033[0m       Launch ExamShell in Coaching / Practice Mode\n"
	@printf "  \033[1;33mmake list\033[0m                        Display all 17 Piscine modules & 10 Exam pools\n"
	@printf "  \033[1;33mmake norm\033[0m                        Run 42 Norminette v3 on workspace/\n"
	@printf "  \033[1;33mmake shnorm\033[0m                      Run POSIX Shell Norm on bocal/ & bin/\n"
	@printf "  \033[1;33mmake clean\033[0m                       Clean temporary workspace and caches\n"
	@printf "\033[1;36m================================================================================\033[0m\n"

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
	@$(PYTHON) $(SHNORM) bocal/*.sh bin/*.sh

clean:
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f \( -name "*.pyc" -o -name "*.pyo" -o -name "*.o" -o -name "*.log" -o -name "*.trace" -o -name "*~" -o -name "*.swp" \) -delete 2>/dev/null || true
	@rm -rf workspace/* workspace/.* 2>/dev/null || true
	@rm -rf vogsphere/* vogsphere/.* 2>/dev/null || true
	@mkdir -p workspace/rendu workspace/subject vogsphere schemas 2>/dev/null || true
	@touch workspace/rendu/.gitkeep workspace/subject/.gitkeep vogsphere/.gitkeep schemas/.gitkeep 2>/dev/null || true
	@printf "\033[1;32m[OK] Cleaned Python bytecode caches, swap files, and trace artifacts.\033[0m\n"
