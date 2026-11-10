#include <stdio.h>
#include <stdlib.h>

static int target, n;
static int arr[64], pick[64];

static void dfs(int idx, int k, int sum)
{
    if (idx == n) {
        if (sum == target) {
            for (int i = 0; i < k; i++)
                printf("%s%d", (i > 0 ? " " : ""), pick[i]);
            printf("\n");
        }
        return;
    }
    pick[k] = arr[idx];
    dfs(idx + 1, k + 1, sum + arr[idx]);
    dfs(idx + 1, k, sum);
}

int main(int ac, char **av)
{
    if (ac < 2) return 0;
    target = atoi(av[1]);
    n = ac - 2;
    for (int i = 0; i < n; i++) arr[i] = atoi(av[i + 2]);
    dfs(0, 0, 0);
    return 0;
}
