#include <stdio.h>
#include <math.h>

static float xs[16], ys[16];
static int n = 0, used[16];
static float best = 1e30f;

static float dist(int a, int b)
{
    float dx = xs[a] - xs[b], dy = ys[a] - ys[b];
    return sqrtf(dx * dx + dy * dy);
}

static void dfs(int u, int cnt, float cur)
{
    if (cnt == n) {
        float tot = cur + dist(u, 0);
        if (tot < best) best = tot;
        return;
    }
    for (int v = 1; v < n; v++) {
        if (!used[v]) {
            used[v] = 1;
            dfs(v, cnt + 1, cur + dist(u, v));
            used[v] = 0;
        }
    }
}

int main(void)
{
    while (fscanf(stdin, "%f, %f", &xs[n], &ys[n]) == 2) n++;
    if (n <= 1) { printf("0.00\n"); return 0; }
    used[0] = 1;
    dfs(0, 1, 0.0f);
    printf("%.2f\n", best);
    return 0;
}
