#ifndef QUEUE_H
# define QUEUE_H
struct s_node { void *content; struct s_node *next; };
struct s_queue { struct s_node *first; struct s_node *last; };
struct s_queue *init(void);
void enqueue(struct s_queue *queue, void *content);
void *dequeue(struct s_queue *queue);
void *peek(struct s_queue *queue);
int isEmpty(struct s_queue *queue);
#endif
