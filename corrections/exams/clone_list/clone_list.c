#include <stdlib.h>

struct s_node { int data; struct s_node *next; struct s_node *other; };

struct s_node *clone_list(struct s_node *node)
{
    if (!node) return NULL;
    struct s_node *orig[4096];
    struct s_node *copy[4096];
    int n = 0;
    for (struct s_node *p = node; p; p = p->next) {
        orig[n] = p;
        copy[n] = malloc(sizeof(struct s_node));
        if (!copy[n]) return NULL;
        copy[n]->data = p->data;
        copy[n]->next = NULL;
        copy[n]->other = NULL;
        if (n > 0) copy[n - 1]->next = copy[n];
        n++;
    }
    for (int i = 0; i < n; i++) {
        if (orig[i]->other) {
            for (int j = 0; j < n; j++) {
                if (orig[j] == orig[i]->other) {
                    copy[i]->other = copy[j];
                    break;
                }
            }
        }
    }
    return copy[0];
}
