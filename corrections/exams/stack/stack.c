#include <stdlib.h>

struct s_node { void *content; struct s_node *next; };
struct s_stack { struct s_node *top; };

struct s_stack *init(void)
{
    struct s_stack *s = malloc(sizeof(struct s_stack));
    if (s) s->top = NULL;
    return s;
}

void *pop(struct s_stack *stack)
{
    if (!stack || !stack->top) return NULL;
    struct s_node *n = stack->top;
    void *c = n->content;
    stack->top = n->next;
    free(n);
    return c;
}

void push(struct s_stack *stack, void *content)
{
    if (!stack) return;
    struct s_node *n = malloc(sizeof(struct s_node));
    if (!n) return;
    n->content = content;
    n->next = stack->top;
    stack->top = n;
}

void *peek(struct s_stack *stack)
{
    if (!stack || !stack->top) return NULL;
    return stack->top->content;
}

int isEmpty(struct s_stack *stack)
{
    return (!stack || !stack->top) ? 1 : 0;
}
