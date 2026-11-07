struct s_node { int value; struct s_node *left; struct s_node *right; };

static int height_and_diam(struct s_node *n, int *best)
{
    if (!n) return 0;
    int lh = height_and_diam(n->left, best);
    int rh = height_and_diam(n->right, best);
    if (lh + rh + 1 > *best) *best = lh + rh + 1;
    return 1 + (lh > rh ? lh : rh);
}

int width_tree(struct s_node *n)
{
    int best = 0;
    height_and_diam(n, &best);
    return best;
}
