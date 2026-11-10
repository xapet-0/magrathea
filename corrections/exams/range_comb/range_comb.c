#include <stdlib.h>

static void gen(int n, int *cur, int *used, int depth, int **res, int *idx)
{
    if (depth == n) {
        res[*idx] = malloc(sizeof(int) * n);
        if (!res[*idx])
            return;
        for (int i = 0; i < n; i++) res[*idx][i] = cur[i];
        (*idx)++;
        return;
    }
    for (int v = 0; v < n; v++) {
        if (!used[v]) {
            used[v] = 1;
            cur[depth] = v;
            gen(n, cur, used, depth + 1, res, idx);
            used[v] = 0;
        }
    }
}

int **range_comb(int n)
{
    if (n <= 0) return NULL;
    int fact = 1;
    for (int i = 2; i <= n; i++) fact *= i;
    int **res = malloc(sizeof(int *) * (fact + 1));
    int *cur = malloc(sizeof(int) * n);
    int *used = malloc(sizeof(int) * n);
    if (!res || !cur || !used) {
        free(res);
        free(cur);
        free(used);
        return NULL;
    }
    for (int i = 0; i < n; i++) used[i] = 0;
    int idx = 0;
    gen(n, cur, used, 0, res, &idx);
    res[idx] = NULL;
    free(cur);
    free(used);
    return res;
}
