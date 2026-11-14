#include <stdio.h>
#include <ctype.h>

void    unexpected(char c)
{
    if (c)
        printf("Unexpected token '%c'\n", c);
    else
        printf("Unexpected end of input\n");
}

int accept(char **s, char c)
{
    if (**s == c)
    {
        (*s)++;
        return (1);
    }
    return (0);
}

int expect(char **s, char c)
{
    if (accept(s, c))
        return (1);
    unexpected(**s);
    return (0);
}

// TODO: evaluate addition, multiplication, parentheses, and single-digit values
int eval_expr(char **s, int *err)
{
    if (*s && **s)
        unexpected(**s);
    else
        unexpected(0);
    *err = 1;
    return (0);
}

int main(int argc, char **argv)
{
    int err = 0;
    char *s;
    int res;

    if (argc != 2)
        return (1);
    s = argv[1];
    res = eval_expr(&s, &err);
    if (!err && *s)
    {
        unexpected(*s);
        err = 1;
    }
    if (err)
        return (1);
    printf("%d\n", res);
    return (0);
}

