struct s_node { int value; struct s_node **nodes; };

int height_tree(struct s_node *root)
{
    if (!root) return -1;
    int max_h = -1;
    if (root->nodes) {
        for (int i = 0; root->nodes[i]; i++) {
            int h = height_tree(root->nodes[i]);
            if (h > max_h) max_h = h;
        }
    }
    return max_h + 1;
}
