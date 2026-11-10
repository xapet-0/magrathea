#ifndef CAN_SPLIT_H
# define CAN_SPLIT_H
# include <stdlib.h>
struct s_node {
    int value;
    struct s_node *left;
    struct s_node *right;
};

int can_split(struct s_node *n);
#endif
