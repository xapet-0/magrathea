#ifndef CONVERT_BST_H
# define CONVERT_BST_H
struct s_node {
	int           value;
	struct s_node *left;
	struct s_node *right;
};
struct s_node *convert_bst(struct s_node *bst);
#endif
