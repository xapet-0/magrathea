#ifndef CLONE_LIST_H
# define CLONE_LIST_H
# include <stdlib.h>
struct s_node {
    int data;
    struct s_node *next;
    struct s_node *other;
};

struct s_node *clone_list(struct s_node *node);
#endif
