struct s_node { int value; struct s_node *left; struct s_node *right; };

static void dfs(struct s_node *n, int cur, int *best)
{
    if (!n) return;
    if (cur > *best) *best = cur;
    if (n->left)
        dfs(n->left, (n->left->value == n->value + 1) ? cur + 1 : 1, best);
    if (n->right)
        dfs(n->right, (n->right->value == n->value + 1) ? cur + 1 : 1, best);
}

int longest_sequence(struct s_node *node)
{
    if (!node) return 0;
    int best = 1;
    dfs(node, 1, &best);
    return best;
}
