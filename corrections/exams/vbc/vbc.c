#include <stdio.h>
#include <ctype.h>

static const char *s;
static int pos = 0;

static int parse_expr(void);

static int parse_factor(void)
{
    if (s[pos] == '(') {
        pos++;
        int v = parse_expr();
        if (s[pos] == ')') pos++;
        return v;
    }
    int v = 0;
    while (isdigit((unsigned char)s[pos]))
        v = v * 10 + (s[pos++] - '0');
    return v;
}

static int parse_term(void)
{
    int v = parse_factor();
    while (s[pos] == '*') {
        pos++;
        v *= parse_factor();
    }
    return v;
}

static int parse_expr(void)
{
    int v = parse_term();
    while (s[pos] == '+') {
        pos++;
        v += parse_term();
    }
    return v;
}

int main(int ac, char **av)
{
    if (ac != 2) return 1;
    s = av[1];
    printf("%d\n", parse_expr());
    return 0;
}
