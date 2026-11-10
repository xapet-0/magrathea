#include <stdlib.h>

struct s_node { void *content; struct s_node *next; };
struct s_queue { struct s_node *first; struct s_node *last; };

struct s_queue *init(void)
{
    struct s_queue *q = malloc(sizeof(struct s_queue));
    if (q) { q->first = NULL; q->last = NULL; }
    return q;
}

void enqueue(struct s_queue *queue, void *content)
{
    if (!queue) return;
    struct s_node *n = malloc(sizeof(struct s_node));
    if (!n) return;
    n->content = content;
    n->next = NULL;
    if (!queue->last) { queue->first = n; queue->last = n; }
    else { queue->last->next = n; queue->last = n; }
}

void *dequeue(struct s_queue *queue)
{
    if (!queue || !queue->first) return NULL;
    struct s_node *n = queue->first;
    void *c = n->content;
    queue->first = n->next;
    if (!queue->first) queue->last = NULL;
    free(n);
    return c;
}

void *peek(struct s_queue *queue)
{
    if (!queue || !queue->first) return NULL;
    return queue->first->content;
}

int isEmpty(struct s_queue *queue)
{
    return (!queue || !queue->first) ? 1 : 0;
}
