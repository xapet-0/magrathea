struct s_node { int value; struct s_node *left; struct s_node *right; };

void reverse_tree(struct s_node *root)
{
    if (!root) return;
    struct s_node *tmp = root->left;
    root->left = root->right;
    root->right = tmp;
    reverse_tree(root->left);
    reverse_tree(root->right);
}
