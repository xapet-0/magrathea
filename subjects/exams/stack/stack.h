#ifndef STACK_H
# define STACK_H
struct s_node { void *content; struct s_node *next; };
struct s_stack { struct s_node *top; };
struct s_stack *init(void);
void *pop(struct s_stack *stack);
void push(struct s_stack *stack, void *content);
void *peek(struct s_stack *stack);
int isEmpty(struct s_stack *stack);
#endif
