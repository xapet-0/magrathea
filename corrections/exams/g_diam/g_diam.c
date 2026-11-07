#include <unistd.h>
#include <stdlib.h>

static void putnbr(int n)
{
    if (n >= 10) putnbr(n / 10);
    char c = '0' + (n % 10);
    write(1, &c, 1);
}

static int adj[256][256];
static int nodes[256];
static int n_cnt = 0;
static int vis[256];
static int best = 0;

static int get_id(int v)
{
    for (int i = 0; i < n_cnt; i++) if (nodes[i] == v) return i;
    nodes[n_cnt] = v;
    return n_cnt++;
}

static void dfs(int u, int len)
{
    if (len > best) best = len;
    vis[u] = 1;
    for (int v = 0; v < n_cnt; v++) {
        if (adj[u][v] && !vis[v])
            dfs(v, len + 1);
    }
    vis[u] = 0;
}

int main(int ac, char **av)
{
    if (ac == 2) {
        char *s = av[1];
        int i = 0;
        while (s[i]) {
            while (s[i] == ' ') i++;
            if (!s[i]) break;
            int a = 0, b = 0;
            while (s[i] >= '0' && s[i] <= '9') a = a * 10 + (s[i++] - '0');
            if (s[i] == '-') i++;
            while (s[i] >= '0' && s[i] <= '9') b = b * 10 + (s[i++] - '0');
            int ua = get_id(a), ub = get_id(b);
            adj[ua][ub] = adj[ub][ua] = 1;
        }
        for (int u = 0; u < n_cnt; u++) dfs(u, 1);
        putnbr(best);
    }
    write(1, "\n", 1);
    return 0;
}
