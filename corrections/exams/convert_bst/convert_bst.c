#include "convert_bst.h"

static struct s_node *join(struct s_node *left, struct s_node *right)
{
	if (!left)
		return right;
	if (!right)
		return left;
	struct s_node *leftLast = left->left;
	struct s_node *rightLast = right->left;

	leftLast->right = right;
	right->left = leftLast;

	left->left = rightLast;
	rightLast->right = left;
	return left;
}

struct s_node *convert_bst(struct s_node *bst)
{
	if (!bst)
		return (struct s_node *)0;
	struct s_node *left = convert_bst(bst->left);
	struct s_node *right = convert_bst(bst->right);

	bst->right = bst->left = bst;

	return join(join(left, bst), right);
}
