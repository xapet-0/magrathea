struct s_node { int value; struct s_node *left; struct s_node *right; };

static int count_nodes(struct s_node *n)
{
    if (!n) return 0;
    return 1 + count_nodes(n->left) + count_nodes(n->right);
}

static int check_split(struct s_node *n, int total, int *found)
{
    if (!n) return 0;
    int c = 1 + check_split(n->left, total, found) + check_split(n->right, total, found);
    if (c * 2 == total) *found = 1;
    return c;
}

int can_split(struct s_node *n)
{
    if (!n) return 0;
    int total = count_nodes(n);
    if (total % 2 != 0) return 0;
    int found = 0;
    check_split(n, total, &found);
    return found;
}
