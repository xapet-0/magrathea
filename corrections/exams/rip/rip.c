#include <unistd.h>

static int slen(const char *s) { int i = 0; while (s[i]) i++; return i; }

static int valid(const char *s)
{
    int b = 0;
    for (int i = 0; s[i]; i++) {
        if (s[i] == '(') b++;
        else if (s[i] == ')') { if (--b < 0) return 0; }
    }
    return b == 0;
}

static void dfs(char *s, int idx, int rem_l, int rem_r)
{
    if (rem_l == 0 && rem_r == 0) {
        if (valid(s)) {
            write(1, s, slen(s));
            write(1, "\n", 1);
        }
        return;
    }
    for (int i = idx; s[i]; i++) {
        if (s[i] == '(' && rem_l > 0) {
            s[i] = ' ';
            dfs(s, i + 1, rem_l - 1, rem_r);
            s[i] = '(';
        } else if (s[i] == ')' && rem_r > 0) {
            s[i] = ' ';
            dfs(s, i + 1, rem_l, rem_r - 1);
            s[i] = ')';
        }
    }
}

int main(int ac, char **av)
{
    if (ac != 2) return 0;
    char buf[1024];
    int l = 0, r = 0, i = 0;
    for (; av[1][i]; i++) {
        buf[i] = av[1][i];
        if (buf[i] == '(') l++;
        else if (buf[i] == ')') {
            if (l > 0) l--;
            else r++;
        }
    }
    buf[i] = '\0';
    dfs(buf, 0, l, r);
    return 0;
}
