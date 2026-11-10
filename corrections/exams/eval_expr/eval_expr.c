static int	parse_expr(char **s);
static void	skip_sp(char **s) { while (**s == ' ' || **s == '\t') (*s)++; }
static int	parse_factor(char **s) {
	int sign = 1, res = 0;
	skip_sp(s);
	while (**s == '+' || **s == '-') { if (*(*s)++ == '-') sign = -sign; skip_sp(s); }
	if (**s == '(') { (*s)++; res = parse_expr(s); skip_sp(s); if (**s == ')') (*s)++; return (res * sign); }
	while (**s >= '0' && **s <= '9') res = res * 10 + (*(*s)++ - '0');
	return (res * sign);
}
static int	parse_term(char **s) {
	int left = parse_factor(s), right; char op;
	while (1) {
		skip_sp(s); op = **s; if (op != '*' && op != '/' && op != '%') break ;
		(*s)++; right = parse_factor(s);
		if (op == '*') left *= right; else if (op == '/' && right != 0) left /= right; else if (op == '%' && right != 0) left %= right;
	}
	return (left);
}
static int	parse_expr(char **s) {
	int left = parse_term(s), right; char op;
	while (1) {
		skip_sp(s); op = **s; if (op != '+' && op != '-') break ;
		(*s)++; right = parse_term(s);
		if (op == '+') left += right; else left -= right;
	}
	return (left);
}
int	eval_expr(char *str) { return (parse_expr(&str)); }
