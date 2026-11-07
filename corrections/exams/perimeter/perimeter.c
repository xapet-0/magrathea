#include <stdio.h>

struct s_node { int value; struct s_node *left; struct s_node *right; };

static void print_left(struct s_node *n)
{
    if (!n || (!n->left && !n->right)) return;
    printf(" %d", n->value);
    if (n->left) print_left(n->left);
    else print_left(n->right);
}

static void print_leaves(struct s_node *n)
{
    if (!n) return;
    print_leaves(n->left);
    if (!n->left && !n->right) printf(" %d", n->value);
    print_leaves(n->right);
}

static void print_right(struct s_node *n)
{
    if (!n || (!n->left && !n->right)) return;
    if (n->right) print_right(n->right);
    else print_right(n->left);
    printf(" %d", n->value);
}

void perimeter(struct s_node *root)
{
    if (!root) return;
    printf("%d", root->value);
    if (root->left || root->right) {
        print_left(root->left);
        print_leaves(root->left);
        print_leaves(root->right);
        print_right(root->right);
    }
    printf("\n");
}
